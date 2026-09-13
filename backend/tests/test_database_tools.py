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


@pytest.mark.asyncio
async def test_database_tools_post_endpoints():
    """
    Verifies that all database tools endpoints accept HTTP POST requests,
    receiving parameters from the JSON request body rather than URL query parameters.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_tools_post_estate.db"
        connector = EstateConnector()

        # Initialize schema and seed sample data across financial estate tables
        await connector.init_schema(db_path)
        from backend.models.estate import (
            BankTxnRecord,
            EmployeeRecord,
            LedgerRecord,
            PurchaseOrderRecord,
        )

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
            session.add(LedgerRecord(
                entry_id=101,
                date="2025-02-01",
                account_code="601-01",
                account_name="Gastos Operativos",
                debit=Decimal("150000.00"),
                credit=Decimal("0.00"),
                description="Gasto en logistica",
                invoice_uuid="INV-UUID-9999",
                approver="LIC_GONZALEZ",
            ))
            session.add(BankTxnRecord(
                txn_id="TXN-SPEI-001",
                date="2025-02-02",
                from_clabe="012180000000000001",
                to_clabe="123456789012345678",
                amount=Decimal("174000.00"),
                reference="PAGO_INV_9999",
                channel="SPEI",
            ))
            session.add(PurchaseOrderRecord(
                po_id="PO-TEST-001",
                vendor_rfc="TESTVENDOR01",
                date="2025-01-10",
                amount=Decimal("150000.00"),
                requester="DIR_OPERACIONES",
                approver="LIC_GONZALEZ",
                description="Orden de compra servicios de transportacion",
            ))
            session.add(EmployeeRecord(
                emp_id="EMP-001",
                name="Lic. Roberto Gonzalez",
                role="Director de Adquisiciones",
                bank_clabe="012180000000000099",
                hire_date="2020-03-01",
            ))
            await session.commit()
        await connector.dispose_all()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            estate_str = str(db_path)

            # 1. POST /tables
            r_tables = await ac.post("/api/v1/database/tables", json={"estate_path": estate_str})
            assert r_tables.status_code == 200, r_tables.text
            t_names = [t["table_name"] for t in r_tables.json()["tables"]]
            assert "vendors" in t_names
            assert "invoices" in t_names
            assert "contracts" in t_names

            # 2. POST /vendors
            r_vendors = await ac.post("/api/v1/database/vendors", json={
                "estate_path": estate_str,
                "rfc": "TESTVENDOR01",
            })
            assert r_vendors.status_code == 200, r_vendors.text
            v_data = r_vendors.json()
            assert v_data["total"] == 1
            assert v_data["records"][0]["rfc"] == "TESTVENDOR01"

            # 3. POST /invoices
            r_invoices = await ac.post("/api/v1/database/invoices", json={
                "estate_path": estate_str,
                "min_amount": 100000.0,
            })
            assert r_invoices.status_code == 200, r_invoices.text
            i_data = r_invoices.json()
            assert i_data["total"] == 1
            assert i_data["records"][0]["uuid"] == "INV-UUID-9999"

            # 4. POST /ledger
            r_ledger = await ac.post("/api/v1/database/ledger", json={
                "estate_path": estate_str,
                "account_code": "601-01",
            })
            assert r_ledger.status_code == 200, r_ledger.text
            l_data = r_ledger.json()
            assert l_data["total"] == 1
            assert l_data["records"][0]["entry_id"] == 101

            # 5. POST /bank_txns
            r_txns = await ac.post("/api/v1/database/bank_txns", json={
                "estate_path": estate_str,
                "txn_id": "TXN-SPEI-001",
            })
            assert r_txns.status_code == 200, r_txns.text
            tx_data = r_txns.json()
            assert tx_data["total"] == 1
            assert tx_data["records"][0]["txn_id"] == "TXN-SPEI-001"

            # 6. POST /purchase_orders
            r_pos = await ac.post("/api/v1/database/purchase_orders", json={
                "estate_path": estate_str,
                "po_id": "PO-TEST-001",
            })
            assert r_pos.status_code == 200, r_pos.text
            po_data = r_pos.json()
            assert po_data["total"] == 1
            assert po_data["records"][0]["po_id"] == "PO-TEST-001"

            # 7. POST /contracts
            r_contracts = await ac.post("/api/v1/database/contracts", json={
                "estate_path": estate_str,
                "vendor_rfc": "TESTVENDOR01",
            })
            assert r_contracts.status_code == 200, r_contracts.text
            c_data = r_contracts.json()
            assert c_data["total"] == 1
            assert c_data["records"][0]["contract_id"] == "CNT-TEST-001"

            # 8. POST /employees
            r_employees = await ac.post("/api/v1/database/employees", json={
                "estate_path": estate_str,
                "emp_id": "EMP-001",
            })
            assert r_employees.status_code == 200, r_employees.text
            emp_data = r_employees.json()
            assert emp_data["total"] == 1
            assert emp_data["records"][0]["emp_id"] == "EMP-001"

            # 9. POST /efos_list
            r_efos = await ac.post("/api/v1/database/efos_list", json={
                "estate_path": estate_str,
                "rfc": "TESTVENDOR01",
            })
            assert r_efos.status_code == 200, r_efos.text
            efos_data = r_efos.json()
            assert efos_data["total"] == 1
            assert efos_data["records"][0]["rfc"] == "TESTVENDOR01"

            # 10. POST single record lookup: /{table_name}/{record_id}
            r_single_post = await ac.post(f"/api/v1/database/contracts/CNT-TEST-001", json={
                "estate_path": estate_str,
            })
            assert r_single_post.status_code == 200, r_single_post.text
            assert r_single_post.json()["contract_id"] == "CNT-TEST-001"

            # 11. POST single record lookup via /record body
            r_record_post = await ac.post("/api/v1/database/record", json={
                "table_name": "contracts",
                "record_id": "CNT-TEST-001",
                "estate_path": estate_str,
            })
            assert r_record_post.status_code == 200, r_record_post.text
            assert r_record_post.json()["contract_id"] == "CNT-TEST-001"

            # 12. POST dynamic table query: /query
            r_dyn_query = await ac.post("/api/v1/database/query", json={
                "table_name": "invoices",
                "estate_path": estate_str,
                "limit": 10,
            })
            assert r_dyn_query.status_code == 200, r_dyn_query.text
            assert r_dyn_query.json()["total"] == 1

            # 13. POST generic table route: /{table_name}
            r_gen_table = await ac.post("/api/v1/database/vendors", json={
                "estate_path": estate_str,
                "limit": 5,
            })
            assert r_gen_table.status_code == 200, r_gen_table.text
            assert r_gen_table.json()["total"] == 1

            # 14. POST exhibits creation (sentence present -> 201)
            ex_payload = {
                "estate_path": estate_str,
                "exhibit_id": "EX-POST-001",
                "source_table": "contracts",
                "record_id": "CNT-TEST-001",
                "sentence": "Contrato de servicios validado mediante POST.",
            }
            r_create = await ac.post("/api/v1/database/exhibits", json=ex_payload)
            assert r_create.status_code == 201, r_create.text
            assert r_create.json()["status"] == "INSERTED"

            # 15. POST exhibits query (sentence omitted -> 200)
            r_query_ex = await ac.post("/api/v1/database/exhibits", json={
                "estate_path": estate_str,
                "exhibit_id": "EX-POST-001",
            })
            assert r_query_ex.status_code == 200, r_query_ex.text
            assert r_query_ex.json()["total"] == 1
            assert r_query_ex.json()["records"][0]["exhibit_id"] == "EX-POST-001"

            # 16. POST /exhibits/query dedicated route
            r_ex_query_route = await ac.post("/api/v1/database/exhibits/query", json={
                "estate_path": estate_str,
                "exhibit_id": "EX-POST-001",
            })
            assert r_ex_query_route.status_code == 200, r_ex_query_route.text
            assert r_ex_query_route.json()["total"] == 1

            # 17. POST /exhibits/search dedicated route
            r_ex_search_route = await ac.post("/api/v1/database/exhibits/search", json={
                "estate_path": estate_str,
                "q": "validado",
            })
            assert r_ex_search_route.status_code == 200, r_ex_search_route.text
            assert r_ex_search_route.json()["total"] == 1

            # 18. POST alias prefix /tools/database/vendors
            r_alias_post = await ac.post("/api/v1/tools/database/vendors", json={
                "estate_path": estate_str,
                "rfc": "TESTVENDOR01",
            })
            assert r_alias_post.status_code == 200, r_alias_post.text
            assert r_alias_post.json()["total"] == 1

        await connector.dispose_all()
        await estate_connector.dispose_all()
