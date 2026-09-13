import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select

from backend.core.config import Settings, settings
from backend.core.database import (
    create_engine_and_sessionmaker,
    init_db,
    close_db,
    get_db,
    normalize_database_url,
    sanitize_database_url,
)
from backend.models.forensic import (
    Base,
    InvestigationCase,
    TransactionRecord,
    LegalArticleVector,
    SEED_LEGAL_PRECEDENTS,
    generate_deterministic_embedding,
    seed_legal_knowledge,
)


def test_database_url_normalization():
    # 1. postgres:// -> postgresql+asyncpg:// with ssl stripped and in connect_args
    raw_url = "postgres://forensic_user:secret_pass@db.tigerdata.com:5432/audit_db?sslmode=require"
    norm_url, connect_args = normalize_database_url(raw_url)
    assert norm_url == "postgresql+asyncpg://forensic_user:secret_pass@db.tigerdata.com:5432/audit_db"
    assert connect_args.get("ssl") == "require"

    # 2. postgresql:// -> postgresql+asyncpg://
    raw_url2 = "postgresql://user:pass@localhost:5432/testdb"
    norm_url2, connect_args2 = normalize_database_url(raw_url2)
    assert norm_url2 == "postgresql+asyncpg://user:pass@localhost:5432/testdb"
    assert connect_args2.get("ssl") == "require"

    # 3. sqlite url preserved
    sqlite_url = "sqlite+aiosqlite:///:memory:"
    norm_sqlite, connect_sqlite = normalize_database_url(sqlite_url)
    assert norm_sqlite == sqlite_url
    assert connect_sqlite == {}


def test_sanitize_database_url():
    raw_url = "postgresql+asyncpg://audit_admin:super_secret_password_123@host.com:5432/db"
    safe = sanitize_database_url(raw_url)
    assert "super_secret_password_123" not in safe
    assert "audit_admin:****@host.com:5432/db" in safe


def test_settings_database_configuration():
    assert settings.DB_POOL_SIZE == 20
    assert settings.DB_MAX_OVERFLOW == 10
    assert settings.DB_POOL_PRE_PING is True
    assert settings.DB_POOL_RECYCLE == 3600
    assert settings.DB_SSL_REQUIRE is True

    # Test validator for blank URL
    blank_settings = Settings(DATABASE_URL="   ")
    assert blank_settings.DATABASE_URL is None


def test_deterministic_embedding_generator():
    text = "Artículo 69-B del Código Fiscal de la Federación"
    embedding = generate_deterministic_embedding(text, dim=1536)
    assert len(embedding) == 1536
    # Unit norm check: sum(x^2) should be very close to 1.0
    l2_norm = math.sqrt(sum(x * x for x in embedding))
    assert abs(l2_norm - 1.0) < 0.01

    # Reproducibility check
    embedding2 = generate_deterministic_embedding(text, dim=1536)
    assert embedding == embedding2


@pytest.mark.asyncio
async def test_sqlite_model_crud_and_cascade_delete():
    engine, session_factory = create_engine_and_sessionmaker("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # 1. Create InvestigationCase
        case_id = uuid.uuid4()
        case = InvestigationCase(
            id=case_id,
            filename="investigation_batch_01.csv",
            status="PROCESSING",
            ingestion_metadata={"total_records": 100, "unique_accounts": 45},
            metrics={"pruning_efficiency_pct": 92.5, "detected_cycles_count": 2},
            subgraph={"nodes": [{"id": "ACC_1"}, {"id": "ACC_2"}], "edges": []},
            patterns={"cycles": [["ACC_1", "ACC_2", "ACC_1"]]},
            verdict=None,
        )
        session.add(case)
        await session.commit()

        # 2. Add Transactions
        tx1 = TransactionRecord(
            case_id=case_id,
            origin="ACC_1",
            destination="ACC_2",
            amount=Decimal("250000.50"),
            timestamp=datetime.now(timezone.utc),
            is_suspicious=True,
            reasons=["CYCLE_STEP"],
        )
        tx2 = TransactionRecord(
            case_id=case_id,
            origin="ACC_2",
            destination="ACC_1",
            amount=Decimal("249000.00"),
            timestamp=datetime.now(timezone.utc),
            is_suspicious=True,
            reasons=["CYCLE_STEP"],
        )
        session.add_all([tx1, tx2])
        await session.commit()

        # 3. Read and verify
        res = await session.execute(
            select(TransactionRecord).where(TransactionRecord.case_id == case_id)
        )
        records = res.scalars().all()
        assert len(records) == 2
        assert records[0].amount == Decimal("250000.50")
        assert records[0].is_suspicious is True

        # 4. Verify Cascade Deletion
        await session.delete(case)
        await session.commit()

        res_after = await session.execute(
            select(TransactionRecord).where(TransactionRecord.case_id == case_id)
        )
        assert len(res_after.scalars().all()) == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_legal_knowledge_seeding_and_idempotency():
    engine, session_factory = create_engine_and_sessionmaker("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # First seeding run
        inserted = await seed_legal_knowledge(session)
        assert inserted == len(SEED_LEGAL_PRECEDENTS)
        assert inserted >= 5

        # Query all seeded articles
        res = await session.execute(select(LegalArticleVector))
        articles = res.scalars().all()
        assert len(articles) == len(SEED_LEGAL_PRECEDENTS)

        codes = {a.article_code for a in articles}
        assert "CFF-ART-69B" in codes
        assert "NIF-A2-MATERIALIDAD" in codes
        assert "UIF-ROI-24H" in codes
        assert "UIF-ROR-7500USD" in codes
        assert "LIC-ART-115-BLOQUEO" in codes
        assert "CPF-ART-400BIS" in codes

        # Verify embedding stored
        cff = next(a for a in articles if a.article_code == "CFF-ART-69B")
        assert cff.embedding is not None
        assert len(cff.embedding) == 1536

        # Second seeding run: should be idempotent (0 new insertions)
        re_inserted = await seed_legal_knowledge(session)
        assert re_inserted == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_init_db_lifecycle():
    engine, session_factory = create_engine_and_sessionmaker("sqlite+aiosqlite:///:memory:")
    # Calling init_db with engine directly
    await init_db(engine)

    async with engine.connect() as conn:
        from sqlalchemy import text
        res = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {r[0] for r in res.fetchall()}

        # 1. Verify all 9 operational tables from estate_schema - polar.sql exist
        expected_operational = {
            "vendors", "invoices", "ledger", "bank_txns",
            "purchase_orders", "contracts", "employees", "efos_list", "exhibits",
        }
        assert expected_operational.issubset(tables)

        # 2. Verify all 9 historic tables exist
        expected_historic = {
            "vendors_history", "invoices_history", "ledger_history", "bank_txns_history",
            "purchase_orders_history", "contracts_history", "employees_history",
            "efos_list_history", "exhibits_history",
        }
        assert expected_historic.issubset(tables)

        # 3. Verify forensic case tables are provisioned deliberately
        expected_forensic = {
            "investigation_cases", "transactions", "legal_knowledge_vectors",
            "accounts", "account_mappings", "parties", "cash_transactions",
        }
        assert expected_forensic.issubset(tables)

    await engine.dispose()
