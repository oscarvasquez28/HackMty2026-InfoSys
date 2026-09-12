## 2026-09-12T09:03:53Z
You are a Spec Miner for Milestone 1 (Database Layer: Models & Legal Precedents) in the Forensic Auditor Python Backend project.

Your Working Directory: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\spec_miner_m1_1
Workspace Root: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar
Original Request: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\ORIGINAL_REQUEST.md
Project Plan: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\orchestrator_1\PROJECT.md

Scope & Instructions:
1. Initialize your .agents/spec_miner_m1_1 folder with BRIEFING.md, progress.md.
2. Read ORIGINAL_REQUEST.md, PROJECT.md, and doc/data-and-compliance/README.md.
3. Formulate the exact implementation specification for `backend/models/forensic.py`:
   - `InvestigationCase`: UUID PK (`uuid.uuid4`), filename (`String(255)`), status (`String(50)`), timestamps (`created_at`, `updated_at`), JSONB fields (`ingestion_metadata`, `metrics`, `subgraph`, `patterns`, `verdict`).
   - `TransactionRecord`: UUID PK (`uuid.uuid4`), FK to `investigation_cases.id` with `CASCADE` delete and index, `origin` (`String(100)`, indexed), `destination` (`String(100)`, indexed), `amount` (`Numeric(18, 2)`), `timestamp` (`DateTime(timezone=True)`), `is_suspicious` (`Boolean`, default False, indexed), `reasons` (`JSONB`, default list).
   - `LegalArticleVector`: UUID PK (`uuid.uuid4`), `article_code` (`String(50)`, unique, indexed), `law_name` (`String(100)`), `content` (`Text`), `embedding` (`Vector(1536)` with HNSW cosine index `m=16, ef_construction=64`).
   - Exact seed knowledge data for Mexican AML jurisprudence: CFF Art. 69-B (EFOS/EDOS presumptions, 15 days rebuttal, 30 days regularization), NIF A-2 (economic substance, evidentiary triad: fecha cierta, verifiable deliverables, financial flow), and UIF regulations (ROI 24-48h, ROR >$7,500 USD, Art. 115 LIC account freezing).
4. Recommend exact code structures and type annotations for the Worker.
5. Write your report to `analysis.md` and complete a structured handoff in `handoff.md` in your directory.
6. Send a message to the orchestrator with your summary and handoff path.

Boundaries:
- Read-only exploration and planning. Do NOT modify source code files outside .agents/.
