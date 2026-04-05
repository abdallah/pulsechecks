# PulseChecks Security Testing Quickstart

After security fixes are merged, run these tests to validate the fixes.

## Prerequisites

```bash
# Set up environment
export API_URL="https://pulsechecks-api-prod.run.app"
export USER_TOKEN="<your-jwt-token>"
export TEAM_ID="<your-team-id>"

# Get these from:
# - USER_TOKEN: Login to frontend, open DevTools, localStorage['auth_token']
# - TEAM_ID: From team settings URL or API /teams response
```

## Quick Security Test

Run the automated pen test suite (30 min):

```bash
./scripts/pentest.sh
```

This tests:
- ✅ Domain allowlist enforcement (Issue #35)
- ✅ SSRF protection (Issue #36)
- ✅ Rate limiting basics (Issue #38)
- ✅ API token functionality (Issue #35)
- ✅ No token leakage in logs (Issue #36)

**Expected output:** `PASS` for all tests.

## Cost Amplification Test

Test that spam pings don't cause alert explosion (10 min):

```bash
# Create a check first
curl -X POST "$API_URL/teams/$TEAM_ID/checks" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-cost", "type": "heartbeat", "periodSeconds": 300}' \
  | jq -r '.token' > /tmp/check_token.txt

# Run cost amplification test
export CHECK_TOKEN=$(cat /tmp/check_token.txt)
python3 scripts/test_cost_amplification.py
```

**Expected output:**
```
Rate Limit (429):   >=30
Rate Limited (%):   >=30%
✅ GOOD: Rate limiting is active and effective
```

If you see `⚠️ WARNING: No rate limiting detected!` → rate limiting fix is not working.

## Manual SSRF Test

Test that metadata endpoint requests are blocked (5 min):

```bash
# Get a channel ID or create one
CHANNEL_ID=$(curl -s -X POST "$API_URL/teams/$TEAM_ID/channels" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "test", "type": "webhook", "configuration": {"url": "https://example.com"}}' \
  | jq -r '.id')

# Try to update webhook to AWS metadata endpoint
curl -X PUT "$API_URL/teams/$TEAM_ID/channels/$CHANNEL_ID" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "configuration": {
      "url": "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
    }
  }' \
  | jq .

# Expected: 400 Bad Request with message like "private IP", "metadata", or "internal"
# Bad: 200 OK (SSRF protection not working)
```

## Manual Rate Limit Test

Test that per-token rate limiting works (10 min):

```bash
# Get check token
CHECK_TOKEN=$(curl -s -X POST "$API_URL/teams/$TEAM_ID/checks" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-rate", "type": "heartbeat", "periodSeconds": 300}' \
  | jq -r '.token')

# Send 150 pings in 60 seconds
for i in {1..150}; do
  curl -X POST "$API_URL/ping/$CHECK_TOKEN/success" -w "HTTP %{http_code}\n" &
  [ $((i % 10)) -eq 0 ] && sleep 1
done
wait

# Count responses
# Expected: ~100 200s (accepted), ~50 429s (rate limited)
# Bad: all 200s (no rate limiting)
```

## Manual Domain Allowlist Test

Test that non-OTGS domains are blocked (5 min):

```bash
# Try to "register" with non-OTGS domain (this is tricky without full OAuth flow)
# Instead, check the code has the check enabled:

grep -A2 "check_domain_allowed" backend/app/dependencies.py | grep -v "^--$"

# Should output uncommented code like:
# if not check_domain_allowed(email):
#     raise ForbiddenError("Email domain not allowed")
```

## Full Integration Test

For comprehensive testing after all fixes:

```bash
# Run all pen tests
./scripts/pentest.sh

# Run cost amplification test
export CHECK_TOKEN=$(...)
python3 scripts/test_cost_amplification.py

# Monitor CloudWatch logs for no token leakage
gcloud logging read "resource.type=cloud_run_revision" \
  --filter='severity=DEBUG' --limit=10 --format=json | grep -i "token\|credential" || echo "✅ No credentials in logs"
```

## Monitoring During Tests

In another terminal, watch for unexpected behavior:

```bash
# Watch API latency
watch -n 1 'curl -s -o /dev/null -w "%{time_total}\n" "$API_URL/teams/$TEAM_ID"'

# Watch Cloud Run logs
gcloud run services describe pulsechecks --platform managed \
  && gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=pulsechecks" \
  --stream --limit=50 --format='[%(severity)] %(textPayload)'

# Watch DynamoDB throttling (AWS)
aws dynamodb describe-table --table-name pulsechecks-checks --profile wpml_production \
  | jq '.Table | {ProvisionedThroughput, TableStatus}'
```

## Issue-by-Issue Testing

### Issue #35: Domain Allowlist
```bash
# Code check
grep -n "check_domain_allowed" backend/app/dependencies.py | grep -v "^[0-9]*:[[:space:]]*#"
# Should have uncommented line(s)

# Function test
./scripts/pentest.sh
# Look for "Domain allowlist" test result
```

### Issue #36: SSRF Protection
```bash
# Run SSRF subset of pentest
./scripts/pentest.sh | grep -A5 "Phase 2"

# Or manual test
curl ... -d '{"url": "http://169.254.169.254/..."}' | grep -E "400|403|private|internal"
```

### Issue #37: OIDC Validation
```bash
# Code check - ensure token is actually validated, not just checked for presence
grep -A10 "_verify_oidc" backend/app/routers/internal.py | grep "verify_oauth2_token\|id_token"

# Functional test (requires valid OIDC token)
curl -X POST "$API_URL/internal/late-detection" \
  -H "Authorization: Bearer invalid-token"
# Expected: 401 Unauthorized
```

### Issue #38: Rate Limiting
```bash
# Run cost amplification test
python3 scripts/test_cost_amplification.py

# Or manual rate limit test
for i in {1..150}; do curl -X POST "$API_URL/ping/$TOKEN/success" &; done; wait
# Check for 429 responses
```

### Issue #39: SNS Topic Ownership
```bash
# Code check
grep -B5 -A5 "def.*subscribe.*alert" backend/app/routers/alerts.py | grep -A5 "def get_alert"
# Should have tag ownership check before any SNS call

# Note: Full functional test requires access to Team B's topic ARN
```

## Success Checklist

- [ ] All pentest.sh tests pass (GREEN)
- [ ] Cost amplification test shows rate limiting working
- [ ] No token/credential leakage in CloudWatch logs
- [ ] SSRF blocking tests all pass (169.254, metadata.google.internal, RFC 1918)
- [ ] OIDC validation test blocks invalid tokens
- [ ] Domain allowlist code is uncommented and active

## Troubleshooting

**pentest.sh fails with "jq: command not found"**
```bash
# Install jq
brew install jq  # macOS
apt-get install jq  # Linux
```

**API returns 401 Unauthorized**
- Check USER_TOKEN is valid and hasn't expired
- Get fresh token from frontend localStorage

**Cost amplification test times out**
- Check network connectivity to API
- Try reducing CONCURRENT_PINGS in test_cost_amplification.py

**SSRF test shows channel creation failing**
- Verify TEAM_ID is correct
- Check team has API access enabled

## After Testing

Once all tests pass:

1. ✅ Merge security fix PRs to main
2. ✅ Deploy to production
3. ✅ Update security audit status: "REMEDIATED"
4. ✅ Add tests to CI/CD pipeline
5. ✅ Schedule quarterly retesting

See PENTEST_PLAN.md for full details and additional test phases.
