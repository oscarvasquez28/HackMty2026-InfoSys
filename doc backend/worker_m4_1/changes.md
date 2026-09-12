# Changes Summary: Milestone 4 (Speech Synthesis Proxy & Security Hardening)

## 1. `backend/core/config.py`
- Added `TTS_TIMEOUT: float = 30.0` to configure HTTP read timeout for speech synthesis requests.
- Added `TTS_CONNECT_TIMEOUT: float = 5.0` to configure fast failover connection timeout for speech synthesis upstream connections.

## 2. `backend/api/routes/tts.py`
- Shielded `ELEVENLABS_API_KEY` by keeping all upstream calls strictly server-side.
- Added structured logging for TTS operations, warnings, and errors.
- Resolved Starlette early-header streaming crash on upstream failure:
  - Wrapped `client.stream(...)` inside `stream_elevenlabs_audio` with exception handling and status checking.
  - If ElevenLabs returns non-200 (401, 429, 500, etc.), the generator logs the error and gracefully yields `generate_fallback_silence_mp3()`, avoiding raising an unhandled `HTTPException` after ASGI headers are already committed.
  - If connection/timeout exceptions occur (`httpx.TimeoutException`, `httpx.ConnectError`, etc.), the generator catches them and yields `generate_fallback_silence_mp3()`.
- Implemented client cancellation handling (`asyncio.CancelledError`, `GeneratorExit`): logs disconnect event and raises to let the async generator terminate and close context resources cleanly without leaks or unhandled errors.
- Enforced granular timeout using `settings.TTS_CONNECT_TIMEOUT` (5.0s) and `settings.TTS_TIMEOUT` (30.0s).
- Maintained synthetic silent MP3 generator producing 320 bytes of valid MPEG-1 Layer 3 audio frames (128kbps, 44.1kHz, Joint Stereo, 10 frames of 32 bytes) for unconfigured API key and upstream error resilience.
- Handled offline/demo fallback with `X-Audio-Source: synthetic-fallback-mode` when API key is None, empty, or default `your_...`.

## 3. `backend/tests/test_tts.py`
- Implemented comprehensive 17-test suite covering:
  - 4 Fallback & binary structure tests (empty key, None key, placeholder key, MPEG-1 Layer 3 15-attribute bitwise validation).
  - 2 Proxy streaming success tests (default voice/model and custom voice/model).
  - 5 Upstream failure resilience tests (500, 401, 429, timeout, connect error) verifying HTTP 200 and silent MP3 delivery.
  - 5 Request validation tests (empty text, missing text, >5000 chars, boundary lengths 1 and 5000 chars, non-string text).
  - 1 Security secret shielding test verifying `ELEVENLABS_API_KEY` is never leaked in headers or body.

