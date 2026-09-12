## 2026-09-12T13:51:51Z
You are Worker M4 implementing Milestone 4 (Speech Synthesis Proxy & Security Hardening) in the Forensic Auditor Python Backend project.

Your Working Directory: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\worker_m4_1
Workspace Root: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar
Original Request: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\ORIGINAL_REQUEST.md
Project Plan: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\orchestrator_1\PROJECT.md

Exclusive Write Ownership:
- `backend/core/config.py` (TTS timeout settings)
- `backend/api/routes/tts.py`
- `backend/tests/test_tts.py`

Authoritative Reference Reports:
Read before implementing:
- `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_m4_1\handoff.md`
- `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_m4_2\handoff.md`
- Inspect `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_m4_1\proposed_tts.py`
- Inspect `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_m4_2\proposed_test_tts.py`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks:
1. Initialize `.agents/worker_m4_1` with BRIEFING.md and progress.md.
2. Update `backend/core/config.py` to add `TTS_TIMEOUT: float = 30.0` and `TTS_CONNECT_TIMEOUT: float = 5.0`.
3. Harden `backend/api/routes/tts.py`:
   - Proxy audio synthesis to ElevenLabs API streaming endpoint (`https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream`), shielding `ELEVENLABS_API_KEY`.
   - Resolve the Starlette early-header streaming crash by pre-probing/connecting or cleanly handling upstream errors (500, 401, 429, timeout, connect error) to gracefully fall back to `generate_fallback_silence_mp3()` with `X-Audio-Source: synthetic-fallback-mode`.
   - Maintain the synthetic silent MP3 generator (320-byte MPEG-1 Layer 3 frames repeated 10 times).
   - Handle client cancellation (`asyncio.CancelledError`, `GeneratorExit`) cleanly without unhandled exceptions or resource leaks.
4. Implement `backend/tests/test_tts.py` using the 17-test suite formulated in `explorer_m4_2/proposed_test_tts.py`:
   - Fallback when API key is None, empty, or default `your_...`.
   - Proxy mode with mocked 200 OK chunked stream.
   - Upstream error fallback (500, 401, 429, timeout, connect error) returning HTTP 200 silent audio.
   - Request validation (empty text, text > 5000 chars, boundary length).
   - Security test confirming API key is never exposed.
5. Verification:
   - Run `pytest backend/tests/ -v` using `run_command` and confirm all tests pass cleanly.
6. Document changes in `changes.md` and complete `handoff.md`.
7. Send a message to orchestrator upon completion.

