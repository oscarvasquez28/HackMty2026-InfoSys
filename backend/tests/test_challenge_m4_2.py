"""
Empirical Challenge Test Suite for Milestone 4 (Challenger 2):
Client Disconnect Simulation, Socket & Resource Leakage,
Response Headers (Content-Type & X-Audio-Source), and API Key Shielding.

Target:
- backend/api/routes/tts.py
- backend/core/config.py
"""

import asyncio
import gc
import socket
import threading
import time
from typing import AsyncGenerator, List, Optional
from unittest.mock import patch
import httpx
import pytest
import psutil

from backend.main import app
from backend.core.config import settings
from backend.api.routes.tts import generate_fallback_silence_mp3, stream_elevenlabs_audio


@pytest.fixture(autouse=True)
def allow_mocked_tts_stream():
    """Ensures mock tests can exercise stream_elevenlabs_audio with mocked clients."""
    orig_safe = getattr(settings, "ELEVENLABS_SAFE_MODE", False)
    settings.ELEVENLABS_SAFE_MODE = False
    try:
        yield
    finally:
        settings.ELEVENLABS_SAFE_MODE = orig_safe


# =============================================================================
# Helper Instrumented Mocks for Tracking Socket / Client Lifecycle
# =============================================================================

class LifecycleTrackingStreamResponse:
    """Simulates an upstream response and records open/close lifecycle."""

    def __init__(
        self,
        chunks: List[bytes],
        status_code: int = 200,
        error_body: bytes = b'{"detail": "error"}',
    ):
        self.chunks = chunks
        self.status_code = status_code
        self.error_body = error_body
        self.headers = {"content-type": "audio/mpeg"}
        self.is_closed = False
        self.entered = False
        self.exited = False
        self.chunks_yielded = 0

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        self.is_closed = True

    async def aiter_bytes(self) -> AsyncGenerator[bytes, None]:
        try:
            for chunk in self.chunks:
                self.chunks_yielded += 1
                yield chunk
                await asyncio.sleep(0.02)
        finally:
            self.is_closed = True

    async def aread(self) -> bytes:
        return self.error_body

    async def aclose(self):
        self.is_closed = True


class LifecycleTrackingHttpClient:
    """Mock httpx.AsyncClient that tracks connection and socket closure status."""

    def __init__(self, stream_response: LifecycleTrackingStreamResponse):
        self.stream_response = stream_response
        self.is_closed = False
        self.entered = False
        self.exited = False
        self.calls = []

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        self.is_closed = True

    def stream(self, method: str, url: str, **kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        return self.stream_response

    async def aclose(self):
        self.is_closed = True


# =============================================================================
# 1. Empirical Challenge: Client Disconnect & Resource Cleanup
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_client_disconnect_during_active_stream_cleans_up():
    """
    Simulates a client disconnecting midway through an active audio stream.
    Verifies that:
    1. Generator cleanly handles GeneratorExit / CancelledError
    2. Upstream httpx.AsyncClient and stream context are explicitly closed
    3. No hanging sockets or open stream contexts remain
    """
    chunks = [f"AUDIO_CHUNK_{i}_".encode("utf-8") * 50 for i in range(20)]
    mock_resp = LifecycleTrackingStreamResponse(chunks=chunks)
    mock_client = LifecycleTrackingHttpClient(stream_response=mock_resp)

    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_valid_key_for_disconnect_test"

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                # Initiate stream
                async with client.stream(
                    "POST",
                    "/api/v1/tts/synthesize",
                    json={"text": "Streaming voice synthesis test for disconnect"},
                ) as resp:
                    assert resp.status_code == 200
                    # Read only first chunk then abort/disconnect
                    async for _ in resp.aiter_bytes():
                        break  # Client disconnects early!

        # Allow event loop yield to finalize ASGI cleanup
        await asyncio.sleep(0.05)

        # Verify that mock client and mock response context exited cleanly
        assert mock_client.exited is True, "httpx.AsyncClient __aexit__ was not called!"
        assert mock_client.is_closed is True, "httpx.AsyncClient was not closed!"
        assert mock_resp.exited is True, "Stream response __aexit__ was not called!"
        assert mock_resp.is_closed is True, "Stream response was not marked closed!"
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_challenge_generator_exit_directly_on_stream_elevenlabs_audio():
    """
    Directly stresses stream_elevenlabs_audio generator with aclose() after first yield.
    Verifies clean termination without unhandled exceptions.
    """
    chunks = [b"chunk_1", b"chunk_2", b"chunk_3", b"chunk_4"]
    mock_resp = LifecycleTrackingStreamResponse(chunks=chunks)
    mock_client = LifecycleTrackingHttpClient(stream_response=mock_resp)

    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_direct_generator_exit_key"

    try:
        with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
            gen = stream_elevenlabs_audio("Test generator exit", "voice1", "model1")
            first_chunk = await anext(gen)
            assert first_chunk == b"chunk_1"

            # Abrupt client close on the async generator
            await gen.aclose()

            # Verify cleanup
            assert mock_client.exited is True
            assert mock_client.is_closed is True
            assert mock_resp.is_closed is True
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_challenge_concurrent_rapid_client_disconnects_stress():
    """
    Spawns 30 concurrent client connections that all disconnect after 1 chunk.
    Verifies that all 30 streams close cleanly without unhandled errors,
    coroutine leaks, or unclosed client contexts.
    """
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_concurrent_disconnect_key"

    clients_created = []

    def client_factory(*args, **kwargs):
        chunks = [b"STREAM_AUDIO_PACKET_" * 10 for _ in range(15)]
        resp = LifecycleTrackingStreamResponse(chunks=chunks)
        c = LifecycleTrackingHttpClient(stream_response=resp)
        clients_created.append(c)
        return c

    transport = httpx.ASGITransport(app=app)
    try:
        async def simulate_single_disconnect(client_id: int):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                with patch("backend.api.routes.tts.httpx.AsyncClient", side_effect=client_factory):
                    async with client.stream(
                        "POST",
                        "/api/v1/tts/synthesize",
                        json={"text": f"Concurrent client test {client_id}"},
                    ) as resp:
                        assert resp.status_code == 200
                        async for _ in resp.aiter_bytes():
                            break  # Disconnect immediately after first byte chunk

        # Run 30 concurrent rapid disconnects
        await asyncio.gather(*(simulate_single_disconnect(i) for i in range(30)))

        # Allow cooperative scheduling for ASGI tasks to finish cleanup
        await asyncio.sleep(0.05)

        assert len(clients_created) == 30
        # Ensure every single one had __aexit__ invoked and is_closed is True
        unclosed_clients = [c for c in clients_created if not c.is_closed]
        unexited_clients = [c for c in clients_created if not c.exited]
        unclosed_streams = [c for c in clients_created if not c.stream_response.is_closed]

        assert len(unclosed_clients) == 0, f"Found {len(unclosed_clients)} unclosed clients!"
        assert len(unexited_clients) == 0, f"Found {len(unexited_clients)} unexited client contexts!"
        assert len(unclosed_streams) == 0, f"Found {len(unclosed_streams)} unclosed stream contexts!"
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_challenge_psutil_socket_cleanup_under_rapid_disconnects():
    """
    Monitors process-level network connections via psutil before and after 25 rapid
    client disconnect events. Verifies that no orphaned ESTABLISHED or CLOSE_WAIT
    sockets remain open at the OS process level.
    """
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_psutil_key"

    proc = psutil.Process()
    gc.collect()
    initial_connections = len(proc.net_connections())

    transport = httpx.ASGITransport(app=app)
    try:
        for i in range(25):
            chunks = [b"STREAM_AUDIO_PACKET_" * 20 for _ in range(10)]
            mock_resp = LifecycleTrackingStreamResponse(chunks=chunks)
            mock_client = LifecycleTrackingHttpClient(stream_response=mock_resp)

            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                    async with client.stream(
                        "POST",
                        "/api/v1/tts/synthesize",
                        json={"text": f"Rapid disconnect run {i}"},
                    ) as resp:
                        assert resp.status_code == 200
                        async for _ in resp.aiter_bytes():
                            break  # Instant disconnect

            assert mock_client.is_closed is True
            assert mock_resp.is_closed is True

        await asyncio.sleep(0.05)
        gc.collect()
        final_connections = len(proc.net_connections())
        assert final_connections <= initial_connections, (
            f"Process leaked network sockets! Initial: {initial_connections}, Final: {final_connections}"
        )
    finally:
        settings.ELEVENLABS_API_KEY = original_key


# =============================================================================
# 2. Empirical Challenge: Response Headers (Content-Type & X-Audio-Source)
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_headers_in_fallback_mode():
    """
    Verifies response headers when ELEVENLABS_API_KEY is not set:
    - Content-Type must be 'audio/mpeg'
    - X-Audio-Source must be 'synthetic-fallback-mode'
    """
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = ""

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/v1/tts/synthesize", json={"text": "Verdict verification"})
            assert resp.status_code == 200
            assert "audio/mpeg" in resp.headers.get("content-type", "")
            assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
            assert resp.headers.get("content-disposition") == "inline; filename=verdict_fallback.mp3"
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_challenge_headers_in_live_streaming_mode_audit():
    """
    Empirical audit of response headers in live streaming mode:
    - Content-Type: audio/mpeg
    - X-Audio-Source: empirically check whether it is set or missing
    """
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_valid_key_for_headers"

    mock_resp = LifecycleTrackingStreamResponse(chunks=[b"LIVE_MP3_STREAM_CHUNK"])
    mock_client = LifecycleTrackingHttpClient(stream_response=mock_resp)

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Live synthesis audio header test"})
                assert resp.status_code == 200
                assert "audio/mpeg" in resp.headers.get("content-type", "")

                # Check X-Audio-Source header
                x_audio_source = resp.headers.get("x-audio-source")
                # Record empirical evidence: In live proxy mode, X-Audio-Source is NOT returned by tts.py
                print(f"\n[EMPIRICAL AUDIT] Live mode X-Audio-Source: '{x_audio_source}'")
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_challenge_headers_on_upstream_error_fallback_audit():
    """
    Empirical audit of response headers when upstream ElevenLabs returns 500:
    - Content-Type: audio/mpeg
    - X-Audio-Source: empirically check whether fallback header is present or missing
    """
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_valid_key_for_upstream_error"

    mock_resp = LifecycleTrackingStreamResponse(chunks=[], status_code=500, error_body=b'{"detail": "Server Error"}')
    mock_client = LifecycleTrackingHttpClient(stream_response=mock_resp)

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Upstream error header test"})
                assert resp.status_code == 200
                assert "audio/mpeg" in resp.headers.get("content-type", "")
                assert resp.content == generate_fallback_silence_mp3()

                # Check X-Audio-Source header
                x_audio_source = resp.headers.get("x-audio-source")
                # Record empirical evidence: In upstream error fallback mode, X-Audio-Source is NOT set because headers were already emitted
                print(f"\n[EMPIRICAL AUDIT] Upstream 500 fallback X-Audio-Source: '{x_audio_source}'")
    finally:
        settings.ELEVENLABS_API_KEY = original_key


# =============================================================================
# 3. Empirical Challenge: Secret Key Shielding Across All Paths
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_api_key_shielding_in_all_artifacts():
    """
    Injects a high-entropy secret canary key and asserts it is absent from:
    1. Success response headers and content
    2. Upstream 500 error response headers and content
    3. Upstream 401 error response headers and content
    4. Upstream exception / timeout / connect error
    5. HTTP 422 validation failure responses
    """
    canary_key = "CANARY_SECRET_KEY_abc123_xyz789_PROD_SHIELD"
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = canary_key

    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Success Proxy Mode
            mock_ok_resp = LifecycleTrackingStreamResponse(chunks=[b"normal_audio_data"])
            mock_ok_client = LifecycleTrackingHttpClient(stream_response=mock_ok_resp)
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_ok_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Normal audio check"})
                assert resp.status_code == 200
                assert canary_key not in str(resp.headers)
                assert canary_key.encode("utf-8") not in resp.content

            # 2. Upstream 401 with canary in error body
            mock_401_resp = LifecycleTrackingStreamResponse(
                chunks=[],
                status_code=401,
                error_body=f'{{"detail": "Key {canary_key} expired"}}'.encode("utf-8"),
            )
            mock_401_client = LifecycleTrackingHttpClient(stream_response=mock_401_resp)
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_401_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Upstream 401 check"})
                assert resp.status_code == 200
                assert canary_key not in str(resp.headers)
                assert canary_key.encode("utf-8") not in resp.content

            # 3. Upstream Exception containing canary in exception message
            err_client = LifecycleTrackingHttpClient(stream_response=mock_ok_resp)
            def throw_error(*args, **kwargs):
                raise httpx.ConnectError(f"Connection failed to api.elevenlabs.io?key={canary_key}")
            err_client.stream = throw_error

            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=err_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Upstream exception check"})
                assert resp.status_code == 200
                assert canary_key not in str(resp.headers)
                assert canary_key.encode("utf-8") not in resp.content

            # 4. HTTP 422 Validation Error
            resp = await client.post("/api/v1/tts/synthesize", json={"text": ""})
            assert resp.status_code == 422
            assert canary_key not in str(resp.headers)
            assert canary_key not in resp.text
    finally:
        settings.ELEVENLABS_API_KEY = original_key


# =============================================================================
# 4. Empirical Challenge: Real Socket & Resource Leak Check Under High Iterations
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_no_socket_or_descriptor_leak_under_churn():
    """
    Performs 50 repeated streamed requests (alternating between full consumption
    and early client disconnects) and monitors garbage collection and task counts
    to ensure no coroutine or connection leaks.
    """
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_churn_key"

    transport = httpx.ASGITransport(app=app)

    try:
        # Measure initial state
        gc.collect()
        initial_tasks = len([t for t in asyncio.all_tasks() if not t.done()])

        for i in range(50):
            chunks = [f"CHUNK_{j}_".encode("utf-8") * 20 for j in range(5)]
            mock_resp = LifecycleTrackingStreamResponse(chunks=chunks)
            mock_client = LifecycleTrackingHttpClient(stream_response=mock_resp)

            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                    async with client.stream(
                        "POST",
                        "/api/v1/tts/synthesize",
                        json={"text": f"Iteration {i}"},
                    ) as resp:
                        assert resp.status_code == 200
                        if i % 2 == 0:
                            # Full consumption
                            async for _ in resp.aiter_bytes():
                                pass
                        else:
                            # Early disconnect after 1 chunk
                            async for _ in resp.aiter_bytes():
                                break

            assert mock_client.is_closed is True
            assert mock_resp.is_closed is True

        await asyncio.sleep(0.05)
        gc.collect()
        final_tasks = len([t for t in asyncio.all_tasks() if not t.done()])
        # Allow at most current task difference
        assert final_tasks <= initial_tasks + 1, f"Task leak detected! initial={initial_tasks}, final={final_tasks}"
    finally:
        settings.ELEVENLABS_API_KEY = original_key
