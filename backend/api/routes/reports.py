"""
Historic Audit Reports API Router.
Exposes persisted forensic audit reports keyed by pipeline run_id, allowing
past verdicts and case files to be listed and reopened. Degrades gracefully
when DATABASE_URL is not configured (no persistent history available).
"""

import logging
import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from backend.core.config import settings
from backend.core.database import get_session_factory
from backend.models.estate import AuditReportRecord, HISTORIC_TABLE_MODELS
from backend.schemas.investigation import (
    AuditReportDetailResponse,
    AuditReportListResponse,
    AuditReportSummary,
)

logger = logging.getLogger("forensic_auditor.reports")

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "",
    response_model=AuditReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="List persisted audit reports",
    description="Paginated list of historic forensic audit reports ordered by archival date descending.",
)
async def list_audit_reports(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Reports per page (1-100)"),
    risk_level: Optional[str] = Query(default=None, description="Filter by verdict risk tier"),
    q: Optional[str] = Query(default=None, description="Search across run_id, company name, and RFC"),
):
    """
    Returns a paginated catalog of persisted audit reports. When the database
    is not configured, responds with an empty list and database_enabled=False
    instead of failing.
    """
    if not settings.DATABASE_URL:
        return AuditReportListResponse(
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            database_enabled=False,
            items=[],
        )

    clauses = []
    if risk_level:
        clauses.append(
            func.upper(AuditReportRecord.risk_level) == risk_level.strip().upper()
        )
    if q and q.strip():
        term = f"%{q.strip()}%"
        clauses.append(
            or_(
                AuditReportRecord.run_id.ilike(term),
                AuditReportRecord.company_name.ilike(term),
                AuditReportRecord.company_rfc.ilike(term),
            )
        )

    try:
        factory = get_session_factory()
        async with factory() as session:
            count_stmt = select(func.count()).select_from(AuditReportRecord)
            if clauses:
                count_stmt = count_stmt.where(*clauses)
            total = (await session.execute(count_stmt)).scalar() or 0

            rows_stmt = (
                select(AuditReportRecord)
                .order_by(AuditReportRecord.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            if clauses:
                rows_stmt = rows_stmt.where(*clauses)
            rows = (await session.execute(rows_stmt)).scalars().all()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Could not list audit reports: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit report storage is unavailable.",
        )

    return AuditReportListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
        database_enabled=True,
        items=[AuditReportSummary.model_validate(r) for r in rows],
    )


@router.get(
    "/{run_id}",
    response_model=AuditReportDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a persisted audit report",
    description="Returns the full submission payload, rendered Markdown case file, terminal verdict, and archived row counts for the given run_id.",
)
async def get_audit_report(run_id: str):
    """
    Retrieves a single persisted audit report by its pipeline run_id, including
    the per-table record counts archived under that run in the historic estate
    tables.
    """
    if not settings.DATABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is not configured; audit history is unavailable.",
        )

    try:
        factory = get_session_factory()
        async with factory() as session:
            record = (
                await session.execute(
                    select(AuditReportRecord).where(
                        AuditReportRecord.run_id == run_id
                    )
                )
            ).scalar_one_or_none()

            if record is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Audit report '{run_id}' not found.",
                )

            record_counts = {}
            for tbl_name, model_cls in HISTORIC_TABLE_MODELS.items():
                try:
                    count = (
                        await session.execute(
                            select(func.count())
                            .select_from(model_cls)
                            .where(model_cls.run_id == run_id)
                        )
                    ).scalar() or 0
                    record_counts[tbl_name] = count
                except Exception as count_err:
                    logger.warning(f"Could not count {tbl_name} for {run_id}: {count_err}")
                    record_counts[tbl_name] = 0
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Could not retrieve audit report {run_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit report storage is unavailable.",
        )

    detail = AuditReportDetailResponse.model_validate(record)
    detail.record_counts = record_counts
    return detail
