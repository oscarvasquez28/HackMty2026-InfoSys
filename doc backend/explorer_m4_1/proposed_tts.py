"""
Speech Synthesis Proxy & Security Hardening Module.

Proxies speech synthesis to ElevenLabs API streaming endpoint (audio/mpeg),
shielding the ELEVENLABS_API_KEY from exposure on the client side.
Provides resilient graceful fallback to synthetic silent MPEG-1 Layer 3 frames
under all failure conditions (missing credentials, authentication errors,
rate limits, upstream 5xx outages, and network/timeout exceptions).
Handles client disconnects (asyncio.CancelledError) cleanly during chunk streaming.
"""

import asyncio
import io
import logging
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx

from backend.core.config import settings

logger = logging.getLogger("backend.api.routes.tts")

router = APIRouter(prefix="/tts", tags=["tts"])


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Text to synthesize to speech")
    voice_id: Optional[str] = Field(None, description="ElevenLabs Voice ID")
    model_id: Optional[str] = Field(None, description="ElevenLabs Model ID")


def generate_fallback_silence_mp3() -> bytes:
    """
    Generates a valid minimal MPEG audio frame sequence (silent audio) as a fallback
    when no ElevenLabs API key is configured or when upstream synthesis fails.
    Prevents front-end HTML5 audio element and Web Audio API decoder crashes.

    Binary Format Specification:
    - Standard: MPEG-1 Layer III (MP3), 128 kbps, 44.1 kHz, Joint Stereo, No CRC
    - Frame Header: 0xFF 0xFB 0x90 0x64 (4 bytes)
    - Payload: 28 zeroed bytes (silent frequency subbands)
    - Total: 32 bytes per frame * 10 frames = 320 bytes
    """
    silent_mp3_frame = (
        b"\xff\xfb\x90\x64\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        * 10
    )
    return silent_mp3_frame


def create_fallback_streaming_response(reason: str = "Fallback synthetic audio") -> StreamingResponse:
    """
    Constructs a valid HTTP 200 StreamingResponse containing the 320-byte
    synthetic silent MP3 fallback with X-Audio-Source: synthetic-fallback-mode.
    """
    logger.info("Emitting synthetic fallback silence MP3 (%s)", reason)

    async def fallback_stream():
        yield generate_fallback_silence_mp3()

    return StreamingResponse(
        fallback_stream(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=verdict_fallback.mp3",
            "Cache-Control": "no-cache",
            "X-Audio-Source": "synthetic-fallback-mode",
        },
    )


async def stream_elevenlabs_audio(
    text: str,
    voice_id: str,
    model_id: str,
    timeout: Optional[httpx.Timeout] = None,
) -> AsyncGenerator[bytes, None]:
    """
    Streams audio bytes directly from ElevenLabs TTS API.
    Designed for standalone programmatic usage with graceful error fallback
    and client cancellation protection.
    """
    if timeout is None:
        timeout = httpx.Timeout(
            connect=getattr(settings, "TTS_CONNECT_TIMEOUT", 5.0),
            read=getattr(settings, "TTS_TIMEOUT", 30.0),
            write=10.0,
            pool=5.0,
        )

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": settings.ELEVENLABS_API_KEY,
    }
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }

    client = httpx.AsyncClient(timeout=timeout)
    response = None
    try:
        req = client.build_request("POST", url, headers=headers, json=payload)
        response = await client.send(req, stream=True)
        if response.status_code != 200:
            error_body = await response.aread()
            logger.warning(
                "ElevenLabs TTS API returned status %s: %s. Yielding fallback silence frame.",
                response.status_code,
                error_body.decode("utf-8", errors="ignore"),
            )
            yield generate_fallback_silence_mp3()
            return

        async for chunk in response.aiter_bytes():
            if chunk:
                yield chunk
    except (asyncio.CancelledError, GeneratorExit):
        logger.info("Client disconnected during ElevenLabs audio stream.")
        raise
    except (httpx.HTTPError, httpx.TimeoutException, Exception) as exc:
        logger.warning("Error during ElevenLabs audio streaming: %s. Yielding fallback silence frame.", exc)
        yield generate_fallback_silence_mp3()
    finally:
        if response is not None:
            await response.aclose()
        await client.aclose()


@router.post("/synthesize")
async def synthesize_speech(request: SynthesizeRequest):
    """
    Proxy endpoint to synthesize speech via ElevenLabs in streaming mode (audio/mpeg).
    Shields the ELEVENLABS_API_KEY from exposure on the client side.

    Hardened Resilience:
    1. If ELEVENLABS_API_KEY is unset, empty, or placeholder ('your_*'), returns
       synthetic silent MP3 with header `X-Audio-Source: synthetic-fallback-mode`.
    2. Probes upstream connection with configured granular timeout (5s connect, 30s read).
    3. If upstream returns non-200 (401 invalid key, 429 quota, 500 outage) or raises
       httpx.HTTPError/httpx.TimeoutException, gracefully falls back to synthetic silence MP3
       with header `X-Audio-Source: synthetic-fallback-mode` instead of returning HTTP 500.
    4. If client disconnects mid-stream (asyncio.CancelledError / GeneratorExit), catches
       cleanly, logs disconnect event, and closes all upstream sockets.
    """
    voice_id = request.voice_id or settings.ELEVENLABS_VOICE_ID
    model_id = request.model_id or settings.ELEVENLABS_MODEL_ID

    # 1. Check for unconfigured / placeholder credentials
    if not settings.ELEVENLABS_API_KEY or settings.ELEVENLABS_API_KEY.startswith("your_"):
        return create_fallback_streaming_response("API key unconfigured or placeholder")

    # 2. Granular timeout configuration
    connect_timeout = getattr(settings, "TTS_CONNECT_TIMEOUT", 5.0)
    read_timeout = getattr(settings, "TTS_TIMEOUT", 30.0)
    timeout = httpx.Timeout(
        connect=connect_timeout,
        read=read_timeout,
        write=10.0,
        pool=5.0,
    )

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": settings.ELEVENLABS_API_KEY,
    }
    payload = {
        "text": request.text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }

    # 3. Probe upstream connection before initiating client response
    client = httpx.AsyncClient(timeout=timeout)
    try:
        req = client.build_request("POST", url, headers=headers, json=payload)
        response = await client.send(req, stream=True)
        if response.status_code != 200:
            error_body = await response.aread()
            logger.warning(
                "ElevenLabs upstream error (HTTP %s): %s. Falling back to synthetic silence MP3.",
                response.status_code,
                error_body.decode("utf-8", errors="ignore"),
            )
            await response.aclose()
            await client.aclose()
            return create_fallback_streaming_response(f"Upstream HTTP {response.status_code}")
    except (httpx.HTTPError, httpx.TimeoutException, Exception) as exc:
        logger.warning(
            "ElevenLabs request failed (%s: %s). Falling back to synthetic silence MP3.",
            type(exc).__name__,
            exc,
        )
        await client.aclose()
        return create_fallback_streaming_response(f"Upstream exception: {type(exc).__name__}")

    # 4. Stream verified live chunks with cancellation & disconnect handling
    async def live_audio_stream():
        try:
            async for chunk in response.aiter_bytes():
                if chunk:
                    yield chunk
        except (asyncio.CancelledError, GeneratorExit):
            logger.info("Client disconnected during live TTS audio streaming.")
            raise
        except Exception as exc:
            logger.warning("Error while streaming live audio chunks from ElevenLabs: %s", exc)
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        live_audio_stream(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=verdict.mp3",
            "Cache-Control": "no-cache",
            "X-Audio-Source": "elevenlabs",
        },
    )
