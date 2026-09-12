# Milestone 3 Changes Documentation

**Agent**: `worker_m3_1`  
**Milestone**: Milestone 3 (Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents)  
**Date**: 2026-09-12  

---

## 1. Overview of Changes

Milestone 3 implements the Scalable Query Interface & Dynamic Tool Registry (Requirement R3 in `ORIGINAL_REQUEST.md`) for autonomous forensic AI agents (operating via external n8n workflows or local reasoning agents).

Five primary modules were authored or modified within exclusive write boundaries:
1. `backend/schemas/agent_tools.py` (New): Complete Pydantic v2 schemas and enums for dedicated tool endpoints and dynamic queries.
2. `backend/services/tool_registry.py` (New): Extensible `ToolRegistry` engine with decorator registration (`@tool_registry.register`), parameterized SQLAlchemy AST compilation, column/sort whitelists, mandatory `case_id` scoping, and dual-mode execution (PostgreSQL `AsyncSession` + `INVESTIGATION_CASES` fallback).
3. `backend/api/routes/agent_tools.py` (New): 5 REST endpoints under `/api/v1/tools` (`/transactions`, `/entities`, `/patterns`, `/legal-precedents`, `/query`).
4. `backend/main.py` (Modified): Imported `agent_tools_router` and registered route prefix `settings.API_V1_STR`.
5. `backend/tests/test_agent_tools.py` (New): 15 comprehensive automated test cases covering dedicated endpoints, dynamic query operators, SQL injection prevention, whitelisting, sorting, pagination, offline parity, and runtime tool extension.

---

## 2. File-by-File Detail

### 2.1 `backend/schemas/agent_tools.py`
- **Target Entities & Enums**: `TargetEntity` (`transactions`, `cases`, `entities`, `nodes`, `edges`, `patterns`, `cycles`, `passthrough_accounts`, `legal_precedents`, `legal_vectors`), `FilterOperator` (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, `not_in`), `SortOrder` (`asc`, `desc`), `PatternType` (`all`, `cycles`, `passthrough_mules`).
- **Whitelisting Dictionary**: `TARGET_FIELD_WHITELISTS` mapping valid fields per entity target to strictly disallow unwhitelisted schema traversal or arbitrary injection.
- **Dedicated Endpoint Schemas**:
  - `TransactionQueryRequest` & `TransactionQueryResponse`: Case-scoped filtering on origin, destination, amount range, time window, and suspicion flag, with cross-bound validation (`min_amount <= max_amount`, `start_time <= end_time`).
  - `EntityProfileRequest` & `EntityProfileResponse`: Case-scoped topological profiling for accounts/nodes with degree, inflow, outflow, net flow (`inflow - outflow`), risk score, and connected counterparties.
  - `PatternQueryRequest` & `PatternQueryResponse`: Extraction of elementary directed cycles and high-velocity pass-through mule accounts with cycle length bounds and ratio filtering.
  - `LegalPrecedentQueryRequest` & `LegalPrecedentQueryResponse`: Vector search with natural language query text, optional 1536-dimensional query vector, similarity threshold, and top_k ranking.
- **Dynamic Query Schemas**:
  - `QueryFilter`: Field, operator, and comparison value with validation ensuring `in` and `not_in` operators receive array values.
  - `DynamicQueryRequest` & `DynamicQueryResponse`: Composable query payload enforcing mandatory `case_id` scoping for case-scoped entities, column whitelisting, sort validation, and pagination.

### 2.2 `backend/services/tool_registry.py`
- **`ToolRegistry` Class**: Extensible singleton registry supporting decorator registration (`@tool_registry.register(...)`) and programmatic registration.
- **Parameterized SQL AST Compiler**: Compiles relational queries into SQLAlchemy 2.0 binary expressions (`apply_sa_operator`). Value binding prevents all SQL injection attack vectors.
- **Security & Scoping**:
  - Mandatory `case_id` check: Aborts execution with HTTP 400 Bad Request if missing for case-scoped targets (`transactions`, `entities`, `nodes`, `edges`, `patterns`, `cycles`, `passthrough_accounts`).
  - Column whitelisting: Rejects unwhitelisted fields and sort columns with HTTP 400 before query generation.
- **Dual Execution Engine**:
  - Database mode: Parameterized queries against PostgreSQL/SQLite via `AsyncSession`.
  - In-memory fallback mode: Pure Python predicate evaluator (`evaluate_in_memory_predicate`) against `INVESTIGATION_CASES` dictionary, guaranteeing 100% test and offline execution reliability.
- **Built-in Handlers Registered**:
  - `transactions`: Relational search over `TransactionRecord`.
  - `cases`: History and status search over `InvestigationCase`.
  - `entities` (alias `nodes`): Topological profile extraction from `subgraph["nodes"]`.
  - `patterns` (aliases `cycles`, `passthrough_accounts`): Extraction of cyclic layering loops and mule accounts.
  - `edges`: Directed graph relationship queries.
  - `legal_precedents` (alias `legal_vectors`): Relational metadata queries against Mexican AML statutes.

### 2.3 `backend/api/routes/agent_tools.py`
- Exposes 5 endpoints under `/api/v1/tools`:
  1. `POST /api/v1/tools/transactions`: Filters transactions by case, origin/dest, min/max amount, time window, suspicion.
  2. `POST /api/v1/tools/entities`: Profiles individual or bulk entities, computing degree, net flow, and counterparty connections.
  3. `POST /api/v1/tools/patterns`: Returns cycles and pass-through mule account metrics for a case.
  4. `POST /api/v1/tools/legal-precedents`: Semantic vector search computing cosine similarity against Mexican jurisprudence with deterministic hash embedding generation fallback.
  5. `POST /api/v1/tools/query`: Composable query endpoint delegating to `tool_registry.execute_query`.

### 2.4 `backend/main.py`
- Imported `agent_tools_router` from `backend.api.routes.agent_tools`.
- Registered router with `app.include_router(agent_tools_router, prefix=settings.API_V1_STR)`.

### 2.5 `backend/tests/test_agent_tools.py`
- 15 comprehensive automated test cases:
  1. `test_dedicated_transactions_basic_and_filtering`: Tests origin, destination, suspicion, amounts, pagination.
  2. `test_dedicated_transactions_validation_errors`: Tests inverted amounts, 404 nonexistent case, malformed UUID.
  3. `test_dedicated_entities_profiling`: Tests bulk profiling, single entity profiling, risk score filtering, counterparty degrees.
  4. `test_dedicated_patterns_retrieval`: Tests pattern types `all`, `cycles`, `passthrough_mules`, length/volume filtering.
  5. `test_dedicated_legal_precedents_vector_search`: Tests semantic matching on CFF 69-B, law filter, 1536-D vector, dimension validation, cutoff thresholds.
  6. `test_dynamic_query_transactions_operators`: Tests `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, `not_in`.
  7. `test_dynamic_query_sorting_and_pagination`: Tests ascending/descending sorts and slices.
  8. `test_dynamic_query_security_and_injection_prevention`: Tests SQL injection column rejection, unwhitelisted field rejection, mandatory scoping violation.
  9. `test_dynamic_query_all_targets`: Tests all targets (`cases`, `entities`, `nodes`, `patterns`, `cycles`, `passthrough_accounts`, `edges`, `legal_precedents`).
  10. `test_in_memory_fallback_full_parity`: Tests execution with zero database connection (`DATABASE_URL = None`).
  11. `test_runtime_custom_tool_registration`: Tests registering a new tool at runtime without backend code changes.
  12. `test_edge_case_time_window_and_inverted_timestamps`: Tests start/end time windows and inverted date rejection.
  13. `test_edge_case_pagination_limits_and_negative_offsets`: Tests rejection of limit <= 0, limit > 1000, and negative offsets.
  14. `test_edge_case_empty_in_and_not_in_operators`: Tests safe SQL generation for empty arrays in `in` and `not_in`.
  15. `test_edge_case_case_id_in_filters_satisfies_scoping`: Tests scoping detection when `case_id` is inside filters array.

---

## 3. Verification Summary

- Test Command: `python -m pytest backend/tests/ -v`
- Result: **50 passed in 15.44s** (35 baseline Milestone 1 & 2 tests + 15 new Milestone 3 tests).
- Regressions: **0**.
