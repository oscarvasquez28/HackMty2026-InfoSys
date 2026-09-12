# Progress — Milestone 2 Explorer

Last visited: 2026-09-12T09:17:35Z

- [x] Initialized BRIEFING.md and progress.md
- [x] Read ORIGINAL_REQUEST.md (R2), Project Plan (PROJECT.md), models, ingestion, deterministic_filter, investigations route, database setup
- [x] Analyze exact data schemas, models, and relations in `backend/models/forensic.py` and `backend/database.py`
- [x] Trace ingestion and pruning output in `ingestion.py` and `deterministic_filter.py`
- [x] Formulate mapping from Polars DataFrame & GraphPruneResult to `InvestigationCase` and `TransactionRecord`
- [x] Formulate SQLAlchemy async queries for `POST /upload`, `GET /investigations`, and `GET /investigations/{case_id}`
- [x] Formulate graceful fallback for offline/in-memory mode when database is not configured
- [x] Produce `analysis.md` and `handoff.md`
- [x] Update `BRIEFING.md`
- [x] Send handoff message to orchestrator
