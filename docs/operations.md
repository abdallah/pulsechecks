# Operations Guide

## Monitoring

### Key Metrics

**Lambda Functions:**
- Invocation count and duration
- Error rate and throttling
- Memory utilization

**DynamoDB:**
- Read/write capacity consumption
- Throttling events
- Item count and storage size

**API Gateway:**
- Request count and latency
- 4xx/5xx error rates
- Cache hit ratio

**CloudFront:**
- Request count and data transfer
- Cache hit ratio
- Origin response time

**Edge Throttling:**
- AWS production: API Gateway stage throttling is the primary edge control.
- GCP production: Cloud Armor in front of a global HTTPS load balancer is the primary edge control.
- App-local FastAPI rate limiting is defense-in-depth only.

### CloudWatch Alarms

The system includes pre-configured alarms for:
- Lambda function errors (>5% error rate)
- DynamoDB throttling
- API Gateway high latency (>5s)
- Late detection failures

### Health Checks

```bash
# API health
curl https://api.pulsechecks.example.com/health

# Frontend availability
curl -I https://pulsechecks.example.com

# Test ping endpoint
curl -X POST https://api.pulsechecks.example.com/ping/test-token \
  -d "Health check test"
```

## Warm Standby & Mutual Watching (Who Watches the Watchers)

Two independent deployments watch **each other**, dogfooding PulseChecks
itself. GCP is the primary; AWS runs as a warm standby that can take over
ingestion + alerting.

### Mutual watching (sentinel checks — set up once)

On the **AWS** deployment (watches GCP):
1. Create an HTTP check on `https://api.<domain>/health` — detects GCP API down.
2. Create a heartbeat check; set the GCP primary's `HEARTBEAT_URL` to its
   ping URL — detects GCP's detection loop silently stopping.
3. Attach real alert channels (SNS email / Mattermost) to both.

On the **GCP** deployment (watches AWS): mirror image — HTTP check on the
AWS API's `/health`, and AWS's `HEARTBEAT_URL` pings a GCP-hosted check.

Accepted residual risk (explicit decision): a *simultaneous* AWS+GCP
failure silences monitoring. No third-party backstop is configured.

### Standby configuration (AWS tfvars)

```hcl
auth_provider       = "firebase"        # one identity space with the primary
firebase_project_id = "<gcp-project>"
standby_mode        = true              # shadow alerting for synced checks
sync_token          = "<long random>"   # same value as GCP's sync_token
primary_export_url  = "https://api.<domain>/internal/export-definitions"

enable_cross_cloud_failover = true
primary_api_fqdn            = "<GCP LB hostname or api domain>"
gcp_primary_api_ip          = "<terraform output from infra/gcp>"
```

On GCP, set the matching `sync_token`. The sync payload contains **check
ping tokens and channel configurations** — treat `sync_token` as a
database credential.

### How it behaves day-to-day

- Every 5 min the standby pulls team/member/check/channel definitions
  (`standby-sync` Lambda) and mirrors them, stamped `managed_by_sync`.
- The standby's late detector runs in **shadow mode**: it tracks state for
  synced checks but never alerts for them (the primary is alerting).
  Its own sentinel checks alert normally.
- Route53 health-checks the primary's `/health` every 30s; on 3
  consecutive failures, `api.<domain>` fails over to the AWS API Gateway
  (TTL 60s). Customer pings start landing on the standby automatically —
  tokens match because they were synced.

### Promotion runbook (manual, by design)

DNS failover for *ingestion* is automatic. Enabling the standby's
*alerting* is a human decision — automatic promotion under a network
partition would produce split-brain double alerting.

1. Confirm the primary is really down (not just the health check):
   Cloud Run console, Cloud Status Dashboard, `curl` the run.app URL.
2. Verify DNS has failed over: `dig api.<domain>` returns the AWS answer.
3. Promote: set `standby_mode = false` in the AWS tfvars and apply
   (or update the two Lambdas' `STANDBY_MODE` env var to `false` directly
   for speed) — synced checks now alert.
4. Announce; monitor the AWS deployment's Alert History for deliveries.

**Fail-back** when GCP recovers: confirm Route53 flipped back to primary,
then restore `standby_mode = true` on AWS. The next sync pull re-mirrors
anything that changed during the outage window. Note: pings ingested on
AWS during failover stay on AWS (history diverges for that window —
accepted; definitions re-converge automatically).

## Rate Limiting Architecture

Rate limiting is enforced **at the cloud edge, per client IP** — never as a
single shared bucket, and never only inside the app. The in-app limiter is
defense-in-depth, not the primary control (a per-instance limiter cannot see
global traffic in a serverless deployment).

### GCP (primary): Cloud Armor on the global HTTPS LB

With `edge_throttling_enabled = true` (default), all public traffic flows
through the global external HTTPS load balancer, where Cloud Armor enforces:

| Rule | Scope | Limit | Action |
|---|---|---|---|
| 900 | Management API (`!/ping/*`, `!/health`) | `edge_throttle_api_requests_per_minute`/min **per IP** | 429 |
| 1000 | All paths | `edge_throttle_requests_per_second`/s **per IP** | 429 |
| 1010 | All paths | `edge_throttle_burst`/min **per IP** | ban for `edge_throttle_ban_duration_seconds` |

Design invariants:
- **`enforce_on_key = "IP"` on every rule.** A keyless (global-bucket)
  throttle is worse than none: one flooder exhausts the shared budget and
  legitimate ping traffic becomes the collateral damage.
- **Cloud Run ingress is locked to `internal-and-cloud-load-balancing`**,
  so the `run.app` URL cannot be used to bypass Cloud Armor. Cloud
  Scheduler's OIDC calls still arrive (Google-internal network).
- **Availability**: enforcement happens on Google's edge (LB SLA 99.99%),
  costs the backend nothing, and per-IP keying means an attack degrades
  only the attacker — this is what lets the limiter *protect* the 99.99%
  ingestion target instead of threatening it.

### AWS: API Gateway throttling with isolated budgets

HTTP APIs cannot do per-client throttling natively, so the design isolates
token buckets per traffic class:

- **Ping routes** get a dedicated budget (`ping_throttling_rate_limit`/
  `ping_throttling_burst_limit`) — a flood against the dashboard API can
  never starve ping ingestion, and vice versa.
- **Everything else** shares the stage default
  (`api_gateway_throttling_rate_limit`/`_burst_limit`).
- Throttling is enforced by API Gateway before Lambda is invoked, so
  floods cost no compute and cannot exhaust Lambda concurrency.
- **If AWS becomes a primary target**: put CloudFront + WAF (rate-based
  rules are per-IP) in front of the API for parity with Cloud Armor.

### In-app limiter (defense-in-depth)

The process-local limiter in `middleware.py` remains as a backstop. Its
per-instance nature is remedied two ways:
1. The **authoritative** limits live at the edge (above) where global
   traffic is visible.
2. Its keying is now correct behind proxies: `TRUSTED_PROXY_HOPS` tells it
   how many trailing `X-Forwarded-For` entries were appended by trusted
   infrastructure (2 behind the global LB, 1 for direct Cloud Run, 0 on
   Lambda where API Gateway supplies the real source IP). Entries earlier
   in the header are client-supplied and ignored, so spoofing can only
   diversify an attacker's keys at the in-app layer — the edge layer keys
   on the true connection IP regardless.

## Alert Delivery Pipeline

Every alert (late / recovery / escalation) is written as a durable
`AlertDelivery` record before any notification is attempted — one record per
target channel. The record is both the queue item and the permanent history
entry shown in the check's "Alert History" section.

**Lifecycle:**
- `pending` — enqueued; attempted immediately in scheduler context, or picked
  up by the next late-detection run (≤2 minutes) when enqueued from the ping
  endpoint's recovery path (which never blocks on outbound calls).
- Failed attempts retry with exponential backoff: 2m, 4m, 8m, 16m after each
  failure — 5 attempts spanning ~30 minutes.
- `delivered` — terminal success, with `deliveredAt`.
- `failed` — terminal dead-letter state after `maxAttempts` (or immediately
  if the channel/check no longer exists), with `lastError` preserved.

**Monitoring:** each exhausted delivery emits the `AlertDeliveryExhausted`
metric (dimension: `ChannelType`) and an `alert_delivery_exhausted` business
log event. Alarm on this metric — it means a user did not get an alert they
configured.

**Retention:** delivery records expire with the same TTL as pings
(`PING_RETENTION_DAYS`, default 90 days).

## Troubleshooting

### Common Issues

#### 1. Authentication Failures
**Symptoms:** 401 errors, login redirects

**Diagnosis:**
```bash
# Check Cognito configuration
aws cognito-idp describe-user-pool --user-pool-id {pool-id}

# Verify Google OAuth settings
# - Authorized redirect URIs must include https://pulsechecks.example.com/callback
# - Domain allowlist configured correctly
```

**Resolution:**
- Update OAuth redirect URIs in Google Console
- Verify domain allowlist in Terraform variables
- Check Cognito domain configuration

#### 2. Ping Delivery Issues
**Symptoms:** Pings not recorded, 404 errors on ping URLs

**Diagnosis:**
```bash
# Check API Gateway logs
aws logs filter-log-events \
  --log-group-name /aws/apigateway/pulsechecks-api \
  --start-time $(date -d '1 hour ago' +%s)000

# Test ping endpoint directly
curl -v https://api.pulsechecks.example.com/ping/{token}
```

**Resolution:**
- Verify token exists in DynamoDB TokenIndex
- Check Lambda function logs for errors
- Ensure API Gateway routes are configured

#### 3. Late Detection Not Working
**Symptoms:** Checks stuck in "up" status despite missed pings

**Diagnosis:**
```bash
# Check EventBridge rule
aws events describe-rule --name pulsechecks-late-detector

# Check Lambda logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/pulsechecks-late-detector \
  --start-time $(date -d '1 hour ago' +%s)000
```

**Resolution:**
- Verify EventBridge rule is enabled
- Check DynamoDB DueIndex configuration
- Review Lambda function permissions

#### 4. Frontend Not Loading
**Symptoms:** Blank page, 404 errors

**Diagnosis:**
```bash
# Check S3 bucket contents
aws s3 ls s3://pulsechecks-frontend-prod/

# Check CloudFront distribution
aws cloudfront get-distribution --id {distribution-id}
```

**Resolution:**
- Redeploy frontend: `./deploy.sh --frontend-only`
- Create CloudFront invalidation
- Verify S3 bucket policy

### Log Analysis

**API Gateway Logs:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/apigateway/pulsechecks-api \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

**Lambda Function Logs:**
```bash
# API Handler
aws logs tail /aws/lambda/pulsechecks-api --follow

# Ping Handler
aws logs tail /aws/lambda/pulsechecks-ping --follow

# Late Detector
aws logs tail /aws/lambda/pulsechecks-late-detector --follow
```

**DynamoDB Metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=Pulsechecks \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

## Maintenance

### Backup and Recovery

**DynamoDB:**
- Point-in-time recovery enabled
- On-demand backups for major changes
- Cross-region replication for disaster recovery

**Configuration:**
- Terraform state in S3 with versioning
- Infrastructure as Code for reproducibility

### Updates and Deployments

**Automated Pipeline:**
```bash
git add .
git commit -m "Update description"
git push origin main  # Triggers CI/CD
```

**Manual Deployment:**
```bash
# Full deployment
./deploy.sh

# Component-specific
./deploy.sh --infrastructure-only
./deploy.sh --backend-only
./deploy.sh --frontend-only
```

**Rollback Procedures:**
```bash
# Infrastructure rollback
cd infra
terraform plan -destroy
terraform apply

# Lambda rollback
aws lambda update-function-code \
  --function-name pulsechecks-api-prod \
  --s3-bucket pulsechecks-deployments \
  --s3-key lambda-backup-{timestamp}.zip

# Frontend rollback
aws s3 sync s3://pulsechecks-frontend-backup/ s3://pulsechecks-frontend-prod/
aws cloudfront create-invalidation \
  --distribution-id {distribution-id} \
  --paths "/*"
```

### Performance Optimization

**DynamoDB:**
- Monitor hot partitions
- Optimize GSI usage
- Consider reserved capacity for predictable workloads

**Lambda:**
- Monitor cold starts
- Adjust memory allocation based on usage
- Use provisioned concurrency for critical functions

**CloudFront:**
- Optimize cache behaviors
- Monitor cache hit ratios
- Configure appropriate TTLs

### Security Maintenance

**Regular Tasks:**
- Rotate OAuth client secrets
- Review IAM permissions
- Update dependencies
- Monitor access logs

**Security Monitoring:**
```bash
# Check for unusual API activity
aws logs filter-log-events \
  --log-group-name /aws/apigateway/pulsechecks-api \
  --filter-pattern "[timestamp, requestId, ip, user, timestamp, method, resource, protocol, status=4*, size, referer, agent]" \
  --start-time $(date -d '24 hours ago' +%s)000

# Monitor failed authentication attempts
aws logs filter-log-events \
  --log-group-name /aws/lambda/pulsechecks-api \
  --filter-pattern "401" \
  --start-time $(date -d '24 hours ago' +%s)000
```

## Disaster Recovery

### RTO/RPO Targets
- **RTO**: 4 hours (infrastructure recreation)
- **RPO**: 1 hour (DynamoDB point-in-time recovery)

### Recovery Procedures

1. **Infrastructure Loss:**
   ```bash
   # Recreate from Terraform
   cd infra
   terraform init
   terraform plan
   terraform apply
   ```

2. **Data Loss:**
   ```bash
   # Restore DynamoDB from backup
   aws dynamodb restore-table-from-backup \
     --target-table-name Pulsechecks \
     --backup-arn {backup-arn}
   ```

3. **Regional Outage:**
   - Deploy to alternate region
   - Update DNS to point to new region
   - Restore data from cross-region backup
