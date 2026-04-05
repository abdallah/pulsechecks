# ADR: Comprehensive Testing Strategy for PulseChecks

**Date:** 2026-04-05  
**Status:** ACCEPTED  
**Author:** Security & Reliability Team

---

## Problem

PulseChecks is a critical monitoring service. Failures could:
- Cause missed alerts (monitoring blind spot)
- Trigger false alerts (alert fatigue)
- Leak credentials (security breach)
- Amplify costs via spam/DoS (financial impact)
- Lose ping data (data loss)

Without comprehensive testing, these risks materialize in production.

---

## Decision

Implement a three-phase testing strategy:

### Phase 1: Security Testing (Pen Testing)
**Scope:** Authentication, authorization, SSRF, rate limiting, OIDC, logging
**Frequency:** Before every production deployment + quarterly
**Owner:** Security team
**Artifacts:** `PENTEST_PLAN.md`, `TESTING_QUICKSTART.md`, `./scripts/pentest.sh`

### Phase 2: Resilience Testing
**Scope:** Availability, data durability, alert delivery, performance, graceful degradation
**Frequency:** Before every production deployment + monthly
**Owner:** Reliability team
**Artifacts:** `RESILIENCE_PLAN.md`, `./scripts/test_resilience.sh`

### Phase 3: Cost Amplification Testing
**Scope:** Rate limiting prevents ping spam, alert deduplication prevents email spam
**Frequency:** Continuous (CI/CD), plus on-demand
**Owner:** DevOps
**Artifacts:** `./scripts/test_cost_amplification.py`

---

## Rationale

### Why Three Phases?

1. **Security Testing** validates fix for identified vulnerabilities (#35-#39)
2. **Resilience Testing** ensures the service never fails the user
3. **Cost Testing** prevents financial attacks

Each phase tests different risk dimensions:
- Security: "Can someone break in?"
- Resilience: "Will it keep running?"
- Costs: "Can someone break my wallet?"

### Why Automated Scripts?

Manual testing is:
- Slow (hours of clicking)
- Unreliable (human error, inconsistency)
- Hard to reproduce
- Not CI/CD-friendly

Automated scripts:
- Fast (~45 min total)
- Reliable (deterministic)
- Reproducible
- Integrates with CI/CD
- Provides metrics

### Why Before Every Deployment?

Security and resilience are not optional. Running tests before every deploy:
- Catches regressions
- Prevents known vulnerabilities from re-appearing
- Builds confidence in production safety
- Creates audit trail

### Why Also Quarterly/Monthly?

Continuous testing catches introduced bugs. Periodic testing (beyond CI/CD) catches:
- Environmental changes (DNS, firewall rules)
- Configuration drift
- New attack vectors
- Infrastructure changes

---

## Testing Matrix

| Aspect | Phase | Script | Frequency | Time | Pass Rate |
|--------|-------|--------|-----------|------|-----------|
| Domain allowlist | 1 | pentest.sh | Every deploy | 2min | 100% |
| SSRF protection | 1 | pentest.sh | Every deploy | 5min | 100% |
| Rate limiting | 1+3 | pentest.sh + cost_amp | Every deploy | 2min + 5min | 100% |
| OIDC validation | 1 | pentest.sh | Every deploy | 2min | 100% |
| Token leakage | 1 | pentest.sh | Every deploy | 2min | 0 leaks |
| Ping latency | 2 | test_resilience.sh | Every deploy | 3min | p99 <500ms |
| Data persistence | 2 | test_resilience.sh | Every deploy | 2min | 100% |
| Alert delivery | 2 | test_resilience.sh | Monthly | 5min | 99%+ |
| Graceful degradation | 2 | test_resilience.sh | Monthly | 3min | Degrades, not crashes |
| Cost prevention | 3 | test_cost_amplification.py | Continuous | 5min | Rate limited |

**Total time for full suite:** ~45 minutes  
**Minimum (critical path):** ~15 minutes

---

## Success Criteria

### Security Testing
- ✅ All Phase 1-6 tests in PENTEST_PLAN pass
- ✅ No token/credential leakage
- ✅ All SSRF vectors blocked
- ✅ Cross-team access denied

### Resilience Testing
- ✅ Ping endpoint latency p99 <500ms
- ✅ 100% data persistence
- ✅ >95% concurrent success rate
- ✅ Graceful degradation (pings never fail)

### Cost Prevention
- ✅ Rate limiting active (>30% of spam blocked)
- ✅ Alert deduplication working
- ✅ No cost spike under load

---

## Risks Mitigated

| Risk | Phase | Test | Mitigation |
|------|-------|------|-----------|
| Any Google user can register | 1 | Domain allowlist | Issue #35 fixed + tested |
| SSRF to steal credentials | 1 | SSRF protection | Issue #36 fixed + tested |
| Alert flooding DoS | 1+3 | Rate limiting | Issue #38 fixed + tested |
| Pings lost in transit | 2 | Data persistence | Verified in database |
| Service unavailable | 2 | Availability tests | Latency <500ms, uptime 99.9% |
| Alert delivery fails | 2 | Alert reliability | Queue + retry infrastructure |
| Cost amplification | 3 | Spam blocking | Rate limits prevent 10k pings |

---

## Implementation

### Immediate (This Sprint)
- ✅ Finish security fixes (#35-#39)
- ✅ Create testing infrastructure (scripts, docs)
- ✅ Run full test suite locally
- ✅ Merge to main
- ✅ Deploy to production

### Ongoing (Next Month)
- [ ] Integrate tests into CI/CD pipeline
- [ ] Set up test environment (staging)
- [ ] Configure alerts on test failures
- [ ] Train team on running tests
- [ ] Document troubleshooting

### Long-Term (Next Quarter)
- [ ] Quarterly pen test (external firm)
- [ ] Monthly resilience review
- [ ] Update tests based on incidents
- [ ] Continuous monitoring dashboard

---

## Alternatives Considered

### Alternative 1: Manual Testing Only
**Rejected** because:
- Slow (hours per deploy)
- Unreliable (human error)
- Hard to reproduce results
- Not suitable for CI/CD

### Alternative 2: Contract with Pen Testing Firm
**Partial:** Use internal testing + external quarterly review
- Internal tests catch regressions fast
- External firm catches new attack vectors
- Hybrid approach provides defense in depth

### Alternative 3: No Testing Before Prod
**Rejected** because:
- Unacceptable risk for monitoring service
- No safety net for regressions
- Increases MTTR on incidents
- Non-compliant with security standards

---

## Metrics & Monitoring

Track these KPIs:

**Test Coverage:**
- % of security findings tested (target: 100%)
- % of critical paths tested (target: 100%)
- Test execution time (track for regression)

**Deployment Safety:**
- Deployments with all tests passing (target: 100%)
- Deployments with test failures (target: 0%)
- Regressions caught by tests before prod (target: >80%)

**Production Reliability:**
- Ping endpoint uptime (target: 99.9%)
- Alert delivery success rate (target: 99%+)
- False positive rate (target: <0.1%)
- Incidents related to tested issues (target: 0)

---

## Dependencies

- jq (JSON query tool) — for parsing API responses
- curl (HTTP client) — for API calls
- Python 3.8+ — for async load testing
- GitHub CLI (gh) — for issue creation
- Cloud tools (gcloud, aws cli) — for infrastructure tests

---

## Related Documents

- `PENTEST_PLAN.md` — Detailed pen test procedures
- `RESILIENCE_PLAN.md` — Detailed resilience procedures
- `TESTING_QUICKSTART.md` — Quick reference for running tests
- `TESTING_GUIDE.md` — Unified testing guide
- `Security_REVIEW.md` — Original security audit findings
- Issues #35-#42 — Security fixes and feature requests

---

## Approval

| Role | Name | Signed | Date |
|------|------|--------|------|
| Security Lead | TBD | [ ] | |
| Ops Lead | TBD | [ ] | |
| Product Lead | Abdallah | [x] | 2026-04-05 |

---

## Changelog

- **2026-04-05:** Initial draft, three-phase strategy
