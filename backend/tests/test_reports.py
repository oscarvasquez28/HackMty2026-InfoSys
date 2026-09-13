"""
Tests for the historic audit reports layer:
- EstateSyncService.persist_audit_report persistence into audit_reports.
- GET /api/v1/reports paginated listing.
- GET /api/v1/reports/{run_id} detail retrieval.
- Graceful degradation when DATABASE_URL is not configured.
"""

import contextlib
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from backend.api.routes.investigations import INVESTIGATION_CASES
from backend.core.config import settings
from backend.core.database import close_db, get_session_factory, init_db
from backend.main import app
from backend.models.estate import AuditReportRecord, VendorHistoryRecord
from backend.services.estate_sync import estate_sync_service


SAMPLE_SUBMISSION = {
    "seed": 42,
    "findings": [
        {
            "finding_id": "FINDING-001",
            "scheme_type": "phantom_vendor",
            "entities": ["RFC:PHANTOM001"],
            "peso_amount": 58000.0,
        }
    ],
    "leads_not_pursued": [
        {"entity": "RFC:LEGIT001", "signal": "threshold_splitting", "reason": "closed"}
    ],
    "run_metadata": {
        "run_id": "RUN-20260101000000-TESTID01",
        "llm_calls": 0,
        "mxn_cost": 0.0,
        "wall_clock_seconds": 1.234,
        "deterministic": True,
    },
    "header": {"company": "Audited Company Test", "company_rfc": "AUD990101XYZ"},
}

SAMPLE_VERDICT = {
    "case_id": "ESTATE-42",
    "run_id": "RUN-20260101000000-TESTID01",
    "risk_level": "CRITICAL",
    "total_amount_mxn": 58000.0,
    "completed_at": "2026-01-01T00:00:00+00:00",
}


@contextlib.asynccontextmanager
async def isolated_test_db():
    """
    Configures an isolated in-memory SQLite database, provisions the schema
    (including audit_reports and historic tables), and cleans up on exit.
    """
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    await init_db()
    INVESTIGATION_CASES.clear()
    try:
        yield
    finally:
        await close_db()
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()


@pytest.mark.asyncio
async def test_persist_and_retrieve_audit_report():
    """
    Persisting a completed audit report stores an AuditReportRecord keyed by
    run_id, and the /reports endpoints expose it in list and detail views.
    """
    async with isolated_test_db():
        # Seed one historic row so record_counts reflects the archive
        factory = get_session_factory()
        async with factory() as session:
            session.add(
                VendorHistoryRecord(
                    run_id="RUN-20260101000000-TESTID01",
                    rfc="PHANTOM001",
                    legal_name="Phantom Inc",
                )
            )
            await session.commit()

        persisted = await estate_sync_service.persist_audit_report(
            submission=SAMPLE_SUBMISSION,
            case_file_markdown="## 1. Header\nTest case file",
            verdict=SAMPLE_VERDICT,
            company_name="Audited Company Test",
            company_rfc="AUD990101XYZ",
            estate_source="tmp/test_estate.db",
        )
        assert persisted is True

        async with factory() as session:
            row = (
                await session.execute(
                    select(AuditReportRecord).where(
                        AuditReportRecord.run_id == "RUN-20260101000000-TESTID01"
                    )
                )
            ).scalar_one_or_none()
            assert row is not None
            assert row.seed == 42
            assert row.risk_level == "CRITICAL"
            assert row.total_amount_mxn == Decimal("58000")
            assert row.findings_count == 1
            assert row.leads_count == 1
            assert row.report["findings"][0]["scheme_type"] == "phantom_vendor"

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            list_resp = await client.get("/api/v1/reports")
            assert list_resp.status_code == 200
            listing = list_resp.json()
            assert listing["database_enabled"] is True
            assert listing["total"] == 1
            assert listing["items"][0]["run_id"] == "RUN-20260101000000-TESTID01"
            assert listing["items"][0]["risk_level"] == "CRITICAL"
            assert listing["items"][0]["findings_count"] == 1

            detail_resp = await client.get(
                "/api/v1/reports/RUN-20260101000000-TESTID01"
            )
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            assert detail["run_id"] == "RUN-20260101000000-TESTID01"
            assert detail["report"]["seed"] == 42
            assert detail["case_file_markdown"].startswith("## 1. Header")
            assert detail["verdict"]["risk_level"] == "CRITICAL"
            assert detail["record_counts"]["vendors_history"] == 1


@pytest.mark.asyncio
async def test_get_audit_report_not_found():
    """Requesting a non-existent run_id returns 404."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/v1/reports/RUN-DOES-NOT-EXIST")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reports_degrade_gracefully_without_database():
    """
    Without DATABASE_URL the reports endpoints degrade instead of failing:
    list returns an empty catalog flagged database_enabled=False, and
    persist_audit_report no-ops.
    """
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = None
    try:
        persisted = await estate_sync_service.persist_audit_report(
            submission=SAMPLE_SUBMISSION,
            case_file_markdown="",
            verdict=SAMPLE_VERDICT,
        )
        assert persisted is False

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            list_resp = await client.get("/api/v1/reports")
            assert list_resp.status_code == 200
            listing = list_resp.json()
            assert listing["database_enabled"] is False
            assert listing["items"] == []

            detail_resp = await client.get("/api/v1/reports/RUN-ANYTHING")
            assert detail_resp.status_code == 503
    finally:
        settings.DATABASE_URL = original_db_url
