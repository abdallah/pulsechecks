"""Downloadable report endpoints."""
import csv
import json
from io import StringIO
from typing import List

from fastapi import APIRouter, Response

from ..config import get_settings
from ..dependencies import AuthUser, Database, check_team_access
from ..errors import NotFoundError, ValidationError
from ..models import CreateReportRequest, OkResponse, Permission, Report, ReportResponse
from ..routers.checks import (
    _build_check_error_summary_response,
    _build_check_stats_response,
    _build_check_uptime_response,
)
from ..utils import generate_id, get_iso_timestamp, parse_iso_timestamp

router = APIRouter(prefix="/teams/{team_id}/reports", tags=["reports"])

REPORT_TTL_SECONDS = 7 * 24 * 60 * 60


def _serialize_report(report: Report) -> ReportResponse:
    return ReportResponse(
        reportId=report.report_id,
        teamId=report.team_id,
        checkId=report.check_id,
        reportType=report.report_type,
        format=report.format,
        **{"from": report.from_date, "to": report.to_date},
        status=report.status,
        downloadUrl=report.download_url,
        createdAt=report.created_at,
        createdBy=report.created_by,
        expiresAt=report.expires_at,
        fileName=report.file_name,
        contentType=report.content_type,
    )


async def _resolve_checks(db: Database, team_id: str, check_id: str | None):
    if check_id:
        check = await db.get_check(team_id, check_id)
        if not check:
            raise NotFoundError("Check not found")
        return [check]
    return await db.list_team_checks(team_id)


async def _collect_check_dataset(db: Database, team_id: str, check, from_date: str, to_date: str) -> dict:
    pings = await db.list_check_pings_between(check.check_id, from_date, to_date)
    windows = await db.list_maintenance_windows(team_id, check.check_id)
    stats = _build_check_stats_response(pings, "custom").model_dump(by_alias=True)
    errors = _build_check_error_summary_response(pings, "custom").model_dump(by_alias=True)
    uptime = _build_check_uptime_response(check, pings, windows, from_date, to_date, True).model_dump(by_alias=True)
    return {
        "checkId": check.check_id,
        "name": check.name,
        "type": check.type,
        "status": check.status,
        "url": getattr(check, "url", None),
        "stats": stats,
        "errors": errors,
        "uptime": uptime,
    }


def _build_report_payload(report_type: str, scope: str, team_id: str, from_date: str, to_date: str, datasets: List[dict]) -> dict:
    checks = []
    for dataset in datasets:
        if report_type == "uptime":
            checks.append({
                "checkId": dataset["checkId"],
                "name": dataset["name"],
                "type": dataset["type"],
                "status": dataset["status"],
                "uptime": dataset["uptime"],
            })
        elif report_type == "errors":
            checks.append({
                "checkId": dataset["checkId"],
                "name": dataset["name"],
                "type": dataset["type"],
                "status": dataset["status"],
                "errors": dataset["errors"],
            })
        elif report_type == "performance":
            checks.append({
                "checkId": dataset["checkId"],
                "name": dataset["name"],
                "type": dataset["type"],
                "status": dataset["status"],
                "stats": dataset["stats"],
            })
        elif report_type == "summary":
            checks.append({
                "checkId": dataset["checkId"],
                "name": dataset["name"],
                "type": dataset["type"],
                "status": dataset["status"],
                "uptimePct": dataset["uptime"]["uptimePct"],
                "downtimeMinutes": dataset["uptime"]["downtimeMinutes"],
                "excludedMaintenanceMinutes": dataset["uptime"]["excludedMaintenanceMinutes"],
                "totalFailures": dataset["errors"]["totalFailures"],
                "mostCommonCode": dataset["errors"].get("mostCommonCode"),
                "avgResponseMs": dataset["stats"].get("avgResponseMs"),
                "p95ResponseMs": dataset["stats"].get("p95ResponseMs"),
                "latestResponseMs": dataset["stats"].get("latestResponseMs"),
            })
        else:
            raise ValidationError("Unsupported report type")

    return {
        "teamId": team_id,
        "scope": scope,
        "reportType": report_type,
        "from": from_date,
        "to": to_date,
        "checks": checks,
    }


def _report_rows(report_type: str, payload: dict) -> list[dict]:
    checks = payload["checks"]
    rows = []
    if report_type == "uptime":
        for entry in checks:
            uptime = entry["uptime"]
            rows.append({
                "check_id": entry["checkId"],
                "check_name": entry["name"],
                "check_type": entry["type"],
                "status": entry["status"],
                "uptime_pct": uptime["uptimePct"],
                "total_observed_minutes": uptime["totalObservedMinutes"],
                "downtime_minutes": uptime["downtimeMinutes"],
                "excluded_maintenance_minutes": uptime["excludedMaintenanceMinutes"],
                "incident_count": len(uptime["incidents"]),
            })
    elif report_type == "performance":
        for entry in checks:
            stats = entry["stats"]
            rows.append({
                "check_id": entry["checkId"],
                "check_name": entry["name"],
                "check_type": entry["type"],
                "status": entry["status"],
                "total_pings": stats["totalPings"],
                "success_count": stats["successCount"],
                "fail_count": stats["failCount"],
                "avg_response_ms": stats.get("avgResponseMs"),
                "p95_response_ms": stats.get("p95ResponseMs"),
                "latest_response_ms": stats.get("latestResponseMs"),
            })
    elif report_type == "errors":
        for entry in checks:
            errors = entry["errors"]
            failure_codes = errors.get("failureCodes") or [None]
            for code_row in failure_codes:
                rows.append({
                    "check_id": entry["checkId"],
                    "check_name": entry["name"],
                    "check_type": entry["type"],
                    "status": entry["status"],
                    "total_failures": errors["totalFailures"],
                    "most_common_code": errors.get("mostCommonCode"),
                    "last_failure_at": errors.get("lastFailureAt"),
                    "failure_code": code_row["code"] if code_row else None,
                    "failure_code_count": code_row["count"] if code_row else None,
                })
    elif report_type == "summary":
        rows.extend({
            "check_id": entry["checkId"],
            "check_name": entry["name"],
            "check_type": entry["type"],
            "status": entry["status"],
            "uptime_pct": entry["uptimePct"],
            "downtime_minutes": entry["downtimeMinutes"],
            "excluded_maintenance_minutes": entry["excludedMaintenanceMinutes"],
            "total_failures": entry["totalFailures"],
            "most_common_code": entry.get("mostCommonCode"),
            "avg_response_ms": entry.get("avgResponseMs"),
            "p95_response_ms": entry.get("p95ResponseMs"),
            "latest_response_ms": entry.get("latestResponseMs"),
        } for entry in checks)
    return rows


def _render_report_content(report_type: str, fmt: str, payload: dict) -> tuple[str, str]:
    if fmt == "json":
        return json.dumps(payload, indent=2), "application/json"

    rows = _report_rows(report_type, payload)
    stream = StringIO()
    fieldnames = list(rows[0].keys()) if rows else ["team_id", "report_type", "from", "to"]
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    if rows:
        writer.writerows(rows)
    else:
        writer.writerow({"team_id": payload["teamId"], "report_type": payload["reportType"], "from": payload["from"], "to": payload["to"]})
    return stream.getvalue(), "text/csv"


@router.post("", response_model=ReportResponse)
async def create_report(
    team_id: str,
    request: CreateReportRequest,
    current_user: AuthUser,
    db: Database,
) -> ReportResponse:
    """Generate and persist a downloadable report."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)

    checks = await _resolve_checks(db, team_id, request.check_id)
    datasets = [await _collect_check_dataset(db, team_id, check, request.from_date, request.to_date) for check in checks]
    payload = _build_report_payload(
        request.report_type,
        "check" if request.check_id else "team",
        team_id,
        request.from_date,
        request.to_date,
        datasets,
    )
    content, content_type = _render_report_content(request.report_type, request.format, payload)

    report_id = generate_id()
    created_at = get_iso_timestamp()
    expires_at = get_iso_timestamp(parse_iso_timestamp(created_at) + REPORT_TTL_SECONDS)
    file_name = f"{request.report_type}-report-{report_id}.{request.format}"
    report = Report(
        report_id=report_id,
        team_id=team_id,
        check_id=request.check_id,
        report_type=request.report_type,
        format=request.format,
        from_date=request.from_date,
        to_date=request.to_date,
        status="completed",
        download_url=f"/teams/{team_id}/reports/{report_id}/download",
        created_at=created_at,
        created_by=current_user.user_id,
        expires_at=expires_at,
        file_name=file_name,
        content_type=content_type,
        content=content,
    )
    await db.create_report(report)
    return _serialize_report(report)


@router.get("", response_model=List[ReportResponse])
async def list_reports(team_id: str, current_user: AuthUser, db: Database) -> List[ReportResponse]:
    """List generated reports for a team."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)
    reports = await db.list_reports(team_id)
    return [_serialize_report(report) for report in reports]


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(team_id: str, report_id: str, current_user: AuthUser, db: Database) -> ReportResponse:
    """Get report metadata."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)
    report = await db.get_report(team_id, report_id)
    if not report:
        raise NotFoundError("Report not found")
    return _serialize_report(report)


@router.get("/{report_id}/download")
async def download_report(team_id: str, report_id: str, current_user: AuthUser, db: Database) -> Response:
    """Download generated report content."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)
    report = await db.get_report(team_id, report_id)
    if not report or not report.content:
        raise NotFoundError("Report not found")
    if parse_iso_timestamp(report.expires_at) <= parse_iso_timestamp(get_iso_timestamp()):
        raise ValidationError("Report download has expired")

    headers = {
        "Content-Disposition": f'attachment; filename="{report.file_name or "report"}"'
    }
    return Response(content=report.content, media_type=report.content_type or "application/octet-stream", headers=headers)


@router.delete("/{report_id}", response_model=OkResponse)
async def delete_report(team_id: str, report_id: str, current_user: AuthUser, db: Database) -> OkResponse:
    """Delete a generated report."""
    await check_team_access(team_id, current_user, db, Permission.VIEW)
    await db.delete_report(team_id, report_id)
    return OkResponse(message="Report deleted")