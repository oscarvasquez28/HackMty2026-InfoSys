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
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.investigations import (
    INVESTIGATION_CASES,
    get_optional_db,
)
from backend.models.forensic import (
    AccountMappingRecord,
    AccountRecord,
    CashTransactionRecord,
    IN_MEMORY_BANKING_DATA,
    InvestigationCase,
    LegalArticleVector,
    PartyRecord,
    SEED_LEGAL_PRECEDENTS,
    TransactionRecord,
    generate_deterministic_embedding,
)
from backend.schemas.agent_tools import (
    AnalyzePaymentPatternsRequest,
    AnalyzePaymentPatternsResponse,
    CashoutItem,
    CashoutRequest,
    CashoutResponse,
    CompareEntitiesRequest,
    CompareEntitiesResponse,
    CyclePatternItem,
    DetectCircularFlowRequest,
    DetectCircularFlowResponse,
    DynamicQueryRequest,
    DynamicQueryResponse,
    EntityOwnerComparisonItem,
    EntityProfileItem,
    EntityProfileRequest,
    EntityProfileResponse,
    FinancialHistoryRequest,
    FinancialHistoryResponse,
    FlowPathItem,
    LegalPrecedentItem,
    LegalPrecedentQueryRequest,
    LegalPrecedentQueryResponse,
    PassthroughMuleItem,
    PatternQueryRequest,
    PatternQueryResponse,
    PatternType,
    RelatedEntitiesRequest,
    RelatedEntitiesResponse,
    RelatedEntityItem,
    RelatedTransactionGroup,
    RelatedTransactionsRequest,
    RelatedTransactionsResponse,
    SharedEntitiesRequest,
    SharedEntitiesResponse,
    SharedEntityPairItem,
    TraceMoneyFlowRequest,
    TraceMoneyFlowResponse,
    TransactionChainItem,
    TransactionChainsRequest,
    TransactionChainsResponse,
    TransactionItem,
    TransactionQueryRequest,
    TransactionQueryResponse,
)
from backend.services.tool_registry import tool_registry

logger = logging.getLogger("forensic_auditor.agent_tools")

router = APIRouter(prefix="/tools", tags=["agent-tools"])


# =============================================================================
# 1. Dedicated Tool: Transactions (search_transactions)
# =============================================================================
@router.post(
    "/transactions",
    response_model=TransactionQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query and filter case transactions (search_transactions)",
    description="Filter transactions by case_id, origin, destination, amount range, time window, and suspicion flag.",
)
@router.post(
    "/search_transactions",
    response_model=TransactionQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for search_transactions",
    include_in_schema=False,
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
        if request.entity_id:
            where_clauses.append(
                or_(
                    TransactionRecord.origin == request.entity_id,
                    TransactionRecord.destination == request.entity_id,
                )
            )
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
            if request.entity_id and r.get("origin") != request.entity_id and r.get("destination") != request.entity_id:
                continue
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


# =============================================================================
# Helper: Transaction Pool Extraction for Graph & Relational Traversals
# =============================================================================
async def _get_transactions_pool(
    case_id: Optional[Union[uuid.UUID, str]],
    db: Optional[AsyncSession],
) -> List[Dict[str, Any]]:
    """Fetches transactions scoped to case_id, or from all cases in fallback/DB."""
    if db is not None:
        stmt = select(TransactionRecord)
        if case_id:
            try:
                c_uuid = uuid.UUID(str(case_id))
                stmt = stmt.where(TransactionRecord.case_id == c_uuid)
            except ValueError:
                pass
        rows = (await db.execute(stmt)).scalars().all()
        return [
            {
                "id": str(r.id),
                "case_id": str(r.case_id),
                "origin": r.origin,
                "destination": r.destination,
                "amount": float(r.amount),
                "timestamp": r.timestamp.isoformat() if hasattr(r.timestamp, "isoformat") else str(r.timestamp),
                "is_suspicious": r.is_suspicious,
                "reasons": r.reasons or [],
            }
            for r in rows
        ]
    else:
        results = []
        if case_id and str(case_id) in INVESTIGATION_CASES:
            case_data = INVESTIGATION_CASES[str(case_id)]
            txs = case_data.get("transactions", [])
            if not txs and "subgraph" in case_data:
                edges = case_data["subgraph"].get("edges", [])
                txs = [
                    {
                        "id": str(uuid.uuid4()),
                        "case_id": str(case_id),
                        "origin": e.get("source", ""),
                        "destination": e.get("target", ""),
                        "amount": float(e.get("amount", 0.0)),
                        "timestamp": (e.get("timestamps") or ["0"])[0],
                        "is_suspicious": bool(e.get("reasons")),
                        "reasons": e.get("reasons", []),
                    }
                    for e in edges
                ]
            results.extend(txs)
        else:
            for cid, cdata in INVESTIGATION_CASES.items():
                results.extend(cdata.get("transactions", []))
        return results


# =============================================================================
# 6. Tool 1: find_related_entities
# =============================================================================
@router.post(
    "/related-entities",
    response_model=RelatedEntitiesResponse,
    status_code=status.HTTP_200_OK,
    summary="Find entities frequently transacting with target",
    description="Returns a list of associated companies, subsidiaries, parent organizations, or known individuals constantly transacting with target.",
)
@router.post(
    "/find_related_entities",
    response_model=RelatedEntitiesResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for find_related_entities",
    include_in_schema=False,
)
async def find_related_entities(
    request: RelatedEntitiesRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> RelatedEntitiesResponse:
    tx_pool = await _get_transactions_pool(request.case_id, db)

    # Counterparty metrics aggregation
    stats: Dict[str, Dict[str, Any]] = {}
    target = str(request.entity_id).strip()

    for tx in tx_pool:
        orig = str(tx.get("origin", "")).strip()
        dest = str(tx.get("destination", "")).strip()
        amt = float(tx.get("amount", 0.0))

        if orig == target and dest:
            cp = dest
            if cp not in stats:
                stats[cp] = {"tx_count": 0, "total_vol": 0.0, "in_from_tgt": 0.0, "out_to_tgt": 0.0}
            stats[cp]["tx_count"] += 1
            stats[cp]["total_vol"] += amt
            stats[cp]["in_from_tgt"] += amt
        elif dest == target and orig:
            cp = orig
            if cp not in stats:
                stats[cp] = {"tx_count": 0, "total_vol": 0.0, "in_from_tgt": 0.0, "out_to_tgt": 0.0}
            stats[cp]["tx_count"] += 1
            stats[cp]["total_vol"] += amt
            stats[cp]["out_to_tgt"] += amt

    # Filter by min_tx_count and min_volume
    filtered_cps = [
        (cp, data)
        for cp, data in stats.items()
        if data["tx_count"] >= request.min_tx_count
        and (request.min_volume is None or data["total_vol"] >= request.min_volume)
    ]
    # Sort by total volume descending
    filtered_cps.sort(key=lambda x: x[1]["total_vol"], reverse=True)
    total_matches = len(filtered_cps)
    sliced = filtered_cps[request.offset : request.offset + request.limit]

    items: List[RelatedEntityItem] = []
    for cp, data in sliced:
        party_name = None
        party_type = None
        rel_type = "FREQUENT_COUNTERPARTY"

        if db is not None:
            # Check party and mapping tables
            mapping_stmt = select(AccountMappingRecord.cust_id).where(AccountMappingRecord.acct_id == cp)
            cust_id = (await db.execute(mapping_stmt)).scalar_one_or_none()
            if cust_id:
                p_stmt = select(PartyRecord).where(PartyRecord.party_id == cust_id)
                party = (await db.execute(p_stmt)).scalar_one_or_none()
                if party:
                    party_name = party.legal_name or f"{party.first_name or ''} {party.last_name or ''}".strip()
                    party_type = party.party_type
            if not party_name:
                a_stmt = select(AccountRecord).where(AccountRecord.acct_id == cp)
                acct = (await db.execute(a_stmt)).scalar_one_or_none()
                if acct:
                    party_name = acct.dsply_nm or f"{acct.first_name or ''} {acct.last_name or ''}".strip()
                    party_type = "Corporate" if acct.type == "C" else "Individual"
        else:
            # In-memory lookup
            mappings = [m for m in IN_MEMORY_BANKING_DATA["account_mappings"] if m["acct_id"] == cp]
            if mappings:
                cid = mappings[0]["cust_id"]
                p = IN_MEMORY_BANKING_DATA["parties"].get(cid)
                if p:
                    party_name = p.get("legal_name") or f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip()
                    party_type = p.get("party_type")
            if not party_name:
                a = IN_MEMORY_BANKING_DATA["accounts"].get(cp)
                if a:
                    party_name = a.get("dsply_nm") or f"{a.get('first_name') or ''} {a.get('last_name') or ''}".strip()
                    party_type = "Corporate" if a.get("type") == "C" else "Individual"

        if party_type == "Organization":
            rel_type = "SUBSIDIARY_OR_AFFILIATE"

        items.append(
            RelatedEntityItem(
                entity_id=cp,
                party_name=party_name,
                party_type=party_type,
                relationship_type=rel_type,
                tx_count=data["tx_count"],
                total_volume=round(data["total_vol"], 2),
                inflow_from_target=round(data["in_from_tgt"], 2),
                outflow_to_target=round(data["out_to_tgt"], 2),
            )
        )

    return RelatedEntitiesResponse(
        target_entity_id=target,
        case_id=str(request.case_id) if request.case_id else None,
        total_related=total_matches,
        items=items,
    )


# =============================================================================
# 7. Tool 2: compare_entities
# =============================================================================
@router.post(
    "/compare-entities",
    response_model=CompareEntitiesResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare entities and detect shared ownership",
    description="Returns entities that have the same owner (physical or moral person) through customer mappings, SSNs, and party records.",
)
@router.post(
    "/compare_entities",
    response_model=CompareEntitiesResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for compare_entities",
    include_in_schema=False,
)
async def compare_entities(
    request: CompareEntitiesRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> CompareEntitiesResponse:
    entity_ids = [str(e).strip() for e in request.entity_ids if str(e).strip()]
    owner_info: Dict[str, Dict[str, Any]] = {}

    for eid in entity_ids:
        info = {"owner_id": None, "owner_name": None, "owner_type": None, "ssn": None}
        if db is not None:
            # 1. Look in account_mappings
            mapping_stmt = select(AccountMappingRecord.cust_id).where(AccountMappingRecord.acct_id == eid)
            cust_id = (await db.execute(mapping_stmt)).scalar_one_or_none()
            if cust_id:
                info["owner_id"] = str(cust_id)
                p_stmt = select(PartyRecord).where(PartyRecord.party_id == cust_id)
                party = (await db.execute(p_stmt)).scalar_one_or_none()
                if party:
                    info["owner_name"] = party.legal_name or f"{party.first_name or ''} {party.last_name or ''}".strip()
                    info["owner_type"] = party.party_type
            # 2. Look in accounts
            acct_stmt = select(AccountRecord).where(AccountRecord.acct_id == eid)
            acct = (await db.execute(acct_stmt)).scalar_one_or_none()
            if acct:
                if not info["owner_name"]:
                    info["owner_name"] = acct.dsply_nm or f"{acct.first_name or ''} {acct.last_name or ''}".strip()
                if not info["owner_type"]:
                    info["owner_type"] = "Corporate" if acct.type == "C" else "Individual"
                info["ssn"] = acct.ssn
                if not info["owner_id"]:
                    info["owner_id"] = acct.ssn or acct.acct_id
        else:
            mappings = [m for m in IN_MEMORY_BANKING_DATA["account_mappings"] if m["acct_id"] == eid]
            if mappings:
                cid = mappings[0]["cust_id"]
                info["owner_id"] = str(cid)
                p = IN_MEMORY_BANKING_DATA["parties"].get(cid)
                if p:
                    info["owner_name"] = p.get("legal_name") or f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip()
                    info["owner_type"] = p.get("party_type")
            a = IN_MEMORY_BANKING_DATA["accounts"].get(eid)
            if a:
                if not info["owner_name"]:
                    info["owner_name"] = a.get("dsply_nm") or f"{a.get('first_name') or ''} {a.get('last_name') or ''}".strip()
                if not info["owner_type"]:
                    info["owner_type"] = "Corporate" if a.get("type") == "C" else "Individual"
                info["ssn"] = a.get("ssn")
                if not info["owner_id"]:
                    info["owner_id"] = a.get("ssn") or a.get("acct_id")

        owner_info[eid] = info

    # Group entities by owner key
    groups_by_owner: Dict[str, List[str]] = {}
    for eid, info in owner_info.items():
        owner_key = info["owner_id"] or info["ssn"] or info["owner_name"] or f"UNKNOWN_{eid}"
        groups_by_owner.setdefault(owner_key, []).append(eid)

    comparisons: List[EntityOwnerComparisonItem] = []
    for eid, info in owner_info.items():
        owner_key = info["owner_id"] or info["ssn"] or info["owner_name"] or f"UNKNOWN_{eid}"
        all_in_group = groups_by_owner.get(owner_key, [])
        shared_with = [other for other in all_in_group if other != eid]
        comparisons.append(
            EntityOwnerComparisonItem(
                entity_id=eid,
                owner_id=info["owner_id"],
                owner_name=info["owner_name"],
                owner_type=info["owner_type"],
                ssn=info["ssn"],
                shared_with=shared_with,
                has_common_owner=len(shared_with) > 0,
            )
        )

    return CompareEntitiesResponse(
        entities_analyzed=len(entity_ids),
        groups_by_owner={k: v for k, v in groups_by_owner.items() if len(v) > 1 or not k.startswith("UNKNOWN")},
        comparisons=comparisons,
    )


# =============================================================================
# 8. Tool 4: analyze_payment_patterns
# =============================================================================
@router.post(
    "/analyze-payment-patterns",
    response_model=AnalyzePaymentPatternsResponse,
    status_code=status.HTTP_200_OK,
    summary="Fast pattern check for fraudulent circular or mule behaviors",
    description="Returns whether there are fraudulent patterns (circular or mule) with no other metadata needed.",
)
@router.post(
    "/analyze_payment_patterns",
    response_model=AnalyzePaymentPatternsResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for analyze_payment_patterns",
    include_in_schema=False,
)
async def analyze_payment_patterns(
    request: AnalyzePaymentPatternsRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> AnalyzePaymentPatternsResponse:
    try:
        case_uuid = uuid.UUID(str(request.case_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format for case_id: '{request.case_id}'",
        )

    patterns: Dict[str, Any] = {}
    if db is not None:
        stmt = select(InvestigationCase.patterns).where(InvestigationCase.id == case_uuid)
        res = await db.execute(stmt)
        patterns = res.scalar_one_or_none() or {}
        if not patterns:
            exists = (await db.execute(select(InvestigationCase.id).where(InvestigationCase.id == case_uuid))).scalar_one_or_none()
            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Investigation case '{case_uuid}' not found.",
                )
    else:
        case_data = INVESTIGATION_CASES.get(str(case_uuid))
        if not case_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation case '{case_uuid}' not found.",
            )
        patterns = case_data.get("patterns", {})

    cycles = patterns.get("cycles", [])
    mules = patterns.get("passthrough_accounts", [])

    if request.entity_id:
        target = str(request.entity_id).strip()
        cycles = [c for c in cycles if target in c.get("path", [])]
        mules = [m for m in mules if m.get("account") == target]

    has_circular = len(cycles) > 0
    has_mule = len(mules) > 0
    has_fraud = has_circular or has_mule

    summary_parts = []
    if has_circular:
        summary_parts.append(f"{len(cycles)} circular layering cycle(s) detected")
    if has_mule:
        summary_parts.append(f"{len(mules)} high-velocity pass-through mule account(s) detected")
    if not has_fraud:
        summary_parts.append("No suspicious circular or pass-through mule topologies detected")

    return AnalyzePaymentPatternsResponse(
        case_id=str(case_uuid),
        has_fraudulent_patterns=has_fraud,
        has_circular_patterns=has_circular,
        has_mule_patterns=has_mule,
        detected_cycles_count=len(cycles),
        passthrough_mules_count=len(mules),
        summary="; ".join(summary_parts),
    )


# =============================================================================
# 9. Tool 5: search_financial_history
# =============================================================================
@router.post(
    "/financial-history",
    response_model=FinancialHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve complete metadata of an account owner",
    description="Returns metadata of a specific account owner by linking accounts, account mappings, and party KYC records.",
)
@router.post(
    "/search_financial_history",
    response_model=FinancialHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for search_financial_history",
    include_in_schema=False,
)
async def search_financial_history(
    request: FinancialHistoryRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> FinancialHistoryResponse:
    if not request.account_id and not request.party_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'account_id' or 'party_id' must be provided.",
        )

    acct_id = str(request.account_id).strip() if request.account_id else None
    party_id = str(request.party_id).strip() if request.party_id else None

    acct_details = None
    party_details = None
    associated_accounts: List[Dict[str, Any]] = []
    owner_name = None
    owner_type = None
    initial_deposit = None
    acct_status = None
    prior_sar = 0

    if db is not None:
        if acct_id:
            acct_stmt = select(AccountRecord).where(AccountRecord.acct_id == acct_id)
            acct = (await db.execute(acct_stmt)).scalar_one_or_none()
            if acct:
                acct_details = {
                    "acct_id": acct.acct_id,
                    "dsply_nm": acct.dsply_nm,
                    "type": acct.type,
                    "acct_stat": acct.acct_stat,
                    "acct_rptng_crncy": acct.acct_rptng_crncy,
                    "branch_id": acct.branch_id,
                    "initial_deposit": float(acct.initial_deposit) if acct.initial_deposit else None,
                    "open_dt": acct.open_dt,
                    "ssn": acct.ssn,
                    "city": acct.city,
                    "state": acct.state,
                }
                initial_deposit = acct_details["initial_deposit"]
                acct_status = acct.acct_stat
                prior_sar = acct.prior_sar_count or 0
                owner_name = acct.dsply_nm or f"{acct.first_name or ''} {acct.last_name or ''}".strip()
                owner_type = "Corporate" if acct.type == "C" else "Individual"

            if not party_id:
                mapping_stmt = select(AccountMappingRecord.cust_id).where(AccountMappingRecord.acct_id == acct_id)
                party_id = (await db.execute(mapping_stmt)).scalar_one_or_none()

        if party_id:
            p_stmt = select(PartyRecord).where(PartyRecord.party_id == party_id)
            party = (await db.execute(p_stmt)).scalar_one_or_none()
            if party:
                party_details = {
                    "party_id": party.party_id,
                    "party_type": party.party_type,
                    "is_individual": party.is_individual,
                    "legal_name": party.legal_name,
                    "first_name": party.first_name,
                    "last_name": party.last_name,
                    "nationality": party.nationality,
                    "country_of_residency": party.country_of_residency,
                    "occupation": party.occupation,
                    "is_active": party.is_active,
                    "primary_phone": party.primary_phone,
                    "personal_email": party.personal_email,
                }
                owner_name = party.legal_name or f"{party.first_name or ''} {party.last_name or ''}".strip()
                owner_type = party.party_type

            # Find all accounts associated with this party
            map_stmt = select(AccountMappingRecord).where(AccountMappingRecord.cust_id == party_id)
            maps = (await db.execute(map_stmt)).scalars().all()
            for m in maps:
                associated_accounts.append({
                    "acct_id": m.acct_id,
                    "cust_acct_role": m.cust_acct_role,
                    "src_sys": m.src_sys,
                    "data_dump_dt": m.data_dump_dt,
                })
    else:
        # In-memory lookup
        if acct_id:
            a = IN_MEMORY_BANKING_DATA["accounts"].get(acct_id)
            if a:
                acct_details = dict(a)
                initial_deposit = a.get("initial_deposit")
                acct_status = a.get("acct_stat")
                prior_sar = a.get("prior_sar_count") or 0
                owner_name = a.get("dsply_nm") or f"{a.get('first_name') or ''} {a.get('last_name') or ''}".strip()
                owner_type = "Corporate" if a.get("type") == "C" else "Individual"

            if not party_id:
                for m in IN_MEMORY_BANKING_DATA["account_mappings"]:
                    if m["acct_id"] == acct_id:
                        party_id = m["cust_id"]
                        break

        if party_id:
            p = IN_MEMORY_BANKING_DATA["parties"].get(party_id)
            if p:
                party_details = dict(p)
                owner_name = p.get("legal_name") or f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip()
                owner_type = p.get("party_type")

            for m in IN_MEMORY_BANKING_DATA["account_mappings"]:
                if m["cust_id"] == party_id:
                    associated_accounts.append({
                        "acct_id": m["acct_id"],
                        "cust_acct_role": m["cust_acct_role"],
                        "src_sys": m["src_sys"],
                        "data_dump_dt": m["data_dump_dt"],
                    })

    if not acct_details and not party_details and not associated_accounts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Financial history record not found for account '{acct_id}' / party '{party_id}'",
        )

    return FinancialHistoryResponse(
        account_id=acct_id,
        party_id=party_id,
        owner_name=owner_name,
        owner_type=owner_type,
        account_details=acct_details,
        party_details=party_details,
        associated_accounts=associated_accounts,
        initial_deposit=initial_deposit,
        account_status=acct_status,
        prior_sar_count=prior_sar,
    )


# =============================================================================
# 10. Tool 6: get_cashout
# =============================================================================
@router.post(
    "/cashout",
    response_model=CashoutResponse,
    status_code=status.HTTP_200_OK,
    summary="List all ATM cash takeouts of an account",
    description="Returns the list of all cash takeouts at an ATM of a specific account.",
)
@router.post(
    "/get_cashout",
    response_model=CashoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for get_cashout",
    include_in_schema=False,
)
async def get_cashout(
    request: CashoutRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> CashoutResponse:
    target_acct = str(request.account_id).strip()

    if db is not None:
        stmt = select(CashTransactionRecord).where(CashTransactionRecord.account_id == target_acct)
        # Filter cashouts
        stmt = stmt.where(CashTransactionRecord.tx_type.ilike("%CASH-OUT%"))
        if request.min_amount is not None:
            stmt = stmt.where(CashTransactionRecord.amount >= Decimal(str(request.min_amount)))
        if request.max_amount is not None:
            stmt = stmt.where(CashTransactionRecord.amount <= Decimal(str(request.max_amount)))

        rows = (await db.execute(stmt)).scalars().all()
        matched = [
            CashoutItem(
                tran_id=r.tran_id,
                account_id=r.account_id,
                tx_type=r.tx_type,
                amount=float(r.amount),
                timestamp=r.timestamp,
                branch_id=r.branch_id,
                is_sar=bool(r.is_sar),
            )
            for r in rows
        ]
    else:
        raw_cash = IN_MEMORY_BANKING_DATA["cash_transactions"]
        filtered = []
        for r in raw_cash:
            if r["account_id"] != target_acct:
                continue
            if "cash-out" not in str(r.get("tx_type", "")).lower() and "atm" not in str(r.get("tx_type", "")).lower():
                continue
            amt = float(r.get("amount", 0.0))
            if request.min_amount is not None and amt < request.min_amount:
                continue
            if request.max_amount is not None and amt > request.max_amount:
                continue
            filtered.append(r)

        matched = [
            CashoutItem(
                tran_id=r["tran_id"],
                account_id=r["account_id"],
                tx_type=r["tx_type"],
                amount=float(r["amount"]),
                timestamp=r.get("timestamp"),
                branch_id=r.get("branch_id"),
                is_sar=bool(r.get("is_sar")),
            )
            for r in filtered
        ]

    total_count = len(matched)
    total_amount = sum(c.amount for c in matched)
    sliced = matched[request.offset : request.offset + request.limit]

    return CashoutResponse(
        account_id=target_acct,
        total_cashouts=total_count,
        total_amount=round(total_amount, 2),
        items=sliced,
    )


# =============================================================================
# 11. Tool 7: trace_money_flow
# =============================================================================
@router.post(
    "/trace-money-flow",
    response_model=TraceMoneyFlowResponse,
    status_code=status.HTTP_200_OK,
    summary="Trace capital flow paths across accounts",
    description="Returns directed paths and transaction node sequences mapping how capital moves from source accounts to destination accounts.",
)
@router.post(
    "/trace_money_flow",
    response_model=TraceMoneyFlowResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for trace_money_flow",
    include_in_schema=False,
)
async def trace_money_flow(
    request: TraceMoneyFlowRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> TraceMoneyFlowResponse:
    tx_pool = await _get_transactions_pool(request.case_id, db)

    # Build adjacency mapping: src -> list of (dst, amount, timestamp, id)
    adj: Dict[str, List[Dict[str, Any]]] = {}
    for tx in tx_pool:
        src = str(tx.get("origin", "")).strip()
        dst = str(tx.get("destination", "")).strip()
        if src and dst and src != dst:
            adj.setdefault(src, []).append({
                "target": dst,
                "amount": float(tx.get("amount", 0.0)),
                "timestamp": tx.get("timestamp"),
                "id": str(tx.get("id", "")),
            })

    src_target = str(request.source_account).strip() if request.source_account else None
    dst_target = str(request.destination_account).strip() if request.destination_account else None

    paths: List[FlowPathItem] = []

    def dfs(curr: str, target: Optional[str], visited: List[str], current_steps: List[Dict[str, Any]], depth: int):
        if len(paths) >= request.limit or depth > request.max_depth:
            return

        if target and curr == target and len(visited) > 1:
            tot_amt = sum(s["amount"] for s in current_steps)
            paths.append(FlowPathItem(
                path=list(visited),
                hops=len(visited) - 1,
                total_flow_amount=round(tot_amt, 2),
                step_details=list(current_steps),
            ))
            return

        if not target and len(visited) > 1:
            tot_amt = sum(s["amount"] for s in current_steps)
            paths.append(FlowPathItem(
                path=list(visited),
                hops=len(visited) - 1,
                total_flow_amount=round(tot_amt, 2),
                step_details=list(current_steps),
            ))

        for edge in adj.get(curr, []):
            nxt = edge["target"]
            if nxt not in visited:
                visited.append(nxt)
                current_steps.append(edge)
                dfs(nxt, target, visited, current_steps, depth + 1)
                current_steps.pop()
                visited.pop()

    if src_target:
        dfs(src_target, dst_target, [src_target], [], 0)
    elif dst_target:
        # Search all nodes that have outgoing edges leading to dst_target
        for node in adj.keys():
            if len(paths) >= request.limit:
                break
            if node != dst_target:
                dfs(node, dst_target, [node], [], 0)
    else:
        # Trace from top volume origin nodes
        top_origins = sorted(adj.keys(), key=lambda k: sum(e["amount"] for e in adj[k]), reverse=True)[:5]
        for start_node in top_origins:
            if len(paths) >= request.limit:
                break
            dfs(start_node, None, [start_node], [], 0)

    return TraceMoneyFlowResponse(
        case_id=str(request.case_id) if request.case_id else None,
        source_account=src_target,
        destination_account=dst_target,
        total_paths=len(paths),
        paths=paths[: request.limit],
    )


# =============================================================================
# 12. Tool 8: find_related_transactions
# =============================================================================
@router.post(
    "/related-transactions",
    response_model=RelatedTransactionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Find secondary and tertiary transactions linked to a core transaction",
    description="Returns secondary and tertiary transactions linked directly or indirectly to a core transaction identifier.",
)
@router.post(
    "/find_related_transactions",
    response_model=RelatedTransactionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for find_related_transactions",
    include_in_schema=False,
)
async def find_related_transactions(
    request: RelatedTransactionsRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> RelatedTransactionsResponse:
    tx_pool = await _get_transactions_pool(request.case_id, db)
    tid = str(request.transaction_id).strip()

    core_tx = None
    for tx in tx_pool:
        if str(tx.get("id")) == tid:
            core_tx = tx
            break

    if not core_tx and tx_pool:
        # Fallback by index or first transaction for tests if numeric id
        for tx in tx_pool:
            if tx.get("origin") == tid or tx.get("destination") == tid:
                core_tx = tx
                break

    if not core_tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Core transaction '{tid}' not found in case records.",
        )

    u = core_tx["origin"]
    v = core_tx["destination"]

    secondary_set: List[Dict[str, Any]] = []
    secondary_nodes: Set[str] = set()

    for tx in tx_pool:
        if tx.get("id") == core_tx.get("id"):
            continue
        orig = tx.get("origin")
        dest = tx.get("destination")
        if orig in (u, v) or dest in (u, v):
            secondary_set.append(tx)
            secondary_nodes.add(orig)
            secondary_nodes.add(dest)

    tertiary_set: List[Dict[str, Any]] = []
    if request.hops >= 3:
        sec_ids = {tx.get("id") for tx in secondary_set} | {core_tx.get("id")}
        for tx in tx_pool:
            if tx.get("id") in sec_ids:
                continue
            orig = tx.get("origin")
            dest = tx.get("destination")
            if orig in secondary_nodes or dest in secondary_nodes:
                tertiary_set.append(tx)

    group = RelatedTransactionGroup(
        direct_transaction=core_tx,
        secondary_transactions=secondary_set[: request.limit],
        tertiary_transactions=tertiary_set[: request.limit],
        total_secondary=len(secondary_set),
        total_tertiary=len(tertiary_set),
    )

    return RelatedTransactionsResponse(
        transaction_id=tid,
        hops=request.hops,
        results=group,
    )


# =============================================================================
# 13. Tool 9: find_transaction_chains
# =============================================================================
@router.post(
    "/transaction-chains",
    response_model=TransactionChainsResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover sequential multi-hop transaction chains between two endpoints",
    description="Returns multi-hop paths of sequential transactions connecting two distinct endpoints across intermediary nodes (possible mules).",
)
@router.post(
    "/find_transaction_chains",
    response_model=TransactionChainsResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for find_transaction_chains",
    include_in_schema=False,
)
async def find_transaction_chains(
    request: TransactionChainsRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> TransactionChainsResponse:
    tx_pool = await _get_transactions_pool(request.case_id, db)
    src = str(request.source_account).strip()
    dst = str(request.destination_account).strip()

    adj: Dict[str, List[Dict[str, Any]]] = {}
    for tx in tx_pool:
        o = str(tx.get("origin", "")).strip()
        d = str(tx.get("destination", "")).strip()
        if o and d and o != d:
            adj.setdefault(o, []).append(tx)

    chains: List[TransactionChainItem] = []

    def dfs(curr: str, visited: List[str], current_txs: List[Dict[str, Any]]):
        if len(chains) >= request.limit or len(visited) > request.max_hops + 1:
            return

        if curr == dst and len(visited) >= 3:  # At least 1 intermediary (>= 2 hops)
            tot_vol = sum(float(t.get("amount", 0.0)) for t in current_txs)
            intermediaries = visited[1:-1]
            chains.append(
                TransactionChainItem(
                    chain_id=str(uuid.uuid4()),
                    path=list(visited),
                    length=len(visited) - 1,
                    intermediaries=intermediaries,
                    total_volume=round(tot_vol, 2),
                    transactions=list(current_txs),
                )
            )
            return

        for tx in adj.get(curr, []):
            nxt = tx["destination"]
            if nxt not in visited:
                visited.append(nxt)
                current_txs.append(tx)
                dfs(nxt, visited, current_txs)
                current_txs.pop()
                visited.pop()

    dfs(src, [src], [])

    return TransactionChainsResponse(
        source_account=src,
        destination_account=dst,
        case_id=str(request.case_id) if request.case_id else None,
        total_chains=len(chains),
        chains=chains,
    )


# =============================================================================
# 14. Tool 10: find_shared_entities
# =============================================================================
@router.post(
    "/shared-entities",
    response_model=SharedEntitiesResponse,
    status_code=status.HTTP_200_OK,
    summary="Identify entities following similar downstream transaction sequences",
    description="Returns entities which follow similar transaction patterns in different transaction flows (e.g., Company A -> C -> D and Company B -> C -> D).",
)
@router.post(
    "/find_shared_entities",
    response_model=SharedEntitiesResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for find_shared_entities",
    include_in_schema=False,
)
async def find_shared_entities(
    request: SharedEntitiesRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> SharedEntitiesResponse:
    tx_pool = await _get_transactions_pool(request.case_id, db)

    adj: Dict[str, Set[str]] = {}
    for tx in tx_pool:
        o = str(tx.get("origin", "")).strip()
        d = str(tx.get("destination", "")).strip()
        if o and d:
            adj.setdefault(o, set()).add(d)

    # Find common 2-hop sequences: orig -> nxt1 -> nxt2
    sequence_to_origins: Dict[str, Set[str]] = {}
    for orig, targets in adj.items():
        for t1 in targets:
            if t1 in adj:
                for t2 in adj[t1]:
                    seq_key = f"{t1}->{t2}"
                    sequence_to_origins.setdefault(seq_key, set()).add(orig)

    pairs: List[SharedEntityPairItem] = []
    for seq_key, origins in sequence_to_origins.items():
        if len(origins) >= 2:
            orig_list = sorted(list(origins))
            seq_nodes = seq_key.split("->")
            for i in range(len(orig_list)):
                for j in range(i + 1, len(orig_list)):
                    pairs.append(
                        SharedEntityPairItem(
                            entities=[orig_list[i], orig_list[j]],
                            common_target_sequence=seq_nodes,
                            similarity_type="SHARED_DOWNSTREAM_PATH",
                            shared_hops=len(seq_nodes),
                        )
                    )
                    if len(pairs) >= request.limit:
                        break
                if len(pairs) >= request.limit:
                    break
        if len(pairs) >= request.limit:
            break

    return SharedEntitiesResponse(
        case_id=str(request.case_id) if request.case_id else None,
        total_shared_pairs=len(pairs),
        items=pairs[: request.limit],
    )


# =============================================================================
# 15. Tool 11: detect_circular_flow
# =============================================================================
@router.post(
    "/circular-flow",
    response_model=DetectCircularFlowResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect closed cyclical transaction loops (round-tripping)",
    description="Returns detected closed loops or cyclical routing paths where funds originate and return to the same entity or allied shell accounts.",
)
@router.post(
    "/detect_circular_flow",
    response_model=DetectCircularFlowResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias for detect_circular_flow",
    include_in_schema=False,
)
async def detect_circular_flow(
    request: DetectCircularFlowRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> DetectCircularFlowResponse:
    cycles: List[CyclePatternItem] = []

    if request.case_id:
        try:
            case_uuid = uuid.UUID(str(request.case_id))
            if db is not None:
                stmt = select(InvestigationCase.patterns).where(InvestigationCase.id == case_uuid)
                p = (await db.execute(stmt)).scalar_one_or_none() or {}
                raw_cycles = p.get("cycles", [])
            else:
                cdata = INVESTIGATION_CASES.get(str(case_uuid), {})
                raw_cycles = cdata.get("patterns", {}).get("cycles", [])
        except ValueError:
            raw_cycles = []
    else:
        # Scan across all known cases
        raw_cycles = []
        for cdata in INVESTIGATION_CASES.values():
            raw_cycles.extend(cdata.get("patterns", {}).get("cycles", []))

    # Also extract graph cycles directly from tx_pool if no cycles stored yet
    if not raw_cycles:
        tx_pool = await _get_transactions_pool(request.case_id, db)
        import networkx as nx
        G = nx.DiGraph()
        for tx in tx_pool:
            G.add_edge(tx["origin"], tx["destination"], amount=tx["amount"])
        try:
            detected = nx.simple_cycles(G)
            for c in detected:
                if 2 <= len(c) <= request.max_cycle_length:
                    cycle_path = c + [c[0]]
                    vol = sum(G[u][v].get("amount", 0.0) for u, v in zip(cycle_path[:-1], cycle_path[1:]))
                    raw_cycles.append({
                        "path": cycle_path,
                        "length": len(c),
                        "estimated_volume": vol,
                    })
        except Exception:
            pass

    # Filter by entity_id, max_cycle_length, and min_volume
    for c in raw_cycles:
        path = c.get("path", [])
        length = int(c.get("length", len(path) - 1 if len(path) > 1 else 0))
        vol = float(c.get("estimated_volume", 0.0))

        if request.entity_id and str(request.entity_id).strip() not in path:
            continue
        if length > request.max_cycle_length:
            continue
        if request.min_volume is not None and vol < request.min_volume:
            continue

        cycles.append(
            CyclePatternItem(
                path=path,
                length=length,
                estimated_volume=round(vol, 2),
            )
        )

    tot_vol = sum(c.estimated_volume for c in cycles)

    return DetectCircularFlowResponse(
        case_id=str(request.case_id) if request.case_id else None,
        total_cycles=len(cycles),
        cycles=cycles[: request.limit],
        total_cyclical_volume=round(tot_vol, 2),
    )

