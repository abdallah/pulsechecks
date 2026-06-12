# Edge Throttling Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add provider-aware edge throttling for Pulsechecks so AWS deployments use API Gateway throttling and GCP deployments use Cloud Armor in front of a global HTTPS load balancer.

**Architecture:** Keep the FastAPI in-process limiter as defense-in-depth only. Make edge throttling the primary enforcement layer in production. On AWS, expose API Gateway throttle values as Terraform variables. On GCP, introduce a load balancer + Cloud Armor path that fronts Cloud Run, and keep direct Cloud Run access only for explicitly non-production or internal setups.

**Tech Stack:** Terraform, AWS API Gateway, GCP Cloud Run, GCP Cloud Armor, GCP external HTTPS load balancer, FastAPI, Docker-based test harness.

---

### Task 1: Parameterize AWS API Gateway throttling

**Objective:** Make AWS edge throttling configurable per environment via Terraform variables.

**Files:**
- Modify: `infra/aws/variables.tf`
- Modify: `infra/aws/api-gateway.tf`
- Modify: `docs/multi-cloud-architecture.md`
- Modify: `docs/operations.md` or `docs/development.md` if deployment notes belong there
- Test: `infra/aws` Terraform validation / plan checks

**Step 1: Confirm current defaults**
- Read `infra/aws/api-gateway.tf` and `infra/aws/variables.tf`.
- Verify the current stage-level throttle values are hardcoded.

**Step 2: Add variables**
Add these variables to `infra/aws/variables.tf`:

```hcl
variable "api_gateway_throttling_rate_limit" {
  description = "Default API Gateway request rate limit (requests per second)"
  type        = number
  default     = 1000
}

variable "api_gateway_throttling_burst_limit" {
  description = "Default API Gateway burst limit"
  type        = number
  default     = 2000
}
```

**Step 3: Wire variables into the API Gateway stage**
Replace the hardcoded values in `infra/aws/api-gateway.tf`:

```hcl
default_route_settings {
  throttling_rate_limit  = var.api_gateway_throttling_rate_limit
  throttling_burst_limit = var.api_gateway_throttling_burst_limit
}
```

**Step 4: Document the AWS behavior**
Add a short note in `docs/multi-cloud-architecture.md` that AWS uses API Gateway throttling as the edge layer for public API traffic.

**Step 5: Verify**
Run from the repo root:

```bash
terraform -chdir=infra/aws fmt -check
terraform -chdir=infra/aws init -backend=false
terraform -chdir=infra/aws validate
```

Expected: all commands succeed.

**Step 6: Commit**
```bash
git add infra/aws/variables.tf infra/aws/api-gateway.tf docs/multi-cloud-architecture.md docs/operations.md
git commit -m "infra: parameterize AWS edge throttling"
```

---

### Task 2: Add GCP edge throttling design and infra scaffold

**Objective:** Introduce the GCP edge path needed for Cloud Armor rate limiting in front of Cloud Run.

**Files:**
- Modify/Create: `infra/gcp/*.tf` as needed
- Modify: `infra/gcp/variables.tf`
- Modify: `infra/gcp/main.tf`
- Modify: `infra/gcp/cloudrun.tf`
- Modify: `docs/multi-cloud-architecture.md`
- Modify/Create: `docs/operations.md` or `docs/deployment.md`
- Test: Terraform validation in `infra/gcp`

**Step 1: Add provider-aware variables**
Add GCP edge throttling variables to `infra/gcp/variables.tf`.
Keep them explicit and environment-driven, for example:

```hcl
variable "edge_throttling_enabled" {
  description = "Enable edge throttling in front of GCP Cloud Run"
  type        = bool
  default     = true
}

variable "edge_throttle_requests_per_second" {
  description = "Cloud Armor rate limit threshold"
  type        = number
  default     = 1000
}

variable "edge_throttle_burst" {
  description = "Cloud Armor burst threshold"
  type        = number
  default     = 2000
}
```

**Step 2: Add infra scaffolding**
Model the GCP edge path as:
- global external HTTPS load balancer
- serverless NEG to Cloud Run
- Cloud Armor security policy attached to the backend service

Keep this minimal and provider-native. If the repo already has a load balancer pattern elsewhere, follow that style.

**Step 3: Keep direct Cloud Run access explicit**
In `infra/gcp/cloudrun.tf`, document whether public access remains enabled for internal/test environments or is only for the LB path. If you keep `allUsers`, call out that production traffic is expected to go through the load balancer.

**Step 4: Update architecture docs**
Add a clear note in `docs/multi-cloud-architecture.md`:
- AWS: API Gateway throttling
- GCP: Cloud Armor requires the external HTTPS load balancer path
- Cloud Run domain mapping by itself is not the edge-throttling solution

**Step 5: Verify**
Run:

```bash
terraform -chdir=infra/gcp fmt -check
terraform -chdir=infra/gcp init -backend=false
terraform -chdir=infra/gcp validate
```

If the full LB resource graph is too large for one pass, stop after scaffolding the variables + docs + the initial LB/security-policy resources, and note any remaining provider-specific outputs or DNS wiring as a follow-up task.

**Step 6: Commit**
```bash
git add infra/gcp/variables.tf infra/gcp/main.tf infra/gcp/cloudrun.tf docs/multi-cloud-architecture.md docs/operations.md
git commit -m "infra: scaffold GCP edge throttling"
```

---

### Task 3: Document fallback app limiter and provider mapping

**Objective:** Make the operational model obvious so nobody mistakes the in-process limiter for the real production control.

**Files:**
- Modify: `backend/app/middleware.py`
- Modify: `docs/operations.md`
- Modify: `docs/development.md` or `README.md`

**Step 1: Clarify the middleware role**
Update the middleware docstring and any nearby comments to say it is defense-in-depth only.

**Step 2: Add provider mapping**
Explain:
- AWS production = API Gateway throttling
- GCP production = Cloud Armor + load balancer
- In-app limiter = fallback/secondary guardrail

**Step 3: Verify wording**
Read the edited docs to ensure they do not imply process-local throttling is cluster-wide.

**Step 4: Commit**
```bash
git add backend/app/middleware.py docs/operations.md docs/development.md
git commit -m "docs: clarify edge throttling model"
```

---

### Task 4: Add regression tests for deployment mapping

**Objective:** Ensure the cloud-provider mapping and throttling config stay intentional.

**Files:**
- Modify/Create: `infra/aws` or `infra/gcp` validation helpers if needed
- Modify: existing docs/config tests if the repo has Terraform smoke tests
- Test: containerized Terraform validation and relevant existing backend tests

**Step 1: Add or extend validation coverage**
If Terraform tests exist, add assertions that:
- AWS exposes the throttle variables
- AWS API Gateway stage consumes those variables
- GCP docs mention Cloud Armor + LB as the edge layer

**Step 2: Add a guard against hardcoded AWS values**
Add a test or lint check that fails if `infra/aws/api-gateway.tf` reverts to numeric literals for throttle settings.

**Step 3: Verify**
Run the relevant infra checks again, plus the full Docker suites already used for the repo.

**Step 4: Commit**
```bash
git add <changed files>
git commit -m "test: cover edge throttling mapping"
```

---

## Final verification checklist
- [ ] AWS Terraform validates
- [ ] GCP Terraform validates or the scaffold compiles cleanly
- [ ] Docs clearly distinguish AWS vs GCP edge throttling
- [ ] In-process middleware is explicitly secondary
- [ ] Docker backend suite passes
- [ ] Docker frontend suite passes
- [ ] `git diff --check` passes
