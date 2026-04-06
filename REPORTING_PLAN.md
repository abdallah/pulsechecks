# PulseChecks - Detailed Reporting: Implementation Plan

## Overview

Four reporting features:
1. **Response Time Graphs** - historical latency charts for HTTP checks
2. **Detailed Error Logs** - per-check error summaries + individual event log
3. **Uptime Reports** - uptime % for any time range, with maintenance exclusions
4. **Emailed Reports** - daily/weekly/monthly outage summaries

---

## Current State Assessment

### What we have
- `Ping` entity stores: `check_id`, `timestamp`, `received_at`, `ping_type` (success/fail/start), `code`, `data`
- Firestore stores up to 20 pings per check (frontend fetches latest 20)
- HTTP scheduler (`scheduler.py`) polls checks but **does not record response time**
- No aggregation layer - all reporting would be computed on-the-fly from raw pings

### What's missing
- `response_time_ms` field on Ping (HTTP checks only)
- Historical ping storage beyond latest 20 (Firestore has no limit - backend just fetches 20)
- Aggregated uptime/error statistics (no pre-computed summaries)
- Maintenance window entity
- Email delivery integration
- Report schedule entity (per-check or per-team preferences)

---

## Feature 1: Response Time Graphs

### Goal
Show a time-series graph of HTTP response times for any check, filterable by time range (last 24h / 7d / 30d).

### Backend changes

**1. Add `response_time_ms` to Ping model** (`models/entities.py`)
```python
response_time_ms: Optional[int] = None  # HTTP checks only
```

**2. Record response time in scheduler** (`scheduler.py`)
```python
import time
start = time.monotonic()
resp = await client.get(check.url)
response_time_ms = int((time.monotonic() - start) * 1000)
# Store on ping
```

**3. Increase ping history limit**
- Current: `list_pings` fetches last 20
- Change: fetch up to 1000 (30 days at 1/min = 43,200; realistically most checks run hourly = ~720)
- Add `since` filter to Firestore query (already exists in API, just increase limit)
- Add `GET /teams/{team_id}/checks/{check_id}/pings?since=<iso>&limit=1000`

**4. New aggregation endpoint**
```
GET /teams/{team_id}/checks/{check_id}/stats?range=24h|7d|30d
```
Returns:
```json
{
  "period": "7d",
  "uptime_pct": 99.7,
  "total_pings": 168,
  "success_count": 167,
  "fail_count": 1,
  "avg_response_ms": 234,
  "p95_response_ms": 412,
  "max_response_ms": 1203,
  "min_response_ms": 187,
  "response_time_series": [
    { "timestamp": "2026-04-01T10:00:00Z", "response_ms": 201 },
    ...
  ]
}
```

### Frontend changes
- New tab/section on `CheckDetailPage`: **"Performance"**
- Line chart using **Recharts** (already in most React stacks; if not, lightweight `react-charts` or plain SVG)
- Time range selector: 24h / 7d / 30d
- Show: response time line + status overlay (red bands for failures)
- Tooltip on hover showing exact ms + timestamp

### Data retention
- Firestore pings: keep indefinitely (Firestore has no TTL by default)
- Add optional daily cleanup cron for pings older than 90 days (configurable)

---

## Feature 2: Detailed Error Logs

### Goal
Two views:
- **Summary**: counts by error type, most frequent errors, last occurrence
- **Log**: paginated list of individual failure events with full details

### Backend changes

**1. Enhanced ping query endpoint**
```
GET /teams/{team_id}/checks/{check_id}/pings?type=fail&since=<iso>&limit=50&page_token=<cursor>
```
- Filter by `ping_type=fail`
- Return `code`, `data`, `response_time_ms`, `received_at`
- Cursor-based pagination (Firestore `start_after`)

**2. Error summary endpoint**
```
GET /teams/{team_id}/checks/{check_id}/errors/summary?range=7d
```
Returns:
```json
{
  "total_errors": 14,
  "by_code": {
    "timeout": 8,
    "503": 4,
    "unexpected_response": 2
  },
  "first_error_at": "2026-03-30T14:22:00Z",
  "last_error_at": "2026-04-06T09:11:00Z",
  "longest_outage_minutes": 47,
  "recent_errors": [...]
}
```

**3. Team-level error summary**
```
GET /teams/{team_id}/errors/summary?range=7d
```
Aggregates across all checks in a team - useful for dashboard overview.

### Frontend changes
- New tab on `CheckDetailPage`: **"Errors"**
- Summary card at top: total errors, most common code, longest outage
- Filterable table: date | check | error code | details | duration
- Pagination
- CSV export button (generate client-side from fetched data)

---

## Feature 3: Uptime Reports

### Goal
Show uptime % for a user-specified date range. Allow marking maintenance windows so those periods don't count as downtime.

### Backend changes

**1. New `MaintenanceWindow` entity** (`models/entities.py`)
```python
class MaintenanceWindow(BaseModel):
    window_id: str
    check_id: str          # or None for team-wide
    team_id: str
    start_at: str          # ISO timestamp
    end_at: str
    label: Optional[str]   # e.g. "Scheduled DB migration"
    created_by: str
```

**2. Maintenance window CRUD**
```
POST   /teams/{team_id}/maintenance
GET    /teams/{team_id}/maintenance?check_id=<id>
DELETE /teams/{team_id}/maintenance/{window_id}
```

**3. Uptime calculation endpoint**
```
GET /teams/{team_id}/checks/{check_id}/uptime?from=<iso>&to=<iso>&exclude_maintenance=true
```
Returns:
```json
{
  "from": "2026-03-01T00:00:00Z",
  "to": "2026-04-06T23:59:59Z",
  "uptime_pct": 99.82,
  "total_minutes": 53280,
  "downtime_minutes": 95,
  "maintenance_excluded_minutes": 120,
  "incidents": [
    {
      "started_at": "2026-03-15T04:12:00Z",
      "resolved_at": "2026-03-15T05:47:00Z",
      "duration_minutes": 95,
      "cause": "Connection timeout"
    }
  ]
}
```

**Calculation logic:**
- Reconstruct downtime from ping history
- A "downtime" period = from the last successful ping before a failure to the first successful ping after
- Subtract any maintenance windows that overlap the downtime period

### Frontend changes
- New page: **"Uptime Report"** (`/teams/{id}/uptime`)
- Date range picker (from/to)
- Big uptime % display (green/amber/red based on thresholds)
- Incident table: start | end | duration | cause
- Maintenance window management (add/remove)
- "Export PDF" / "Copy link" for sharing SLA reports

---

## Feature 4: Downloadable Reports

### Goal
Generate reports on demand and return a URL to download them. No email delivery - user requests a report, gets a link.

### Backend changes

**1. New `Report` entity**
```python
class Report(BaseModel):
    report_id: str
    team_id: str
    check_id: Optional[str]     # None = team-wide report
    report_type: str            # uptime | errors | performance | summary
    format: str                 # json | csv | pdf
    from_date: str              # ISO date
    to_date: str                # ISO date
    status: str                 # generating | ready | failed
    download_url: Optional[str] # signed GCS URL, expires in 24h
    created_at: str
    created_by: str
    expires_at: str             # when the file + record are cleaned up
```

**2. Report generation endpoints**
```
POST /teams/{team_id}/reports
  Body: { type, format, from, to, check_id? }
  → Returns report_id + status=generating (or status=ready if fast enough)

GET  /teams/{team_id}/reports/{report_id}
  → Returns status + download_url when ready

GET  /teams/{team_id}/reports
  → Lists recent reports (last 30 days)

DELETE /teams/{team_id}/reports/{report_id}
  → Delete report + GCS file
```

**3. Report generation function** (`reports.py`)

For each report type:
- **Uptime report**: computes uptime %, incident list, maintenance exclusions → CSV or JSON
- **Error log**: filtered fail pings with codes + details → CSV
- **Performance report**: response time series, p50/p95/max per day → CSV
- **Summary report**: all of the above combined → JSON (renderable as a shareable page)

Generation is synchronous for small ranges (≤7 days). For larger ranges, generate in background and poll.

**4. Storage**
- **GCP**: Generate file → upload to GCS → return signed URL (24h expiry)
- **AWS**: Generate file → upload to S3 → return presigned URL (24h expiry)
- Files cleaned up by a daily cron after expiry

**5. Report formats**
- **JSON**: machine-readable, can be consumed by other tools
- **CSV**: spreadsheet-friendly, easy to open in Excel/Sheets
- **PDF**: human-friendly summary page (use WeasyPrint in Cloud Run - no headless Chrome needed)

### Frontend changes
- **"Reports" tab** on team settings page
- Form: report type | time range | check(s) | format
- On submit: show progress spinner → "Download" button when ready
- List of recently generated reports with re-download links
- Report expires badge ("Expires in 23h")

### Example flow
```
1. User selects: Uptime Report | Last 30 days | All checks | CSV
2. POST /teams/xxx/reports → { report_id: "r-abc", status: "generating" }
3. Frontend polls GET /teams/xxx/reports/r-abc every 2s
4. status → "ready", download_url → "https://storage.googleapis.com/..."
5. Browser opens the signed URL → file downloads directly
```

---

## Implementation Order

### Phase 1 - Data foundation (prerequisite for everything else)
1. Add `response_time_ms` to `Ping` model + Firestore schema
2. Record response time in HTTP scheduler
3. Increase ping fetch limit + add `since`/`type` filters
4. New `/stats` aggregation endpoint
5. Tests

### Phase 2 - Response Time Graphs (highest user value, self-contained)
1. Install Recharts in frontend
2. `PerformanceTab` component on CheckDetailPage
3. Time range selector
4. Line chart with failure overlays

### Phase 3 - Error Logs
1. Enhanced ping query (filter by type, pagination)
2. Error summary endpoint
3. `ErrorsTab` component + table + CSV export

### Phase 4 - Uptime Reports
1. `MaintenanceWindow` entity + CRUD
2. Uptime calculation endpoint
3. Uptime Report page + date range picker
4. Maintenance window UI

### Phase 5 — Downloadable Reports
1. `Report` entity + CRUD endpoints
2. Report generators: uptime, errors, performance, summary (JSON + CSV)
3. GCS signed URL upload + expiry cleanup cron
4. PDF generation via WeasyPrint
5. Reports UI: form + progress polling + download list

---

## Open Questions / Decisions Needed

1. **Ping retention**: How long to keep raw ping data?
   - 90 days is a good default
   - Could make it configurable per team

2. **Response time for non-HTTP checks**: Heartbeat/cron checks don’t have server-side response times. Show ping interval regularity instead (time between pings vs expected period).

3. **Uptime SLA thresholds**: What % triggers amber vs red?
   - Suggestion: ≥99.9% green, ≥99% amber, <99% red

4. **Report granularity**: For 30-day charts, should we aggregate to hourly data points or keep per-ping resolution?
   - Per-ping for ≤7 days
   - Hourly averages for 7–30 days
   - Daily averages for 30–90 days

5. **Report expiry**: How long should generated files be available?
   - 24h is a safe default (signed URLs are temporary by nature)
   - Could offer 7-day retention for team admins

---

## Estimated Effort

| Phase | Backend | Frontend | Tests | Total |
|-------|---------|----------|-------|-------|
| 1 - Data foundation | 2-3h | - | 1h | ~4h |
| 2 - Response Time Graphs | 1h | 2-3h | 1h | ~5h |
| 3 - Error Logs | 1h | 2h | 1h | ~4h |
| 4 - Uptime Reports | 3-4h | 3-4h | 2h | ~9h |
| 5 — Downloadable Reports | 3–4h | 2h | 1h | ~7h |
| **Total** | | | | **~29h** |

Realistic across 2-3 sessions.
