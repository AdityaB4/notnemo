from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SearchStatus = Literal["queued", "running", "completed", "failed"]
EventType = Literal[
    "job.started",
    "seeds.ready",
    "domains.ready",
    "branch.started",
    "tinyfish.progress",
    "result.item",
    "branch.completed",
    "job.completed",
    "job.failed",
    "keepalive",
]
SourceKind = Literal[
    "seed",
    "enumerated_domain",
    "web_search",
    "tinyfish",
    "sub_explorer",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class EmptyRequest(StrictModel):
    pass


class SearchLimits(StrictModel):
    max_depth: int = Field(default=1, ge=0)
    max_subexplorers: int = Field(default=2, ge=0)
    max_results: int = Field(default=10, ge=1, le=50)
    seed_limit: int = Field(default=8, ge=0, le=50)
    domain_limit: int = Field(default=24, ge=0, le=100)


class SearchRequest(StrictModel):
    query: Any = Field(
        ...,
        description="Arbitrary JSON payload describing the niche query and optional user profile.",
    )
    limits: SearchLimits = Field(default_factory=SearchLimits)
    stream_tinyfish: bool = True


class ApiError(StrictModel):
    code: str
    message: str
    details: Any | None = None


class JobError(StrictModel):
    code: str
    message: str
    retryable: bool = False
    details: Any | None = None


class TinyFishTraceEvent(StrictModel):
    type: str
    purpose: str | None = None
    status: str | None = None
    raw_event: dict[str, Any] | None = None


class TinyFishArtifact(StrictModel):
    summary: str
    trace: list[TinyFishTraceEvent] = Field(default_factory=list)
    result_json: Any | None = None


class NormalizedQuery(StrictModel):
    raw_query: Any
    query_text: str
    profile: dict[str, Any] = Field(default_factory=dict)
    keywords: list[str] = Field(default_factory=list)


class SearchQuerySnapshot(StrictModel):
    raw_query: Any
    normalized: NormalizedQuery


class SeedCandidate(StrictModel):
    url: str
    description: str
    tags: list[str] = Field(default_factory=list)
    rationale: str


class SearchResultDraft(StrictModel):
    url: str
    description: str
    source_kind: SourceKind
    why_matched: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tinyfish: TinyFishArtifact | None = None


class SearchResult(StrictModel):
    result_id: str
    url: str
    description: str
    source_kind: SourceKind
    why_matched: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    branch_id: str
    tinyfish: TinyFishArtifact | None = None


class SearchAcceptedResponse(StrictModel):
    job_id: str
    status: Literal["queued"] = "queued"
    snapshot_url: str
    events_url: str
    cached_from: str | None = None


class SearchSnapshotResponse(StrictModel):
    job_id: str
    status: SearchStatus
    query: SearchQuerySnapshot
    results: list[SearchResult] = Field(default_factory=list)
    errors: list[JobError] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    cached_from: str | None = None


class SearchEvent(StrictModel):
    seq: int
    event_type: EventType
    event_id: str
    job_id: str
    branch_id: str | None = None
    payload: Any = Field(default_factory=dict)
    created_at: datetime


class SearchEventsPage(StrictModel):
    job_id: str
    status: SearchStatus
    events: list[SearchEvent] = Field(default_factory=list)
    next_seq: int = 0


class ExplorerBranchInput(StrictModel):
    job_id: str
    branch_id: str
    parent_branch_id: str | None = None
    depth: int = Field(ge=0)
    normalized_query: NormalizedQuery
    candidate_urls: list[str] = Field(default_factory=list)
    limits: SearchLimits
    stream_tinyfish: bool = True
    trace_parent: str | None = None


class BranchSummary(StrictModel):
    branch_id: str
    depth: int
    coverage_assessment: str
    notes: str
    result_count: int
    follow_up_queries: list[str] = Field(default_factory=list)


class BranchOutcome(StrictModel):
    results: list[SearchResultDraft] = Field(default_factory=list)
    coverage_assessment: str = ""
    notes: str = ""
    follow_up_queries: list[str] = Field(default_factory=list)


class EventsCursorRequest(StrictModel):
    since: int = Field(default=0, ge=0)


class EventAppendRequest(StrictModel):
    event_type: EventType
    event_id: str | None = None
    branch_id: str | None = None
    payload: Any = Field(default_factory=dict)


class JobInitializeRequest(StrictModel):
    raw_query: Any
    normalized_query: NormalizedQuery
    limits: SearchLimits
    stream_tinyfish: bool = True


class JobStatusUpdate(StrictModel):
    branch_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class TinyFishToolRequest(StrictModel):
    url: str
    extraction_goal: str


class TinyFishExecutionRequest(StrictModel):
    job_id: str
    branch_id: str
    tool_call_id: str
    url: str
    extraction_goal: str
    stream_events: bool = True


class TinyFishToolResult(StrictModel):
    status: Literal["completed", "error", "rejected"]
    url: str
    summary: str = ""
    result_json: Any | None = None
    trace: list[TinyFishTraceEvent] = Field(default_factory=list)
    message: str | None = None


class SubExplorerToolRequest(StrictModel):
    focus_query: str
    urls: list[str] = Field(default_factory=list)
    rationale: str


class JobStartedPayload(StrictModel):
    status: Literal["running"] = "running"


class SeedsReadyPayload(StrictModel):
    seeds: list[SeedCandidate]


class DomainsReadyPayload(StrictModel):
    domains: list[str]


class BranchStartedPayload(StrictModel):
    depth: int
    candidate_urls: list[str] = Field(default_factory=list)


class TinyFishProgressPayload(StrictModel):
    url: str
    purpose: str | None = None
    trace: TinyFishTraceEvent


class ResultItemPayload(StrictModel):
    result: SearchResult


class BranchCompletedPayload(StrictModel):
    summary: BranchSummary


class JobCompletedPayload(StrictModel):
    status: Literal["completed"] = "completed"
    result_count: int


class JobFailedPayload(StrictModel):
    error: JobError


class KeepAlivePayload(StrictModel):
    ts: datetime


class StreamEventBase(StrictModel):
    seq: int
    event_id: str
    job_id: str
    branch_id: str | None = None
    created_at: datetime


class JobStartedEvent(StreamEventBase):
    event_type: Literal["job.started"] = "job.started"
    payload: JobStartedPayload


class SeedsReadyEvent(StreamEventBase):
    event_type: Literal["seeds.ready"] = "seeds.ready"
    payload: SeedsReadyPayload


class DomainsReadyEvent(StreamEventBase):
    event_type: Literal["domains.ready"] = "domains.ready"
    payload: DomainsReadyPayload


class BranchStartedEvent(StreamEventBase):
    event_type: Literal["branch.started"] = "branch.started"
    payload: BranchStartedPayload


class TinyFishProgressEvent(StreamEventBase):
    event_type: Literal["tinyfish.progress"] = "tinyfish.progress"
    payload: TinyFishProgressPayload


class ResultItemEvent(StreamEventBase):
    event_type: Literal["result.item"] = "result.item"
    payload: ResultItemPayload


class BranchCompletedEvent(StreamEventBase):
    event_type: Literal["branch.completed"] = "branch.completed"
    payload: BranchCompletedPayload


class JobCompletedEvent(StreamEventBase):
    event_type: Literal["job.completed"] = "job.completed"
    payload: JobCompletedPayload


class JobFailedEvent(StreamEventBase):
    event_type: Literal["job.failed"] = "job.failed"
    payload: JobFailedPayload


class KeepAliveEvent(StreamEventBase):
    event_type: Literal["keepalive"] = "keepalive"
    payload: KeepAlivePayload
