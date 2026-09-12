## 2026-09-12T09:32:41Z

You are Worker M3 implementing Milestone 3 (Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents) in the Forensic Auditor Python Backend project.

Your Working Directory: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\worker_m3_1
Workspace Root: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar
Original Request: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\ORIGINAL_REQUEST.md
Project Plan: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\orchestrator_1\PROJECT.md

Exclusive Write Ownership:
- `backend/schemas/agent_tools.py`
- `backend/services/tool_registry.py`
- `backend/api/routes/agent_tools.py`
- `backend/main.py` (router inclusion)
- `backend/tests/test_agent_tools.py`

Authoritative Reference Reports:
Read before implementing:
- `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\spec_miner_m3_1\handoff.md`
- `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_m3_1\handoff.md`
- `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_m3_2\handoff.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks:
1. Initialize `.agents/worker_m3_1` with BRIEFING.md and progress.md.
2. Implement `backend/schemas/agent_tools.py`:
   - Schemas for `TransactionQueryRequest` / `Response`, `EntityProfileRequest` / `Response`, `PatternQueryRequest` / `Response`, `LegalPrecedentQueryRequest` / `Response`, `DynamicQueryRequest` / `Response`, `QueryFilter`, enums.
3. Implement `backend/services/tool_registry.py`:
   - `ToolRegistry` class with `@tool_registry.register(...)` and method registration.
   - Built-in handlers for: `transactions`, `cases`, `entities`, `patterns`, `legal_precedents`.
   - Dynamic query engine with column whitelisting, mandatory `case_id` scoping for case-scoped targets, safe parameterized SQLAlchemy expressions (zero string interpolation), operators (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`), sorting, and pagination.
   - Dual execution support (PostgreSQL `AsyncSession` with fallback to in-memory `INVESTIGATION_CASES` when database is unconfigured).
4. Implement `backend/api/routes/agent_tools.py`:
   - `POST /api/v1/tools/transactions`: filters `TransactionRecord` by `case_id`, origin/dest, min/max amounts, time window, and `is_suspicious` flag.
   - `POST /api/v1/tools/entities`: profiles financial entities/nodes (in/out volumes, counterparty degree, assigned risk scores and reasons).
   - `POST /api/v1/tools/patterns`: retrieves detected elementary cycles and pass-through mule account metrics for a case.
   - `POST /api/v1/tools/legal-precedents`: vector similarity search against `legal_knowledge_vectors` using cosine similarity (`<=>`) with keyword search fallback when no embedding is provided.
   - `POST /api/v1/tools/query`: dynamic, composable query endpoint invoking `tool_registry.execute_query(...)`.
5. Update `backend/main.py`:
   - Import `agent_tools_router` from `backend.api.routes.agent_tools` and include router with `prefix=settings.API_V1_STR`.
6. Implement `backend/tests/test_agent_tools.py`:
   - Comprehensive tests for all 4 dedicated endpoints with varied parameters.
   - Comprehensive tests for `/tools/query` with various targets, operators, sorts, invalid column rejection, and injection safety.
7. Verification:
   - Run `pytest backend/tests/ -v` using `run_command` and ensure all tests pass cleanly.
8. Document changes in `changes.md` and complete `handoff.md`.
9. Send a message to orchestrator upon completion.
