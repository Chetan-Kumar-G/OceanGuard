"""Shared API response and error envelope models.

This module is a compatibility *superset*: it carries the canonical
``ApiResponse[T]`` / ``ApiMeta`` used by F3/F4/F8, the ``APIResponse.ok/.fail``
helper used by F6, and the ``APIEnvelope`` / graph node & edge schemas used by F7.
Every feature imports what it needs from here so there is a single envelope module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id() -> str:
    """``RUN_<UTC-ISO-compact>`` e.g. ``RUN_20260904T102000Z``."""
    return "RUN_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# --------------------------------------------------------------------------- #
# Canonical envelope (F3 / F4 / F8)
# --------------------------------------------------------------------------- #
class ApiMeta(BaseModel):
    """Metadata attached to every successful API response.

    ``extra="allow"`` so features such as F5 can attach ``event_id`` / ``summary``
    / ``skipped_reason`` without a bespoke meta model.
    """
    model_config = ConfigDict(extra="allow")

    run_id: str = Field(default_factory=new_run_id, description="Unique pipeline or request execution ID")
    generated_at: str = Field(default_factory=_utc_now_iso, description="UTC ISO-8601 generation timestamp")


class ApiResponse(BaseModel, Generic[T]):
    """Standard top-level successful response envelope."""
    data: T = Field(..., description="Payload data")
    meta: ApiMeta = Field(default_factory=ApiMeta, description="Execution metadata")


class ErrorDetail(BaseModel):
    """Error information payload."""
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable summary of the error")
    detail: Optional[Any] = Field(None, description="Additional context or validation details")


class ApiError(BaseModel):
    """Standard error response envelope."""
    error: ErrorDetail = Field(..., description="Error details")


def error_response(code: str, message: str, detail: Any = None) -> dict:
    """Build the uniform error body used by feature routers raising HTTPException."""
    return ApiError(error=ErrorDetail(code=code, message=message, detail=detail)).model_dump()


# --------------------------------------------------------------------------- #
# F1 / F2 style — response meta carrying a real datetime
# --------------------------------------------------------------------------- #
class ResponseMeta(BaseModel):
    run_id: str = Field(..., description="Unique run/execution identifier")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of response generation",
    )


# --------------------------------------------------------------------------- #
# F6 style — success/data/error/meta flat envelope
# --------------------------------------------------------------------------- #
class APIResponse(BaseModel):
    """Flat JSON envelope with a ``success`` flag (used by F6)."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    meta: Optional[dict] = None

    @classmethod
    def ok(cls, data: Any, meta: Optional[dict] = None) -> "APIResponse":
        return cls(success=True, data=data, meta=meta)

    @classmethod
    def fail(cls, error: str) -> "APIResponse":
        return cls(success=False, data=None, error=error)


# --------------------------------------------------------------------------- #
# F7 style — generic envelope + graph node/edge schemas
# --------------------------------------------------------------------------- #
class APIEnvelope(BaseModel, Generic[T]):
    """Top-level response wrapper used by F7."""
    success: bool = True
    data: Optional[T] = None
    error: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)


class NodeSchema(BaseModel):
    """Forensic-graph node (F7)."""
    node_id: str
    event_id: str
    node_type: str  # SPILL_OBSERVATION | SOURCE_HYPOTHESIS | ENVIRONMENTAL_STATE | VESSEL | EVIDENCE | FORECAST
    timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence: Optional[float] = None
    uncertainty: Optional[float] = None
    provenance: Optional[str] = None


class EdgeSchema(BaseModel):
    """Forensic-graph edge (F7)."""
    edge_id: str
    event_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str  # DERIVED-FROM | SUPPORTS | CONTRADICTS | TEMPORALLY-COMPATIBLE
    confidence: Optional[float] = None
    timestamp: Optional[str] = None
    provenance: Optional[str] = None


class GraphResponse(BaseModel):
    """Full graph payload returned by ``GET /events/{event_id}/graph``."""
    event_id: str
    nodes: List[NodeSchema]
    edges: List[EdgeSchema]
    node_count: int
    edge_count: int
    is_partial: bool = False


NodeEnvelope = APIEnvelope[NodeSchema]
GraphEnvelope = APIEnvelope[GraphResponse]
