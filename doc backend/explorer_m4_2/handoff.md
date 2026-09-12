# Handoff Report: Milestone 4 TTS Verification & Test Strategy

**From**: `explorer_m4_2`  
**To**: `orchestrator_1` / Worker Agent  
**Milestone**: Milestone 4 (Speech Synthesis Proxy & Security Hardening)  
**Date**: 2026-09-12  
**Handoff Type**: Hard (Task Complete)

---

## 1. Observation

1. **Current Route Implementation**:
   - File: `backend/api/routes/tts.py`
   - Lines 54-65:
     ```python
     async with httpx.AsyncClient(timeout=30.0) as client:
         async with client.stream("POST", url, headers=headers, json=payload) as response:
             if response.status_code != 200:
                 error_body = await response.aread()
                 raise HTTPException(
                     status_code=response.status_code,
                     detail=f"ElevenLabs TTS API error: {error_body.decode('utf-8', errors='ignore')}"
                 )
             async for chunk in response.aiter_bytes():
                 if chunk:
                     yield chunk
     ```
   - Lines 90-105:
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
2. **Execution Result on Upstream Non-200**:
   - When mocked upstream ElevenLabs returns status 500, executing `POST /api/v1/tts/synthesize` produces:
     `RuntimeError: Caught handled exception, but response already started.`
3. **Execution Result on Upstream Timeout / Connection Error**:
   - When mocked upstream raises `httpx.TimeoutException` or `httpx.ConnectError`, executing `POST /api/v1/tts/synthesize` raises unhandled `httpx.TimeoutException` / `httpx.ConnectError`.
4. **Existing Test Suite Baseline**:
   - Command: `python -m pytest backend/tests/`
   - Result: 72 passed in 16.14s.
   - `backend/tests/test_tts.py` did not exist in the repository; only a single smoke test existed in `backend/tests/test_pipeline.py`.
5. **Formulated Test Suite Execution**:
   - Formulated 17 comprehensive test cases in `.agents/explorer_m4_2/proposed_test_tts.py`.
   - Executed against current codebase: 12 passed, 5 failed (all 5 upstream error handling cases failed due to generator exception).
   - Executed against proposed hardened implementation (`.agents/explorer_m4_2/proposed_tts.py`): 17 passed, 0 failed in 0.24s.

---

## 2. Logic Chain

1. **Step 1 (Observation 1 -> Pre-flight vs Streaming Execution)**:
   In FastAPI, `StreamingResponse` sends HTTP 200 headers immediately before consuming the async generator.
2. **Step 2 (Observation 1 & 2 -> Header Commit Collision)**:
   Because HTTP headers are committed upon returning `StreamingResponse`, any `HTTPException` raised inside `stream_elevenlabs_audio` cannot modify the already-sent status code. Starlette catches the exception and raises `RuntimeError: Caught handled exception, but response already started`.
3. **Step 3 (Observation 3 -> Unhandled Network Interruptions)**:
   Because the `try...except` block in `synthesize_speech` only surrounds the instantiation of `StreamingResponse`, network errors (`TimeoutException`, `ConnectError`) inside `client.stream(...)` bubble out directly, aborting the connection without returning a fallback response.
4. **Step 4 (Requirement R4 & Prompt -> Resilient Silence Fallback)**:
   R4 requires: *"Maintain the synthetic silent MP3 fallback generator for offline resilience"*, and the prompt specifies: *"Test upstream failure fallback (upstream 500, 401, timeout) falling back gracefully to silent audio with HTTP 200."*
5. **Step 5 (Proposed Implementation -> Safe Generator Fallback)**:
   Wrapping `client.stream(...)` inside `stream_elevenlabs_audio` with exception handling and status code validation such that any upstream error yields `generate_fallback_silence_mp3()` ensures:
   - Client receives HTTP 200 and a valid 320-byte MPEG frame.
   - No exceptions are raised after headers are sent.
   - Frontend audio players receive valid audio without crashing.
6. **Step 6 (Observation 5 -> Test Strategy Proof)**:
   Testing the formulated 17-test suite against both implementations confirms that the 5 failing tests precisely isolate the defect, and applying the proposed hardening resolves all 5 failures with zero regressions.

---

## 3. Caveats

1. **No Source Code Modified Outside `.agents/`**:
   In strict adherence to the read-only explorer constraint, `backend/api/routes/tts.py` was NOT modified in-place, and `backend/tests/test_tts.py` was NOT created directly in `backend/tests/`. Both files are fully provided in `.agents/explorer_m4_2/`.
2. **Upstream Response Headers**:
   When upstream ElevenLabs fails mid-flight or upon initial connection, the response header `X-Audio-Source` cannot be changed after initial dispatch because headers are sent with the `StreamingResponse` call. However, the client receives the valid silent MP3 audio bytes, fulfilling the primary resilience requirement.
3. **Respx Dependency**:
   The `respx` library is not installed in the environment. All tests were constructed using standard `unittest.mock` and `httpx.ASGITransport` to ensure zero external dependency requirements and 100% deterministic test execution.

---

## 4. Conclusion

1. **Test Suite Deliverable**:
   - Ready-to-use test suite formulated in:  
     `.agents/explorer_m4_2/proposed_test_tts.py`  
     Contains 17 automated tests covering:
     - 4 Fallback mode and MPEG frame structure tests.
     - 2 Proxy streaming success tests (default and custom voice/model).
     - 5 Upstream failure resilience tests (500, 401, 429, timeout, connect error).
     - 5 Request validation tests (empty text, missing text, >5000 chars, non-string, boundary valid lengths).
     - 1 Security secret shielding test.
2. **Implementation Deliverables for Worker Agent**:
   - Target route implementation: `.agents/explorer_m4_2/proposed_tts.py`.
   - Unified diff patch: `.agents/explorer_m4_2/tts_hardening.patch`.
   - Action for Worker Agent:
     1. Copy `.agents/explorer_m4_2/proposed_test_tts.py` to `backend/tests/test_tts.py`.
     2. Apply `.agents/explorer_m4_2/tts_hardening.patch` to `backend/api/routes/tts.py`.
     3. Run `python -m pytest backend/tests/` to verify all 89 tests pass (72 existing + 17 new).

---

## 5. Verification Method

To independently reproduce the findings and verify the solution:

1. **Reproduce Failure on Current Code**:
   ```powershell
   python -m pytest .agents/explorer_m4_2/proposed_test_tts.py
   ```
   *Expected*: 12 passed, 5 failed (the 5 upstream failure tests fail with `RuntimeError` or `ConnectError`).

2. **Verify 100% Pass with Proposed Implementation**:
   ```powershell
   python -c "import importlib.util, sys; spec = importlib.util.spec_from_file_location('p', '.agents/explorer_m4_2/proposed_tts.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); import backend.api.routes.tts; backend.api.routes.tts.stream_elevenlabs_audio = mod.stream_elevenlabs_audio; import pytest; sys.exit(pytest.main(['.agents/explorer_m4_2/proposed_test_tts.py', '-v']))"
   ```
   *Expected*: `17 passed in 0.24s`.

3. **Verify Existing Tests Zero Regression**:
   ```powershell
   python -m pytest backend/tests/
   ```
   *Expected*: `72 passed`.

