import asyncio
import logging
from typing import Optional, AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["tts"])


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Text to synthesize to speech")
    voice_id: Optional[str] = Field(None, description="ElevenLabs Voice ID")
    model_id: Optional[str] = Field(None, description="ElevenLabs Model ID")


def generate_fallback_silence_mp3() -> bytes:
    """
    Generates a valid minimal MPEG audio frame (silent audio) as a fallback
    when no ElevenLabs API key is configured or when upstream fails,
    avoiding front-end player crashes.

    Binary Format Specification:
    - Standard: MPEG-1 Layer III (MP3), 128 kbps, 44.1 kHz, Joint Stereo, No CRC
    - Frame Header: 0xFF 0xFB 0x90 0x64 (4 bytes)
    - Payload: 28 zeroed bytes (silent frequency subbands)
    - Total: 32 bytes per frame * 10 frames = 320 bytes
    """
    # Valid minimal silent MP3 frame sequence (MPEG-1 Layer 3, 128kbps, 44.1kHz)
    silent_mp3_frame = (
        b"\xff\xfb\x90\x64\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        * 10
    )
    return silent_mp3_frame


async def stream_elevenlabs_audio(
    text: str, voice_id: str, model_id: str
) -> AsyncGenerator[bytes, None]:
    """
    Streams audio bytes directly from ElevenLabs TTS API.
    Gracefully falls back to silent MPEG audio on any upstream failure
    (500, 401, 429, timeout, connect error) so client audio playback never crashes.
    """
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

    timeout = httpx.Timeout(
        connect=getattr(settings, "TTS_CONNECT_TIMEOUT", 5.0),
        read=getattr(settings, "TTS_TIMEOUT", 30.0),
        write=10.0,
        pool=5.0,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    logger.warning(
                        "ElevenLabs TTS API returned status %s: %s. Gracefully falling back to silent MP3.",
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
    except Exception as exc:
        logger.warning(
            "ElevenLabs TTS network/connection failure (%s: %s). Gracefully falling back to silent MP3.",
            type(exc).__name__,
            exc,
        )
        yield generate_fallback_silence_mp3()


@router.post("/synthesize")
async def synthesize_speech(request: SynthesizeRequest):
    """
    Proxy endpoint to synthesize speech via ElevenLabs in streaming mode (audio/mpeg).
    Shields the ELEVENLABS_API_KEY from exposure on the client side.
    Falls back gracefully to synthetic silent audio when unconfigured or on upstream failure.
    """
    voice_id = request.voice_id or settings.ELEVENLABS_VOICE_ID
    model_id = request.model_id or settings.ELEVENLABS_MODEL_ID

    # If no key is provided or placeholder is used, return simulated audio stream
    if not settings.ELEVENLABS_API_KEY or settings.ELEVENLABS_API_KEY.startswith("your_"):
        async def fallback_stream():
            yield generate_fallback_silence_mp3()

        return StreamingResponse(
            fallback_stream(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=verdict_fallback.mp3",
                "X-Audio-Source": "synthetic-fallback-mode",
            },
        )

    return StreamingResponse(
        stream_elevenlabs_audio(request.text, voice_id, model_id),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=verdict.mp3",
            "Cache-Control": "no-cache",
        },
    )
