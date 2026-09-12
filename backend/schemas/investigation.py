"""
Pydantic v2 schemas for Investigation API endpoints, graph topology,
and persistent forensic analysis cases.
"""

from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Union
import uuid

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class CaseStatus(str, Enum):
    """Lifecycle status states for an AML investigation case."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# -----------------------------------------------------------------------------
# Graph & Topological Structures
# -----------------------------------------------------------------------------
class GraphNode(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str = Field(..., description="Unique bank account identifier")
    total_in: float = Field(default=0.0, description="Total received funds in MXN")
    total_out: float = Field(default=0.0, description="Total dispersed funds in MXN")
    in_degree: int = Field(default=0, description="Incoming degree / number of incoming connections")
    out_degree: int = Field(default=0, description="Outgoing degree / number of outgoing connections")
    reasons: List[str] = Field(default_factory=list, description="Topological risk reasons")
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Assigned risk score [0.0 - 1.0]")


class GraphEdge(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    source: str = Field(..., description="Origin account ID")
    target: str = Field(..., description="Destination account ID")
    amount: float = Field(default=0.0, description="Aggregated transfer volume in MXN")
    count: int = Field(default=1, description="Number of transfers between accounts")
    timestamps: List[float] = Field(default_factory=list, description="Observed timestamps or steps")
    reasons: List[str] = Field(default_factory=list, description="Suspicion justification flags")


class SubgraphData(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    nodes: List[GraphNode] = Field(default_factory=list, description="Isolated suspicious graph nodes")
    edges: List[GraphEdge] = Field(default_factory=list, description="Suspicious directed edges between nodes")


class InvestigationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    total_nodes_analyzed: int = Field(default=0, description="Total unique nodes in dataset")
    suspicious_nodes_count: int = Field(default=0, description="Count of suspicious nodes in isolated subgraph")
    pruned_nodes_count: int = Field(default=0, description="Count of benign nodes discarded")
    total_edges_analyzed: int = Field(default=0, description="Total transactions in raw dataset")
    suspicious_edges_count: int = Field(default=0, description="Count of suspicious edges retained")
    pruned_edges_count: int = Field(default=0, description="Count of benign edges discarded")
    suspicious_volume_mxn: float = Field(default=0.0, description="Total volume flagged as suspicious in MXN")
    detected_cycles_count: int = Field(default=0, description="Number of detected circular flow cycles")
    passthrough_accounts_count: int = Field(default=0, description="Number of rapid pass-through mule accounts")
    pruning_efficiency_pct: float = Field(default=0.0, description="Percentage of benign transactions pruned")


class CyclePattern(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    path: List[str] = Field(default_factory=list, description="Closed cycle account sequence")
    length: int = Field(default=0, description="Cycle hop length")
    estimated_volume: float = Field(default=0.0, description="Estimated volume circulating in cycle")


class PassthroughAccountPattern(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    account: str = Field(..., description="Mule account identifier")
    total_in: float = Field(default=0.0, description="Total incoming volume in MXN")
    total_out: float = Field(default=0.0, description="Total outgoing volume in MXN")
    ratio: float = Field(default=0.0, description="Pass-through ratio >= 0.90")
    time_delta_hours: float = Field(default=0.0, description="Window duration in hours between in and out")


class InvestigationPatterns(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    cycles: List[CyclePattern] = Field(default_factory=list, description="Detected directed cycles")
    passthrough_accounts: List[PassthroughAccountPattern] = Field(
        default_factory=list, description="Detected mule accounts"
    )


# -----------------------------------------------------------------------------
# Verdict & Reasoning Models
# -----------------------------------------------------------------------------
class VerdictPatternsSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    closed_cycles: int = Field(default=0, description="Count of closed cycles detected")
    passthrough_accounts: int = Field(default=0, description="Count of pass-through accounts detected")
    pruning_efficiency_pct: float = Field(default=0.0, description="Percentage of noise transactions pruned")


class VerdictPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: Union[uuid.UUID, str] = Field(..., description="Case UUID")
    risk_level: str = Field(..., description="Risk tier: CRÍTICO, ALTO, MEDIO, BAJO")
    fraud_type: str = Field(..., description="Identified money laundering typology")
    total_amount_mxn: float = Field(..., description="Total flagged volume in MXN")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence score [0.0 - 1.0]")
    entities_involved: List[str] = Field(default_factory=list, description="Key suspicious account IDs")
    pruned_leads_count: int = Field(default=0, description="Count of discarded non-suspicious leads")
    patterns_summary: VerdictPatternsSummary = Field(..., description="Topological patterns metrics summary")
    legal_recommendation: str = Field(..., description="Legal and regulatory recommendation")
    audit_summary_text: str = Field(..., description="Narrative summary for forensic report")
    completed_at: Union[datetime, str] = Field(..., description="Verdict completion timestamp (UTC)")


class ThoughtEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    step: int = Field(..., ge=1, le=6, description="Step sequence index")
    phase: str = Field(..., description="Investigation phase name")
    message: str = Field(..., description="Step reasoning observation")
    timestamp: Union[datetime, str] = Field(..., description="Timestamp of event emission")


# -----------------------------------------------------------------------------
# Endpoint Request & Response Schemas
# -----------------------------------------------------------------------------
class InvestigationUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: Union[uuid.UUID, str] = Field(..., description="Newly allocated case UUID")
    filename: Optional[str] = Field(None, description="Filename of uploaded dataset")
    status: str = Field(default="PROCESSING", description="Initial case status")
    created_at: Optional[Union[datetime, str]] = Field(None, description="Creation timestamp")
    message: str = Field(default="Dataset successfully processed and pruned.", description="Status message")
    metrics: InvestigationMetrics = Field(..., description="Topological pruning metrics")
    subgraph: SubgraphData = Field(..., description="Suspicious graph topology")
    patterns: InvestigationPatterns = Field(..., description="Detected cycles and pass-through patterns")


class InvestigationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: Union[uuid.UUID, str] = Field(..., validation_alias=AliasChoices("case_id", "id"))
    filename: str = Field(default="", description="Dataset filename")
    status: str = Field(default="PENDING", description="Case status")
    created_at: Union[datetime, str] = Field(..., description="Creation timestamp")
    updated_at: Optional[Union[datetime, str]] = Field(None, description="Last updated timestamp")
    metrics: Optional[InvestigationMetrics] = Field(None, description="Topological metrics")
    has_verdict: bool = Field(default=False, description="True if verdict has been generated")
    risk_level: Optional[str] = Field(None, description="Risk level if verdict exists")

    @model_validator(mode="before")
    @classmethod
    def populate_summary_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Resolve case_id if not explicit
            cid = data.get("case_id") or data.get("id")
            verdict = data.get("verdict")
            has_verdict = data.get("has_verdict", bool(verdict))
            risk_level = data.get("risk_level")
            if risk_level is None and isinstance(verdict, dict):
                risk_level = verdict.get("risk_level")

            # Metrics resolution
            metrics = data.get("metrics")
            if metrics is None and "filter_results" in data:
                metrics = data["filter_results"].get("metrics")

            return {
                "case_id": cid,
                "filename": data.get("filename", ""),
                "status": data.get("status", "PENDING"),
                "created_at": data.get("created_at") or datetime.now(timezone.utc),
                "updated_at": data.get("updated_at"),
                "metrics": metrics,
                "has_verdict": has_verdict,
                "risk_level": risk_level,
            }

        # ORM model instance
        verdict = getattr(data, "verdict", None)
        has_verdict = bool(verdict)
        risk_level = verdict.get("risk_level") if isinstance(verdict, dict) else None

        return {
            "case_id": getattr(data, "id", None),
            "filename": getattr(data, "filename", ""),
            "status": getattr(data, "status", "PENDING"),
            "created_at": getattr(data, "created_at", datetime.now(timezone.utc)),
            "updated_at": getattr(data, "updated_at", None),
            "metrics": getattr(data, "metrics", None),
            "has_verdict": has_verdict,
            "risk_level": risk_level,
        }


class InvestigationPaginationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    total: int = Field(..., ge=0, description="Total matching cases in database")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total pages available")
    items: List[InvestigationSummary] = Field(default_factory=list, description="Investigation summaries on this page")


class InvestigationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: Union[uuid.UUID, str] = Field(..., validation_alias=AliasChoices("case_id", "id"))
    filename: str = Field(default="", description="Dataset filename")
    status: str = Field(default="PROCESSING", description="Investigation status")
    created_at: Union[datetime, str] = Field(..., description="Creation timestamp")
    updated_at: Optional[Union[datetime, str]] = Field(None, description="Last updated timestamp")
    ingestion_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("ingestion_metadata", "ingestion"),
        description="Raw ingestion statistics",
    )
    metrics: InvestigationMetrics = Field(default_factory=InvestigationMetrics, description="Topological pruning metrics")
    subgraph: SubgraphData = Field(default_factory=SubgraphData, description="Isolated suspicious subgraph")
    patterns: InvestigationPatterns = Field(default_factory=InvestigationPatterns, description="Detected patterns")
    verdict: Optional[VerdictPayload] = Field(None, description="Final forensic verdict if generated")

    @model_validator(mode="before")
    @classmethod
    def extract_case_details(cls, data: Any) -> Any:
        if isinstance(data, dict):
            filter_res = data.get("filter_results") or {}
            metrics = data.get("metrics") or filter_res.get("metrics") or {}
            subgraph = data.get("subgraph") or filter_res.get("subgraph") or {}
            patterns = data.get("patterns") or filter_res.get("patterns") or {}
            ingestion = data.get("ingestion_metadata") or data.get("ingestion") or {}

            return {
                "case_id": data.get("case_id") or data.get("id"),
                "filename": data.get("filename", ""),
                "status": data.get("status", "PROCESSING"),
                "created_at": data.get("created_at") or datetime.now(timezone.utc),
                "updated_at": data.get("updated_at"),
                "ingestion_metadata": ingestion,
                "metrics": metrics,
                "subgraph": subgraph,
                "patterns": patterns,
                "verdict": data.get("verdict"),
            }

        return data
