"""
Agent Tools API Router for n8n Forensic Auditor workflows.
Exposes dedicated endpoints for transactions, entities, topological patterns,
legal precedent vector search, and the composable dynamic query builder.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
import math
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.investigations import (
    INVESTIGATION_CASES,
    get_optional_db,
)
from backend.models.forensic import (
    InvestigationCase,
    LegalArticleVector,
    SEED_LEGAL_PRECEDENTS,
    TransactionRecord,
    generate_deterministic_embedding,
)
from backend.schemas.agent_tools import (
    CyclePatternItem,
    DynamicQueryRequest,
    DynamicQueryResponse,
    EntityProfileItem,
    EntityProfileRequest,
    EntityProfileResponse,
    LegalPrecedentItem,
    LegalPrecedentQueryRequest,
    LegalPrecedentQueryResponse,
    PassthroughMuleItem,
    PatternQueryRequest,
    PatternQueryResponse,
    PatternType,
    TransactionItem,
    TransactionQueryRequest,
    TransactionQueryResponse,
)
from backend.services.tool_registry import tool_registry

logger = logging.getLogger("forensic_auditor.agent_tools")

router = APIRouter(prefix="/tools", tags=["agent-tools"])


# =============================================================================
# 1. Dedicated Tool: Transactions
# =============================================================================
@router.post(
    "/transactions",
    response_model=TransactionQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query and filter case transactions",
    description="Filter transactions by case_id, origin, destination, amount range, time window, and suspicion flag.",
)
async def query_transactions(
    request: TransactionQueryRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> TransactionQueryResponse:
    try:
        case_uuid = uuid.UUID(str(request.case_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format for case_id: '{request.case_id}'",
        )

    if db is not None:
        # Check case existence
        case_exists_stmt = select(InvestigationCase.id).where(InvestigationCase.id == case_uuid)
        if not (await db.execute(case_exists_stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation case '{case_uuid}' not found.",
            )

        where_clauses = [TransactionRecord.case_id == case_uuid]
        if request.origin:
            where_clauses.append(TransactionRecord.origin == request.origin)
        if request.destination:
            where_clauses.append(TransactionRecord.destination == request.destination)
        if request.min_amount is not None:
            where_clauses.append(TransactionRecord.amount >= Decimal(str(request.min_amount)))
        if request.max_amount is not None:
            where_clauses.append(TransactionRecord.amount <= Decimal(str(request.max_amount)))
        if request.start_time is not None:
            where_clauses.append(TransactionRecord.timestamp >= request.start_time)
        if request.end_time is not None:
            where_clauses.append(TransactionRecord.timestamp <= request.end_time)
        if request.is_suspicious is not None:
            where_clauses.append(TransactionRecord.is_suspicious == request.is_suspicious)

        count_stmt = select(func.count(TransactionRecord.id)).where(*where_clauses)
        total = (await db.execute(count_stmt)).scalar() or 0

        sum_stmt = select(func.sum(TransactionRecord.amount)).where(*where_clauses)
        vol_result = (await db.execute(sum_stmt)).scalar()
        total_volume_mxn = float(vol_result) if vol_result is not None else 0.0

        query_stmt = (
            select(TransactionRecord)
            .where(*where_clauses)
            .order_by(TransactionRecord.timestamp.desc())
            .limit(request.limit)
            .offset(request.offset)
        )
        rows = (await db.execute(query_stmt)).scalars().all()

        items = [
            TransactionItem(
                id=str(r.id),
                case_id=str(r.case_id),
                origin=r.origin,
                destination=r.destination,
                amount=float(r.amount),
                timestamp=r.timestamp,
                is_suspicious=r.is_suspicious,
                reasons=r.reasons or [],
            )
            for r in rows
        ]
    else:
        case_data = INVESTIGATION_CASES.get(str(case_uuid))
        if not case_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation case '{case_uuid}' not found.",
            )

        raw_records = case_data.get("transactions", [])
        if not raw_records and "subgraph" in case_data:
            edges = case_data["subgraph"].get("edges", [])
            raw_records = [
                {
                    "id": str(uuid.uuid4()),
                    "case_id": str(case_uuid),
                    "origin": e.get("source", ""),
                    "destination": e.get("target", ""),
                    "amount": float(e.get("amount", 0.0)),
                    "timestamp": (e.get("timestamps") or [datetime.now(timezone.utc).isoformat()])[0],
                    "is_suspicious": bool(e.get("reasons")),
                    "reasons": e.get("reasons", []),
                }
                for e in edges
            ]

        filtered = []
        for r in raw_records:
            if request.origin and r.get("origin") != request.origin:
                continue
            if request.destination and r.get("destination") != request.destination:
                continue
            amt = float(r.get("amount", 0.0))
            if request.min_amount is not None and amt < request.min_amount:
                continue
            if request.max_amount is not None and amt > request.max_amount:
                continue
            if request.is_suspicious is not None and bool(r.get("is_suspicious")) != request.is_suspicious:
                continue
            filtered.append(r)

        total = len(filtered)
        total_volume_mxn = sum(float(r.get("amount", 0.0)) for r in filtered)
        sliced = filtered[request.offset : request.offset + request.limit]
        items = [
            TransactionItem(
                id=str(r.get("id")),
                case_id=str(case_uuid),
                origin=r.get("origin", ""),
                destination=r.get("destination", ""),
                amount=float(r.get("amount", 0.0)),
                timestamp=r.get("timestamp") or datetime.now(timezone.utc),
                is_suspicious=bool(r.get("is_suspicious")),
                reasons=r.get("reasons", []),
            )
            for r in sliced
        ]

    return TransactionQueryResponse(
        case_id=str(case_uuid),
        total=total,
        limit=request.limit,
        offset=request.offset,
        total_volume_mxn=round(total_volume_mxn, 2),
        items=items,
    )


# =============================================================================
# 2. Dedicated Tool: Entities
# =============================================================================
@router.post(
    "/entities",
    response_model=EntityProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Profile topological entities/nodes",
    description="Retrieve topological degrees, inflows, outflows, net flows, and forensic risk scores for accounts in a case.",
)
async def profile_entities(
    request: EntityProfileRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> EntityProfileResponse:
    try:
        case_uuid = uuid.UUID(str(request.case_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format for case_id: '{request.case_id}'",
        )

    subgraph: Dict[str, Any] = {}
    if db is not None:
        stmt = select(InvestigationCase.subgraph).where(InvestigationCase.id == case_uuid)
        res = await db.execute(stmt)
        subgraph = res.scalar_one_or_none()
        if subgraph is None:
            exists = (await db.execute(select(InvestigationCase.id).where(InvestigationCase.id == case_uuid))).scalar_one_or_none()
            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Investigation case '{case_uuid}' not found.",
                )
            subgraph = {}
    else:
        case_data = INVESTIGATION_CASES.get(str(case_uuid))
        if not case_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation case '{case_uuid}' not found.",
            )
        subgraph = case_data.get("subgraph", {})

    nodes = list(subgraph.get("nodes", []))
    edges = list(subgraph.get("edges", []))

    # Map counterparties per entity
    counterparties_in_map: Dict[str, Set[str]] = {}
    counterparties_out_map: Dict[str, Set[str]] = {}
    for e in edges:
        src = str(e.get("source", ""))
        tgt = str(e.get("target", ""))
        if src and tgt:
            counterparties_out_map.setdefault(src, set()).add(tgt)
            counterparties_in_map.setdefault(tgt, set()).add(src)

    profiles: List[EntityProfileItem] = []
    for n in nodes:
        entity_id = str(n.get("id") or n.get("entity_id") or n.get("account"))
        t_in = float(n.get("total_inflow", n.get("total_in", 0.0)))
        t_out = float(n.get("total_outflow", n.get("total_out", 0.0)))
        r_score = float(n.get("risk_score", 0.0))
        reasons = n.get("reasons", [])
        is_susp = bool(reasons or r_score >= 0.5)

        profiles.append(
            EntityProfileItem(
                entity_id=entity_id,
                in_degree=int(n.get("in_degree", len(counterparties_in_map.get(entity_id, [])))),
                out_degree=int(n.get("out_degree", len(counterparties_out_map.get(entity_id, [])))),
                total_inflow=t_in,
                total_outflow=t_out,
                net_flow=round(t_in - t_out, 2),
                risk_score=r_score,
                reasons=reasons,
                is_suspicious=is_susp,
                counterparties_in=sorted(list(counterparties_in_map.get(entity_id, []))),
                counterparties_out=sorted(list(counterparties_out_map.get(entity_id, []))),
            )
        )

    # Filter by specific entity_id if provided
    if request.entity_id:
        profiles = [p for p in profiles if p.entity_id == request.entity_id]
        if not profiles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity '{request.entity_id}' not found in case '{case_uuid}'.",
            )

    # Filter by min_risk_score
    if request.min_risk_score is not None:
        profiles = [p for p in profiles if p.risk_score >= request.min_risk_score]

    # Filter by is_suspicious
    if request.is_suspicious is not None:
        profiles = [p for p in profiles if p.is_suspicious == request.is_suspicious]

    # Sort by risk_score desc
    profiles.sort(key=lambda x: x.risk_score, reverse=True)

    total_entities = len(profiles)
    sliced = profiles[request.offset : request.offset + request.limit]

    return EntityProfileResponse(
        case_id=str(case_uuid),
        total_entities=total_entities,
        entities=sliced,
    )


# =============================================================================
# 3. Dedicated Tool: Patterns
# =============================================================================
@router.post(
    "/patterns",
    response_model=PatternQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve detected topological patterns",
    description="Extract circular transaction flow cycles and high-turnover pass-through mule account patterns.",
)
async def query_patterns(
    request: PatternQueryRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> PatternQueryResponse:
    try:
        case_uuid = uuid.UUID(str(request.case_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format for case_id: '{request.case_id}'",
        )

    patterns_dict: Dict[str, Any] = {}
    if db is not None:
        stmt = select(InvestigationCase.patterns).where(InvestigationCase.id == case_uuid)
        res = await db.execute(stmt)
        patterns_dict = res.scalar_one_or_none()
        if patterns_dict is None:
            exists = (await db.execute(select(InvestigationCase.id).where(InvestigationCase.id == case_uuid))).scalar_one_or_none()
            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Investigation case '{case_uuid}' not found.",
                )
            patterns_dict = {}
    else:
        case_data = INVESTIGATION_CASES.get(str(case_uuid))
        if not case_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation case '{case_uuid}' not found.",
            )
        patterns_dict = case_data.get("patterns", {})

    # Extract & Filter Cycles
    cycles: List[CyclePatternItem] = []
    if request.pattern_type in (PatternType.ALL, PatternType.CYCLES, "all", "cycles"):
        for c in patterns_dict.get("cycles", []):
            path = c.get("path", [])
            length = int(c.get("length", len(path)))
            volume = float(c.get("estimated_volume", 0.0))

            if request.min_cycle_length is not None and length < request.min_cycle_length:
                continue
            if request.max_cycle_length is not None and length > request.max_cycle_length:
                continue
            if request.min_volume is not None and volume < request.min_volume:
                continue

            cycles.append(
                CyclePatternItem(
                    path=path,
                    length=length,
                    estimated_volume=round(volume, 2),
                )
            )

    # Extract & Filter Passthrough Mule Accounts
    mules: List[PassthroughMuleItem] = []
    if request.pattern_type in (PatternType.ALL, PatternType.PASSTHROUGH_MULES, "all", "passthrough_mules"):
        for pt in patterns_dict.get("passthrough_accounts", []):
            account = str(pt.get("account_id") or pt.get("account") or pt.get("node_id") or "")
            t_in = float(pt.get("inflow", pt.get("total_in", 0.0)))
            t_out = float(pt.get("outflow", pt.get("total_out", 0.0)))
            ratio = float(pt.get("ratio", 0.0))
            w_hours = float(pt.get("window_hours", pt.get("time_delta_hours", 48.0)))

            if request.min_volume is not None and t_in < request.min_volume:
                continue
            if request.min_passthrough_ratio is not None and ratio < request.min_passthrough_ratio:
                continue

            mules.append(
                PassthroughMuleItem(
                    account=account,
                    total_in=round(t_in, 2),
                    total_out=round(t_out, 2),
                    ratio=round(ratio, 4),
                    time_delta_hours=round(w_hours, 2),
                )
            )

    pt_type_str = request.pattern_type.value if isinstance(request.pattern_type, PatternType) else str(request.pattern_type)
    return PatternQueryResponse(
        case_id=str(case_uuid),
        pattern_type=pt_type_str,
        total_cycles_count=len(cycles),
        total_mules_count=len(mules),
        cycles=cycles,
        passthrough_mules=mules,
    )


# =============================================================================
# 4. Dedicated Tool: Legal Precedents Vector Search
# =============================================================================
@router.post(
    "/legal-precedents",
    response_model=LegalPrecedentQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic vector search against Mexican AML statutes",
    description="Vector similarity search using pgvector cosine distance (<=>) or deterministic cosine similarity matching Mexican AML / CFF 69-B jurisprudence.",
)
async def query_legal_precedents(
    request: LegalPrecedentQueryRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> LegalPrecedentQueryResponse:
    # 1. Resolve embedding vector
    if request.query_vector is not None:
        target_vector = request.query_vector
    else:
        target_vector = generate_deterministic_embedding(request.query_text, dim=1536)

    articles: List[Dict[str, Any]] = []

    # 2. Retrieve candidates from database or fallback
    if db is not None:
        stmt = select(LegalArticleVector)
        if request.law_name_filter:
            stmt = stmt.where(LegalArticleVector.law_name.ilike(f"%{request.law_name_filter}%"))
        rows = (await db.execute(stmt)).scalars().all()
        for r in rows:
            emb = r.embedding
            if emb is None:
                emb = generate_deterministic_embedding(r.content, dim=1536)
            articles.append({
                "article_code": r.article_code,
                "law_name": r.law_name,
                "content": r.content,
                "embedding": emb,
            })
    else:
        for seed in SEED_LEGAL_PRECEDENTS:
            if request.law_name_filter and request.law_name_filter.lower() not in seed["law_name"].lower():
                continue
            emb = seed.get("embedding")
            if emb is None:
                emb = generate_deterministic_embedding(seed["content"], dim=1536)
            articles.append({
                "article_code": seed["article_code"],
                "law_name": seed["law_name"],
                "content": seed["content"],
                "embedding": emb,
            })

    # 3. Compute cosine similarity
    # Both vectors are unit-normalized, so cosine similarity = dot product
    results: List[LegalPrecedentItem] = []
    target_norm = math.sqrt(sum(x * x for x in target_vector)) or 1.0

    for item in articles:
        cand_emb = item["embedding"]
        cand_norm = math.sqrt(sum(x * x for x in cand_emb)) or 1.0
        dot = sum(a * b for a, b in zip(target_vector, cand_emb))
        similarity = dot / (target_norm * cand_norm)
        similarity = max(-1.0, min(1.0, similarity))
        distance = max(0.0, 1.0 - similarity)

        threshold = request.similarity_threshold if request.similarity_threshold is not None else -1.0
        if similarity >= threshold:
            results.append(
                LegalPrecedentItem(
                    article_code=item["article_code"],
                    law_name=item["law_name"],
                    content=item["content"],
                    similarity_score=round(similarity, 4),
                    distance=round(distance, 4),
                )
            )

    # 4. Rank by similarity score descending
    results.sort(key=lambda x: x.similarity_score, reverse=True)
    sliced = results[: request.top_k]

    return LegalPrecedentQueryResponse(
        query_text=request.query_text,
        top_k=request.top_k,
        total_matches=len(results),
        results=sliced,
    )


# =============================================================================
# 5. Dynamic Tool: Composable Query Builder
# =============================================================================
@router.post(
    "/query",
    response_model=DynamicQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Dynamic Composable Query for AI Agents",
    description="Safely queries case transactions, entities, patterns, cases, or legal precedents with parameterized ASTs and column whitelisting.",
)
async def dynamic_query(
    request: DynamicQueryRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> DynamicQueryResponse:
    return await tool_registry.execute_query(request, db)
