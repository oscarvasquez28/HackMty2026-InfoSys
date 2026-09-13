"""
Tests for database tools API endpoints.
Verifies table catalog, dedicated table readers, filtering, record lookups,
and exhibit insertion into the database exhibits table.
"""

from decimal import Decimal
from pathlib import Path
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.estate import ContractRecord, EfosRecord, InvoiceRecord, VendorRecord
from backend.services.estate_connector import EstateConnector, estate_connector


@pytest.mark.asyncio
async def test_database_tools_endpoints():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_tools_estate.db"
        connector = EstateConnector()

        # Initialize schema and seed sample data
        await connector.init_schema(db_path)
        async with connector.session_scope(db_path) as session:
            session.add(VendorRecord(
                rfc="TESTVENDOR01",
                legal_name="Test Supplies SA de CV",
                bank_clabe="123456789012345678",
                category="Logistica",
            ))
            session.add(EfosRecord(
                rfc="TESTVENDOR01",
                legal_name="Test Supplies SA de CV",
                status="definitivo",
                publication_date="2025-01-01",
            ))
            session.add(ContractRecord(
                contract_id="CNT-TEST-001",
                vendor_rfc="TESTVENDOR01",
                start_date="2025-01-15",
                value=Decimal("150000.00"),
                scope_text="Contrato de servicios logisticos",
            ))
            session.add(InvoiceRecord(
                uuid="INV-UUID-9999",
                issuer_rfc="TESTVENDOR01",
                receiver_rfc="EMPRESA_AUDITADA",
                issue_date="2025-02-01",
                subtotal=Decimal("150000.00"),
                total=Decimal("174000.00"),
                concepto_text="Servicios logisticos fehacientes",
                status="vigente",
            ))
            await session.commit()
        await connector.dispose_all()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            estate_query = f"estate_path={db_path.as_posix()}"

            # 1. Test tables catalog
            r_tables = await ac.get(f"/api/v1/database/tables?{estate_query}")
            assert r_tables.status_code == 200, r_tables.text
            tables_data = r_tables.json()
            table_names = [t["table_name"] for t in tables_data["tables"]]
            assert "vendors" in table_names
            assert "invoices" in table_names
            assert "contracts" in table_names
            assert "efos_list" in table_names
            assert "exhibits" in table_names

            # 2. Test dedicated vendors endpoint
            r_vendors = await ac.get(f"/api/v1/database/vendors?{estate_query}&rfc=TESTVENDOR01")
            assert r_vendors.status_code == 200, r_vendors.text
            v_data = r_vendors.json()
            assert v_data["total"] == 1
            assert v_data["records"][0]["legal_name"] == "Test Supplies SA de CV"
            assert v_data["records"][0]["evidence_citation"]["record_id"] == "TESTVENDOR01"

            # 3. Test contracts endpoint with filter
            r_contracts = await ac.get(f"/api/v1/database/contracts?{estate_query}&vendor_rfc=TESTVENDOR01")
            assert r_contracts.status_code == 200, r_contracts.text
            c_data = r_contracts.json()
            assert c_data["total"] == 1
            assert c_data["records"][0]["contract_id"] == "CNT-TEST-001"
            assert c_data["records"][0]["value"] == 150000.00

            # 4. Test direct record lookup by ID
            r_single = await ac.get(f"/api/v1/database/contracts/CNT-TEST-001?{estate_query}")
            assert r_single.status_code == 200, r_single.text
            assert r_single.json()["contract_id"] == "CNT-TEST-001"

            # 5. Test inserting an exhibit into exhibits table
            ex_payload = {
                "estate_path": str(db_path),
                "exhibit_id": "EX-ADV-9001",
                "source_table": "contracts",
                "record_id": "CNT-TEST-001",
                "sentence": "Contrato formal debidamente registrado desvirtua presuncion de inexistencia.",
            }
            r_ex_create = await ac.post("/api/v1/database/exhibits", json=ex_payload)
            assert r_ex_create.status_code == 201, r_ex_create.text
            ex_res = r_ex_create.json()
            assert ex_res["status"] == "INSERTED"
            assert ex_res["exhibit_id"] == "EX-ADV-9001"
            assert ex_res["verified"] is True

            # 6. Verify exhibit is readable in exhibits table
            r_ex_query = await ac.get(f"/api/v1/database/exhibits?{estate_query}&exhibit_id=EX-ADV-9001")
            assert r_ex_query.status_code == 200
            assert r_ex_query.json()["total"] == 1
            assert r_ex_query.json()["records"][0]["source_table"] == "contracts"
            assert r_ex_query.json()["records"][0]["record_id"] == "CNT-TEST-001"

            # 7. Test alias under /tools/database
            r_alias = await ac.get(f"/api/v1/tools/database/vendors?{estate_query}")
            assert r_alias.status_code == 200
            assert r_alias.json()["total"] == 1

        await estate_connector.dispose_all()
