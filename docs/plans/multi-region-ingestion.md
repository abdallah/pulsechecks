# Multi-Region Ping Ingestion Plan (GCP)

**Status:** Plan — apply when check volume or an availability commitment demands it.
**Goal:** 99.99% availability for the *ping ingestion path* specifically.
**Prerequisite honesty:** this is a **migration**, not a Terraform flag. The
current Firestore database was created in a single region, and Firestore's
location is immutable after creation. Everything else in this plan is
additive, but the database step requires an export/import migration window.

## Why ingestion-first

For a monitoring product, the failure that destroys trust is a *lost ping*
(false "late" alerts) or a *missed alert*. Dashboard/API downtime is
annoying; ingestion downtime is product failure. So the plan raises the
ingestion path to active-active multi-region and deliberately leaves the
management API single-region until later.

Current ingestion ceiling (single region): Cloud Run SLA 99.95% × regional
Firestore 99.99% ≈ **99.94%**. Target stack: global LB 99.99% × two
Cloud Run regions (independent failures) × multi-region Firestore 99.999%
≈ **99.98–99.99%**.

## Step 1 — Firestore to multi-region (the migration)

1. Create a new Firestore database in `nam5` (US multi-region) or `eur3`
   (Europe multi-region) — pick based on where checks ping from.
2. Announce a short maintenance window (pings buffered by senders' retries;
   most cron jobs simply ping again next period).
3. `gcloud firestore export` from the regional DB → `gcloud firestore import`
   into the multi-region DB. At current data sizes this is minutes.
4. Flip `FIRESTORE_DATABASE` on Cloud Run to the new database name and
   redeploy. The backend already treats the database name as config.
5. Re-apply the Firestore indexes/TTL Terraform against the new database
   (all index definitions are already in `infra/gcp/firestore.tf` and
   `backend/firestore.indexes.json`).

Multi-region Firestore alone lifts the data layer to 99.999% and removes
the biggest single-region dependency, even before step 2.

## Step 2 — Second Cloud Run region behind the global LB

The repo already provisions a global external HTTPS load balancer when
`edge_throttling_enabled = true` (Cloud Armor path). Extend it:

1. Deploy the same container as a second `google_cloud_run_service` in a
   second region (e.g. `us-east1` alongside `us-central1`), same env vars —
   Firestore multi-region serves both with no code changes.
2. Create a serverless NEG per region and put **both** NEGs in the LB's
   backend service. Outlier detection ejects an unhealthy region
   automatically; requests route to the nearest healthy region.
3. Keep Cloud Scheduler jobs (late detection, HTTP poll) targeting **one**
   region only — the detector is a singleton by design; the delivery queue
   makes its work durable. If the scheduler region is down, the dead-man's-
   switch (`HEARTBEAT_URL`) fires and detection resumes on the next tick
   after recovery. (Optional hardening: a second scheduler job, paused,
   in the other region as a manual failover.)

Terraform sketch (variables to add): `secondary_region`,
`enable_multi_region` gating the second service + NEG. Estimated cost:
one extra idle-scale-to-zero Cloud Run service ≈ $0; the global LB is
already paid for by the edge-throttling setup (~$18/month).

## Step 3 — Verify

- Synthetic pings from two geographies through the LB, per-region
  Cloud Run logs confirming both serve traffic.
- Chaos drill: disable the primary region's Cloud Run service; confirm
  pings keep landing (LB fails over) and late detection resumes within
  one scheduler tick after re-enable, with the delivery queue draining
  any backlog.
- The existing `no pings in 30 min` style alarms plus
  `AlertDeliveryExhausted` remain the canaries.

## Explicitly out of scope (and why)

- **Multi-region management API/frontend** — Firebase Hosting is already
  a global CDN; the API's 99.9% is acceptable for a dashboard.
- **Multi-cloud active-active** — operational cost far exceeds the
  availability gain; the AWS stack remains a cold-standby option.
- **Six nines** — not achievable on any serverless dependency chain and
  not required: with retried pings and a durable alert queue, brief
  ingestion blips do not lose data or alerts.
