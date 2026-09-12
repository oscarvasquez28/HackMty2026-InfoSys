"""
Tests for the /api/v1/investigations/audit-estate endpoint.
"""

from decimal import Decimal
from pathlib import Path
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.estate import EfosRecord, InvoiceRecord, VendorRecord
from backend.services.estate_connector import EstateConnector


@pytest.mark.asyncio
async def test_audit_estate_endpoint():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "api_test_estate.db"
        connector = EstateConnector()

        await connector.init_schema(db_path)
        async with connector.session_scope(db_path) as session:
            # Seed a simple phantom vendor
            session.add(VendorRecord(
                rfc="PHANTOM001",
                legal_name="Phantom Inc",
                registered_date="2025-01-01",
                address="Calle Falsa 123",
                bank_clabe="000000000000000001",
                category="Servicios",
            ))
            session.add(EfosRecord(
                rfc="PHANTOM001",
                legal_name="Phantom Inc",
                status="definitivo",
                publication_date="2025-02-01",
            ))
            session.add(InvoiceRecord(
                uuid="INV-API-001",
                issuer_rfc="PHANTOM001",
                receiver_rfc="EMPRESA_AUDITADA",
                issue_date="2026-01-10",
                subtotal=Decimal("50000.00"),
                iva=Decimal("8000.00"),
                total=Decimal("58000.00"),
                concepto_text="Asesoria tecnica ficticia",
                status="vigente",
            ))
            await session.commit()
        await connector.dispose_all()

        # Call FastAPI endpoint via ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {
                "estate_path": str(db_path),
                "seed": 42,
                "company_name": "Empresa Auditada Test",
            }
            resp = await ac.post("/api/v1/investigations/audit-estate", json=payload)
            assert resp.status_code == 200, f"API failed: {resp.text}"
            data = resp.json()
            assert data["status"] == "COMPLETED"
            assert data["seed"] == 42
            assert len(data["findings"]) >= 1
            assert "## 1. Header" in data["case_file_markdown"]
            assert "## 2. Executive summary" in data["case_file_markdown"]
            assert data["validation_passed"] is True
