"""
Tests for n8n LLM Enrichment Service, Sequential One-by-One Review,
Per-Review Judge Verdicts, SSE Streaming, and Exhibit Database Persistence.
"""

from decimal import Decimal
import json
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
async def test_n8n_enrichment_sequential_mock_online():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_n8n_estate.db"
        connector = EstateConnector()

        # Seed sample data estate
        await connector.init_schema(db_path)
        async with connector.session_scope(db_path) as session:
            session.add(VendorRecord(
                rfc="PHANTOM999",
                legal_name="Phantom Operations SA",
                bank_clabe="123456789012345678",
                category="Consulting",
            ))
            session.add(ContractRecord(
                contract_id="CNT-ADV-001",
                vendor_rfc="PHANTOM999",
                start_date="2025-01-01",
                value=Decimal("80000.00"),
                scope_text="Formal contract with no material deliverables",
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
                "narrative": "Suspected phantom company detected.",
                "rule_broken": "SAT Article 69-B",
                "peso_amount": 92800.00,
                "confidence": "proven",
                "exhibits": [
                    {"exhibit_id": "EX-001", "source_table": "invoices", "record_id": "INV-ADV-001", "note": "Simulated invoice"},
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

        service = N8nEnrichmentService(connector=connector)

        # Mock handler routing by action in payload
        async def mock_post_handler(url, json=None, **kwargs):
            action = json.get("action") if json else ""
            if action == "adversarial_review_finding":
                return Response(
                    status_code=200,
                    json={
                        "adversarial_review": "The defense examined contract CNT-ADV-001 but could not substantiate deliverables.",
                        "judge_verdict": "JUDGE'S VERDICT (FINDING 1): GUILTY / CHARGE UPHELD. Fraud is confirmed.",
                        "final_narrative": "Simulated transaction with EFOS for $92,800.00 MXN fully proven.",
                        "adversarial_evidences": [
                            {
                                "exhibit_id": "EX-ADV-0001",
                                "source_table": "contracts",
                                "record_id": "CNT-ADV-001",
                                "sentence": "Commercial contract disproven due to the absence of material deliverables.",
                            },
                        ],
                    },
                    request=None,
                )
            elif action == "review_decoy_lead":
                return Response(
                    status_code=200,
                    json={
                        "adversarial_review": "Ordinary transaction with verified quotes and deliveries.",
                        "judge_verdict": "JUDGE'S VERDICT (LEAD 1): ACQUITTED / LEAD DISMISSED.",
                        "reason": "Ordinary supply transaction with verified quotes.",
                        "closed_by": "Technical Defense / Examining Judge",
                    },
                    request=None,
                )
            elif action == "synthesize_case_verdict":
                return Response(
                    status_code=200,
                    json={
                        "judge_verdict": "GLOBAL EXPERT JUDICIAL VERDICT: Corporate liability confirmed.",
                        "final_narrative": "Conclusive expert investigation for $92,800.00 MXN.",
                    },
                    request=None,
                )
            return Response(status_code=400, json={"error": "unknown action"}, request=None)

        with patch("httpx.AsyncClient.post", side_effect=mock_post_handler):
            # Test streaming generator steps
            steps_collected = []
            async for step in service.stream_enrichment_steps(
                findings=sample_findings,
                leads_not_pursued=sample_leads,
                seed=42,
                estate_target=db_path,
                n8n_url="http://mock-n8n:5678/webhook/investigation",
            ):
                steps_collected.append(step)

            step_types = [s["type"] for s in steps_collected]
            assert "enrichment_started" in step_types
            assert "finding_reviewed" in step_types
            assert "lead_reviewed" in step_types
            assert "verdict_synthesized" in step_types

            # Verify finding received its individual judge verdict
            finding_step = next(s for s in steps_collected if s["type"] == "finding_reviewed")
            assert "GUILTY" in finding_step["judge_verdict"]
            assert len(finding_step["adversarial_evidences"]) == 1

            # Verify lead received its dismissal judge verdict
            lead_step = next(s for s in steps_collected if s["type"] == "lead_reviewed")
            assert "ACQUITTED" in lead_step["judge_verdict"]

            # 1. Check exhibit records were inserted into the database exhibits table
            async with connector.session_scope(db_path) as session:
                from sqlalchemy import select
                ex1 = (await session.execute(select(ExhibitRecord).where(ExhibitRecord.exhibit_id == "EX-ADV-0001"))).scalar_one_or_none()
                assert ex1 is not None
                assert ex1.source_table == "contracts"
                assert ex1.record_id == "CNT-ADV-001"

            # 2. Check CaseFileGenerator incorporates the results into markdown
            generator = CaseFileGenerator()
            synthesis_step = next(s for s in steps_collected if s["type"] == "verdict_synthesized")
            submission_payload = {
                "seed": 42,
                "findings": synthesis_step["findings"],
                "leads_not_pursued": synthesis_step["leads_not_pursued"],
                "adversarial_review": synthesis_step["adversarial_review"],
                "judge_verdict": synthesis_step["judge_verdict"],
                "final_narrative": synthesis_step["final_narrative"],
                "adversarial_evidences": synthesis_step["adversarial_evidences"],
                "run_metadata": {"llm_calls": synthesis_step["llm_calls"], "wall_clock_seconds": 1.2, "mxn_cost": 0.0},
            }
            case_md = generator.generate_case_file_markdown(submission_payload)
            assert "GLOBAL EXPERT JUDICIAL VERDICT" in case_md
            assert "Judicial Verdict on the Finding" in case_md
            assert "GUILTY" in case_md
            assert "EX-ADV-0001" in case_md

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
                "narrative": "Finding detected in offline mode.",
                "rule_broken": "SAT Article 69-B",
                "peso_amount": 50000.00,
                "confidence": "proven",
                "exhibits": [
                    {"exhibit_id": "EX-OFF-01", "source_table": "invoices", "record_id": "INV-001", "note": "Invoice"},
                ],
                "money_trail": [],
            }
        ]

        service = N8nEnrichmentService(connector=connector)
        result = await service.run_enrichment(
            findings=sample_findings,
            leads_not_pursued=[],
            seed=1,
            estate_target=db_path,
            n8n_url=None,
        )

        assert "Article 69-B" in result["adversarial_review"]
        assert "EXPERT VERDICT ISSUED" in result["judge_verdict"]
        assert "forensic audit" in result["final_narrative"]
        assert len(result["adversarial_evidences"]) >= 1

        # Check per-finding judge verdict was populated
        f0 = result["findings"][0]
        assert "JUDGE'S VERDICT (FINDING 1/1)" in f0["judge_verdict"]

        # Check exhibit inserted in exhibits table
        async with connector.session_scope(db_path) as session:
            from sqlalchemy import func, select
            count = (await session.execute(select(func.count()).select_from(ExhibitRecord))).scalar()
            assert count >= 1

        await connector.dispose_all()


@pytest.mark.asyncio
async def test_audit_estate_stream_sse_endpoint():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_stream_estate.db"
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
                "seed": 102,
                "company_name": "Audit Corp SSE Test",
            }
            resp = await ac.post("/api/v1/investigations/audit-estate/stream", json=payload)
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            content = resp.text
            assert "event: thought" in content
            assert "event: verdict" in content
            assert "event: audit_completed" in content

        await estate_connector.dispose_all()
