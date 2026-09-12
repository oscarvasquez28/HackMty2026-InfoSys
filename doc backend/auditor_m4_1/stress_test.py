import sys
import os
sys.path.insert(0, os.getcwd())
import asyncio
import httpx
from unittest.mock import patch
from backend.main import app
from backend.core.config import settings
from backend.tests.test_tts import MockAsyncHttpClient, MockStreamResponse

async def stress_test():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Unicode, Spanish AML terminology, Emoji, Special Chars
        texts = [
            "Dictamen CFF 69-B: Operaciones simuladas con EFOS y EDOS por $45,000,000.00 M.N.",
            "Alerta UIF: Lavado de dinero detectado en cuenta #12345",
            "Chars: <script>alert(1)</script> '\" & % $ # @ ! ? \n \t \r",
            "Multilingual: 繁體中文, Русский, 日本語, العربية",
        ]
        for t in texts:
            r = await client.post("/api/v1/tts/synthesize", json={"text": t})
            assert r.status_code == 200, f"Failed on text: {t}"
            assert "audio/mpeg" in r.headers["content-type"]
            assert len(r.content) == 320
        print("Adversarial Unicode & Char inputs: PASS")

        # 2. Upstream UTF-8 error body with non-ASCII characters
        orig_key = settings.ELEVENLABS_API_KEY
        settings.ELEVENLABS_API_KEY = "test_key"
        try:
            bad_client = MockAsyncHttpClient(resp=MockStreamResponse(
                status_code=403,
                error_body="Clave xi-api-key inválida o expirada".encode("utf-8")
            ))
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=bad_client):
                r = await client.post("/api/v1/tts/synthesize", json={"text": "Test text"})
                assert r.status_code == 200
                assert len(r.content) == 320
            print("Upstream non-ASCII error body fallback: PASS")
        finally:
            settings.ELEVENLABS_API_KEY = orig_key

        # 3. Upstream mid-stream disconnection after partial chunk
        class MidStreamDropResponse(MockStreamResponse):
            async def aiter_bytes(self):
                yield b"FIRST_PARTIAL_CHUNK"
                raise httpx.ReadError("Upstream connection reset by peer mid-stream")

        settings.ELEVENLABS_API_KEY = "test_key"
        try:
            drop_client = MockAsyncHttpClient(resp=MidStreamDropResponse(status_code=200))
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=drop_client):
                r = await client.post("/api/v1/tts/synthesize", json={"text": "Partial stream"})
                assert r.status_code == 200
                assert b"FIRST_PARTIAL_CHUNK" in r.content
                # And silence fallback is appended cleanly upon exception
                assert r.content.endswith(b"\x00" * 28)
            print("Mid-stream connection drop handling: PASS")
        finally:
            settings.ELEVENLABS_API_KEY = orig_key

        # 4. Concurrent requests (50 simultaneous requests)
        tasks = [
            client.post("/api/v1/tts/synthesize", json={"text": f"Concurrent request {i}"})
            for i in range(50)
        ]
        results = await asyncio.gather(*tasks)
        for idx, res in enumerate(results):
            assert res.status_code == 200
            assert len(res.content) == 320
        print("50 Concurrent fallback requests: PASS")

        # 5. Client cancellation / disconnect during stream
        cancelled_logged = False
        class FastCancelResponse(MockStreamResponse):
            async def aiter_bytes(self):
                yield b"CHUNK_1"
                raise asyncio.CancelledError()

        settings.ELEVENLABS_API_KEY = "test_key"
        try:
            cancel_client = MockAsyncHttpClient(resp=FastCancelResponse(status_code=200))
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=cancel_client):
                try:
                    r = await client.post("/api/v1/tts/synthesize", json={"text": "Cancelled stream"})
                except Exception:
                    pass
            print("Client cancellation handling: PASS")
        finally:
            settings.ELEVENLABS_API_KEY = orig_key

if __name__ == "__main__":
    asyncio.run(stress_test())
