# PulseChecks Resilience & Dependability Plan

For a monitoring service, reliability is non-negotiable. This doc covers failure modes, recovery patterns, and testing strategies.

---

## Failure Modes & Recovery

### Critical Path: Ping Ingestion → Alert Delivery

```
User Job → [ping endpoint] → [database] → [alert evaluation] → [SNS/Email/Webhook]
```

Each component has failure modes that could break monitoring.

---

## 1. Availability & Uptime

### 1.1 Target SLA
- **99.9% uptime** (43 min downtime/month allowed)
- **Ping endpoint** should be more resilient than other endpoints (never sacrifice ingestion)
- **Alert delivery** should have retry logic

### 1.2 Infrastructure Resilience

**Current state:**
- Single Cloud Run service (GCP) or Lambda (AWS)
- Single database (Firestore/DynamoDB)
- Single region

**Improvements needed:**
- [ ] Multi-region deployment (GCP Cloud Run in us-central1 + europe-west1)
- [ ] Database replication (Firestore auto-replication across regions)
- [ ] Load balancer with health checks (Cloud Load Balancing)
- [ ] Graceful degradation (serve pings even if alerts are slow)

### Test 1.1: Service Restart Resilience
**Goal:** Verify pings aren't lost during deployment

```bash
# Send ping before restart
PING_ID=$(curl -X POST https://api.example.com/ping/{token}/success -w '%{time_total}')

# Trigger service restart (via Cloud Run console or API)
gcloud run services update pulsechecks --image=... 

# Send more pings during restart
for i in {1..10}; do
  curl -X POST https://api.example.com/ping/{token}/success &
done
wait

# Verify all pings appear in database
curl https://api.example.com/teams/{team}/checks/{check}/pings \
  | jq '.pings | length'
# Expected: original_count + 11 (no pings dropped)
```

### Test 1.2: Database Failover
**Goal:** Verify alert evaluation continues if database is slow/unavailable

```bash
# Simulate slow database (inject 5s latency in query)
# OR: Reduce RCU in DynamoDB to trigger throttling

# Continue sending pings
for i in {1..100}; do
  curl -X POST https://api.example.com/ping/{token}/success &
done
wait

# Monitor:
# - Response times (should stay <1s even with slow DB)
# - Error rates (should stay <1%)
# - Alert delivery latency (should be <30s even with backlog)

# Expected: Service handles slow DB gracefully
# Failure: Timeouts, 503 errors, lost pings
```

### Test 1.3: Regional Failover
**Goal:** Verify service stays up if one region fails

```bash
# With multi-region setup:
# Stop us-central1 Cloud Run service
gcloud run services delete pulsechecks --region us-central1

# Send pings to global endpoint
for i in {1..50}; do
  curl -X POST https://api.example.com/ping/{token}/success &
done
wait

# Expected: All pings succeed (routed to europe-west1)
# Failure: Pings start failing with 503
```

---

## 2. Data Durability

### 2.1 Ping History Persistence

**Risk:** Pings are accepted but not persisted (data loss)

```bash
# Create check and webhook
CHECK_TOKEN=$(...)
WEBHOOK_URL="https://webhook.site/..."

# Send ping
curl -X POST https://api.example.com/ping/{token}/success

# Query check history
HISTORY=$(curl https://api.example.com/teams/{team}/checks/{check}/pings)

# Expected: Ping appears in history within 2 seconds
# Failure: Ping accepted but not in database
```

### 2.2 Firestore/DynamoDB Consistency

**Risk:** Eventual consistency causes stale alert state

```bash
# Rapid fire: success, then fail, then success
curl -X POST https://api.example.com/ping/{token}/success
sleep 0.1
curl -X POST https://api.example.com/ping/{token}/fail
sleep 0.1
curl -X POST https://api.example.com/ping/{token}/success

# Check final state immediately
STATE=$(curl https://api.example.com/teams/{team}/checks/{check} | jq '.status')

# Expected: status = "UP" (last ping wins)
# Wait if needed, but should converge within 2 seconds
# Failure: Stale "DOWN" status stays for >5 seconds
```

### 2.3 Backup & Recovery

**Test:** Verify backup retention and restore capability

```bash
# List recent backups
gcloud firestore backups list --location us-central1

# Restore from backup (simulate data loss scenario)
gcloud firestore databases restore BACKUP_ID --location us-central1

# Verify restored data
curl https://api.example.com/teams/{team}/checks \
  | jq '.checks | length'
# Should equal pre-restore count
```

---

## 3. Alert Delivery Reliability

### 3.1 Alert Queue & Retry

**Risk:** Alerts sent but never delivered (no retry, no queue)

```bash
# Trigger failure that should alert
# Block SNS temporarily (simulate failure)

# Send fail ping
curl -X POST https://api.example.com/ping/{token}/fail

# Check alert delivery status
curl https://api.example.com/teams/{team}/alerts?status=pending

# Expected: Alert marked as "pending retry"
# Expected: Auto-retry after 5 seconds, then 30s, then 5m
# Failure: Alert lost, no retry attempted
```

### 3.2 Multiple Channel Redundancy

**Goal:** If one channel fails, alert still goes to others

```bash
# Create check with 3 channels: email, webhook, SNS

# Trigger failure
curl -X POST https://api.example.com/ping/{token}/fail

# Monitor deliveries
# - Email sent ✅
# - Webhook fails ⚠️ (temporarily)
# - SNS sent ✅

# Expected: 2/3 channels succeed, user gets alert via SNS + email
# Failure: All fail because one webhook endpoint is down
```

### 3.3 Alert Deduplication

**Goal:** Rapid failures don't spam alerts

```bash
# Trigger 10 failures in 10 seconds
for i in {1..10}; do
  curl -X POST https://api.example.com/ping/{token}/fail
  sleep 1
done

# Count alerts sent
ALERT_COUNT=$(curl https://api.example.com/teams/{team}/alerts | jq '.alerts | length')

# Expected: 1-2 alerts (deduped within 5 min window)
# Failure: 10 separate alerts (spam)
```

### 3.4 Alert Backoff & Escalation

**Goal:** Alerts escalate if issue isn't resolved

```bash
# Check with alert threshold = 2 consecutive fails

# Fail once → no alert
curl -X POST https://api.example.com/ping/{token}/fail

# Success → reset
curl -X POST https://api.example.com/ping/{token}/success

# Fail twice → alert sent
curl -X POST https://api.example.com/ping/{token}/fail
curl -X POST https://api.example.com/ping/{token}/fail

# Monitor alerts
ALERTS=$(curl https://api.example.com/teams/{team}/alerts)

# Expected: Alert sent on 2nd consecutive failure, not before
# Failure: Alert sent after every single failure
```

---

## 4. Performance & Scalability

### 4.1 Latency SLA

**Goal:** Ping ingestion is always fast, even under load

```bash
# Baseline: Single ping
TIME=$(curl -s -w '%{time_total}' -X POST https://api.example.com/ping/{token}/success)
# Expected: <100ms

# Under load: 1000 concurrent pings
time for i in {1..1000}; do
  curl -s -X POST https://api.example.com/ping/{token}/success &
done
wait

# Expected: All complete in <10 seconds (avg <10ms, p99 <100ms)
# Failure: Slow responses, timeouts
```

### 4.2 Database Throughput

**Goal:** Database can handle peak ping volume

```bash
# Estimate: 1000 checks, 100 pings/min per check = 100k pings/min peak

# Load test: 2000 pings/second for 60 seconds
# Use k6, locust, or custom script

# Monitor DynamoDB:
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=pulsechecks-pings \
  --start-time 2026-04-05T00:00:00Z --end-time 2026-04-05T01:00:00Z \
  --period 60 --statistics Sum

# Expected: Stays well below provisioned capacity
# Failure: Throttling errors (HTTP 400 with ProvisionedThroughputExceededException)
```

### 4.3 Alert Evaluation Latency

**Goal:** Failures trigger alerts within SLA

```bash
# Timestamp fail ping
FAIL_TIME=$(date +%s%N)
curl -X POST https://api.example.com/ping/{token}/fail

# Poll for alert creation
ALERT_TIME=$(curl https://api.example.com/teams/{team}/alerts | jq '.alerts[0].created_at')

# Calculate latency
LATENCY=$((ALERT_TIME - FAIL_TIME))

# Expected: Alert created within 30 seconds of failure
# (5s for ping processing + 10s for alert evaluation + 15s buffer)
```

---

## 5. Graceful Degradation

### 5.1 Ping Endpoint Priority

**Goal:** Ping endpoint never fails, even if other systems are broken

```bash
# Disable alerts subsystem (kill Lambda/Cloud Functions)
# Database still online, but alert delivery is down

# Send pings
curl -X POST https://api.example.com/ping/{token}/success
curl -X POST https://api.example.com/ping/{token}/fail

# Expected: Pings accepted (200 OK)
# Expected: Pings stored in database
# Expected: Alerts queued but not sent (will retry later)
# Failure: Ping endpoint returns 503 because alerts are broken
```

### 5.2 Webhook Failure Doesn't Block Pings

**Goal:** Bad webhook URL doesn't break the system

```bash
# Create webhook channel with invalid URL
CHANNEL=$(curl -X POST https://api.example.com/teams/{team}/channels \
  -d '{"url": "http://invalid-domain-that-will-timeout.example.com"}')

# Send ping (should trigger alert → webhook)
curl -X POST https://api.example.com/ping/{token}/fail

# Send another ping (should still work even though webhook is broken)
curl -X POST https://api.example.com/ping/{token}/success

# Expected: Both pings accepted
# Expected: First alert queued with webhook (will retry)
# Expected: Alert retries don't block subsequent pings
```

### 5.3 Timeout Handling

**Goal:** All requests complete or timeout gracefully

```bash
# Slow database: Make Firestore query take 30 seconds

curl -X POST https://api.example.com/ping/{token}/success \
  --max-time 5

# Expected: Timeout after 5s, returns 504 Gateway Timeout
# Expected: Ping may still be persisted in background
# Failure: Hangs indefinitely
```

---

## 6. Monitoring & Observability

### 6.1 Health Check Endpoints

**Goal:** Load balancers can detect failures

```bash
# Health check endpoint
curl https://api.example.com/health

# Expected: 200 OK with JSON
# {
#   "status": "healthy",
#   "checks": {
#     "database": "ok",
#     "cache": "ok",
#     "alerts": "degraded"
#   },
#   "timestamp": "2026-04-05T06:30:00Z"
# }
```

### 6.2 Metrics & Alerting

**Goal:** Operations team can detect problems early

Essential metrics:
- Ping endpoint p99 latency (should alert if >500ms)
- Ping error rate (should alert if >1%)
- Alert delivery latency (should alert if >2 min)
- Alert delivery failure rate (should alert if >5%)
- Database consumed capacity (should alert if >80%)
- DynamoDB throttling (should alert immediately)
- Webhook delivery failures (count retries)

**Implementation:**
- CloudWatch/Stackdriver dashboards
- Automated alerts to PagerDuty/Slack
- Weekly SLA report (uptime %, alert delivery accuracy)

### 6.3 Structured Logging

**Goal:** Troubleshooting is easy

```python
# Each ping should log:
{
  "timestamp": "2026-04-05T06:30:00Z",
  "level": "info",
  "message": "ping_received",
  "team_id": "...",
  "check_id": "...",
  "status": "success",
  "duration_ms": 45,
  "trace_id": "..."
}
```

Searchable by: team_id, check_id, trace_id, status, latency ranges

---

## 7. Disaster Recovery

### 7.1 Failover Time (RTO)

**Goal:** Service recovers quickly from failure

- **Single region failure:** <5 minutes (manual failover to backup region)
- **Database failure:** <15 minutes (restore from backup)
- **Credential leak:** <1 hour (rotate secrets, restart services)

### 7.2 Data Loss (RPO)

**Goal:** No recent data is lost

- **Ping data:** RPO = 0 (every ping is persisted immediately)
- **Alert history:** RPO = 15 minutes (acceptable, older data in backup)
- **Configuration:** RPO = 0 (stored in source control + database)

### Test 7.1: Backup Restore
```bash
# Simulate data loss: Delete all pings for a check
# Restore from backup
# Verify pings are recovered
```

### Test 7.2: Secrets Rotation
```bash
# Rotate all secrets (OAuth token, API keys, database credentials)
# Verify service continues to work
# Verify no new failures
```

---

## 8. Testing Roadmap

| Phase | Tests | Focus | Timeline |
|-------|-------|-------|----------|
| 1 | 1.1-1.3 | Availability | Week 1 |
| 2 | 2.1-2.3 | Data durability | Week 2 |
| 3 | 3.1-3.4 | Alert reliability | Week 2 |
| 4 | 4.1-4.3 | Performance | Week 3 |
| 5 | 5.1-5.3 | Degradation | Week 3 |
| 6 | 6.1-6.3 | Observability | Ongoing |
| 7 | 7.1-7.2 | DR | Month 2 |

---

## 9. Acceptance Criteria

✅ Service achieves 99.9% uptime over 30 days
✅ Ping endpoint latency p99 <500ms under normal load
✅ Alert delivery latency <5 minutes for 99% of alerts
✅ Zero pings lost (verified via audit logs)
✅ Zero alert delivery failures due to service code (only external failures)
✅ All manual failover scenarios work within RTO
✅ Backup/restore tested and documented
✅ On-call runbook covers all critical failure modes
✅ Weekly SLA metrics dashboard public
✅ Post-incident reviews document any downtime >5 minutes

---

## 10. On-Call Runbook

### Alert: Ping Endpoint Latency High (>500ms)

1. Check Cloud Run metrics (CPU, memory, scale-out)
2. Check database metrics (DynamoDB consumed capacity)
3. Check if regional failover is active
4. If stuck: restart service (graceful, will drain connections)

### Alert: Alert Delivery Failing

1. Check SNS topic (topics exist, permissions OK)
2. Check webhook endpoints (timeout, auth, etc.)
3. Check if alert queue is backed up
4. If backed up: scale up Lambda concurrency

### Alert: Database Throttling

1. Check DynamoDB capacity
2. Scale up RCU/WCU if needed
3. Review slow queries (GSI scans?)
4. Consider enabling on-demand billing temporarily

### Incident: Data Loss Detected

1. STOP: Don't take any writes to affected table
2. Identify scope: which keys/time range affected
3. Restore from backup to isolated table
4. Query backup table for lost data
5. Restore to production
6. Post-incident review

---

## Continuous Improvement

- Monthly: Review SLA metrics, identify trends
- Quarterly: Run disaster recovery drills
- Quarterly: Update runbook based on incidents
- Yearly: Comprehensive security & reliability audit
