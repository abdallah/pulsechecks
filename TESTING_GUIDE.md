# PulseChecks Testing Guide

Complete guide to validating security, resilience, and reliability of PulseChecks.

## Quick Start

```bash
# Set up environment
export API_URL="https://pulsechecks-api-prod.run.app"
export USER_TOKEN="<your-jwt-token>"
export TEAM_ID="<your-team-id>"

# Run all tests
./scripts/pentest.sh          # Security tests (~30 min)
./scripts/test_resilience.sh  # Resilience tests (~15 min)
python3 scripts/test_cost_amplification.py  # Cost test (~2 min)
```

## Testing Phases

### Phase 1: Security (After fixes #35-#39 merged)

**Documents:** `PENTEST_PLAN.md`, `TESTING_QUICKSTART.md`
**Script:** `./scripts/pentest.sh`
**Time:** 30 minutes

Tests:
- ✅ Domain allowlist enforcement (Issue #35)
- ✅ SSRF protection on webhook URLs (Issue #36)
- ✅ Rate limiting (Issue #38)
- ✅ SNS topic ownership validation (Issue #39)
- ✅ OIDC token validation (Issue #37)
- ✅ No token/credential leakage in logs

**Success criteria:**
All tests show PASS. No 403/401 errors on valid requests, all 400+ errors on invalid requests.

### Phase 2: Resilience (Before production deployment)

**Document:** `RESILIENCE_PLAN.md`
**Script:** `./scripts/test_resilience.sh`
**Time:** 15 minutes

Tests:
- ✅ Ping endpoint latency <500ms
- ✅ Data persistence to database
- ✅ Rapid failure handling
- ✅ Concurrent ping handling (50+)
- ✅ Alert infrastructure exists
- ✅ Health check endpoint
- ✅ Graceful error handling
- ✅ Load distribution (500 pings)

**Success criteria:**
Latencies <500ms, 100% data persistence, >95% concurrent success rate.

### Phase 3: Cost Amplification Prevention (Ongoing)

**Script:** `python3 scripts/test_cost_amplification.py`
**Time:** 2 minutes

Tests:
- ✅ Rate limiting prevents ping spam
- ✅ Alert deduplication prevents email spam
- ✅ Cost-per-check stays low under load

**Success criteria:**
Rate limiting active, >30% of requests return 429.

---

## Test Results Format

Each test suite produces:
- **PASS** (green): Test succeeded, condition met
- **FAIL** (red): Test failed, condition not met
- **WARN** (yellow): Test passed but with concerns
- **SKIP** (gray): Test not applicable or disabled

Example output:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PulseChecks Security Pen Test
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Phase 1] Authentication & Authorization
  ➜ Domain allowlist (non-OTGS) ... PASS
  
[Phase 2] SSRF Protection
  ➜ Creating test webhook channel ...     ✅ Created
  ➜ Block AWS metadata endpoint ... PASS
  ➜ Block GCP metadata endpoint ... PASS
  ➜ Block RFC 1918 (10.0.0.0/8) ... PASS

Results: 4 passed, 0 failed
```

---

## Environment Setup

### Get Tokens

1. **USER_TOKEN (JWT):**
   ```bash
   # Open frontend (https://pulsechecks.web.app)
   # Open DevTools (F12)
   # Go to Application → LocalStorage
   # Copy value of 'auth_token'
   export USER_TOKEN="eyJhbGc..."
   ```

2. **TEAM_ID:**
   ```bash
   # Option A: From team settings URL
   # https://pulsechecks.web.app/team/TEAM_ID/settings
   
   # Option B: From API
   curl -X GET "https://pulsechecks-api-prod.run.app/teams" \
     -H "Authorization: Bearer $USER_TOKEN" | jq '.[0].id'
   ```

3. **API_URL:**
   ```bash
   # Production (default)
   export API_URL="https://pulsechecks-api-prod.run.app"
   
   # Staging or local
   export API_URL="http://localhost:8000"
   ```

---

## CI/CD Integration

Add to your GitHub Actions workflow:

```yaml
name: Security & Resilience Tests

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run security tests
        env:
          API_URL: https://pulsechecks-api-prod.run.app
          USER_TOKEN: ${{ secrets.TEST_USER_TOKEN }}
          TEAM_ID: ${{ secrets.TEST_TEAM_ID }}
        run: ./scripts/pentest.sh
      
      - name: Run resilience tests
        env:
          API_URL: https://pulsechecks-api-prod.run.app
          USER_TOKEN: ${{ secrets.TEST_USER_TOKEN }}
          TEAM_ID: ${{ secrets.TEST_TEAM_ID }}
        run: ./scripts/test_resilience.sh

  cost-amplification:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Create test check
        id: check
        run: |
          # Create check and extract token
          RESPONSE=$(curl -X POST ... -d '...')
          TOKEN=$(echo $RESPONSE | jq -r '.token')
          echo "CHECK_TOKEN=$TOKEN" >> $GITHUB_OUTPUT
      
      - name: Test cost amplification
        env:
          API_URL: https://pulsechecks-api-prod.run.app
          USER_TOKEN: ${{ secrets.TEST_USER_TOKEN }}
          TEAM_ID: ${{ secrets.TEST_TEAM_ID }}
          CHECK_TOKEN: ${{ steps.check.outputs.CHECK_TOKEN }}
        run: python3 scripts/test_cost_amplification.py
```

---

## Monitoring Dashboard

After deploying to production, monitor these metrics:

**Availability:**
- Ping endpoint uptime (target: 99.9%)
- API endpoint uptime (target: 99%)
- Database availability (target: 99.9%)

**Performance:**
- Ping endpoint p50 latency (target: <50ms)
- Ping endpoint p99 latency (target: <200ms)
- Alert delivery latency (target: <5 min)

**Reliability:**
- Alert delivery success rate (target: >99%)
- Webhook delivery success rate (target: >95%)
- Ping persistence (target: 100%)

**Costs:**
- Lambda/Cloud Run cost per 1M pings (track for regression)
- SNS cost per 1M alerts (should be proportional to checks)
- Database cost (should not spike)

---

## Troubleshooting Tests

### `pentest.sh` fails with "jq: command not found"
```bash
brew install jq  # macOS
apt-get install jq  # Linux
```

### API returns 401 Unauthorized
Token has expired. Get a fresh one:
1. Open frontend, DevTools
2. Copy new `auth_token` from localStorage
3. Re-run tests

### Cannot connect to API
```bash
curl -v "$API_URL/health"
```
If timeout: network issue or API is down.

### Cost amplification test times out
```bash
# Reduce load in test_cost_amplification.py
CONCURRENT_PINGS = 50  # was 100
DURATION_SECONDS = 15  # was 30
```

---

## Compliance Checklist

Before production deployment:

- [ ] All security tests PASS (Phase 1)
- [ ] All resilience tests PASS (Phase 2)
- [ ] Cost amplification test shows rate limiting (Phase 3)
- [ ] No token/credential leakage in logs
- [ ] Domain allowlist is enforced
- [ ] SSRF protection blocks all private IPs
- [ ] OIDC validation is implemented
- [ ] Rate limiting per-token works
- [ ] SNS topic ownership is validated
- [ ] Ping endpoint latency <500ms
- [ ] Health check endpoint works
- [ ] Graceful degradation tested
- [ ] Monitoring dashboards configured
- [ ] On-call runbook documented
- [ ] Post-incident review process defined

---

## After Fixes: Deployment Checklist

1. ✅ Merge all security fix PRs
2. ✅ Run full test suite (security + resilience)
3. ✅ Deploy to staging
4. ✅ Run pen tests against staging
5. ✅ Monitor for 24 hours
6. ✅ Deploy to production
7. ✅ Monitor production metrics
8. ✅ Update security audit: "REMEDIATED"
9. ✅ Schedule quarterly retesting
10. ✅ Archive test results

---

## Resources

- **Security Review:** `Security_REVIEW.md`
- **Detailed Pen Test Plan:** `PENTEST_PLAN.md`
- **Security Testing Quick Start:** `TESTING_QUICKSTART.md`
- **Resilience Plan:** `RESILIENCE_PLAN.md`
- **GitHub Issues:** #35-#42 (security + features)

---

Questions? See individual test docs or check the issue descriptions.
