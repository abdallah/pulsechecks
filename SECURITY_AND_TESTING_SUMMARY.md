# PulseChecks: Security & Testing Summary

**Date:** 2026-04-05  
**Status:** Security fixes in progress, testing infrastructure complete

---

## Overview

PulseChecks underwent a security audit (Security_REVIEW.md) that identified 17 findings across 5 severity levels. This document tracks remediation and testing to ensure the service is secure, resilient, and cost-effective.

---

## Security Issues & Status

### 🔴 CRITICAL (Fix immediately)

| Issue | Title | Status | PR | ETA |
|-------|-------|--------|----|----|
| #35 | Re-enable domain allowlist | ✅ FIXED | #40 | Done |
| #36 | Add SSRF protection | 🟡 IN PROGRESS | — | This week |
| #37 | Fix internal endpoint OIDC validation | 🟡 IN PROGRESS | — | This week |
| #38 | Implement distributed rate limiting | 🟡 IN PROGRESS | — | This week |

### 🟠 HIGH (Fix this sprint)

| Issue | Title | Status | PR | ETA |
|-------|-------|--------|----|----|
| #39 | Add SNS topic ownership validation | 🟡 IN PROGRESS | — | This week |
| FINDING-07 | Alert topic ownership checks | — | — | Next sprint |
| FINDING-08 | Shared SNS topic access control | — | — | Next sprint |

### 🟡 MEDIUM (Fix next sprint)

| Issue | Title | Status | PR |
|-------|-------|--------|-----|
| FINDING-10 | API token expiry enforcement | — | — |
| FINDING-12 | CORS wildcard in production | — | — |
| FINDING-13-14 | Lambda IAM overly broad | — | — |
| FINDING-15 | Webhook headers not validated | — | — |

---

## Testing Infrastructure

### ✅ Completed

| Document | Purpose | Location |
|----------|---------|----------|
| PENTEST_PLAN.md | 8-phase security pen test plan | docs root |
| TESTING_QUICKSTART.md | Quick reference for running tests | docs root |
| RESILIENCE_PLAN.md | Availability, durability, alert reliability | docs root |
| TESTING_GUIDE.md | Unified testing guide with CI/CD setup | docs root |
| ADR-testing-strategy.md | Architecture decision for 3-phase approach | docs/ |
| pentest.sh | Automated security test harness | scripts/ |
| test_resilience.sh | Automated resilience test harness | scripts/ |
| test_cost_amplification.py | Load test for cost prevention | scripts/ |
| ssrf_utils.py | SSRF validation utilities | backend/app/ |

### Test Coverage

**Phase 1: Security Testing** (30 min)
- Domain allowlist enforcement
- SSRF protection (metadata endpoints, RFC 1918)
- Rate limiting basics
- API token functionality
- Token leakage in logs
- SNS topic ownership
- OIDC validation

**Phase 2: Resilience Testing** (15 min)
- Ping endpoint latency (<500ms)
- Data persistence to database
- Concurrent ping handling (50+)
- Alert infrastructure
- Health check endpoints
- Graceful error handling
- Load distribution (500 pings)

**Phase 3: Cost Amplification Testing** (2 min)
- Rate limiting prevents spam
- Alert deduplication
- Cost per check stays proportional

---

## Issue Resolution Plan

### This Week (by 2026-04-11)

Priority: Security fixes #35-#39

1. ✅ **#35: Domain allowlist** — DONE (PR #40)
   - Uncommented domain check in dependencies.py
   - Added test for ForbiddenError on non-OTGS domains
   - Ready to merge and deploy

2. 🟡 **#36: SSRF protection** — In Kiro's queue
   - Add SSRF validation to channel webhook URLs
   - Block private IPs, metadata endpoints
   - Test all 4 webhook endpoints
   - ETA: 2-3 hours

3. 🟡 **#37: OIDC validation** — In Kiro's queue
   - Implement proper JWT validation in /internal/* endpoints
   - Verify token signature, expiry, audience
   - Restrict Cloud Run IAM or validate token
   - ETA: 2-3 hours

4. 🟡 **#38: Rate limiting** — In Kiro's queue
   - Implement distributed rate limiting (Redis or API Gateway)
   - Add per-token rate limiting (max 10 pings/min)
   - Test cost amplification scenario
   - ETA: 3-4 hours

5. 🟡 **#39: SNS topic ownership** — In Kiro's queue
   - Add tag validation to details and subscribe endpoints
   - Match logic in delete/unsubscribe endpoints
   - Test cross-team access is blocked
   - ETA: 1-2 hours

### After Fixes (by 2026-04-14)

1. **Run full test suite** (45 min)
   ```bash
   ./scripts/pentest.sh              # Security
   ./scripts/test_resilience.sh      # Resilience
   python3 scripts/test_cost_amplification.py  # Costs
   ```

2. **Deploy to production**
   - Merge all fix PRs to main
   - Deploy via Cloud Build + Cloud Run
   - Monitor for 24 hours

3. **Update audit status**
   - Mark Security_REVIEW.md as "REMEDIATED"
   - Archive test results
   - Schedule quarterly retesting

### Next Sprint (by 2026-04-30)

Remaining HIGH/MEDIUM issues:
- #07: Alert topic access control for shared topics
- #10: API token expiry enforcement
- #12: CORS origin configuration
- #13-14: Lambda IAM policy refinement
- #15: Webhook header allowlist

---

## Feature Requests

Created from discussion:

| Issue | Title | Status | Priority |
|-------|-------|--------|----------|
| #41 | Add error code parameter to ping URLs | OPEN | Enhancement |
| #42 | Create checks by friendly name (not ID) | OPEN | Enhancement |

**Can be queued after security fixes are verified.**

---

## Success Checklist

### Before Deployment
- [ ] All 5 critical security fixes merged to main
- [ ] pentest.sh shows all tests PASS
- [ ] test_resilience.sh shows all tests PASS
- [ ] test_cost_amplification.py shows rate limiting active
- [ ] No token/credential leakage in logs
- [ ] Deployment steps documented

### After Deployment
- [ ] Monitoring dashboards show normal operation
- [ ] No spike in 401/403 errors (domain allowlist)
- [ ] No spike in webhook errors (SSRF protection)
- [ ] Rate limiting active (visible in metrics)
- [ ] Alerts delivered within SLA
- [ ] On-call runbook updated

### Long-Term
- [ ] Tests integrated into CI/CD
- [ ] Quarterly pen test scheduled
- [ ] Monitoring alerts configured
- [ ] Post-incident reviews scheduled
- [ ] Security audit retesting planned (Q3 2026)

---

## Key Metrics

### Availability
- **Target:** 99.9% uptime
- **Testing:** RESILIENCE_PLAN Test 1.1-1.3
- **Monitoring:** CloudWatch/Stackdriver uptime metric

### Security
- **Target:** 100% of known vulns fixed before prod
- **Testing:** PENTEST_PLAN all phases pass
- **Monitoring:** Security event logging + alerting

### Performance
- **Target:** Ping latency p99 <500ms
- **Testing:** RESILIENCE_PLAN Test 4.1
- **Monitoring:** CloudWatch latency metrics

### Costs
- **Target:** No cost amplification (rate limiting prevents spam)
- **Testing:** test_cost_amplification.py shows >30% rate limited
- **Monitoring:** CloudWatch cost metrics

---

## Documents & Artifacts

**In repository:**
- `Security_REVIEW.md` — Original audit findings (17 issues)
- `PENTEST_PLAN.md` — 8-phase pen test procedures
- `RESILIENCE_PLAN.md` — Availability, durability, reliability
- `TESTING_GUIDE.md` — Quick start + CI/CD setup
- `TESTING_QUICKSTART.md` — Per-issue testing guide
- `docs/ADR-testing-strategy.md` — Strategic decision record
- `scripts/pentest.sh` — Automated security tests
- `scripts/test_resilience.sh` — Automated resilience tests
- `scripts/test_cost_amplification.py` — Async load test
- `backend/app/ssrf_utils.py` — SSRF validation utilities

**On GitHub:**
- Issues #35-#42 (security + features)
- PR #40 (domain allowlist fix)
- PR #41+ (remaining fixes, in progress)

---

## Timeline

```
Apr 5 (today)     | Security fixes created (#35-#39)
Apr 5-11 (week 1) | Kiro implements fixes, testing docs complete ✅
Apr 11-14 (week 2)| Run full test suite, deploy to prod
Apr 14+ (ongoing) | Monitor metrics, quarterly retesting
```

---

## Risks & Contingencies

### Risk 1: Test Harness Doesn't Catch a Vulnerability
**Mitigation:** Quarterly external pen test, bug bounty program

### Risk 2: Deployment Breaks Production
**Mitigation:** Staging environment, canary deployment, quick rollback

### Risk 3: Rate Limiting Implementation Is Buggy
**Mitigation:** Extended load testing, monitor alert email counts, easy config tuning

### Risk 4: False Positives in Tests Cause Alert Fatigue
**Mitigation:** Baseline all metrics, adjust thresholds, document expected behavior

---

## Next Steps

1. **Immediate:** Kiro continues with fixes #36-#39
2. **Daily:** Check PR status, review code, run tests locally
3. **End of week:** Merge all fixes, run full test suite
4. **Following week:** Deploy to production, monitor 24h
5. **Ongoing:** Weekly metrics review, quarterly retesting

---

## Questions?

See individual documents:
- **How do I run tests?** → TESTING_GUIDE.md
- **What security issues were found?** → Security_REVIEW.md
- **What's the detailed pen test plan?** → PENTEST_PLAN.md
- **How do I ensure reliability?** → RESILIENCE_PLAN.md
- **What's the strategic decision?** → docs/ADR-testing-strategy.md
