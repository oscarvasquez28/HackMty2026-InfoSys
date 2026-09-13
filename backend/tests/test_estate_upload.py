"""
Tests for the /api/v1/estates/upload endpoint.
"""

from decimal import Decimal
from pathlib import Path
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.estate import EfosRecord, InvoiceRecord, VendorRecord
from backend.services.estate_connector import EstateConnector, estate_connector


@pytest.mark.asyncio
async def test_estate_upload_and_audit():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_upload_estate.db"
        connector = EstateConnector()

        await connector.init_schema(db_path)
        async with connector.session_scope(db_path) as session:
            session.add(VendorRecord(
                rfc="PHANTOM_UP_01",
                legal_name="Upload Phantom Corp",
                registered_date="2025-01-01",
                address="Av. Falsa 456",
                bank_clabe="000000000000000099",
                category="Servicios",
            ))
            session.add(EfosRecord(
                rfc="PHANTOM_UP_01",
                legal_name="Upload Phantom Corp",
                status="definitivo",
                publication_date="2025-02-01",
            ))
            session.add(InvoiceRecord(
                uuid="INV-UP-001",
                issuer_rfc="PHANTOM_UP_01",
                receiver_rfc="EMPRESA_AUDITADA",
                issue_date="2026-01-10",
                subtotal=Decimal("80000.00"),
                iva=Decimal("12800.00"),
                total=Decimal("92800.00"),
                concepto_text="Asesoria tecnica ficticia",
                status="vigente",
            ))
            await session.commit()
        await connector.dispose_all()

        db_bytes = db_path.read_bytes()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Upload without immediate audit
            files = {"file": ("estate.db", db_bytes, "application/vnd.sqlite3")}
            data = {"seed": "1", "company_name": "Empresa Auditada Test", "audit": "false"}
            resp = await ac.post("/api/v1/estates/upload", files=files, data=data)
            assert resp.status_code == 200, f"Upload failed: {resp.text}"
            res_json = resp.json()
            assert res_json["status"] == "READY"
            assert "estate_path" in res_json

            # 2. Upload with immediate audit
            files2 = {"file": ("estate.db", db_bytes, "application/vnd.sqlite3")}
            data2 = {"seed": "1", "company_name": "Empresa Auditada Test", "audit": "true"}
            resp2 = await ac.post("/api/v1/estates/upload", files=files2, data=data2)
            assert resp2.status_code == 200, f"Audit failed: {resp2.text}"
            audit_json = resp2.json()
            assert audit_json["status"] == "COMPLETED"
            assert len(audit_json["findings"]) >= 1
            assert "submission" in audit_json
            assert "header" in audit_json

        await estate_connector.dispose_all()
