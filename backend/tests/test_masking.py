"""
Tests for Data Masking and PII Redaction Engine.
Verifies that banking CLABEs, emails, phone numbers, and physical addresses
are properly masked when returned to agents and transmitted over the network.
"""

from decimal import Decimal
from pathlib import Path
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.masking import (
    mask_address,
    mask_clabe,
    mask_email,
    mask_free_text,
    mask_phone,
    mask_sensitive_payload,
    mask_sensitive_record,
    mask_ssn,
)
from backend.main import app
from backend.models.estate import BankTxnRecord, VendorRecord
from backend.services.estate_connector import EstateConnector, estate_connector


def test_masking_unit_functions():
    # 1. CLABE masking
    clabe = "012180012345678901"
    masked_c = mask_clabe(clabe)
    assert masked_c.startswith("0121")
    assert masked_c.endswith("8901")
    assert "*" in masked_c
    assert "0123456789" not in masked_c

    # 2. Email masking
    email = "informes@proveedorfantasma.com.mx"
    masked_e = mask_email(email)
    assert masked_e.startswith("i***s@")
    assert "@proveedorfantasma.com.mx" in masked_e

    # 3. Phone masking
    phone = "+52 55 1234 5678"
    masked_p = mask_phone(phone)
    assert masked_p == "******5678"

    # 4. Address masking
    addr = "Av. Insurgentes Sur 1602, Piso 4, Benito Juarez, CDMX"
    masked_a = mask_address(addr)
    assert "PROTEGIDA" in masked_a or "REDACTED" in masked_a

    # 5. Free text scanning
    text = "Transferencia a CLABE 012180012345678901 con contacto pagos@empresa.com"
    masked_t = mask_free_text(text)
    assert "0121**********8901" in masked_t
    assert "p***s@empresa.com" in masked_t


@pytest.mark.asyncio
async def test_database_endpoint_returns_masked_data():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_masking_estate.db"
        connector = EstateConnector()
        await connector.init_schema(db_path)

        async with connector.session_scope(db_path) as session:
            session.add(VendorRecord(
                rfc="VENDORMASK01",
                legal_name="Comercializadora Confidencial SA",
                bank_clabe="012180012345678901",
                address="Calle Secreta 456, Col. Juarez",
                contact_email="director@confidencial.com",
            ))
            session.add(BankTxnRecord(
                txn_id="TXN-MASK-001",
                date="2025-01-15",
                from_clabe="012180000000000001",
                to_clabe="012180012345678901",
                amount=Decimal("250000.00"),
                reference="Pago de servicios confidenciales",
            ))
            await session.commit()
        await connector.dispose_all()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            estate_query = f"estate_path={db_path.as_posix()}"

            # Query vendor endpoint
            r_v = await ac.get(f"/api/v1/database/vendors?{estate_query}&rfc=VENDORMASK01")
            assert r_v.status_code == 200
            v_record = r_v.json()["records"][0]

            # Verify PII fields are masked
            assert v_record["bank_clabe"] == "0121**********8901"
            assert "@confidencial.com" in v_record["contact_email"]
            assert "director" not in v_record["contact_email"]
            assert "Calle Secreta" not in v_record["address"]
            # Identifier must remain intact for evidence matching
            assert v_record["rfc"] == "VENDORMASK01"

            # Query bank_txns endpoint
            r_tx = await ac.get(f"/api/v1/database/bank_txns?{estate_query}&txn_id=TXN-MASK-001")
            assert r_tx.status_code == 200
            tx_record = r_tx.json()["records"][0]
            assert tx_record["from_clabe"].startswith("0121")
            assert "**********" in tx_record["from_clabe"]
            assert tx_record["to_clabe"].startswith("0121")
            assert "**********" in tx_record["to_clabe"]

        await estate_connector.dispose_all()

