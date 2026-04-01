
# Security Review: Pulsechecks

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


## 1. Executive Summary

Overall Risk Level: HIGH

The system has solid structural foundations — JWT verification is correct, team-scoped DB keys are used, and Firestore rules deny all direct access. However,
several critical and high-severity issues exist that a real attacker could exploit today.

Top 5 Risks:

1. Domain allowlist is disabled in production code — any Google account can authenticate
2. Google OAuth client secret committed to version control in terraform.tfvars
3. No SSRF protection on webhook URLs — attacker-controlled URLs can reach internal metadata endpoints
4. Rate limiting is in-memory and per-instance — trivially bypassed in serverless/multi-instance deployments
5. /internal endpoints rely on a trust comment, not actual OIDC validation — exploitable if DEBUG is set or Cloud Run IAM is misconfigured

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


## 2. Findings

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-01: Domain Allowlist Explicitly Disabled

Severity: Critical
File: backend/app/dependencies.py, lines 68–70

python
# Check domain allowlist - temporarily disabled for debugging
# if not check_domain_allowed(email):
#     raise ForbiddenError("Email domain not allowed")


Description: The domain allowlist check is commented out with a "temporarily disabled for debugging" note. The allowed_email_domains setting is configured (
otgs.work,onthegosystems.com) but never enforced.

Exploitation: Any person with a valid Google account (any domain) can authenticate, create teams, create monitors, and trigger alerts. There is no other gate.

Impact: Complete authentication bypass of the intended domain restriction. Any Google user on the internet can access the system.

Fix: Uncomment and restore the check. Remove the debug bypass entirely:
python
if not check_domain_allowed(email):
    raise ForbiddenError("Email domain not allowed")


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-02: Google OAuth Client Secret in Version Control

Severity: Already handled
File: infra/gcp/terraform.tfvars, lines 14–15

google_oauth_client_id     = "HIDDEN.apps.googleusercontent.com"
google_oauth_client_secret = "HIDDEN"

the secret was already rotated and the files are explicitly set to be ignored by .gitignore so will not be pushed to public.

Description: Real OAuth credentials are committed in plaintext to the repository. The .gitignore for infra/gcp/ does not exclude terraform.tfvars (only
terraform.tfstate and .terraform/).

Exploitation: Anyone with repo access (or if the repo is ever public) can use these credentials to impersonate the OAuth application, intercept auth codes, or
abuse the Google OAuth quota.

Impact: OAuth application compromise, potential account takeover via auth code interception.

Fix:
- Rotate the secret immediately in Google Cloud Console
- Move secrets to environment variables or a secrets manager (GCP Secret Manager)
- Add terraform.tfvars to .gitignore
- Use terraform.tfvars.example with placeholder values only

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-03: SSRF via Webhook URLs (No Allowlist / Metadata Endpoint Protection)

Severity: High
Files: backend/app/routers/channels.py, backend/app/handlers.py

python
# In _send_test_notification and _send_channel_alert:
async with httpx.AsyncClient(timeout=10.0) as client:
    resp = await client.post(webhook_url, json=payload, headers=headers)


Description: Webhook URLs stored in channel configuration are used directly in outbound HTTP requests with no validation beyond
startswith(("http://", "https://")). This applies to both the test endpoint and live alert delivery.

Exploitation scenarios:
- http://169.254.169.254/latest/meta-data/iam/security-credentials/ — AWS metadata endpoint (Lambda execution role credentials)
- http://metadata.google.internal/computeMetadata/v1/ — GCP metadata endpoint
- http://10.0.0.1/internal-service — internal network scanning
- http://localhost:8080/internal/late-detection — trigger internal endpoints

On AWS Lambda, the metadata endpoint returns the Lambda execution role's temporary credentials, giving the attacker full IAM access.

Impact: Cloud credential theft, internal network access, potential full cloud account compromise.

Fix:
python
import ipaddress, socket
from urllib.parse import urlparse

BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal", "metadata.internal"}
BLOCKED_PREFIXES = ("10.", "172.16.", "192.168.", "127.", "::1", "fd")

def validate_webhook_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if host in BLOCKED_HOSTS:
        raise ValueError("Webhook URL targets a blocked host")
    try:
        ip = socket.gethostbyname(host)
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            raise ValueError("Webhook URL resolves to a private/internal address")
    except socket.gaierror:
        raise ValueError("Webhook URL host could not be resolved")


Also consider using httpx with a custom transport that enforces this at the connection level to prevent DNS rebinding.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-04: Internal Endpoints — OIDC Validation Is a No-Op

Severity: High
File: backend/app/routers/internal.py

python
async def _verify_oidc(request: Request):
    """Verify Cloud Scheduler OIDC token (skip in debug/local)."""
    if os.getenv("DEBUG", "").lower() in ("1", "true"):
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing OIDC token")
    # On Cloud Run, the platform validates the OIDC token before it reaches the app.
    # If we're here, the request already passed Cloud Run's IAM check.


Description: The function checks that a Bearer token is present but never validates it. The comment says "Cloud Run validates it" — but this is only true if the
Cloud Run service is configured to require authentication. The Terraform config sets member = "allUsers" with roles/run.invoker, meaning the service is publicly
accessible and Cloud Run does NOT validate OIDC tokens.

hcl
# cloudrun.tf
resource "google_cloud_run_service_iam_member" "public_access" {
  role   = "roles/run.invoker"
  member = "allUsers"  # ← public
}


Exploitation: Any attacker can POST to /internal/late-detection or /internal/http-poll with any Bearer token string and trigger the late detector or HTTP
polling on demand. This can:
- Trigger mass alert storms (cost amplification)
- Cause false "late" status on all checks
- Drive excessive Lambda/Cloud Run invocations

Fix:
1. Remove allUsers from Cloud Run IAM — use a dedicated service account for Cloud Scheduler
2. Actually validate the OIDC token in _verify_oidc:
python
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

async def _verify_oidc(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = auth[7:]
    try:
        claims = id_token.verify_oauth2_token(
            token, google_requests.Request(),
            audience=f"https://{request.headers.get('host')}"
        )
        if claims.get("email") != EXPECTED_SCHEDULER_SA_EMAIL:
            raise HTTPException(status_code=403)
    except Exception:
        raise HTTPException(status_code=401)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-05: Rate Limiting Is In-Memory and Per-Instance — Ineffective in Serverless

Severity: High
File: backend/app/middleware.py

python
general_limiter = RateLimiter(max_requests=100, window_seconds=60)
ping_limiter = RateLimiter(max_requests=1000, window_seconds=60)


Description: Rate limiters are Python defaultdict objects stored in process memory. In AWS Lambda, each cold start creates a new instance with a fresh counter.
In Cloud Run with min_instances=0, the same applies. Even with warm instances, multiple concurrent instances each have independent counters.

Exploitation: An attacker can send 1000 ping requests per minute per Lambda instance. With Lambda's auto-scaling, this means effectively unlimited throughput.
The ping endpoint is the highest-risk target since it's public and unauthenticated.

Impact: Cost amplification (Lambda invocations, DynamoDB writes, alert triggers), alert flooding, false monitoring signals at scale.

Fix: Use a distributed rate limiter. Options:
- **AWS:** ElastiCache Redis with a sliding window counter, or API Gateway's built-in throttling (already configured at 1000 req/s — but this is global, not per
-token)
- **GCP:** Cloud Armor rate limiting rules, or Redis Memorystore
- At minimum, add per-token rate limiting at the API Gateway/Cloud Armor layer

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-06: No Rate Limiting on Check-In Tokens (Per-Token Flood)

Severity: High
File: backend/app/routers/ping.py

Description: The ping endpoint accepts any valid token and records a ping + updates DynamoDB/Firestore. There is no per-token rate limit. An attacker who knows
a token (or guesses one) can:
- Flood a check with success pings, masking real failures
- Flood with fail pings, triggering continuous alerts
- Drive DynamoDB write costs

Exploitation: If an attacker discovers a token (e.g., from a leaked cron job script, CI log, or by guessing), they can send thousands of pings per second. Each
ping writes to the database and potentially triggers alert evaluation.

Fix:
- Add per-token rate limiting (e.g., max 10 pings/minute per token) at the API Gateway level or in a distributed cache
- Consider signed ping URLs with a timestamp component to prevent replay flooding

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-07: Alert Topic Ownership Verified Only for Delete/Unsubscribe, Not for Subscribe/Details

Severity: High
File: backend/app/routers/alerts.py

python
@router.get("/{topic_arn:path}/details")
async def get_alert_topic_details(team_id, topic_arn, ...):
    await check_team_access(team_id, current_user, db, Permission.VIEW)
    # No verification that topic_arn belongs to team_id
    sns.get_topic_attributes(TopicArn=topic_arn)  # any ARN accepted

@router.post("/{topic_arn:path}/subscribe")
async def subscribe_to_alert_topic(team_id, topic_arn, ...):
    await check_team_access(team_id, current_user, db, Permission.VIEW)
    # No verification that topic_arn belongs to team_id
    sns.subscribe(TopicArn=topic_arn, Protocol=protocol, Endpoint=endpoint)


Description: The details and subscribe endpoints accept any topic_arn path parameter and act on it without verifying it belongs to the requesting team. Only
delete and unsubscribe check tags.

Exploitation: A member of Team A can:
1. Subscribe their email to Team B's SNS alert topic (receiving Team B's alerts)
2. Enumerate subscriptions on any topic in the account
3. Discover check names, team IDs, and alert patterns of other tenants

Impact: Cross-tenant information disclosure, unauthorized SNS subscriptions.

Fix: Apply the same tag-based ownership check used in delete/unsubscribe to all topic operations:
python
tags = {t["Key"]: t["Value"] for t in sns.list_tags_for_resource(ResourceArn=topic_arn)["Tags"]}
if tags.get("Team") != team_id and tags.get("CreatedByTeam") != team_id:
    raise HTTPException(status_code=403, detail="Topic does not belong to this team")


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-08: Shared SNS Topics — Cross-Tenant Subscription

Severity: High
File: backend/app/routers/alerts.py, backend/app/routers/channels.py

python
# list_alert_topics includes shared topics for ALL teams:
if topic_name.startswith(team_prefix) or topic_name.startswith(shared_prefix):


Description: "Shared" SNS topics are visible and subscribable by any authenticated team. There is no access control on who can subscribe to a shared topic — any
team member with VIEW permission can subscribe any endpoint to a shared topic.

Exploitation: Team A creates a shared alert topic. Team B subscribes their own email/webhook to it, receiving all of Team A's alerts.

Fix: Shared topics need an explicit access control list (ACL) stored in the database. Only teams explicitly granted access should be able to subscribe.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-09: DEBUG Print Statements Leaking Tokens in Logs

Severity: Medium
File: backend/app/dependencies.py, lines 60–65

python
print(f"DEBUG: Received token: {raw[:50]}...")
print(f"DEBUG: JWT claims: {claims}")
print(f"DEBUG: Extracted user info - ID: {user_id}, Email: {email}, Name: {name}")


Description: Raw print() statements log the first 50 characters of every incoming token (JWT or API token), full JWT claims, and user PII to stdout. In Lambda/
Cloud Run, stdout goes to CloudWatch/Cloud Logging — accessible to anyone with log read permissions.

Exploitation: An attacker with CloudWatch/Cloud Logging read access (e.g., a compromised developer account, or overly broad IAM) can harvest partial tokens and
user emails from logs.

Fix: Remove all print() debug statements. Use the structured logger with appropriate log levels:
python
logger.debug("JWT verification attempted", extra={"user_id": user_id})

Never log token values, even truncated.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-10: API Token Expiry Not Enforced

Severity: Medium
File: backend/app/dependencies.py, backend/app/routers/api_tokens.py

python
# In _resolve_api_token:
async for doc in docs.stream():
    data = doc.to_dict()
    # No check of expires_at
    return CurrentUser(user_id=data["user_id"], ...)


Description: API tokens support an expires_at field at creation time, but _resolve_api_token never checks it. Expired tokens remain valid indefinitely.

Fix:
python
expires_at = data.get("expires_at")
if expires_at and datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
    raise UnauthorizedError("API token has expired")


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-11: Duplicate rotate-token Route Definition

Severity: Medium
File: backend/app/routers/checks.py

The rotate-token endpoint is defined twice (lines ~280 and ~360). FastAPI will silently use the first definition. This is a code quality/maintenance risk — if
the second definition diverges (e.g., different permission check), the intended behavior may not be applied.

Fix: Remove the duplicate route definition.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-12: CORS Wildcard in Production

Severity: Medium
Files: backend/app/main.py, infra/aws/api-gateway.tf

python
allow_origins=["*"],  # Configure appropriately for production

hcl
allow_origins = ["*"]


Description: Both the FastAPI app and API Gateway allow all origins. The comment acknowledges this needs fixing. With allow_credentials=True in FastAPI
alongside allow_origins=["*"], browsers will actually reject credentialed cross-origin requests (CORS spec violation) — but the wildcard still allows non-
credentialed requests from any origin.

Fix: Set allow_origins to the specific frontend domain(s):
python
allow_origins=["https://pulsechecks.otgs.work", "http://localhost:3000"],


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-13: Lambda IAM — ses:SendEmail with Wildcard Resource

Severity: Medium
File: infra/aws/lambdas.tf

hcl
{
  Effect = "Allow"
  Action = ["ses:SendEmail", "ses:SendRawEmail"]
  Resource = "*"
}


Description: The Lambda execution role can send email from any SES identity in the account, not just the application's sender address. If the Lambda is
compromised, an attacker can send email from any verified domain/address in the account.

Fix: Restrict to the specific SES identity ARN:
hcl
Resource = "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/noreply@yourdomain.com"


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-14: Lambda IAM — sns:CreateTopic / sns:DeleteTopic with Wildcard

Severity: Medium
File: infra/aws/lambdas.tf

hcl
Action = ["sns:CreateTopic", "sns:TagResource", "sns:DeleteTopic"]
Resource = "*"


Description: The Lambda can create and delete any SNS topic in the account, not just pulsechecks-* prefixed ones. The SNS IAM policy in sns.tf correctly scopes
to pulsechecks-*, but the inline Lambda policy in lambdas.tf overrides this with Resource = "*".

Fix: Align the inline policy with the scoped policy in sns.tf:
hcl
Resource = "arn:aws:sns:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.project_name}-*"


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-15: Webhook Outbound Requests Include Attacker-Controlled Headers

Severity: Medium
File: backend/app/handlers.py, backend/app/routers/channels.py

python
headers = channel.configuration.get('headers') or {}
async with httpx.AsyncClient(timeout=10.0) as client:
    resp = await client.post(webhook_url, json=payload, headers=headers)


Description: Channel configuration can include arbitrary HTTP headers that are forwarded verbatim in outbound webhook requests. An attacker with EDIT permission
could store headers like X-Forwarded-For, Host, or internal service authentication headers to manipulate the target server or bypass internal controls.

Fix: Validate and allowlist header names. Reject headers that could affect routing or authentication:
python
BLOCKED_HEADERS = {"host", "x-forwarded-for", "x-real-ip", "authorization"}
for key in headers:
    if key.lower() in BLOCKED_HEADERS:
        raise ValueError(f"Header '{key}' is not allowed in webhook configuration")


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-16: Pending Invitation Auto-Accept Has No Domain Check

Severity: Medium
File: backend/app/routers/users.py

python
pending_invitations = await db.get_pending_invitations_for_email(current_user.email)
for invitation in pending_invitations:
    await db.add_team_member(member)
    await db.delete_pending_invitation(...)


Description: When a user first logs in, all pending invitations for their email are automatically accepted. Since the domain allowlist is disabled (FINDING-01),
any Google user can register and auto-accept invitations. Even when the allowlist is re-enabled, an admin could invite an external email address, and if that
person ever creates a Google account with that email, they'd be auto-added to the team.

Fix: When re-enabling the domain allowlist, also validate the email domain during invitation acceptance. Consider requiring explicit invitation acceptance
rather than auto-accepting on first login.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


### FINDING-17: /me/debug/versions — Unauthenticated Package Version Disclosure

Severity: Low
File: backend/app/routers/users.py

python
@router.get("/debug/versions")
async def get_runtime_versions():
    """Debug endpoint to check installed package versions."""


Description: This endpoint is under /me/ which requires authentication — but it returns detailed package version information useful for fingerprinting and
finding known CVEs.

Fix: Remove this endpoint from production. If needed for debugging, gate it behind an admin check or remove entirely.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


## 3. Architecture Risks

No webhook signing (HMAC): Outbound webhooks carry no signature. Recipients cannot verify the payload came from Pulsechecks. An attacker who can intercept or
replay a webhook payload can forge alerts.

Single-table DynamoDB with no row-level encryption: All tenant data shares one table. While access is scoped by TEAM# prefix in application code, there is no
encryption-at-rest differentiation per tenant. A DynamoDB data leak exposes all tenants.

No check-in token rotation policy: Tokens are permanent until manually rotated. There is no expiry, no automatic rotation, and no audit log of when tokens were
last used (only last_used_at on API tokens, not ping tokens).

Cloud Run public + internal endpoints on same service: The /internal/* endpoints and the public /ping/* endpoints are served by the same Cloud Run service,
which is configured as allUsers. There is no network-level separation.

Terraform state contains sensitive outputs: terraform.tfstate and terraform.tfstate.backup are present in the repo directory (infra/gcp/). These files contain
resource IDs, service account emails, and potentially sensitive configuration values.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 4. Abuse Scenarios

### Scenario A: Alert Flooding / Cost Exhaustion
1. Attacker registers with any Google account (domain check disabled)
2. Creates a team, creates 100 checks with 60-second periods and 0-second grace
3. Sends /ping/{token}/fail to each check every 60 seconds
4. Each failure triggers alert delivery to all configured channels
5. With SNS + email channels, this generates hundreds of emails/SNS publishes per minute
6. Lambda invocations, DynamoDB writes, and SNS publishes all scale with attacker traffic

### Scenario B: Spoofed Job Success
1. Attacker obtains a ping token (leaked in CI logs, cron job script, or guessed — tokens are secrets.token_urlsafe(32) = 43 chars, adequate entropy but not
rotated)
2. Sends continuous success pings to a critical check
3. The check always shows "UP" even when the real job is failing
4. Monitoring team never receives alerts for a broken job

### Scenario C: Cross-Tenant SNS Subscription
1. Attacker is a legitimate member of Team A
2. Calls POST /teams/team-a-id/alerts/{team-b-topic-arn}/subscribe with Team B's topic ARN
3. Subscribes their email to Team B's alert topic
4. Receives all of Team B's monitoring alerts, learning their check names, failure patterns, and infrastructure details

### Scenario D: SSRF to Steal Lambda Credentials
1. Attacker with EDIT permission on any team creates a webhook channel
2. Sets webhook_url to http://169.254.169.254/latest/meta-data/iam/security-credentials/pulsechecks-lambda-exec-production
3. Calls POST /teams/{team_id}/channels/{channel_id}/test
4. The test notification fires an HTTP request to the metadata endpoint
5. Response is returned in the 502 error message: "Test notification failed: ...{AWS credentials}..."

### Scenario E: Internal Endpoint Abuse (GCP)
1. Attacker sends POST https://pulsechecks-api-prod.run.app/internal/late-detection with Authorization: Bearer anything
2. The OIDC check passes (token presence only, no validation)
3. Late detector runs on demand, marking all currently-due checks as LATE and firing alerts
4. Repeat every few seconds to generate continuous alert storms

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


## 5. Hardening Recommendations (Priority Order)

Immediate (before next deployment):

1. Re-enable domain allowlist — uncomment the 3 lines in dependencies.py. This is the single highest-impact fix.
2. Rotate the Google OAuth client secret — it's committed to git. Rotate in Google Cloud Console now, then move to GCP Secret Manager.
3. Add SSRF protection to webhook URL validation — block RFC 1918, loopback, and link-local addresses before any outbound HTTP call.
4. Fix internal endpoint OIDC validation — either actually validate the token or restrict Cloud Run to require authentication and use a dedicated scheduler
service account.

Short-term (this sprint):

5. Enforce API token expiry — add the expires_at check in _resolve_api_token.
6. Fix SNS topic ownership checks — apply tag verification to details and subscribe endpoints.
7. Remove debug print statements — replace all print(f"DEBUG: ...") with proper logger calls.
8. Scope Lambda IAM policies — fix ses:SendEmail and sns:CreateTopic wildcard resources.
9. Add per-token ping rate limiting — at API Gateway level (AWS) or Cloud Armor (GCP).
10. Remove duplicate rotate-token route.

Medium-term:

11. Implement distributed rate limiting — replace in-memory RateLimiter with Redis/ElastiCache or API Gateway per-route throttling.
12. Add HMAC signing to outbound webhooks — include X-PulseChecks-Signature: hmac-sha256=... header so recipients can verify authenticity.
13. Restrict CORS origins — replace allow_origins=["*"] with explicit frontend domain.
14. Add shared topic ACL — store explicit team grants for shared SNS topics.
15. Move terraform.tfvars to .gitignore and use a secrets manager or CI/CD variable injection.
16. Add webhook header allowlist — prevent attacker-controlled headers from being forwarded.
17. Remove /me/debug/versions endpoint from production.