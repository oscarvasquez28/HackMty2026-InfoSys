"""
Tests for n8n LLM Enrichment Service, Adversarial Defense Review,
Judge Verdict, and Exhibit Database Persistence.
"""

from decimal import Decimal
from pathlib import Path
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient, Response
from unittest.mock import patch

from backend.main import app
from backend.models.estate import ContractRecord, ExhibitRecord, InvoiceRecord, VendorRecord
from backend.services.case_file_generator import CaseFileGenerator
from backend.services.estate_connector import EstateConnector, estate_connector
from backend.services.n8n_enrichment import N8nEnrichmentService


@pytest.mark.asyncio
async def test_n8n_enrichment_mock_online_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_n8n_estate.db"
        connector = EstateConnector()

        # Seed sample data estate
        await connector.init_schema(db_path)
        async with connector.session_scope(db_path) as session:
            session.add(VendorRecord(
                rfc="PHANTOM999",
                legal_name="Operaciones Fantasma SA",
                bank_clabe="123456789012345678",
                category="Consultoria",
            ))
            session.add(ContractRecord(
                contract_id="CNT-ADV-001",
                vendor_rfc="PHANTOM999",
                start_date="2025-01-01",
                value=Decimal("80000.00"),
                scope_text="Contrato formal sin entregables materiales",
            ))
            session.add(InvoiceRecord(
                uuid="INV-ADV-001",
                issuer_rfc="PHANTOM999",
                receiver_rfc="AUDITED_COMPANY",
                issue_date="2025-01-10",
                subtotal=Decimal("80000.00"),
                total=Decimal("92800.00"),
                status="vigente",
            ))
            await session.commit()
        await connector.dispose_all()

        sample_findings = [
            {
                "scheme_type": "phantom_vendor",
                "entities": ["RFC:PHANTOM999"],
                "narrative": "Presunta empresa fantasma detectada.",
                "rule_broken": "SAT Articulo 69-B",
                "peso_amount": 92800.00,
                "confidence": "proven",
                "exhibits": [
                    {"exhibit_id": "EX-001", "source_table": "invoices", "record_id": "INV-ADV-001", "note": "Factura simulada"},
                ],
                "money_trail": [
                    {"from": "RFC:AUDITED_COMPANY", "to": "RFC:PHANTOM999", "amount": 92800.00, "date": "2025-01-10", "exhibit_id": "EX-001"}
                ],
            }
        ]
        sample_leads = [
            {
                "entity": "RFC:LEGIT001",
                "signal": "High transaction volume",
                "reason": "Preliminary check",
                "tool_calls_made": ["vendors"],
                "closed_by": "investigator",
            }
        ]

        mock_n8n_response_data = {
            "adversarial_review": (
                "La defensa adversarial analizó el contrato CNT-ADV-001 alegando materialidad de los servicios. "
                "No obstante, se ratifica la infracción al Artículo 69-B del CFF debido a que el proveedor carece "
                "de activos fijos y personal registrado ante el IMSS."
            ),
            "judge_verdict": (
                "DICTAMEN PERICIAL DEFINITIVO: Se declara procedente la acusación por operaciones simuladas "
                "por $92,800.00 MXN. Se desestima la defensa por falta de sustancia económica."
            ),
            "final_narrative": (
                "Investigación pericial concluyente: Se comprobó que PHANTOM999 emitió comprobantes fiscales sin "
                "capacidad operativa real para erosionar la base fiscal de la empresa auditada."
            ),
            "adversarial_evidences": [
                {
                    "exhibit_id": "EX-ADV-0001",
                    "source_table": "contracts",
                    "record_id": "CNT-ADV-001",
                    "sentence": "Contrato mercantil exhibido por la defensa desvirtuado por ausencia de entregables.",
                },
                {
                    "exhibit_id": "EX-ADV-0002",
                    "source_table": "invoices",
                    "record_id": "INV-ADV-001",
                    "sentence": "CFDI 4.0 conciliado al 100% contra el reclamo pericial.",
                },
            ],
            "leads_not_pursued": [
                {
                    "entity": "RFC:LEGIT001",
                    "signal": "High transaction volume",
                    "reason": "Operación ordinaria de suministro con cotizaciones y entregas de almacén verificadas.",
                    "tool_calls_made": ["contracts", "purchase_orders"],
                    "closed_by": "challenger",
                }
            ],
        }

        service = N8nEnrichmentService(connector=connector)

        # Mock httpx.AsyncClient.post
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Response(
                status_code=200,
                json=mock_n8n_response_data,
                request=None,
            )

            result = await service.run_enrichment(
                findings=sample_findings,
                leads_not_pursued=sample_leads,
                seed=42,
                estate_target=db_path,
                n8n_url="http://mock-n8n:5678/webhook/investigation",
            )

            assert result["is_online_enrichment"] is True
            assert result["adversarial_review"] == mock_n8n_response_data["adversarial_review"]
            assert result["judge_verdict"] == mock_n8n_response_data["judge_verdict"]
            assert result["final_narrative"] == mock_n8n_response_data["final_narrative"]
            assert len(result["adversarial_evidences"]) == 2

            # 1. Check exhibit records were inserted into the database exhibits table
            async with connector.session_scope(db_path) as session:
                from sqlalchemy import select
                ex1 = (await session.execute(select(ExhibitRecord).where(ExhibitRecord.exhibit_id == "EX-ADV-0001"))).scalar_one_or_none()
                assert ex1 is not None
                assert ex1.source_table == "contracts"
                assert ex1.record_id == "CNT-ADV-001"

                ex2 = (await session.execute(select(ExhibitRecord).where(ExhibitRecord.exhibit_id == "EX-ADV-0002"))).scalar_one_or_none()
                assert ex2 is not None
                assert ex2.source_table == "invoices"

            # 2. Check CaseFileGenerator incorporates the results into markdown
            generator = CaseFileGenerator()
            submission_payload = {
                "seed": 42,
                "findings": result["findings"],
                "leads_not_pursued": result["leads_not_pursued"],
                "adversarial_review": result["adversarial_review"],
                "judge_verdict": result["judge_verdict"],
                "final_narrative": result["final_narrative"],
                "adversarial_evidences": result["adversarial_evidences"],
                "run_metadata": {"llm_calls": result["llm_calls"], "wall_clock_seconds": 1.2, "mxn_cost": 0.0},
            }
            case_md = generator.generate_case_file_markdown(submission_payload)
            assert "### Veredicto del Juez Forense / Dictamen Formal" in case_md
            assert "DICTAMEN PERICIAL DEFINITIVO" in case_md
            assert "##### Evidencias Verificadas por la Defensa Adversarial" in case_md
            assert "CNT-ADV-001" in case_md

        await connector.dispose_all()


@pytest.mark.asyncio
async def test_n8n_enrichment_offline_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_offline_estate.db"
        connector = EstateConnector()
        await connector.init_schema(db_path)

        sample_findings = [
            {
                "scheme_type": "phantom_vendor",
                "entities": ["RFC:OFFLINE01"],
                "narrative": "Hallazgo detectado en modo offline.",
                "rule_broken": "SAT Articulo 69-B",
                "peso_amount": 50000.00,
                "confidence": "proven",
                "exhibits": [
                    {"exhibit_id": "EX-OFF-01", "source_table": "invoices", "record_id": "INV-001", "note": "Factura"},
                ],
                "money_trail": [],
            }
        ]

        service = N8nEnrichmentService(connector=connector)
        # Without n8n_url and without settings.N8N_WEBHOOK_URL
        result = await service.run_enrichment(
            findings=sample_findings,
            leads_not_pursued=[],
            seed=1,
            estate_target=db_path,
            n8n_url=None,
        )

        assert result["is_online_enrichment"] is False
        assert "Artículo 69-B" in result["adversarial_review"]
        assert "DICTAMEN PERICIAL" in result["judge_verdict"]
        assert "auditoría forense" in result["final_narrative"]
        assert len(result["adversarial_evidences"]) >= 1

        # Check exhibit inserted in exhibits table
        async with connector.session_scope(db_path) as session:
            from sqlalchemy import func, select
            count = (await session.execute(select(func.count()).select_from(ExhibitRecord))).scalar()
            assert count >= 1

        await connector.dispose_all()


@pytest.mark.asyncio
async def test_audit_estate_endpoint_with_n8n_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_endpoint_estate.db"
        connector = EstateConnector()
        await connector.init_schema(db_path)

        async with connector.session_scope(db_path) as session:
            session.add(VendorRecord(
                rfc="PHANTOM123",
                legal_name="Phantom Company",
                bank_clabe="000000000000000001",
            ))
            session.add(InvoiceRecord(
                uuid="INV-12345",
                issuer_rfc="PHANTOM123",
                receiver_rfc="AUDIT_CORP",
                issue_date="2026-01-01",
                total=Decimal("60000.00"),
                status="vigente",
            ))
            await session.commit()
        await connector.dispose_all()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {
                "estate_path": str(db_path),
                "seed": 101,
                "company_name": "Audit Corp Test",
            }
            resp = await ac.post("/api/v1/investigations/audit-estate", json=payload)
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["status"] == "COMPLETED"
            assert data["adversarial_review"] is not None
            assert data["judge_verdict"] is not None
            assert data["final_narrative"] is not None
            assert isinstance(data["adversarial_evidences"], list)

        await estate_connector.dispose_all()

