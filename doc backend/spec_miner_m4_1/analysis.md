# Specification Discovery & Architecture Analysis: Milestone 4
## Speech Synthesis Proxy & Security Specification

**Working Directory**: `.agents/spec_miner_m4_1`  
**Target Subsystem**: `backend/api/routes/tts.py` & `backend/core/config.py`  
**Milestone**: M4 — Speech Synthesis Proxy & Security Specification  
**Author**: Spec Miner (`spec_miner_m4_1`)  
**Date**: 2026-09-12  

---

## 1. Executive Summary

Milestone 4 governs the speech synthesis capabilities of the Forensic Auditor platform, enabling narration of final forensic audit verdicts (such as legal recommendations, detected money-laundering schemes, and confiscation advisories). The subsystem acts as a high-security reverse proxy between the client browser (`frontend/components/AudioPlayer.tsx` / `frontend/hooks/useAudioStream.ts`) and the upstream **ElevenLabs Text-to-Speech API**.

The service has two critical responsibilities:
1. **Security Gateway**: Shield the private `ELEVENLABS_API_KEY` from client exposure, enforce strict input boundaries on text and identifiers to eliminate SSRF, directory traversal, and HTTP header injection, and scrub credentials from all server logs and error stack traces.
2. **Offline & Upstream Resilience**: Guarantee continuous client playback without browser HTML5 audio element decoding crashes (`DOMException: NotSupportedError`) by transparently falling back to a valid, ISO/IEC 11172-3 compliant 320-byte synthetic silent MPEG-1 Layer 3 audio frame whenever credentials are absent, quota is exhausted, or upstream network failures occur.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | API Contract | `POST /api/v1/tts/synthesize` | Main entry point for converting verdict text to audio stream | JSON `{ text, voice_id?, model_id? }` | `audio/mpeg` binary stream | HTTP 422 for invalid payloads; HTTP 200 with fallback silence on upstream errors | `ORIGINAL_REQUEST.md` §R4, `backend/api/routes/tts.py` |
| 2 | Upstream Proxy | ElevenLabs Streaming Integration | Proxies real-time audio chunk stream from `api.elevenlabs.io` | `voice_id`, `model_id`, `text`, `voice_settings` | Chunked binary MP3 | Upstream non-200 captured and handled gracefully | `backend/api/routes/tts.py:33-65` |
| 3 | Response Headers | Audio Source Tracking Header | Response header declaring source of audio (`elevenlabs-stream` vs `synthetic-fallback-mode`) | None (set by server) | Header `X-Audio-Source` | None (deterministic header) | Dispatch Instructions, `PROJECT.md` Feature 19 |
| 4 | Offline Resilience | Unconfigured Key Fallback | Emits synthetic silent MPEG frame when `ELEVENLABS_API_KEY` is empty, unset, or starts with `your_` | Empty or placeholder API key in settings | 320 bytes silent MP3 with `X-Audio-Source: synthetic-fallback-mode` | Transparent HTTP 200 fallback | `ORIGINAL_REQUEST.md` §R4, `backend/api/routes/tts.py:76-88` |
| 5 | Network Resilience | Upstream Error Graceful Fallback | Catches upstream 401, 403, 429, 500, 502, 503, timeouts, or connection failures and emits silent MP3 fallback | Upstream failure / connection drop | 320 bytes silent MP3 with `X-Audio-Source: synthetic-fallback-mode` | Prevents Starlette 500 crashes and unhandled exceptions | Probing analysis, `explorer_m4_1/handoff.md`, `explorer_m4_2/handoff.md` |
| 6 | Security | Credential Shielding | Prevents `ELEVENLABS_API_KEY` from leaking in response headers, client payloads, error bodies, or debug logs | Incoming request | Response without credential headers | Error sanitizer scrubs key substrings | `ORIGINAL_REQUEST.md` §R4, Security review |
| 7 | Security | SSRF & Directory Traversal Protection | Restricts `voice_id` to alphanumeric/hyphen/underscore format (`^[a-zA-Z0-9_-]{1,64}$`) | Malicious `voice_id` (e.g. `../../admin`) | HTTP 422 Unprocessable Entity | Rejects path manipulation | Probing analysis (`Captured URL: api.elevenlabs.io/admin/delete/stream`) |
| 8 | Security | Model ID Sanitization | Restricts `model_id` to safe slug identifiers (`^[a-zA-Z0-9_.-]{1,64}$`) | Malicious `model_id` | HTTP 422 Unprocessable Entity | Rejects invalid characters | Security review |
| 9 | Validation | Whitespace & Boundary Sanitization | Enforces text length between 1 and 5000 chars, rejecting blank/whitespace-only input | `text` string | Stripped string | HTTP 422 Unprocessable Entity | Pydantic field validation |
| 10 | Lifecycle | Client Disconnect Handling | Catches `asyncio.CancelledError` and `GeneratorExit` during streaming, closing sockets without leaking resources | Client abort (`stopAudio()`) | Immediate generator exit | Clean connection termination; no ASGI error dump | `frontend/hooks/useAudioStream.ts:23-35`, Starlette streaming spec |
| 11 | Configuration | Granular Timeout Configuration | Decouples connect timeout (5.0s) from read streaming timeout (30.0s) | `TTS_CONNECT_TIMEOUT`, `TTS_TIMEOUT` settings | `httpx.Timeout` configuration | Fast failure (5s) for dead networks | `explorer_m4_1/proposed_tts.py` |
| 12 | Binary Audio | ISO/IEC 11172-3 Silent Frame Generator | Generates 10 valid 32-byte MPEG-1 Layer 3 frames (128 kbps, 44.1 kHz, Joint Stereo) | None | Exactly 320 bytes valid MP3 | None (pure in-memory generator) | `backend/api/routes/tts.py:19-30`, Bitwise validation |

---

## 3. Edge Cases & Empirical Observations

| # | Feature | Input / Condition | Observed Behavior (Current Code) | Target Required Behavior | Remediation / Verification |
|---|---------|-------------------|-----------------------------------|--------------------------|----------------------------|
| 1 | Upstream Error (401 / 429 / 500) | `ELEVENLABS_API_KEY` set to invalid key; upstream returns 401 | `RuntimeError: Caught handled exception, but response already started.` Crashes ASGI response runner because headers were sent before generator was consumed. | Return HTTP 200 with `X-Audio-Source: synthetic-fallback-mode` and 320-byte silent MP3 (or clean HTTP 502 without header commit collision). | Pre-flight upstream probing before emitting `StreamingResponse`. |
| 2 | Network Disconnect / DNS Failure | Hostname unreachable (`httpx.ConnectError`) | Unhandled exception bubbles out of `StreamingResponse`, leaking full error and stack trace to server console/client. | Catch `(httpx.HTTPError, httpx.TimeoutException)` before response start, scrub sensitive keys, and return fallback response. | Wrap upstream connection in pre-flight try/except block. |
| 3 | Path Traversal in `voice_id` | `voice_id: "../../admin/delete"` | Current code interpolates into URL: `https://api.elevenlabs.io/admin/delete/stream`. SSRF vulnerability! | Reject with HTTP 422 Unprocessable Entity: `voice_id` must match `^[a-zA-Z0-9_-]{1,64}$`. | Add Pydantic `pattern` regex constraint. |
| 4 | Whitespace-only text | `text: "   "` | Passes current validation (`len("   ") == 3 >= 1`), sends blank text upstream. | Reject with HTTP 422 Unprocessable Entity: text must contain non-whitespace characters. | Add Pydantic `@field_validator` with `.strip()`. |
| 5 | Text Length Exceeded | `text: "a" * 5001` | Correctly rejected by Pydantic with HTTP 422. | Maintain HTTP 422 response. | Verified by automated probe. |
| 6 | Missing `X-Audio-Source` Header | Live ElevenLabs streaming (upstream 200 OK) | Current code returns `Content-Disposition` and `Cache-Control`, but omits `X-Audio-Source`. | Must include `X-Audio-Source: elevenlabs-stream`. | Explicitly configure header dictionary in `StreamingResponse`. |
| 7 | Client Aborts Stream Early | User clicks Stop in frontend (`abortControllerRef.abort()`) | Async generator raises `GeneratorExit` / `asyncio.CancelledError`; unhandled logging or socket leak. | Catch `(asyncio.CancelledError, GeneratorExit)`, log clean info event, and close upstream client in `finally:`. | Explicit context manager & `finally:` cleanup. |
| 8 | Secret Key in Upstream Error Body | ElevenLabs returns error JSON containing API key string | If error body is logged or returned in `HTTPException.detail`, the private API key is leaked. | Any error text must pass through `sanitize_log_message()` stripping the key. | Replace `settings.ELEVENLABS_API_KEY` with `[REDACTED]`. |
| 9 | Monolithic 30s Timeout on Dead Network | Network down / DNS hung | Endpoint hangs for full 30 seconds before failing. | Split timeouts: connect timeout 5.0s, read timeout 30.0s. | Configure `httpx.Timeout(connect=5.0, read=30.0, ...)`. |
| 10 | Missing API Key / Placeholder Key | `ELEVENLABS_API_KEY = ""` or `"your_api_key_here"` | Returns HTTP 200 with `X-Audio-Source: synthetic-fallback-mode` and 320 bytes. | Maintain this behavior. | Verified by automated probe. |

---

## 4. Authoritative Contract Specification

### 4.1 Endpoint Definition
- **Route**: `POST /api/v1/tts/synthesize`
- **Tags**: `["tts"]`
- **Request Content-Type**: `application/json`
- **Response Content-Type**: `audio/mpeg`

### 4.2 Request Body Schema (`SynthesizeRequest`)

```python
class SynthesizeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Forensic audit verdict text to synthesize to speech. Cannot be whitespace-only."
    )
    voice_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]{1,64}$",
        description="ElevenLabs Voice ID (alphanumeric with hyphens/underscores). Defaults to settings.ELEVENLABS_VOICE_ID (Rachel: 21m00Tcm4TlvDq8ikWAM)."
    )
    model_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_.-]{1,64}$",
        description="ElevenLabs Model ID. Defaults to settings.ELEVENLABS_MODEL_ID (eleven_multilingual_v2)."
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Text cannot be empty or whitespace only")
        return stripped
```

### 4.3 Response Headers Specification

#### Branch A: Live ElevenLabs Streaming Mode (`upstream 200 OK`)
| Header Name | Required Value | Description |
|-------------|----------------|-------------|
| `Content-Type` | `audio/mpeg` | Standard MIME type for MP3 audio stream |
| `X-Audio-Source` | `elevenlabs-stream` | Indicates live upstream synthesis |
| `Content-Disposition` | `inline; filename=verdict.mp3` | Inline presentation for audio element |
| `Cache-Control` | `no-cache, no-store, must-revalidate` | Prevents stale audio caching for dynamic verdicts |
| `X-Content-Type-Options` | `nosniff` | Security header preventing MIME sniffing |

#### Branch B: Synthetic Silent Fallback Mode (`unconfigured or upstream failure`)
| Header Name | Required Value | Description |
|-------------|----------------|-------------|
| `Content-Type` | `audio/mpeg` | Standard MIME type for MP3 audio |
| `X-Audio-Source` | `synthetic-fallback-mode` | Indicates fallback silent audio |
| `Content-Disposition` | `inline; filename=verdict_fallback.mp3` | Inline presentation identifier |
| `Cache-Control` | `no-cache, no-store, must-revalidate` | Prevents caching |
| `X-Content-Type-Options` | `nosniff` | Security header preventing MIME sniffing |

---

## 5. Security & Threat Model

### 5.1 Credential Shielding (`ELEVENLABS_API_KEY`)
1. **Never Expose to Frontend**: The frontend client (`useAudioStream.ts`) communicates strictly with the backend proxy (`/api/v1/tts/synthesize`). The `xi-api-key` header is added exclusively in server-to-server calls to `https://api.elevenlabs.io`.
2. **Error Reflection Prevention**: Upstream error responses from ElevenLabs or HTTPX connection exceptions can contain credential fragments. All error logging and potential error responses must pass through an explicit sanitizer:
   ```python
   def sanitize_log_message(msg: str) -> str:
       if settings.ELEVENLABS_API_KEY and settings.ELEVENLABS_API_KEY in msg:
           return msg.replace(settings.ELEVENLABS_API_KEY, "[REDACTED]")
       return msg
   ```
3. **No Key in HTTP Headers**: The backend response headers sent to the client MUST NOT include `xi-api-key` or any authentication credentials.

### 5.2 Injection & SSRF Prevention
1. **Path Traversal / SSRF**: By default, `url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"` is vulnerable if `voice_id` contains `../` or query parameters. The regex `^[a-zA-Z0-9_-]{1,64}$` strictly locks `voice_id` to standard alphanumeric identifiers, preventing path breakout.
2. **HTTP Header Injection & Response Splitting**: Newline characters (`\r`, `\n`) in user inputs are blocked by regex validation on `voice_id` and `model_id`. Text payload is sent strictly as serialized JSON in the request body, preventing HTTP protocol desynchronization.

---

## 6. Architectural Streaming Mechanics & Pre-Flight Design

### 6.1 The Starlette Header Commit Problem
In Starlette / FastAPI, `StreamingResponse` sends the HTTP response start message (`http.response.start` with status 200 and headers) to the ASGI server *before* iterating the body generator.
If an exception (e.g. `HTTPException(401)` or `httpx.ConnectError`) is raised *inside* the generator, Starlette crashes with:
```
RuntimeError: Caught handled exception, but response already started.
```
This leaves the HTTP connection broken and leaks server errors.

### 6.2 Pre-Flight Upstream Verification Pattern
To solve this, upstream HTTP communication must be initiated **before** instantiating `StreamingResponse`:
```python
# 1. Build and send request with stream=True
client = httpx.AsyncClient(timeout=timeout)
try:
    req = client.build_request("POST", url, headers=headers, json=payload)
    response = await client.send(req, stream=True)
    if response.status_code != 200:
        # Catch failure BEFORE headers are committed!
        await response.aclose()
        await client.aclose()
        return create_fallback_streaming_response(reason=f"Upstream HTTP {response.status_code}")
except (httpx.HTTPError, httpx.TimeoutException, Exception) as exc:
    await client.aclose()
    return create_fallback_streaming_response(reason=f"Upstream exception: {type(exc).__name__}")

# 2. Return StreamingResponse only after upstream 200 OK is confirmed
async def live_audio_stream():
    try:
        async for chunk in response.aiter_bytes():
            if chunk:
                yield chunk
    except (asyncio.CancelledError, GeneratorExit):
        logger.info("Client disconnected during live audio streaming.")
        raise
    finally:
        await response.aclose()
        await client.aclose()

return StreamingResponse(
    live_audio_stream(),
    media_type="audio/mpeg",
    headers={
        "Content-Disposition": "inline; filename=verdict.mp3",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "X-Audio-Source": "elevenlabs-stream",
        "X-Content-Type-Options": "nosniff",
    }
)
```

---

## 7. MPEG-1 Layer 3 Binary Specification (Silent Audio Fallback)

The fallback audio buffer consists of 10 identical 32-byte frames, totaling **320 bytes**:
```python
b"\xff\xfb\x90\x64\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" \
b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" * 10
```

### Frame Header Bitwise Breakdown (`0xFF 0xFB 0x90 0x64`):
1. **Sync Word** (`bits 31:21`): `0xFF 0xFB` (binary `11111111 11111...`) — 11 consecutive 1s denoting valid frame synchronization.
2. **MPEG Audio Version** (`bits 20:19`): `0b11` — MPEG Version 1 (ISO/IEC 11172-3).
3. **Layer Description** (`bits 18:17`): `0b01` — Layer III.
4. **Protection Bit** (`bit 16`): `0b1` — Protected by CRC: No.
5. **Bitrate Index** (`bits 15:12`): `0b1001` (9) — 128 kbps.
6. **Sampling Frequency** (`bits 11:10`): `0b00` (0) — 44.1 kHz.
7. **Padding Bit** (`bit 9`): `0b0` — Frame is not padded.
8. **Private Bit** (`bit 8`): `0b0` — Not private.
9. **Channel Mode** (`bits 7:6`): `0b01` (1) — Joint Stereo.
10. **Mode Extension** (`bits 5:4`): `0b10` — Intensity Stereo off, MS Stereo on.
11. **Copyright** (`bit 3`): `0b0` — Audio is not copyrighted.
12. **Original / Home** (`bit 2`): `0b1` — Original media.
13. **Emphasis** (`bits 1:0`): `0b00` — None.
14. **Audio Payload** (28 bytes): All zeros (`0x00`), representing zero-energy frequency subbands (complete silence).

---

## 8. Test Matrix & Verification Coverage

A comprehensive verification suite must test 6 critical domains:

1. **Fallback Silence Frame Bitwise Validity**:
   - Verify buffer is exactly 320 bytes.
   - Verify 10 frames of 32 bytes each.
   - Validate sync word, MPEG-1 Layer 3 markers, 128 kbps, 44.1 kHz.
2. **Unconfigured Key Handling**:
   - Verify `ELEVENLABS_API_KEY = ""` returns HTTP 200 with `X-Audio-Source: synthetic-fallback-mode`.
   - Verify `ELEVENLABS_API_KEY = "your_key_here"` returns HTTP 200 with `X-Audio-Source: synthetic-fallback-mode`.
3. **Live Proxy Streaming**:
   - Mock upstream ElevenLabs 200 OK.
   - Verify HTTP 200, `Content-Type: audio/mpeg`, and `X-Audio-Source: elevenlabs-stream`.
   - Verify audio chunks match upstream byte stream.
   - Verify custom `voice_id` and `model_id` are passed upstream.
4. **Upstream Failure & Timeout Resilience**:
   - Mock upstream 401 Unauthorized -> Gracefully returns HTTP 200 with `X-Audio-Source: synthetic-fallback-mode` (no Starlette crash).
   - Mock upstream 429 Rate Limit -> Gracefully returns HTTP 200 with `X-Audio-Source: synthetic-fallback-mode`.
   - Mock upstream 500 Internal Error -> Gracefully returns HTTP 200 with `X-Audio-Source: synthetic-fallback-mode`.
   - Mock `httpx.ConnectTimeout` & `httpx.ReadTimeout` -> Gracefully returns HTTP 200 with `X-Audio-Source: synthetic-fallback-mode`.
   - Mock `httpx.ConnectError` -> Gracefully returns HTTP 200 with `X-Audio-Source: synthetic-fallback-mode`.
5. **Security & Input Validation**:
   - Empty text (`""`) -> HTTP 422.
   - Whitespace text (`"   "`) -> HTTP 422.
   - Text > 5000 characters -> HTTP 422.
   - Path traversal in `voice_id` (`"../../admin"`) -> HTTP 422.
   - Malicious characters in `model_id` (`"eleven; rm -rf"`) -> HTTP 422.
   - API key leakage verification: mock exception with secret key in message, verify response does NOT contain key.
6. **Client Cancellation & Disconnection**:
   - Client disconnects while streaming chunks -> Catch `(asyncio.CancelledError, GeneratorExit)` and close upstream connection without unhandled errors.
