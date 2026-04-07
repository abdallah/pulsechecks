# PulseChecks Reporting Plan

## Scope

This plan covers four reporting capabilities:
1. Performance history for HTTP checks
2. Error analysis and failure logs
3. Uptime reports with maintenance exclusions
4. On-demand downloadable reports

Out of scope for this phase:
- Scheduled email delivery
- PDF generation
- Retention beyond the existing 30-day ping TTL unless explicitly re-scoped

Resolved product decisions:
- Report delivery: downloadable reports only
- Deployment target for this work: GCP

---

## Current State Assessment

### What the codebase already has
- `Ping` entities already model `code`, `data`, `ping_type`, and timestamps in `backend/app/models/entities.py`
- The check details API already exposes recent ping history with `limit` and `since` parameters in `backend/app/routers/checks.py`
- Both Firestore and DynamoDB already store ping history with a 30-day TTL in `backend/app/db/firestore.py` and `backend/app/db/dynamodb.py`
- The frontend check detail page already shows recent pings and is the natural place for per-check reporting tabs in `frontend/src/pages/CheckDetailPage.jsx`
- Team settings already has a tabbed settings surface that can host team-level reports in `frontend/src/pages/TeamSettingsPage.jsx`

### What is missing or inconsistent today
- `Ping` does not store `response_time_ms`, so there is no latency history for HTTP checks
- `Ping.code` exists in the entity but is not persisted or returned consistently by the database adapters and API response models
- There is no aggregation layer for uptime, latency percentiles, incident grouping, or error summaries
- The scheduler records success and failure outcomes but not request duration
- The frontend only fetches the latest 20 pings for the detail page even though the backend can return up to 100
- There are no maintenance-window entities or APIs
- There are no report-generation APIs, storage abstractions, or downloadable artifacts
- The previous version of this plan mixed two scopes: emailed reports in the overview and downloadable reports in the implementation details

### Constraints that should drive the design
- Multi-cloud support is a repo requirement, so reporting storage and background processing need cloud abstractions, not GCP-only logic buried in handlers
- The current 30-day ping TTL means any reporting design that assumes 90-day raw per-ping history is not accurate unless retention is changed deliberately
- Reporting should not depend on fetching large raw ping datasets into the frontend; aggregation belongs in backend services

---

## Proposed Architecture

### Phase 0 foundation
- Add a dedicated reporting service layer in the backend instead of embedding aggregation logic inside routers
- Normalize ping persistence so both Firestore and DynamoDB store the same reporting fields
- Keep per-check reporting on the check detail page and team-wide report generation under team settings

### Backend building blocks
- `ReportingService`: computes latency stats, uptime summaries, incident windows, and error summaries
- `ReportGenerator`: renders JSON and CSV payloads for download
- `ReportStorage`: uploads generated artifacts and returns time-limited download URLs
- `MaintenanceWindow` and `Report` entities stored in the same database abstraction pattern already used elsewhere

### Frontend building blocks
- `Performance` and `Errors` tabs on the check detail page
- `Uptime` page for custom date-range reporting
- `Reports` tab in team settings for on-demand report generation and download history

---

## Feature 1: Performance History

### Goal
Show response-time history and summary statistics for HTTP checks for common ranges such as 24h, 7d, and 30d.

### Backend changes
1. Add `response_time_ms` to `Ping`
2. Persist `code` and `response_time_ms` in both Firestore and DynamoDB adapters
3. Record response time in the HTTP polling scheduler using a monotonic timer
4. Add a stats endpoint:

```text
GET /teams/{team_id}/checks/{check_id}/stats?range=24h|7d|30d
```

5. Return:
- uptime percentage for the selected window
- success and failure counts
- average, min, max, p50, and p95 latency
- range-aware time series data

### Frontend changes
- Add a `Performance` tab to the check detail page
- Add a range selector: 24h, 7d, 30d
- Render latency charts with failure markers
- Show summary cards for average latency, p95, uptime, and total failures

### Notes
- Keep raw ping list endpoint for debugging and recent history
- Do not fetch large histories directly into the UI for charting when the stats endpoint can return aggregated series

---

## Feature 2: Error Analysis

### Goal
Provide both a summarized error view and a paginated failure log for a check, plus a team-level summary.

### Backend changes
1. Extend ping query support to include:
- `type=fail|success|start`
- cursor-based pagination
- optional error-code filtering later if needed

2. Add a check-level error summary endpoint:

```text
GET /teams/{team_id}/checks/{check_id}/errors/summary?range=24h|7d|30d
```

3. Add a team-level summary endpoint:

```text
GET /teams/{team_id}/errors/summary?range=24h|7d|30d
```

4. Group failures into incidents where applicable so the UI can distinguish between raw failure events and outages

### Frontend changes
- Add an `Errors` tab to the check detail page
- Show summary cards for total failures, most common code, last failure, and longest incident
- Add a paginated log view with timestamp, code, detail, response time, and incident grouping where available
- Support CSV export from the downloadable reports flow, not as a separate one-off client-only export path

### Notes
- The existing `Ping.code` field should become first-class instead of remaining effectively dead metadata

---

## Feature 3: Uptime Reports

### Goal
Allow users to calculate uptime for arbitrary date ranges and exclude scheduled maintenance windows.

### Backend changes
1. Add `MaintenanceWindow` entity:

```python
class MaintenanceWindow(BaseModel):
    window_id: str
    team_id: str
    check_id: Optional[str] = None
    start_at: str
    end_at: str
    label: Optional[str] = None
    created_by: str
    created_at: str
```

2. Add CRUD endpoints:

```text
POST   /teams/{team_id}/maintenance
GET    /teams/{team_id}/maintenance?check_id=<id>
DELETE /teams/{team_id}/maintenance/{window_id}
```

3. Add uptime endpoint:

```text
GET /teams/{team_id}/checks/{check_id}/uptime?from=<iso>&to=<iso>&exclude_maintenance=true
```

4. Compute:
- uptime percentage
- total observed minutes
- downtime minutes
- excluded maintenance minutes
- incident list with start, end, duration, and dominant failure reason

### Frontend changes
- Add a dedicated uptime page reachable from a check and from team reporting
- Add date-range selection
- Add maintenance window management UI
- Add incident table and summary state for SLA-style review

### Notes
- Because ping retention is currently 30 days, arbitrary-range uptime beyond 30 days is not available unless retention or rollups are added
- If long-range uptime becomes a requirement, add daily rollups before increasing raw ping retention

---

## Feature 4: Downloadable Reports

### Goal
Generate reports on demand and return a downloadable URL for JSON or CSV output.

### Backend changes
1. Add `Report` entity:

```python
class Report(BaseModel):
    report_id: str
    team_id: str
    check_id: Optional[str] = None
    report_type: str
    format: str
    from_date: str
    to_date: str
    status: str
    download_url: Optional[str] = None
    created_at: str
    created_by: str
    expires_at: str
```

2. Add report endpoints:

```text
POST   /teams/{team_id}/reports
GET    /teams/{team_id}/reports/{report_id}
GET    /teams/{team_id}/reports
DELETE /teams/{team_id}/reports/{report_id}
```

3. Implement report types:
- `uptime`
- `errors`
- `performance`
- `summary`

4. Implement `ReportStorage` abstraction with cloud-specific implementations:
- GCS for GCP
- S3 for AWS

5. Use synchronous generation for small jobs and background generation for larger ranges

### Frontend changes
- Add a `Reports` tab to team settings
- Add a form for report type, target check or team scope, date range, and format
- Show generation status and recent reports
- Show download expiry so users understand the URL is temporary

### Notes
- Scheduled email delivery remains out of scope for this phase
- JSON and CSV are the only required formats in this iteration

---

## Data Model Changes

### Ping
Add and wire through these fields consistently across entity, storage adapters, response models, and tests:

```python
response_time_ms: Optional[int] = None
code: Optional[str] = None
```

### New entities
- `MaintenanceWindow`
- `Report`

### Response models to add
- `CheckStatsResponse`
- `ErrorSummaryResponse`
- `UptimeReportResponse`
- `ReportResponse`
- `ReportListItemResponse`

---

## API Design Notes

### Range handling
- Use explicit server-supported ranges for common views: `24h`, `7d`, `30d`
- Use `from` and `to` for custom uptime and downloadable report requests
- Validate that requested ranges fit within retained data availability

### Pagination
- Recent pings endpoint should move from simple `limit`-only behavior to cursor-based pagination once used for failure log browsing
- The check detail page can continue using a small recent-pings call separate from paginated reporting APIs

### Authorization
- Reuse existing team access checks for every reporting endpoint
- Team-level report generation should require at least the same view permission as existing team detail endpoints

---

## Full Testing Strategy

No reporting feature is complete until all layers below are covered.

### Backend unit tests
- Scheduler tests for response-time capture on successful and failed HTTP checks
- Aggregation tests for latency calculations including empty datasets, single-point datasets, and percentile edges
- Incident reconstruction tests for consecutive failures, recovery, leading failures, and range boundaries
- Maintenance overlap tests for partial overlap, full overlap, and multiple windows
- Report generation tests for JSON and CSV output formatting

### Database adapter tests
- Firestore tests for storing and reading `code` and `response_time_ms`
- DynamoDB tests for storing and reading `code` and `response_time_ms`
- Tests for paginated ping queries and `since` filtering
- Tests for maintenance-window CRUD in both adapters
- Tests for report metadata CRUD in both adapters

### API tests
- Stats endpoint success and auth failure cases
- Error summary endpoint success, empty-state, and invalid-range cases
- Uptime endpoint with and without maintenance exclusions
- Report creation, polling, listing, deletion, and invalid-format cases
- Validation tests for check-scoped versus team-scoped report requests

### Frontend tests
- Check detail performance tab renders stats, handles loading, empty data, and API failures
- Check detail errors tab renders summaries, paginated failures, and filters
- Uptime page handles date-range validation, maintenance CRUD, and summary rendering
- Team settings reports tab handles report submission, polling, ready, failed, and expired states
- API client tests for all new reporting methods and query-string handling

### End-to-end and smoke coverage
- Backend smoke flow: create check, generate pings, verify stats and errors endpoints
- Uptime flow: create maintenance window, request uptime, verify excluded minutes
- Report flow: request report, poll until ready, download artifact, verify contents
- Post-deploy smoke on GCP for at least one check-level stats request and one report-generation request

### Coverage expectations
- Backend: new reporting modules and router paths should be fully covered by targeted tests, with no untested branches for auth, empty states, or invalid ranges
- Frontend: all new report surfaces should have render-path, loading-path, and failure-path coverage

---

## Implementation Order

### Phase 1: Data and API foundation
1. Add `response_time_ms` and correctly persist `code`
2. Update scheduler to record response time
3. Add reporting service module and response models
4. Add stats endpoint
5. Add unit and adapter tests for the new ping fields

### Phase 2: Performance reporting
1. Add check stats API integration in frontend
2. Build performance tab on check detail page
3. Add frontend tests for range switching and empty states

### Phase 3: Error reporting
1. Add error summary and paginated failure APIs
2. Build errors tab
3. Add backend and frontend tests for summaries and logs

### Phase 4: Uptime and maintenance
1. Add maintenance entities and CRUD
2. Add uptime calculation endpoint
3. Build uptime UI
4. Add incident and maintenance calculation tests

### Phase 5: Downloadable reports
1. Add report entities, generators, and storage abstraction
2. Add report APIs and async job handling where needed
3. Build reports UI in team settings
4. Add end-to-end tests for artifact generation and download

---

## Definition Of Done

A reporting phase is done only when all of the following are true:
- Backend implementation is complete for both Firestore and DynamoDB paths
- Frontend implementation is complete for supported surfaces
- Backend and frontend automated tests pass locally
- Existing test suites still pass without regression
- GCP deployment succeeds via the repo deploy script
- Post-deploy smoke checks confirm the new endpoints and UI path work in the deployed environment
- Documentation is updated for any new environment variables, storage buckets, or operational cleanup rules

---

## Validation And Release Gate

Before any commit for reporting work:
- Run the full backend test suite
- Run the full frontend test suite
- Run targeted tests for any new reporting modules while iterating

Before considering the work ready:
- Deploy with the GCP deployment path
- Run a short smoke validation against the deployed service
- Confirm there are no new failures in existing check, channel, auth, or scheduler behavior

---

## Open Risks

- Retention mismatch: a 30-day TTL limits long-range uptime and trend reporting unless rollups are introduced
- Cost risk: storing large downloadable reports and polling for generation status needs expiry and cleanup discipline
- Data consistency risk: adding reporting fields requires both database adapters and API serializers to stay in sync
- UX risk: trying to make the check detail page do too much at once can make the page harder to scan; performance and errors should stay tabbed

---

## Recommendation

Implement reporting in the order above, keep this phase limited to downloadable reports, and treat the test matrix as mandatory scope rather than follow-up work. The fastest safe path is to land the data-model and aggregation foundation first, because every other reporting surface depends on it.
