import json
import pytest
import httpx
from backend.main import app

# Minimal synthetic CSV with closed cycle + pass-through mule account + legitimate noise
SYNTHETIC_AML_CSV = """origin,destination,amount,timestamp
ACC_A,ACC_B,150000.0,1.0
ACC_B,ACC_C,148000.0,2.0
ACC_C,ACC_A,145000.0,3.0
CORP_INFLOW,MULE_01,500000.0,10.0
MULE_01,OFFSHORE_OUT,485000.0,22.0
LEGIT_PAYROLL,EMPLOYEE_01,2500.0,4.0
STORE_MERCHANT,CONSUMER_99,120.0,5.0
""".encode("utf-8")


@pytest.mark.asyncio
async def test_complete_forensic_pipeline():
    """
    Tests the end-to-end investigation pipeline:
    1. Submits synthetic CSV to upload endpoint.
    2. Validates deterministic graph pruning and metric results.
    3. Connects to SSE streaming endpoint and consumes thoughts and final verdict.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "healthy"

        # 2. Upload CSV
        files = {
            "file": ("synthetic_aml_test.csv", SYNTHETIC_AML_CSV, "text/csv")
        }
        upload_resp = await client.post("/api/v1/investigations/upload", files=files)
        assert upload_resp.status_code == 201
        upload_data = upload_resp.json()

        assert "case_id" in upload_data
        case_id = upload_data["case_id"]

        metrics = upload_data["metrics"]
        assert metrics["total_nodes_analyzed"] > 0
        assert metrics["detected_cycles_count"] >= 1
        assert metrics["passthrough_accounts_count"] >= 1
        assert metrics["pruned_edges_count"] >= 2  # Payroll and merchant were pruned

        # Verify suspicious subgraph
        subgraph = upload_data["subgraph"]
        assert len(subgraph["nodes"]) >= 3
        assert any("CIRCULAR_FLOW_CYCLE" in n["reasons"] for n in subgraph["nodes"])

        # 3. Stream SSE thoughts & verdict
        received_events = []
        async with client.stream("GET", f"/api/v1/investigations/{case_id}/stream") as stream_resp:
            assert stream_resp.status_code == 200
            assert "text/event-stream" in stream_resp.headers["content-type"]

            current_event_name = None
            async for line in stream_resp.aiter_lines():
                line = line.strip()
                if line.startswith("event:"):
                    current_event_name = line.split(":", 1)[1].strip()
                elif line.startswith("data:") and current_event_name:
                    data_str = line.split(":", 1)[1].strip()
                    payload = json.loads(data_str)
                    received_events.append({"event": current_event_name, "data": payload})
                    current_event_name = None

        thought_events = [e for e in received_events if e["event"] == "thought"]
        verdict_events = [e for e in received_events if e["event"] == "verdict"]

        assert len(thought_events) >= 5
        assert len(verdict_events) == 1

        final_verdict = verdict_events[0]["data"]
        assert final_verdict["case_id"] == case_id
        assert final_verdict["risk_level"] in ["CRÍTICO", "ALTO"]
        assert "Estructuración" in final_verdict["fraud_type"]
        assert final_verdict["total_amount_mxn"] > 0
        assert len(final_verdict["entities_involved"]) >= 3


@pytest.mark.asyncio
async def test_tts_synthesize_proxy():
    """
    Validates the ElevenLabs proxy endpoint returning audio/mpeg stream.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "text": "Dictamen pericial forense completado con éxito.",
        }
        tts_resp = await client.post("/api/v1/tts/synthesize", json=payload)
        assert tts_resp.status_code == 200
        assert "audio/mpeg" in tts_resp.headers["content-type"]
        assert len(tts_resp.content) > 0


def test_read_amlsim_csv_synthetic_fallback():
    """Unit test: verifies that read_amlsim_csv handles missing timestamp column."""
    from backend.services.ingestion import read_amlsim_csv
    csv_bytes = b"origin,destination,amount\nACC_1,ACC_2,100.0\nACC_2,ACC_3,200.0"
    df, meta = read_amlsim_csv(csv_bytes)
    assert df.height == 2
    assert "timestamp" in df.columns
    assert df["timestamp"].to_list() == [0.0, 1.0]


def test_read_amlsim_csv_null_timestamp_cells():
    """Unit test: verifies that read_amlsim_csv defaults null timestamp cells to 0.0."""
    from backend.services.ingestion import read_amlsim_csv
    csv_bytes = b"origin,destination,amount,timestamp\nACC_1,ACC_2,100.0,\nACC_2,ACC_3,200.0,5.0"
    df, meta = read_amlsim_csv(csv_bytes)
    assert df.height == 2
    assert df["timestamp"].to_list() == [0.0, 5.0]
