import asyncio
from decimal import Decimal
import json
import os
import sys
import unittest.mock as mock
import uuid

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import httpx
import pytest
from sqlalchemy import select

from backend.main import app
from backend.core.config import settings
from backend.core.database import close_db, get_session_factory, init_db
from backend.api.routes.investigations import INVESTIGATION_CASES
from backend.models.forensic import InvestigationCase, TransactionRecord

SYNTHETIC_CSV = (
    "origin,destination,amount,timestamp\n"
    "ACC_1,ACC_2,100000.0,1.0\n"
    "ACC_2,ACC_3,98000.0,2.0\n"
    "ACC_3,ACC_1,95000.0,3.0\n"
).encode("utf-8")


async def run_adversarial_suite():
    print("=== STARTING ADVERSARIAL STRESS TEST SUITE ===")
    
    # -------------------------------------------------------------------------
    # 1. Database Isolation Setup
    # -------------------------------------------------------------------------
    orig_db_url = settings.DATABASE_URL
    orig_n8n_url = settings.N8N_WEBHOOK_URL
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    settings.N8N_WEBHOOK_URL = None
    await init_db()
    INVESTIGATION_CASES.clear()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:

        # ---------------------------------------------------------------------
        # 2. Pagination Edge Cases
        # ---------------------------------------------------------------------
        print("\n--- Testing Pagination Edge Cases ---")
        # Empty database listing
        resp = await client.get("/api/v1/investigations?page=1&page_size=20")
        assert resp.status_code == 200, f"Expected 200 on empty DB, got {resp.status_code}"
        data = resp.json()
        assert data["total"] == 0
        assert data["total_pages"] == 0
        assert data["items"] == []
        print("  [PASS] Empty database returns total=0, total_pages=0, items=[]")

        # Invalid page and page_size bounds
        for bad_query, code in [
            ("?page=0", 422),
            ("?page=-1", 422),
            ("?page=-999", 422),
            ("?page_size=0", 422),
            ("?page_size=-5", 422),
            ("?page_size=101", 422),
            ("?page=abc", 422),
            ("?page_size=xyz", 422),
        ]:
            bad_resp = await client.get(f"/api/v1/investigations{bad_query}")
            assert bad_resp.status_code == code, f"Query {bad_query} expected {code}, got {bad_resp.status_code}"
        print("  [PASS] Page < 1, page_size < 1, page_size > 100 correctly return 422")

        # Large page_size at boundary (100)
        resp_100 = await client.get("/api/v1/investigations?page=1&page_size=100")
        assert resp_100.status_code == 200
        assert resp_100.json()["page_size"] == 100
        print("  [PASS] Maximum boundary page_size=100 returns 200")

        # Seed 5 cases for pagination verification
        factory = get_session_factory()
        async with factory() as session:
            for i in range(5):
                st = "COMPLETED" if i % 2 == 0 else "PROCESSING"
                c = InvestigationCase(
                    id=uuid.uuid4(),
                    filename=f"adv_case_{i}.csv",
                    status=st,
                    metrics={"total_nodes_analyzed": i + 2},
                    verdict={"risk_level": "ALTO"} if st == "COMPLETED" else None,
                )
                session.add(c)
            await session.commit()

        # Page out of bounds
        resp_oob = await client.get("/api/v1/investigations?page=99&page_size=20")
        assert resp_oob.status_code == 200
        assert resp_oob.json()["total"] == 5
        assert resp_oob.json()["items"] == []
        print("  [PASS] Out of bounds page returns total=5, items=[]")

        # Status filtering case insensitivity
        resp_lower = await client.get("/api/v1/investigations?status=completed")
        assert resp_lower.status_code == 200
        assert resp_lower.json()["total"] == 3
        resp_upper = await client.get("/api/v1/investigations?status=COMPLETED")
        assert resp_upper.status_code == 200
        assert resp_upper.json()["total"] == 3
        resp_mixed = await client.get("/api/v1/investigations?status=cOmPlEtEd")
        assert resp_mixed.status_code == 200
        assert resp_mixed.json()["total"] == 3
        print("  [PASS] Status filtering works case-insensitively across lowercase, uppercase, and mixed case")

        # ---------------------------------------------------------------------
        # 3. Non-existent & Malformed UUID Handling
        # ---------------------------------------------------------------------
        print("\n--- Testing Non-existent & Malformed UUID Handling ---")
        random_uuid = str(uuid.uuid4())
        
        # Detail endpoint
        det_404 = await client.get(f"/api/v1/investigations/{random_uuid}")
        assert det_404.status_code == 404
        assert "not found" in det_404.json()["detail"].lower()
        print("  [PASS] GET /investigations/{random_uuid} returns clean HTTP 404")

        det_422 = await client.get("/api/v1/investigations/not-a-uuid-string")
        assert det_422.status_code == 422
        print("  [PASS] GET /investigations/{malformed_id} returns clean HTTP 422")

        # Stream endpoint
        stream_404 = await client.get(f"/api/v1/investigations/{random_uuid}/stream")
        assert stream_404.status_code == 404
        assert "not found" in stream_404.json()["detail"].lower()
        print("  [PASS] GET /investigations/{random_uuid}/stream returns clean HTTP 404 upfront")

        stream_422 = await client.get("/api/v1/investigations/invalid-uuid-1234/stream")
        assert stream_422.status_code == 422
        print("  [PASS] GET /investigations/{malformed_id}/stream returns clean HTTP 422 upfront")

        # ---------------------------------------------------------------------
        # 4. n8n Webhook Fallback (Empty vs Unreachable vs Reachable)
        # ---------------------------------------------------------------------
        print("\n--- Testing n8n Webhook Fallback Scenarios ---")
        # Create a new case for streaming
        up_resp = await client.post(
            "/api/v1/investigations/upload",
            files={"file": ("stream_test.csv", SYNTHETIC_CSV, "text/csv")},
        )
        assert up_resp.status_code == 201
        test_case_id = up_resp.json()["case_id"]

        # 4a. N8N_WEBHOOK_URL is None (Default internal simulation)
        settings.N8N_WEBHOOK_URL = None
        evs_sim = []
        async with client.stream("GET", f"/api/v1/investigations/{test_case_id}/stream") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    evs_sim.append(line.split(":", 1)[1].strip())
        assert evs_sim.count("thought") == 6
        assert evs_sim.count("verdict") == 1
        print("  [PASS] Empty N8N_WEBHOOK_URL emits 6 thoughts + 1 verdict simulation")

        # 4b. N8N_WEBHOOK_URL is unreachable (e.g., port closed / connection refused)
        # Create another case
        up_resp2 = await client.post(
            "/api/v1/investigations/upload",
            files={"file": ("unreachable_test.csv", SYNTHETIC_CSV, "text/csv")},
        )
        test_case_id_2 = up_resp2.json()["case_id"]
        settings.N8N_WEBHOOK_URL = "http://127.0.0.1:59999/unreachable_webhook"
        
        evs_unreach = []
        async with client.stream("GET", f"/api/v1/investigations/{test_case_id_2}/stream") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    evs_unreach.append(line.split(":", 1)[1].strip())
        assert evs_unreach.count("thought") == 6
        assert evs_unreach.count("verdict") == 1
        print("  [PASS] Unreachable N8N_WEBHOOK_URL smoothly falls back to 6 thoughts + 1 verdict")

        # 4c. N8N_WEBHOOK_URL is reachable and returns an external SSE stream
        up_resp3 = await client.post(
            "/api/v1/investigations/upload",
            files={"file": ("reachable_test.csv", SYNTHETIC_CSV, "text/csv")},
        )
        test_case_id_3 = up_resp3.json()["case_id"]
        settings.N8N_WEBHOOK_URL = "https://n8n.service.local/webhook"

        mock_stream_data = [
            "event: thought\n",
            'data: {"step": 1, "phase": "n8n External", "message": "External thought"}\n\n',
            "event: verdict\n",
            json.dumps({"case_id": test_case_id_3, "risk_level": "ALTO", "fraud_type": "External n8n fraud"}),
        ]

        class MockStreamResponse:
            status_code = 200
            headers = {"content-type": "text/event-stream"}
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def aiter_lines(self):
                yield "event: thought"
                yield 'data: {"step": 1, "phase": "n8n External", "message": "External thought"}'
                yield "event: verdict"
                yield 'data: ' + json.dumps({"case_id": test_case_id_3, "risk_level": "ALTO", "fraud_type": "External n8n fraud"})

        class MockClient:
            def __init__(self, *args, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            def stream(self, method, url, **kwargs):
                return MockStreamResponse()

        with mock.patch("httpx.AsyncClient", MockClient):
            evs_reach = []
            async with client.stream("GET", f"/api/v1/investigations/{test_case_id_3}/stream") as resp:
                assert resp.status_code == 200
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        evs_reach.append(line.split(":", 1)[1].strip())
            assert evs_reach == ["thought", "verdict"]

        # Check that external verdict was persisted to DB
        async with factory() as session:
            res = await session.execute(
                select(InvestigationCase).where(InvestigationCase.id == uuid.UUID(test_case_id_3))
            )
            c3 = res.scalar_one_or_none()
            assert c3.status == "COMPLETED"
            assert c3.verdict["fraud_type"] == "External n8n fraud"
        print("  [PASS] Reachable N8N_WEBHOOK_URL streams proxy events and persists external verdict")

        # ---------------------------------------------------------------------
        # 5. Client Disconnect Handling During SSE Stream
        # ---------------------------------------------------------------------
        print("\n--- Testing SSE Client Disconnect & Session Lifecycle ---")
        up_resp4 = await client.post(
            "/api/v1/investigations/upload",
            files={"file": ("disconnect_test.csv", SYNTHETIC_CSV, "text/csv")},
        )
        test_case_id_4 = up_resp4.json()["case_id"]
        settings.N8N_WEBHOOK_URL = None

        # Simulate direct ASGI disconnect mid-stream
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": f"/api/v1/investigations/{test_case_id_4}/stream",
            "raw_path": f"/api/v1/investigations/{test_case_id_4}/stream".encode(),
            "query_string": b"",
            "headers": [(b"host", b"testserver"), (b"accept", b"text/event-stream")],
        }
        disconnect_sent = False
        chunks_count = 0

        async def mock_receive():
            nonlocal disconnect_sent
            if chunks_count >= 2 and not disconnect_sent:
                disconnect_sent = True
                return {"type": "http.disconnect"}
            await asyncio.sleep(0.05)
            return {"type": "http.request", "body": b"", "more_body": False}

        async def mock_send(msg):
            nonlocal chunks_count
            if msg["type"] == "http.response.body" and len(msg.get("body", b"")) > 0:
                chunks_count += 1

        await app(scope, mock_receive, mock_send)
        await asyncio.sleep(0.2)

        async with factory() as session:
            res = await session.execute(
                select(InvestigationCase).where(InvestigationCase.id == uuid.UUID(test_case_id_4))
            )
            c4 = res.scalar_one_or_none()
            assert c4.status == "PROCESSING"
            assert c4.verdict is None
        print("  [PASS] Disconnect immediately halts generator; status remains PROCESSING and verdict is None (no leak)")

    # -------------------------------------------------------------------------
    # Clean up
    # -------------------------------------------------------------------------
    await close_db()
    settings.DATABASE_URL = orig_db_url
    settings.N8N_WEBHOOK_URL = orig_n8n_url
    print("\n=== ALL ADVERSARIAL STRESS TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    asyncio.run(run_adversarial_suite())
