from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from backend.config import get_settings
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
    SearchSnapshotResponse,
)
from backend.normalize import normalize_query

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
    client = RestateIngressClient(settings)

    job_id = f"search_{uuid.uuid4().hex[:12]}"
    normalized_query = normalize_query(request.query)
    branch = ExplorerBranchInput(
        job_id=job_id,
        branch_id="root",
        parent_branch_id=None,
        depth=0,
        normalized_query=normalized_query,
        candidate_urls=[],
        limits=request.limits,
        stream_tinyfish=request.stream_tinyfish,
    )

    initialize_payload = JobInitializeRequest(
        raw_query=request.query,
        normalized_query=normalized_query,
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

    return SearchAcceptedResponse(
        job_id=job_id,
        snapshot_url=f"/api/search/{job_id}",
        events_url=f"/api/search/{job_id}/events",
    )


@router.get(
    "/search/{job_id}",
    response_model=SearchSnapshotResponse,
    responses={404: {"model": ApiError}, 502: {"model": ApiError}},
)
async def get_search_job(job_id: str) -> SearchSnapshotResponse:
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
