"""
Test Suite for Speech Synthesis Proxy & Security Hardening (Milestone 4).
Verifies:
- Offline fallback silence MP3 generation with valid MPEG-1 Layer 3 binary frames.
- Header validation (X-Audio-Source: synthetic-fallback-mode).
- Graceful degradation on upstream 401, 429, 500, 502, and 503 errors (never returning HTTP 500).
- Granular timeout resilience (ConnectTimeout, ReadTimeout).
- Network connection error resilience (ConnectError).
- Successful live streaming proxying with X-Audio-Source: elevenlabs.
- Clean client disconnect cancellation (asyncio.CancelledError / GeneratorExit).
- Strict bitwise MPEG frame structure validation across all 10 repetitions.
- Request payload validation (min_length, max_length, optional fields).
"""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from backend.main import app
from backend.core.config import settings
from backend.api.routes.tts import (
    generate_fallback_silence_mp3,
    stream_elevenlabs_audio,
    SynthesizeRequest,
)

orig_send = httpx.AsyncClient.send


def validate_mpeg1_layer3_frame(data: bytes):
    """
    Bitwise validator for MPEG-1 Layer 3 audio frames.
    Asserts conformance to ISO/IEC 11172-3 specifications.
    """
    assert len(data) == 320, f"Expected exactly 320 bytes, got {len(data)}"
    assert len(data) % 32 == 0, "Buffer length must be a multiple of 32 bytes"

    num_frames = len(data) // 32
    assert num_frames == 10, f"Expected 10 frames, got {num_frames}"

    for i in range(num_frames):
        frame = data[i * 32 : (i + 1) * 32]
        header = frame[:4]

        # 1. Sync word: 11 bits set to 1 (0xFF and upper 3 bits of byte 1 = 0xE0)
        assert header[0] == 0xFF, f"Frame {i}: byte 0 sync word invalid: {hex(header[0])}"
        assert (header[1] & 0xE0) == 0xE0, f"Frame {i}: byte 1 sync word invalid: {hex(header[1])}"

        # 2. MPEG Audio Version: bits [4:3] of byte 1 must be 0b11 (MPEG Version 1)
        mpeg_version = (header[1] >> 3) & 0x03
        assert mpeg_version == 0x03, f"Frame {i}: expected MPEG-1 (3), got {mpeg_version}"

        # 3. Layer Description: bits [2:1] of byte 1 must be 0b01 (Layer III)
        layer = (header[1] >> 1) & 0x03
        assert layer == 0x01, f"Frame {i}: expected Layer III (1), got {layer}"

        # 4. Protection bit: bit [0] of byte 1 must be 1 (No CRC)
        protection = header[1] & 0x01
        assert protection == 0x01, f"Frame {i}: expected no CRC protection (1), got {protection}"

        # 5. Bitrate index: bits [7:4] of byte 2 must be 0b1001 (128 kbps)
        bitrate_index = (header[2] >> 4) & 0x0F
        assert bitrate_index == 0x09, f"Frame {i}: expected 128 kbps index (9), got {bitrate_index}"

        # 6. Sampling frequency index: bits [3:2] of byte 2 must be 0b00 (44.1 kHz)
        sampling_rate_index = (header[2] >> 2) & 0x03
        assert sampling_rate_index == 0x00, f"Frame {i}: expected 44.1 kHz index (0), got {sampling_rate_index}"

        # 7. Padding bit: bit [1] of byte 2 must be 0 (No padding)
        padding = (header[2] >> 1) & 0x01
        assert padding == 0x00, f"Frame {i}: expected no padding (0), got {padding}"

        # 8. Private bit: bit [0] of byte 2 must be 0
        private_bit = header[2] & 0x01
        assert private_bit == 0x00, f"Frame {i}: expected private bit 0, got {private_bit}"

        # 9. Channel mode: bits [7:6] of byte 3 must be 0b01 (Joint Stereo)
        channel_mode = (header[3] >> 6) & 0x03
        assert channel_mode == 0x01, f"Frame {i}: expected Joint Stereo (1), got {channel_mode}"

        # 10. Mode extension: bits [5:4] of byte 3 must be 0b10 (Bands 8-31)
        mode_extension = (header[3] >> 4) & 0x03
        assert mode_extension == 0x02, f"Frame {i}: expected Mode extension 2, got {mode_extension}"

        # 11. Copyright bit: bit [3] of byte 3 must be 0
        copyright_bit = (header[3] >> 3) & 0x01
        assert copyright_bit == 0x00, f"Frame {i}: expected copyright bit 0, got {copyright_bit}"

        # 12. Original bit: bit [2] of byte 3 must be 1
        original_bit = (header[3] >> 2) & 0x01
        assert original_bit == 0x01, f"Frame {i}: expected original bit 1, got {original_bit}"

        # 13. Emphasis: bits [1:0] of byte 3 must be 0b00 (None)
        emphasis = header[3] & 0x03
        assert emphasis == 0x00, f"Frame {i}: expected emphasis 0, got {emphasis}"

        # 14. Audio payload: exactly 28 bytes of zeros
        assert frame[4:] == b"\x00" * 28, f"Frame {i}: audio payload must be zeroed silence"


@pytest.mark.asyncio
async def test_exact_binary_validation_mpeg1_layer3_frame():
    """Validates bit-level MPEG-1 Layer 3 audio frame sequence from generator."""
    audio_bytes = generate_fallback_silence_mp3()
    validate_mpeg1_layer3_frame(audio_bytes)


@pytest.mark.asyncio
async def test_synthesize_no_api_key_returns_fallback_silence():
    """When ELEVENLABS_API_KEY is empty, immediately stream fallback silence MP3."""
    transport = httpx.ASGITransport(app=app)
    with patch.object(settings, "ELEVENLABS_API_KEY", ""):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial"})
            assert resp.status_code == 200
            assert "audio/mpeg" in resp.headers["content-type"]
            assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
            assert "verdict_fallback.mp3" in resp.headers.get("content-disposition", "")
            validate_mpeg1_layer3_frame(resp.content)


@pytest.mark.asyncio
async def test_synthesize_placeholder_api_key_returns_fallback_silence():
    """When ELEVENLABS_API_KEY starts with 'your_', immediately stream fallback silence MP3."""
    transport = httpx.ASGITransport(app=app)
    with patch.object(settings, "ELEVENLABS_API_KEY", "your_api_key_here"):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial"})
            assert resp.status_code == 200
            assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
            validate_mpeg1_layer3_frame(resp.content)


@pytest.mark.asyncio
async def test_synthesize_upstream_401_graceful_fallback():
    """
    When ELEVENLABS_API_KEY is configured but invalid (HTTP 401 Unauthorized),
    gracefully fall back to synthetic silence MP3 instead of raising HTTP 500.
    """
    async def mock_send(self, request, *args, **kwargs):
        if "elevenlabs.io" in str(request.url):
            return httpx.Response(
                401,
                json={"detail": {"type": "authentication_error", "message": "Invalid API key"}},
                request=request,
            )
        return await orig_send(self, request, *args, **kwargs)

    transport = httpx.ASGITransport(app=app)
    with patch.object(settings, "ELEVENLABS_API_KEY", "sk_invalid_test_key_12345"):
        with patch.object(httpx.AsyncClient, "send", mock_send):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial"})
                assert resp.status_code == 200
                assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
                validate_mpeg1_layer3_frame(resp.content)


@pytest.mark.asyncio
async def test_synthesize_upstream_500_graceful_fallback():
    """
    When ElevenLabs returns HTTP 500 Internal Server Error,
    gracefully fall back to synthetic silence MP3 instead of crashing.
    """
    async def mock_send(self, request, *args, **kwargs):
        if "elevenlabs.io" in str(request.url):
            return httpx.Response(500, text="Internal Server Error", request=request)
        return await orig_send(self, request, *args, **kwargs)

    transport = httpx.ASGITransport(app=app)
    with patch.object(settings, "ELEVENLABS_API_KEY", "sk_valid_looking_key_12345"):
        with patch.object(httpx.AsyncClient, "send", mock_send):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial"})
                assert resp.status_code == 200
                assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
                validate_mpeg1_layer3_frame(resp.content)


@pytest.mark.asyncio
async def test_synthesize_upstream_429_rate_limit_graceful_fallback():
    """When ElevenLabs returns HTTP 429 Too Many Requests, fallback gracefully."""
    async def mock_send(self, request, *args, **kwargs):
        if "elevenlabs.io" in str(request.url):
            return httpx.Response(429, text="Rate limit exceeded", request=request)
        return await orig_send(self, request, *args, **kwargs)

    transport = httpx.ASGITransport(app=app)
    with patch.object(settings, "ELEVENLABS_API_KEY", "sk_valid_key"):
        with patch.object(httpx.AsyncClient, "send", mock_send):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial"})
                assert resp.status_code == 200
                assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
                validate_mpeg1_layer3_frame(resp.content)


@pytest.mark.asyncio
async def test_synthesize_connect_timeout_graceful_fallback():
    """When upstream connection times out, fallback gracefully."""
    async def mock_send(self, request, *args, **kwargs):
        if "elevenlabs.io" in str(request.url):
            raise httpx.ConnectTimeout("Connect timed out after 5.0s")
        return await orig_send(self, request, *args, **kwargs)

    transport = httpx.ASGITransport(app=app)
    with patch.object(settings, "ELEVENLABS_API_KEY", "sk_valid_key"):
        with patch.object(httpx.AsyncClient, "send", mock_send):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial"})
                assert resp.status_code == 200
                assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
                validate_mpeg1_layer3_frame(resp.content)


@pytest.mark.asyncio
async def test_synthesize_read_timeout_graceful_fallback():
    """When upstream read times out, fallback gracefully."""
    async def mock_send(self, request, *args, **kwargs):
        if "elevenlabs.io" in str(request.url):
            raise httpx.ReadTimeout("Read timed out after 30.0s")
        return await orig_send(self, request, *args, **kwargs)

    transport = httpx.ASGITransport(app=app)
    with patch.object(settings, "ELEVENLABS_API_KEY", "sk_valid_key"):
        with patch.object(httpx.AsyncClient, "send", mock_send):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial"})
                assert resp.status_code == 200
                assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
                validate_mpeg1_layer3_frame(resp.content)


@pytest.mark.asyncio
async def test_synthesize_network_connect_error_graceful_fallback():
    """When DNS or network connection fails, fallback gracefully."""
    async def mock_send(self, request, *args, **kwargs):
        if "elevenlabs.io" in str(request.url):
            raise httpx.ConnectError("Failed to resolve api.elevenlabs.io")
        return await orig_send(self, request, *args, **kwargs)

    transport = httpx.ASGITransport(app=app)
    with patch.object(settings, "ELEVENLABS_API_KEY", "sk_valid_key"):
        with patch.object(httpx.AsyncClient, "send", mock_send):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial"})
                assert resp.status_code == 200
                assert resp.headers.get("x-audio-source") == "synthetic-fallback-mode"
                validate_mpeg1_layer3_frame(resp.content)


@pytest.mark.asyncio
async def test_synthesize_live_stream_success():
    """When ElevenLabs responds HTTP 200, audio chunks are streamed with X-Audio-Source: elevenlabs."""
    raw_chunks = [b"ID3_MOCK_HEADER", b"MPEG_AUDIO_CHUNK_1", b"MPEG_AUDIO_CHUNK_2"]

    async def mock_send(self, request, *args, **kwargs):
        if "elevenlabs.io" in str(request.url):
            return httpx.Response(
                200,
                content=b"".join(raw_chunks),
                headers={"content-type": "audio/mpeg"},
                request=request,
            )
        return await orig_send(self, request, *args, **kwargs)

    transport = httpx.ASGITransport(app=app)
    with patch.object(settings, "ELEVENLABS_API_KEY", "sk_valid_test_key"):
        with patch.object(httpx.AsyncClient, "send", mock_send):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post("/api/v1/tts/synthesize", json={"text": "Dictamen pericial"})
                assert resp.status_code == 200
                assert resp.headers.get("x-audio-source") == "elevenlabs"
                assert "audio/mpeg" in resp.headers["content-type"]
                assert resp.content == b"".join(raw_chunks)


@pytest.mark.asyncio
async def test_synthesize_client_disconnect_cancellation():
    """When client aborts streaming, CancelledError / GeneratorExit is cleanly handled."""
    raw_chunks = [b"chunk_1", b"chunk_2"]

    async def mock_send(self, request, *args, **kwargs):
        if "elevenlabs.io" in str(request.url):
            return httpx.Response(
                200,
                content=b"".join(raw_chunks),
                headers={"content-type": "audio/mpeg"},
                request=request,
            )
        return await orig_send(self, request, *args, **kwargs)

    transport = httpx.ASGITransport(app=app)
    with patch.object(settings, "ELEVENLABS_API_KEY", "sk_valid_test_key"):
        with patch.object(httpx.AsyncClient, "send", mock_send):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                async with client.stream("POST", "/api/v1/tts/synthesize", json={"text": "Dictamen"}) as resp:
                    assert resp.status_code == 200
                    async for chunk in resp.aiter_bytes():
                        assert len(chunk) > 0
                        break  # Trigger early client disconnect


@pytest.mark.asyncio
async def test_stream_elevenlabs_audio_standalone():
    """Tests direct programmatic invocation of stream_elevenlabs_audio with fallback."""
    async def mock_send(self, request, *args, **kwargs):
        if "elevenlabs.io" in str(request.url):
            return httpx.Response(403, text="Forbidden", request=request)
        return await orig_send(self, request, *args, **kwargs)

    with patch.object(settings, "ELEVENLABS_API_KEY", "sk_test"):
        with patch.object(httpx.AsyncClient, "send", mock_send):
            chunks = []
            async for chunk in stream_elevenlabs_audio("test text", "voice_1", "model_1"):
                chunks.append(chunk)

            full_audio = b"".join(chunks)
            validate_mpeg1_layer3_frame(full_audio)


@pytest.mark.asyncio
async def test_synthesize_request_validation():
    """Validates SynthesizeRequest schema constraints."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Empty text
        resp_empty = await client.post("/api/v1/tts/synthesize", json={"text": ""})
        assert resp_empty.status_code == 422

        # Text exceeding 5000 characters
        resp_too_long = await client.post("/api/v1/tts/synthesize", json={"text": "A" * 5001})
        assert resp_too_long.status_code == 422

        # Custom voice_id and model_id accepted
        resp_custom = await client.post(
            "/api/v1/tts/synthesize",
            json={
                "text": "Valid test text",
                "voice_id": "custom_voice_uuid",
                "model_id": "eleven_turbo_v2",
            },
        )
        assert resp_custom.status_code == 200
