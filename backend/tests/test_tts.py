"""
Automated Test Suite for Milestone 4:
Speech Synthesis Proxy & Security Hardening (backend/tests/test_tts.py).

Verifies:
1. Fallback mode when ELEVENLABS_API_KEY is None, empty, or default 'your_...'
2. Valid minimal silent MPEG audio frame binary structure (320 bytes, MPEG-1 Layer 3)
3. Proxy streaming mode with mocked 200 streaming response from ElevenLabs (default & custom voice/model)
4. Upstream failure fallback (upstream 500, 401, 429, timeout, connection drop) gracefully yielding silent audio with HTTP 200
5. Request validation (empty text 422, missing text 422, text exceeding 5000 chars 422, valid boundary lengths 1 and 5000)
6. Security shielding: ELEVENLABS_API_KEY is never exposed in response headers or body
"""

import asyncio
from typing import AsyncGenerator, List, Optional
from unittest.mock import patch
import httpx
import pytest

from backend.api.routes.tts import generate_fallback_silence_mp3
from backend.core.config import settings
from backend.main import app


# =============================================================================
# Test Helpers & Mock Structures
# =============================================================================

class MockStreamResponse:
    """Simulates an upstream httpx streaming response."""

    def __init__(
        self,
        status_code: int = 200,
        chunks: Optional[List[bytes]] = None,
        error_body: bytes = b'{"detail": "Upstream error"}',
        headers: Optional[dict] = None,
    ):
        self.status_code = status_code
        self.chunks = chunks if chunks is not None else [b"dummy_mp3_chunk"]
        self.error_body = error_body
        self.headers = headers or {"content-type": "audio/mpeg"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def aiter_bytes(self) -> AsyncGenerator[bytes, None]:
        for chunk in self.chunks:
            yield chunk

    async def aread(self) -> bytes:
        return self.error_body


class MockAsyncHttpClient:
    """Mock httpx.AsyncClient capturing outbound calls and returning controlled responses."""

    def __init__(
        self,
        resp: Optional[MockStreamResponse] = None,
        exc: Optional[Exception] = None,
    ):
        self.resp = resp or MockStreamResponse(200)
        self.exc = exc
        self.calls: List[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def stream(self, method: str, url: str, **kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        if self.exc:
            raise self.exc
        return self.resp


# =============================================================================
# 1. Fallback Mode Tests (No API Key or Default 'your_...' Placeholder)
# =============================================================================

@pytest.mark.asyncio
async def test_tts_fallback_when_api_key_is_empty():
    """Validates fallback to synthetic silent audio when ELEVENLABS_API_KEY is empty."""
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = ""
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial."})
            assert resp.status_code == 200
            assert "audio/mpeg" in resp.headers["content-type"]
            assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
            assert resp.headers.get("content-disposition") == "inline; filename=verdict_fallback.mp3"
            assert resp.content == generate_fallback_silence_mp3()
            assert len(resp.content) == 320
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_tts_fallback_when_api_key_is_none():
    """Validates fallback to synthetic silent audio when ELEVENLABS_API_KEY is None."""
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = None
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial."})
            assert resp.status_code == 200
            assert "audio/mpeg" in resp.headers["content-type"]
            assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
            assert resp.content == generate_fallback_silence_mp3()
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_tts_fallback_when_api_key_is_default_placeholder():
    """Validates fallback to synthetic silent audio when ELEVENLABS_API_KEY starts with 'your_'."""
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "your_elevenlabs_api_key_placeholder"
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial."})
            assert resp.status_code == 200
            assert "audio/mpeg" in resp.headers["content-type"]
            assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
            assert resp.content == generate_fallback_silence_mp3()
            assert len(resp.content) == 320
    finally:
        settings.ELEVENLABS_API_KEY = original_key


def test_synthetic_silent_mp3_frame_structure():
    """Verifies binary structure of the synthetic silent MP3 fallback (MPEG-1 Layer 3, 128kbps, 44.1kHz)."""
    silent_bytes = generate_fallback_silence_mp3()
    # 10 frames of 32 bytes each = 320 bytes
    assert len(silent_bytes) == 320
    # MPEG-1 Layer 3 sync word: 0xFF, 0xFB
    assert silent_bytes[0] == 0xFF
    assert silent_bytes[1] == 0xFB
    # Periodic repetition of 32-byte frames
    single_frame = silent_bytes[:32]
    assert silent_bytes == single_frame * 10

    # Detailed bitwise frame verification
    header = single_frame[:4]
    # Sync word 11 bits set: header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
    assert (header[1] & 0xE0) == 0xE0
    # MPEG-1 Audio Version: bits [4:3] == 0b11
    assert ((header[1] >> 3) & 0x03) == 0x03
    # Layer III: bits [2:1] == 0b01
    assert ((header[1] >> 1) & 0x03) == 0x01
    # No CRC protection: bit [0] == 1
    assert (header[1] & 0x01) == 0x01
    # 128 kbps bitrate: bits [7:4] == 0b1001 (9)
    assert ((header[2] >> 4) & 0x0F) == 0x09
    # 44.1 kHz sampling rate: bits [3:2] == 0b00 (0)
    assert ((header[2] >> 2) & 0x03) == 0x00
    # Joint stereo: bits [7:6] == 0b01 (1)
    assert ((header[3] >> 6) & 0x03) == 0x01
    # Payload: exactly 28 zero bytes
    assert single_frame[4:] == b"\x00" * 28


# =============================================================================
# 2. Proxy Streaming Mode Tests (Valid API Key & Upstream 200 OK)
# =============================================================================

@pytest.mark.asyncio
async def test_tts_proxy_success_default_voice_and_model():
    """Tests successful proxy streaming to ElevenLabs with default voice and model settings."""
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_valid_elevenlabs_api_key"
    mock_chunks = [b"ID3_MPEG_HEADER_", b"AUDIO_DATA_PAYLOAD_CHUNK_1_", b"AUDIO_DATA_PAYLOAD_CHUNK_2"]
    mock_client = MockAsyncHttpClient(resp=MockStreamResponse(status_code=200, chunks=mock_chunks))

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                payload = {"text": "A money laundering cycle was identified between Account A and Account B."}
                resp = await client.post("/api/v1/tts/synthesize", json=payload)

                assert resp.status_code == 200
                assert "audio/mpeg" in resp.headers["content-type"]
                assert resp.headers.get("content-disposition") == "inline; filename=verdict.mp3"
                assert resp.headers.get("cache-control") == "no-cache"
                assert resp.content == b"".join(mock_chunks)

                # Verify outbound request to ElevenLabs
                assert len(mock_client.calls) == 1
                outbound = mock_client.calls[0]
                expected_url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}/stream"
                assert outbound["url"] == expected_url
                assert outbound["kwargs"]["headers"]["xi-api-key"] == "test_valid_elevenlabs_api_key"
                assert outbound["kwargs"]["headers"]["Accept"] == "audio/mpeg"
                assert outbound["kwargs"]["json"]["model_id"] == settings.ELEVENLABS_MODEL_ID
                assert outbound["kwargs"]["json"]["text"] == payload["text"]
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_tts_proxy_success_custom_voice_and_model():
    """Tests proxy streaming with custom voice_id and model_id provided in request body."""
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_valid_elevenlabs_api_key"
    custom_voice = "custom_forensic_voice_id_99"
    custom_model = "eleven_turbo_v2_custom"
    mock_chunks = [b"CUSTOM_VOICE_AUDIO_DATA"]
    mock_client = MockAsyncHttpClient(resp=MockStreamResponse(status_code=200, chunks=mock_chunks))

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                payload = {
                    "text": "Dictamen pericial especial.",
                    "voice_id": custom_voice,
                    "model_id": custom_model,
                }
                resp = await client.post("/api/v1/tts/synthesize", json=payload)

                assert resp.status_code == 200
                assert resp.content == b"CUSTOM_VOICE_AUDIO_DATA"

                # Verify custom URL parameters
                outbound = mock_client.calls[0]
                assert outbound["url"] == f"https://api.elevenlabs.io/v1/text-to-speech/{custom_voice}/stream"
                assert outbound["kwargs"]["json"]["model_id"] == custom_model
    finally:
        settings.ELEVENLABS_API_KEY = original_key


# =============================================================================
# 3. Upstream Failure Fallback Tests (HTTP 200 with Silent Audio)
# =============================================================================

@pytest.mark.asyncio
async def test_tts_upstream_500_fallback_to_silent_mp3():
    """Verifies that upstream 500 from ElevenLabs falls back gracefully to silent MP3 with HTTP 200."""
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_valid_elevenlabs_api_key"
    mock_client = MockAsyncHttpClient(
        resp=MockStreamResponse(status_code=500, error_body=b'{"detail": "Internal Server Error in ElevenLabs"}')
    )

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Test upstream 500 error."})
                assert resp.status_code == 200
                assert "audio/mpeg" in resp.headers["content-type"]
                assert resp.content == generate_fallback_silence_mp3()
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_tts_upstream_401_fallback_to_silent_mp3():
    """Verifies that upstream 401 Unauthorized from ElevenLabs falls back gracefully with HTTP 200."""
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "expired_or_invalid_api_key"
    mock_client = MockAsyncHttpClient(
        resp=MockStreamResponse(status_code=401, error_body=b'{"detail": "Invalid xi-api-key provided"}')
    )

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Test upstream 401 error."})
                assert resp.status_code == 200
                assert "audio/mpeg" in resp.headers["content-type"]
                assert resp.content == generate_fallback_silence_mp3()
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_tts_upstream_429_rate_limit_fallback():
    """Verifies that upstream 429 Too Many Requests falls back gracefully with HTTP 200."""
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_valid_elevenlabs_api_key"
    mock_client = MockAsyncHttpClient(
        resp=MockStreamResponse(status_code=429, error_body=b'{"detail": "Rate limit exceeded"}')
    )

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Test upstream rate limit."})
                assert resp.status_code == 200
                assert "audio/mpeg" in resp.headers["content-type"]
                assert resp.content == generate_fallback_silence_mp3()
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_tts_upstream_timeout_fallback():
    """Verifies that network timeout contacting ElevenLabs falls back gracefully with HTTP 200."""
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_valid_elevenlabs_api_key"
    mock_client = MockAsyncHttpClient(exc=httpx.TimeoutException("Connection timed out after 30.0s"))

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Test timeout fallback."})
                assert resp.status_code == 200
                assert "audio/mpeg" in resp.headers["content-type"]
                assert resp.content == generate_fallback_silence_mp3()
    finally:
        settings.ELEVENLABS_API_KEY = original_key


@pytest.mark.asyncio
async def test_tts_upstream_connect_error_fallback():
    """Verifies that DNS / connection refusal contacting ElevenLabs falls back gracefully with HTTP 200."""
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = "test_valid_elevenlabs_api_key"
    mock_client = MockAsyncHttpClient(exc=httpx.ConnectError("Failed to resolve api.elevenlabs.io"))

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Test connection error fallback."})
                assert resp.status_code == 200
                assert "audio/mpeg" in resp.headers["content-type"]
                assert resp.content == generate_fallback_silence_mp3()
    finally:
        settings.ELEVENLABS_API_KEY = original_key


# =============================================================================
# 4. Request Validation Tests (HTTP 422 Unprocessable Entity)
# =============================================================================

@pytest.mark.asyncio
async def test_tts_validation_empty_text():
    """Verifies HTTP 422 Unprocessable Entity when text is empty string."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/api/v1/tts/synthesize", json={"text": ""})
        assert resp.status_code == 422
        errors = resp.json()["detail"]
        assert any("text" in str(err.get("loc", [])) for err in errors)


@pytest.mark.asyncio
async def test_tts_validation_missing_text():
    """Verifies HTTP 422 Unprocessable Entity when text field is completely absent."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/api/v1/tts/synthesize", json={"voice_id": "rachel"})
        assert resp.status_code == 422
        errors = resp.json()["detail"]
        assert any("text" in str(err.get("loc", [])) for err in errors)


@pytest.mark.asyncio
async def test_tts_validation_exceeds_max_length():
    """Verifies HTTP 422 Unprocessable Entity when text exceeds 5000 characters."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/api/v1/tts/synthesize", json={"text": "A" * 5001})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tts_validation_boundary_valid_lengths():
    """Verifies that boundary valid text lengths (1 character and 5000 characters) succeed."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Minimum boundary: 1 character
        resp_min = await client.post("/api/v1/tts/synthesize", json={"text": "A"})
        assert resp_min.status_code == 200

        # Maximum boundary: 5000 characters
        resp_max = await client.post("/api/v1/tts/synthesize", json={"text": "B" * 5000})
        assert resp_max.status_code == 200


@pytest.mark.asyncio
async def test_tts_validation_non_string_text():
    """Verifies HTTP 422 Unprocessable Entity when text is not a string."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/api/v1/tts/synthesize", json={"text": 12345})
        assert resp.status_code == 422


# =============================================================================
# 5. Security & Secret Shielding Tests
# =============================================================================

@pytest.mark.asyncio
async def test_tts_security_key_never_leaked():
    """
    Verifies that the ELEVENLABS_API_KEY is shielded and never leaked to the client
    in response headers, response body, or error messages.
    """
    secret_key = "super_confidential_elevenlabs_api_key_xyz987"
    original_key = settings.ELEVENLABS_API_KEY
    settings.ELEVENLABS_API_KEY = secret_key
    mock_client = MockAsyncHttpClient(resp=MockStreamResponse(status_code=200, chunks=[b"legit_audio"]))

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("backend.api.routes.tts.httpx.AsyncClient", return_value=mock_client):
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Audit complete."})
                assert resp.status_code == 200
                assert secret_key not in str(resp.headers)
                assert secret_key not in resp.text
    finally:
        settings.ELEVENLABS_API_KEY = original_key

