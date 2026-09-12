## 2026-09-12T09:29:40Z

You are a Spec Miner for Milestone 3 (Agent Tools API Contracts & Schemas) in the Forensic Auditor Python Backend project.

Your Working Directory: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\spec_miner_m3_1
Workspace Root: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar
Original Request: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\ORIGINAL_REQUEST.md
Project Plan: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\orchestrator_1\PROJECT.md

Scope & Instructions:
1. Initialize `.agents/spec_miner_m3_1` with BRIEFING.md and progress.md.
2. Read ORIGINAL_REQUEST.md (specifically R3) and `doc/backend/README.md`.
3. Formulate the exact request and response Pydantic schemas in `backend/schemas/agent_tools.py`:
   - `TransactionQueryRequest` & `TransactionQueryResponse`: case_id, origin, destination, min_amount, max_amount, start_time, end_time, is_suspicious, limit, offset.
   - `EntityProfileRequest` & `EntityProfileResponse`: case_id, entity_id (optional for single entity vs all entities), return in_degree, out_degree, total_inflow, total_outflow, net_flow, risk_score, reasons.
   - `PatternQueryRequest` & `PatternQueryResponse`: case_id, pattern_type (optional filter for cycles vs mules), cycles, passthrough_mules.
   - `LegalPrecedentQueryRequest` & `LegalPrecedentQueryResponse`: query_text, query_vector (optional), top_k, similarity_threshold, returned articles with similarity scores.
   - `DynamicQueryRequest` & `DynamicQueryResponse`: target, filters (list of field, operator, value), sort_by, sort_order, limit, offset.
4. Recommend exact type annotations and validation rules.
5. Write your report to `analysis.md` and `handoff.md`.
6. Send a message to orchestrator with summary and path.

Boundaries:
- Read-only exploration and planning. Do NOT modify source code files outside .agents/.
