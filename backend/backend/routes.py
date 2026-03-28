from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from backend import db
from backend.config import get_settings
from backend.embeddings import generate_embedding
from backend.ingress import RestateIngressClient, RestateIngressError
from backend.models import (
    ApiError,
    EmptyRequest,
    EventsCursorRequest,
    ExplorerBranchInput,
    JobError,
    JobInitializeRequest,
    SearchAcceptedResponse,
    SearchEvent,
    SearchRequest,
    SearchResult,
    SearchSnapshotResponse,
)
from backend.normalize import normalize_query
from backend.utils import stable_id, utc_now

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])


def _to_http_exception(exc: RestateIngressError) -> HTTPException:
    if exc.status_code == 404:
        detail = ApiError(code="not_found", message="Search job not found.")
        return HTTPException(status_code=404, detail=detail.model_dump(mode="json"))
    detail = ApiError(
        code="restate_error",
        message="Restate request failed.",
        details={"status_code": exc.status_code, "response": exc.message},
    )
    return HTTPException(status_code=502, detail=detail.model_dump(mode="json"))


def _format_sse(event: SearchEvent) -> str:
    payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=True)
    return f"id: {event.seq}\nevent: {event.event_type}\ndata: {payload}\n\n"


def _snapshot_from_db_row(row: dict[str, Any], job_id: str | None = None) -> SearchSnapshotResponse:
    """Reconstruct a SearchSnapshotResponse from a postgres row."""
    input_data = row["input"] if isinstance(row["input"], dict) else json.loads(row["input"])
    output_data = row["output"] if isinstance(row["output"], dict) else json.loads(row["output"])
    return SearchSnapshotResponse(
        job_id=job_id or row["job_id"],
        status=row["status"],
        query=input_data["query"],
        results=output_data.get("results", []),
        errors=output_data.get("errors", []),
        created_at=row["created_at"],
        updated_at=row.get("completed_at") or row["created_at"],
        cached_from=row.get("cached_from"),
    )


# ---------------------------------------------------------------------------
# POST /api/search — create or cache-hit
# ---------------------------------------------------------------------------


@router.post(
    "/search",
    response_model=SearchAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        502: {
            "model": ApiError,
            "description": "Restate ingress is unavailable or rejected the workflow submission.",
        }
    },
)
async def create_search_job(request: SearchRequest) -> SearchAcceptedResponse:
    settings = get_settings()
    job_id = f"search_{uuid.uuid4().hex[:12]}"
    normalized = normalize_query(request.query)

    # --- Embedding + cache lookup ---
    query_embedding = await generate_embedding(normalized.query_text, settings)
    if query_embedding is not None:
        cached_row = await db.find_cached_job(query_embedding, settings.cache_similarity_threshold)
        if cached_row is not None:
            logger.info(
                "Cache HIT for job %s — query=%r matched %s (similarity=%.3f)",
                job_id,
                normalized.query_text,
                cached_row["job_id"],
                cached_row["similarity"],
            )
            now = utc_now().isoformat()
            input_data = cached_row["input"] if isinstance(cached_row["input"], dict) else json.loads(cached_row["input"])
            output_data = cached_row["output"] if isinstance(cached_row["output"], dict) else json.loads(cached_row["output"])
            await db.create_cached_job(
                job_id=job_id,
                cached_from_job_id=cached_row["job_id"],
                input_data=input_data,
                output_data=output_data,
                query_embedding=query_embedding,
                created_at=now,
            )
            return SearchAcceptedResponse(
                job_id=job_id,
                snapshot_url=f"/api/search/{job_id}",
                events_url=f"/api/search/{job_id}/events",
                cached_from=cached_row["job_id"],
            )
        else:
            logger.info("Cache MISS for job %s — query=%r, no similar completed job found", job_id, normalized.query_text)
    else:
        logger.info("Cache SKIP for job %s — no embedding generated (missing API key?)", job_id, )

    # --- No cache hit: submit to Restate ---
    client = RestateIngressClient(settings)
    branch = ExplorerBranchInput(
        job_id=job_id,
        branch_id="root",
        parent_branch_id=None,
        depth=0,
        normalized_query=normalized,
        candidate_urls=[],
        limits=request.limits,
        stream_tinyfish=request.stream_tinyfish,
    )

    initialize_payload = JobInitializeRequest(
        raw_query=request.query,
        normalized_query=normalized,
        limits=request.limits,
        stream_tinyfish=request.stream_tinyfish,
    )

    try:
        await client.call_virtual_object(
            "SearchJobState",
            job_id,
            "initialize",
            initialize_payload.model_dump(mode="json"),
        )
        await client.submit_workflow(
            "ExplorerWorkflow",
            f"{job_id}__root",
            branch.model_dump(mode="json"),
            send=True,
        )
    except RestateIngressError as exc:
        try:
            await client.call_virtual_object(
                "SearchJobState",
                job_id,
                "mark_failed",
                JobError(
                    code="workflow_submit_failed",
                    message="Unable to submit the search workflow.",
                    retryable=True,
                    details={"restate_error": exc.message},
                ).model_dump(mode="json"),
            )
        except RestateIngressError:
            pass
        raise _to_http_exception(exc)

    # Store embedding early so it's available for future cache lookups even if
    # the job is still running (save_search_job will COALESCE on update).
    if query_embedding is not None:
        await db.save_search_job(
            {
                "job_id": job_id,
                "status": "running",
                "query": {
                    "raw_query": request.query,
                    "normalized": normalized.model_dump(mode="json"),
                },
                "results": [],
                "errors": [],
                "created_at": utc_now().isoformat(),
            },
            query_embedding=query_embedding,
        )

    return SearchAcceptedResponse(
        job_id=job_id,
        snapshot_url=f"/api/search/{job_id}",
        events_url=f"/api/search/{job_id}/events",
    )


# ---------------------------------------------------------------------------
# GET /api/search/{job_id} — snapshot
# ---------------------------------------------------------------------------


@router.get(
    "/search/{job_id}",
    response_model=SearchSnapshotResponse,
    responses={404: {"model": ApiError}, 502: {"model": ApiError}},
)
async def get_search_job(job_id: str) -> SearchSnapshotResponse:
    # Try postgres first (works for cached jobs and completed jobs).
    row = await db.get_job_snapshot(job_id)
    if row is not None and row["status"] in ("completed", "failed"):
        return _snapshot_from_db_row(row)

    # Fall back to Restate for in-progress jobs.
    client = RestateIngressClient(get_settings())
    try:
        payload = await client.call_virtual_object(
            "SearchJobState",
            job_id,
            "get_snapshot",
            EmptyRequest().model_dump(mode="json"),
        )
    except RestateIngressError as exc:
        raise _to_http_exception(exc)
    return SearchSnapshotResponse.model_validate(payload)


# ---------------------------------------------------------------------------
# GET /api/search/{job_id}/events — SSE stream (live or cached replay)
# ---------------------------------------------------------------------------


@router.get(
    "/search/{job_id}/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-Sent Events stream of search progress and result items.",
            "content": {"text/event-stream": {}},
        },
        404: {"model": ApiError},
        502: {"model": ApiError},
    },
)
async def stream_search_events(
    job_id: str,
    since: Annotated[int | None, Query(ge=0)] = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    # Check if this is a cached job — if so, replay from postgres.
    row = await db.get_job_snapshot(job_id)
    if row is not None and row.get("cached_from") is not None:
        return StreamingResponse(
            _cached_event_stream(job_id, row),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    # Otherwise stream live from Restate.
    settings = get_settings()
    client = RestateIngressClient(settings)

    initial_since = since
    if initial_since is None and last_event_id:
        try:
            initial_since = int(last_event_id)
        except ValueError:
            initial_since = 0
    current_since = initial_since or 0

    try:
        initial_payload = await client.call_virtual_object(
            "SearchJobState",
            job_id,
            "get_events_since",
            EventsCursorRequest(since=current_since).model_dump(mode="json"),
        )
    except RestateIngressError as exc:
        raise _to_http_exception(exc)

    async def event_stream():
        nonlocal current_since
        terminal = {"completed", "failed"}
        next_payload = initial_payload
        while True:
            payload = next_payload
            page_status = payload.get("status", "queued")
            events = [SearchEvent.model_validate(item) for item in payload.get("events", [])]
            if events:
                for event in events:
                    current_since = event.seq
                    yield _format_sse(event)
            elif page_status not in terminal:
                keepalive = {
                    "event_type": "keepalive",
                    "job_id": job_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                yield f"event: keepalive\ndata: {json.dumps(keepalive, ensure_ascii=True)}\n\n"

            if page_status in terminal and not events:
                return

            try:
                next_payload = await client.call_virtual_object(
                    "SearchJobState",
                    job_id,
                    "get_events_since",
                    EventsCursorRequest(since=current_since).model_dump(mode="json"),
                )
            except RestateIngressError as exc:
                error = ApiError(
                    code="restate_error",
                    message="Failed to load search events.",
                    details={"status_code": exc.status_code, "response": exc.message},
                )
                yield (
                    "event: job.failed\n"
                    f"data: {json.dumps(error.model_dump(mode='json'), ensure_ascii=True)}\n\n"
                )
                return
            await asyncio.sleep(settings.explorer_sse_poll_ms / 1000)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# Cached event replay — synthesize SSE events from stored results
# ---------------------------------------------------------------------------


async def _cached_event_stream(job_id: str, row: dict[str, Any]):
    """Replay cached results as SSE events with delays between each result."""
    settings = get_settings()
    delay = settings.cache_replay_delay_seconds
    output_data = row["output"] if isinstance(row["output"], dict) else json.loads(row["output"])
    results = output_data.get("results", [])
    now = datetime.now(timezone.utc)
    seq = 0

    # 1. job.started
    seq += 1
    yield _format_sse(SearchEvent(
        seq=seq,
        event_type="job.started",
        event_id=stable_id(job_id, "cache", "job.started"),
        job_id=job_id,
        branch_id="root",
        payload={"status": "running"},
        created_at=now,
    ))
    await asyncio.sleep(delay)

    # 2. result.item for each cached result
    for result_data in results:
        seq += 1
        result = SearchResult.model_validate(result_data)
        yield _format_sse(SearchEvent(
            seq=seq,
            event_type="result.item",
            event_id=stable_id(job_id, "cache", "result.item", str(seq)),
            job_id=job_id,
            branch_id="root",
            payload={"result": result.model_dump(mode="json")},
            created_at=now,
        ))
        await asyncio.sleep(delay)

    # 3. job.completed
    seq += 1
    yield _format_sse(SearchEvent(
        seq=seq,
        event_type="job.completed",
        event_id=stable_id(job_id, "cache", "job.completed"),
        job_id=job_id,
        branch_id="root",
        payload={"status": "completed", "result_count": len(results)},
        created_at=now,
    ))
