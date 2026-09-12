# Handoff Report: Milestone 4 (TTS Proxy Hardening & Resilience)

## 1. Observation
1. **Existing Route Implementation (`backend/api/routes/tts.py:54-105`)**:
   - The route `synthesize_speech` wraps `StreamingResponse(stream_elevenlabs_audio(...))` in a `try...except` block:
     ```python
     try:
         return StreamingResponse(
             stream_elevenlabs_audio(request.text, voice_id, model_id),
             media_type="audio/mpeg",
             headers={
                 "Content-Disposition": "inline; filename=verdict.mp3",
                 "Cache-Control": "no-cache",
             }
         )
     except HTTPException:
         raise
     except Exception as exc:
         raise HTTPException(
             status_code=status.HTTP_502_BAD_GATEWAY,
             detail=f"Failed to stream audio from ElevenLabs: {str(exc)}"
         )
     ```
2. **Starlette ASGI Streaming Response Mechanics (`starlette/responses.py:441-447`)**:
   - Starlette sends response headers before consuming any chunks from `body_iterator`:
     ```python
     async def stream_response(self, send: Send) -> None:
         await send({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
         async for chunk in self.body_iterator:
             if not isinstance(chunk, bytes | memoryview):
                 chunk = chunk.encode(self.charset)
             await send({"type": "http.response.body", "body": chunk, "more_body": True})
         await send({"type": "http.response.body", "body": b"", "more_body": False})
     ```
3. **Observed Crash on Upstream Error / Invalid Key**:
   - When running `POST /api/v1/tts/synthesize` with an invalid `ELEVENLABS_API_KEY`:
     ```
     RuntimeError: Caught handled exception, but response already started.
     ```
   - Starlette threw this runtime exception because the generator raised `HTTPException(401)` after `http.response.start` had already been dispatched over the ASGI wire with status 200.
4. **Timeout Configuration (`backend/api/routes/tts.py:54`)**:
   - `httpx.AsyncClient(timeout=30.0)` sets a single monolithic 30-second timeout for all phases (connect, read, write, pool). DNS or connection failures block the worker for 30s instead of failing fast.
5. **Client Disconnect Handling (`frontend/hooks/useAudioStream.ts:52, backend/api/routes/tts.py:62-65`)**:
   - Frontend `useAudioStream.ts` calls `abortControllerRef.current.abort()` when `stopAudio()` is triggered.
   - `backend/api/routes/tts.py` does not catch `asyncio.CancelledError` or `GeneratorExit` during `response.aiter_bytes()`, leaving open HTTPX client sessions or generating ASGI error logs.
6. **Binary Fallback Frame Structure (`backend/api/routes/tts.py:25-29`)**:
   - Generates 320 bytes: 10 repetitions of 32 bytes (`b"\xff\xfb\x90\x64" + b"\x00" * 28`).
   - Bitwise analysis confirms:
     - Header `0xFF 0xFB 0x90 0x64`: Sync word `0x7FF`, MPEG-1, Layer III, No CRC, 128 kbps, 44.1 kHz, Joint Stereo, Original, No Emphasis.
     - Payload: 28 zeroed bytes representing silent subbands.

---

## 2. Logic Chain
1. **Observation 1 & 2** establish that the `try...except` block in `synthesize_speech` cannot catch any exception raised inside `stream_elevenlabs_audio` because `StreamingResponse` consumes the generator inside the ASGI send loop **after** `synthesize_speech` returns.
2. **Observation 3** proves that when upstream fails (401 invalid credentials, 429 rate limit, 500 upstream failure, or timeout), raising an exception in the generator causes `RuntimeError: Caught handled exception, but response already started.`, exposing an abrupt connection crash instead of the required HTTP 200 silent MP3 fallback.
3. Therefore, upstream connectivity must be probed **before** returning `StreamingResponse`. Using `req = client.build_request(...)` and `response = await client.send(req, stream=True)` enables `status_code` inspection prior to emitting `http.response.start`.
4. If `response.status_code != 200` or if `client.send` raises `(httpx.HTTPError, httpx.TimeoutException, Exception)`, the endpoint can cleanly close `response` and `client` and return `create_fallback_streaming_response()` with `X-Audio-Source: synthetic-fallback-mode` and HTTP 200 OK.
5. **Observation 4** establishes that separating connect timeout (5.0s) from read timeout (30.0s) ensures fast failover to silent fallback within 5 seconds of network or DNS outages.
6. **Observation 5** establishes that catching `(asyncio.CancelledError, GeneratorExit)` in the streaming generator, closing resources in `finally:`, and re-raising `CancelledError` allows clean termination when the client aborts playback via `useAudioStream.ts`.
7. **Observation 6** establishes the exact 15 header attributes and frame structure that must be validated to guarantee standard-compliant MPEG-1 Layer 3 fallback audio.

---

## 3. Caveats
1. **Mid-Stream Upstream Disconnections**:
   - If ElevenLabs disconnects *mid-stream* (after yielding the first chunk), the HTTP headers (`X-Audio-Source: elevenlabs`) have already been sent to the client.
   - The generator catches the exception in `except Exception as exc:` and closes the socket cleanly in `finally:`. It cannot retroactively change HTTP headers or re-send the fallback silent frame from the beginning because the stream has already started. However, the client decoder simply stops playing the received audio without crashing.
2. **Production Audio Output vs. Fallback**:
   - In production with a valid ElevenLabs key, the endpoint streams live voice synthesis chunks with `X-Audio-Source: elevenlabs`.
   - In offline demo or unconfigured mode, it streams 320 bytes of silent MPEG-1 Layer 3 frames with `X-Audio-Source: synthetic-fallback-mode`, ensuring browser HTML5 audio elements and Web Audio API contexts never error.

---

## 4. Conclusion
1. **Direct Code Replacement Prepared**:
   - The hardened implementation has been drafted and validated in `.agents/explorer_m4_1/proposed_tts.py`.
   - Configuration additions (`TTS_TIMEOUT: float = 30.0`, `TTS_CONNECT_TIMEOUT: float = 5.0`) have been prepared for `backend/core/config.py`.
2. **Comprehensive Test Suite Prepared**:
   - The 13-test automated verification suite has been drafted in `.agents/explorer_m4_1/proposed_test_tts.py` and executed against the hardened implementation, achieving a 100% pass rate.
3. **Zero-Downtime Resilience**:
   - All failure modes (missing keys, invalid keys / 401, quota / 429, upstream 5xx, network timeouts, DNS failure, client disconnect) are handled gracefully without 500 errors or unhandled exceptions.

---

## 5. Verification Method
1. **Run the Hardened TTS Test Suite**:
   ```powershell
   python -m pytest -v .agents/explorer_m4_1/proposed_test_tts.py
   ```
   *Expected Result*: All 13 tests pass cleanly (`13 passed in ~1.8s`).
2. **Run the Entire Existing Test Suite**:
   ```powershell
   python -m pytest -v backend/tests/test_pipeline.py
   ```
   *Expected Result*: All tests pass without regression.
3. **Inspect Proposed Replacement Files**:
   - `.agents/explorer_m4_1/proposed_tts.py`
   - `.agents/explorer_m4_1/proposed_test_tts.py`
   - `.agents/explorer_m4_1/analysis.md`
4. **Invalidation Conditions**:
   - Any test returning HTTP 500 or raising `RuntimeError: Caught handled exception, but response already started.`
   - Any fallback stream lacking `X-Audio-Source: synthetic-fallback-mode`.
   - Any failure of the 15-attribute MPEG-1 Layer 3 bitwise validator on the fallback frame.
