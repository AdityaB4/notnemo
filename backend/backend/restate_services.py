from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import braintrust
import restate

from backend.config import get_settings
from backend.db import save_search_job
from backend.domains import enumerate_candidate_urls
from backend.embeddings import generate_embedding
from backend.ingress import RestateIngressClient, RestateIngressError
from backend.models import (
    BranchSummary,
    EventAppendRequest,
    EventsCursorRequest,
    ExplorerBranchInput,
    JobCompletedPayload,
    JobError,
    JobFailedPayload,
    JobInitializeRequest,
    JobStatusUpdate,
    NormalizedQuery,
    ResultItemPayload,
    SearchEvent,
    SearchEventsPage,
    SearchQuerySnapshot,
    SearchResult,
    SearchResultDraft,
    SearchSnapshotResponse,
    TinyFishProgressPayload,
    TinyFishExecutionRequest,
    TinyFishToolResult,
    TinyFishTraceEvent,
)
from backend.normalize import normalize_query
from backend.openai_explorer import (
    OpenAIResponseError,
    OpenAIResponsesClient,
    build_fallback_outcome,
    build_initial_input,
    build_response_payload,
    extract_function_calls,
    parse_branch_outcome,
    saw_web_search,
)
from backend.seeds import MockSeedUrlRepository
from backend.tinyfish import TinyFishClient, TinyFishError
from backend.utils import canonicalize_url, stable_id, to_jsonable, utc_now

logger = logging.getLogger(__name__)

search_job_state = restate.VirtualObject("SearchJobState")
explorer_workflow = restate.Workflow("ExplorerWorkflow")
tinyfish_tasks = restate.Service("TinyFishTasks")
greeter = restate.Service("Greeter")


@greeter.handler()
async def greet(ctx: restate.Context, name: str) -> str:
    return f"Hello, {name}!"


@tinyfish_tasks.handler()
async def scrape_site(ctx: restate.Context, req: TinyFishExecutionRequest) -> TinyFishToolResult:
    req = TinyFishExecutionRequest.model_validate(req)
    settings = get_settings()
    tinyfish_client = TinyFishClient(settings)
    ingress_client = RestateIngressClient(settings)
    event_counter = 0
    last_event_at = time.monotonic()

    async def on_event(trace_event: TinyFishTraceEvent) -> None:
        nonlocal event_counter, last_event_at
        if not req.stream_events:
            return
        last_event_at = time.monotonic()
        event_counter += 1
        payload_model = TinyFishProgressPayload(
            url=canonicalize_url(req.url),
            purpose=trace_event.purpose,
            trace=trace_event,
        )
        try:
            await ingress_client.call_virtual_object(
                "SearchJobState",
                req.job_id,
                "append_event",
                EventAppendRequest(
                    event_type="tinyfish.progress",
                    event_id=stable_id(
                        req.job_id,
                        req.branch_id,
                        req.tool_call_id,
                        "tinyfish.progress",
                        event_counter,
                    ),
                    branch_id=req.branch_id,
                    payload=payload_model,
                ).model_dump(mode="json"),
            )
        except RestateIngressError:
            return

    heartbeat_task: asyncio.Task[None] | None = None
    if req.stream_events:
        async def emit_heartbeats() -> None:
            while True:
                await asyncio.sleep(5.0)
                if time.monotonic() - last_event_at < 5.0:
                    continue
                await on_event(
                    TinyFishTraceEvent(
                        type="HEARTBEAT",
                        purpose="TinyFish scrape still running",
                        status="RUNNING",
                        raw_event={
                            "type": "HEARTBEAT",
                            "status": "RUNNING",
                            "synthetic": True,
                        },
                    )
                )

        heartbeat_task = asyncio.create_task(emit_heartbeats())

    try:
        artifact = await tinyfish_client.run_scrape(
            req.url,
            req.extraction_goal,
            on_event=on_event,
        )
        return TinyFishToolResult(
            status="completed",
            url=canonicalize_url(req.url),
            summary=artifact.summary,
            result_json=artifact.result_json,
            trace=artifact.trace,
        )
    except TinyFishError as exc:
        return TinyFishToolResult(
            status="error",
            url=canonicalize_url(req.url),
            message=str(exc),
        )
    finally:
        if heartbeat_task is not None and not heartbeat_task.done():
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task


async def _get_state_list(ctx: restate.ObjectSharedContext | restate.ObjectContext, key: str) -> list[Any]:
    return await ctx.get(key, type_hint=list) or []


async def _require_created(
    ctx: restate.ObjectSharedContext | restate.ObjectContext,
) -> tuple[dict[str, Any], NormalizedQuery]:
    created_at = await ctx.get("created_at", type_hint=str)
    if created_at is None:
        raise restate.TerminalError(f"Search job {ctx.key()} not found", status_code=404)
    raw_query = await ctx.get("raw_query")
    normalized_raw = await ctx.get("normalized_query", type_hint=dict) or {}
    return {"created_at": created_at, "raw_query": raw_query}, NormalizedQuery.model_validate(
        normalized_raw
    )


async def _load_snapshot(
    ctx: restate.ObjectSharedContext | restate.ObjectContext,
) -> SearchSnapshotResponse:
    stored, normalized_query = await _require_created(ctx)
    status = await ctx.get("status", type_hint=str) or "queued"
    raw_results = await _get_state_list(ctx, "results")
    raw_errors = await _get_state_list(ctx, "errors")
    updated_at = await ctx.get("updated_at", type_hint=str) or stored["created_at"]
    return SearchSnapshotResponse(
        job_id=ctx.key(),
        status=status,  # type: ignore[arg-type]
        query=SearchQuerySnapshot(raw_query=stored["raw_query"], normalized=normalized_query),
        results=[SearchResult.model_validate(item) for item in raw_results],
        errors=[JobError.model_validate(item) for item in raw_errors],
        created_at=stored["created_at"],
        updated_at=updated_at,
    )


async def _append_event_record(
    ctx: restate.ObjectContext,
    *,
    event_type: str,
    branch_id: str | None,
    payload: Any,
    event_id: str,
) -> SearchEvent:
    event_ids = await _get_state_list(ctx, "event_ids")
    events = await _get_state_list(ctx, "events")
    for raw_event in events:
        if raw_event.get("event_id") == event_id:
            return SearchEvent.model_validate(raw_event)

    next_seq = await ctx.get("next_seq", type_hint=int) or 1
    created_at = utc_now()
    event = SearchEvent(
        seq=next_seq,
        event_type=event_type,  # type: ignore[arg-type]
        event_id=event_id,
        job_id=ctx.key(),
        branch_id=branch_id,
        payload=to_jsonable(payload),
        created_at=created_at,
    )
    events.append(event.model_dump(mode="json"))
    event_ids.append(event_id)
    ctx.set("events", events)
    ctx.set("event_ids", event_ids)
    ctx.set("next_seq", next_seq + 1)
    ctx.set("updated_at", created_at.isoformat())
    return event


def _result_id(result: SearchResult) -> str:
    return stable_id("result", canonicalize_url(result.url))


@search_job_state.handler()
async def initialize(ctx: restate.ObjectContext, req: JobInitializeRequest) -> SearchSnapshotResponse:
    existing_created_at = await ctx.get("created_at", type_hint=str)
    if existing_created_at is None:
        now = utc_now().isoformat()
        ctx.set("status", "queued")
        ctx.set("raw_query", to_jsonable(req.raw_query))
        ctx.set("normalized_query", req.normalized_query.model_dump(mode="json"))
        ctx.set("limits", req.limits.model_dump(mode="json"))
        ctx.set("stream_tinyfish", req.stream_tinyfish)
        ctx.set("results", [])
        ctx.set("errors", [])
        ctx.set("events", [])
        ctx.set("event_ids", [])
        ctx.set("next_seq", 1)
        ctx.set("created_at", now)
        ctx.set("updated_at", now)
    return await _load_snapshot(ctx)


@search_job_state.handler()
async def append_event(ctx: restate.ObjectContext, req: EventAppendRequest) -> SearchEvent:
    await _require_created(ctx)
    event_id = req.event_id or stable_id(
        ctx.key(), req.branch_id, req.event_type, req.payload
    )
    return await _append_event_record(
        ctx,
        event_type=req.event_type,
        branch_id=req.branch_id,
        payload=req.payload,
        event_id=event_id,
    )


@search_job_state.handler()
async def publish_result(ctx: restate.ObjectContext, result: SearchResult) -> SearchResult:
    await _require_created(ctx)
    result = result.model_copy(
        update={
            "url": canonicalize_url(result.url),
            "result_id": result.result_id or _result_id(result),
        }
    )
    results = await _get_state_list(ctx, "results")
    updated = False
    for index, raw_result in enumerate(results):
        if raw_result.get("result_id") == result.result_id:
            results[index] = result.model_dump(mode="json")
            updated = True
            break
    if not updated:
        results.append(result.model_dump(mode="json"))
    ctx.set("results", results)
    ctx.set("updated_at", utc_now().isoformat())
    await _append_event_record(
        ctx,
        event_type="result.item",
        branch_id=result.branch_id,
        payload=ResultItemPayload(result=result),
        event_id=stable_id(ctx.key(), "result.item", result.result_id),
    )
    return result


@search_job_state.handler()
async def mark_running(ctx: restate.ObjectContext, req: JobStatusUpdate) -> SearchSnapshotResponse:
    await _require_created(ctx)
    ctx.set("status", "running")
    await _append_event_record(
        ctx,
        event_type="job.started",
        branch_id=req.branch_id,
        payload={"status": "running", **req.payload},
        event_id=stable_id(ctx.key(), "job.started"),
    )
    return await _load_snapshot(ctx)


@search_job_state.handler()
async def mark_completed(ctx: restate.ObjectContext, req: JobStatusUpdate) -> SearchSnapshotResponse:
    await _require_created(ctx)
    ctx.set("status", "completed")
    results = await _get_state_list(ctx, "results")
    await _append_event_record(
        ctx,
        event_type="job.completed",
        branch_id=req.branch_id,
        payload=JobCompletedPayload(result_count=len(results)),
        event_id=stable_id(ctx.key(), "job.completed"),
    )
    return await _load_snapshot(ctx)


@search_job_state.handler()
async def mark_failed(ctx: restate.ObjectContext, error: JobError) -> SearchSnapshotResponse:
    await _require_created(ctx)
    errors = await _get_state_list(ctx, "errors")
    errors.append(error.model_dump(mode="json"))
    ctx.set("errors", errors)
    ctx.set("status", "failed")
    await _append_event_record(
        ctx,
        event_type="job.failed",
        branch_id=None,
        payload=JobFailedPayload(error=error),
        event_id=stable_id(ctx.key(), "job.failed", error.code, error.message),
    )
    return await _load_snapshot(ctx)


@search_job_state.handler(kind="shared")
async def get_snapshot(
    ctx: restate.ObjectSharedContext, _: dict[str, Any] | None = None
) -> SearchSnapshotResponse:
    return await _load_snapshot(ctx)


@search_job_state.handler(kind="shared")
async def get_events_since(
    ctx: restate.ObjectSharedContext, req: EventsCursorRequest
) -> SearchEventsPage:
    snapshot = await _load_snapshot(ctx)
    events = [
        SearchEvent.model_validate(item)
        for item in await _get_state_list(ctx, "events")
        if int(item.get("seq", 0)) > req.since
    ]
    next_seq = events[-1].seq if events else req.since
    return SearchEventsPage(
        job_id=ctx.key(),
        status=snapshot.status,
        events=events,
        next_seq=next_seq,
    )


@dataclass(slots=True)
class BranchRuntimeState:
    web_search_seen: bool = False
    child_counter: int = 0


@dataclass(slots=True)
class WorkflowCallbacks:
    ctx: restate.WorkflowContext
    branch: ExplorerBranchInput
    runtime: BranchRuntimeState = field(default_factory=BranchRuntimeState)

    async def append_event(self, event_type: str, payload: Any) -> None:
        await self.ctx.object_call(
            append_event,
            key=self.branch.job_id,
            arg=EventAppendRequest(
                event_type=event_type,  # type: ignore[arg-type]
                branch_id=self.branch.branch_id,
                payload=payload,
            ),
        )

    async def publish_result(self, draft: SearchResultDraft) -> SearchResult:
        result = SearchResult(
            result_id=stable_id("result", canonicalize_url(draft.url)),
            url=canonicalize_url(draft.url),
            description=draft.description,
            source_kind=draft.source_kind,
            why_matched=draft.why_matched,
            tags=draft.tags,
            confidence=draft.confidence,
            branch_id=self.branch.branch_id,
            tinyfish=draft.tinyfish,
        )
        return await self.ctx.object_call(
            publish_result,
            key=self.branch.job_id,
            arg=result,
        )

    def start_sub_explorer(
        self, focus_query: str, urls: list[str], rationale: str, trace_parent: str | None = None
    ):
        if self.branch.depth >= self.branch.limits.max_depth:
            raise ValueError("Sub-explorer depth budget exhausted.")
        if self.runtime.child_counter >= self.branch.limits.max_subexplorers:
            raise ValueError("Sub-explorer fan-out budget exhausted.")

        self.runtime.child_counter += 1
        child_branch_id = f"{self.branch.branch_id}__{self.runtime.child_counter}"
        child_key = f"{self.branch.job_id}__{self.branch.branch_id}__{self.runtime.child_counter}"
        child_query = normalize_query(
            {
                "text": focus_query,
                "profile": self.branch.normalized_query.profile,
            }
        )
        child_branch = ExplorerBranchInput(
            job_id=self.branch.job_id,
            branch_id=child_branch_id,
            parent_branch_id=self.branch.branch_id,
            depth=self.branch.depth + 1,
            normalized_query=child_query,
            candidate_urls=urls or self.branch.candidate_urls,
            limits=self.branch.limits,
            stream_tinyfish=self.branch.stream_tinyfish,
            trace_parent=trace_parent,
        )
        return self.ctx.workflow_call(run_explorer, key=child_key, arg=child_branch)


@dataclass(slots=True)
class PendingToolInvocation:
    index: int
    name: str
    call_id: str
    future: Any


async def _run_openai_loop(
    ctx: restate.WorkflowContext,
    branch: ExplorerBranchInput,
) -> BranchSummary:
    settings = get_settings()
    callbacks = WorkflowCallbacks(ctx=ctx, branch=branch)
    openai_client = OpenAIResponsesClient(settings)

    span_kwargs: dict[str, Any] = {
        "name": "explorer_loop",
        "input": {
            "job_id": branch.job_id,
            "branch_id": branch.branch_id,
            "depth": branch.depth,
            "query": branch.normalized_query.query_text,
            "keywords": branch.normalized_query.keywords,
            "candidate_urls": branch.candidate_urls[:10],
        },
    }
    if branch.trace_parent:
        span_kwargs["parent"] = branch.trace_parent

    # Use as context manager so wrap_openai auto-spans nest under this span.
    with braintrust.start_span(**span_kwargs) as span:
        try:
            summary = await _run_openai_loop_inner(
                ctx, branch, settings, callbacks, openai_client, span,
            )
            span.log(
                output={
                    "branch_id": summary.branch_id,
                    "result_count": summary.result_count,
                    "coverage_assessment": summary.coverage_assessment,
                    "notes": summary.notes,
                },
            )
            return summary
        except Exception as exc:
            span.log(output={"error": str(exc)})
            raise


async def _run_openai_loop_inner(
    ctx: restate.WorkflowContext,
    branch: ExplorerBranchInput,
    settings,
    callbacks: WorkflowCallbacks,
    openai_client: OpenAIResponsesClient,
    parent_span: braintrust.Span,
) -> BranchSummary:
    if not settings.openai_api_key:
        fallback = build_fallback_outcome(
            branch,
            note="OpenAI API key is not configured; returning deterministic fallback results.",
        )
        for draft in fallback.results[: branch.limits.max_results]:
            await callbacks.publish_result(draft)
        return BranchSummary(
            branch_id=branch.branch_id,
            depth=branch.depth,
            coverage_assessment=fallback.coverage_assessment,
            notes=fallback.notes,
            result_count=len(fallback.results[: branch.limits.max_results]),
            follow_up_queries=fallback.follow_up_queries,
        )

    previous_response_id: str | None = None
    response_input = build_initial_input(branch)

    for iteration in range(settings.explorer_max_iterations):
        payload = build_response_payload(settings, response_input, previous_response_id)

        # wrap_openai auto-traces each responses.create() call with full
        # input/output/usage, nested under the current explorer_loop span.
        try:
            response = await ctx.run_typed(
                "openai-response", openai_client.create_response, payload=payload
            )
        except OpenAIResponseError as exc:
            fallback = build_fallback_outcome(
                branch,
                note=f"OpenAI request failed, using fallback candidates instead: {exc}",
            )
            for draft in fallback.results[: branch.limits.max_results]:
                await callbacks.publish_result(draft)
            return BranchSummary(
                branch_id=branch.branch_id,
                depth=branch.depth,
                coverage_assessment=fallback.coverage_assessment,
                notes=fallback.notes,
                result_count=len(fallback.results[: branch.limits.max_results]),
                follow_up_queries=fallback.follow_up_queries,
            )

        previous_response_id = response.get("id")
        callbacks.runtime.web_search_seen = callbacks.runtime.web_search_seen or saw_web_search(
            response
        )

        function_calls = extract_function_calls(response)
        if function_calls:
            tool_outputs: list[dict[str, Any] | None] = [None] * len(function_calls)
            pending_invocations: list[PendingToolInvocation] = []

            for index, tool_call in enumerate(function_calls):
                if tool_call.name == "tinyfish_scrape":
                    if not callbacks.runtime.web_search_seen:
                        tool_outputs[index] = {
                            "status": "rejected",
                            "reason": "web search must be attempted before tinyfish_scrape.",
                        }
                    else:
                        try:
                            future = ctx.service_call(
                                scrape_site,
                                arg=TinyFishExecutionRequest(
                                    job_id=branch.job_id,
                                    branch_id=branch.branch_id,
                                    tool_call_id=tool_call.call_id or stable_id(
                                        branch.job_id,
                                        branch.branch_id,
                                        "tinyfish",
                                        index,
                                    ),
                                    url=tool_call.arguments["url"],
                                    extraction_goal=tool_call.arguments["extraction_goal"],
                                    stream_events=branch.stream_tinyfish,
                                ),
                            )
                            pending_invocations.append(
                                PendingToolInvocation(
                                    index=index,
                                    name=tool_call.name,
                                    call_id=tool_call.call_id,
                                    future=future,
                                )
                            )
                        except KeyError as exc:
                            tool_outputs[index] = {"status": "error", "message": str(exc)}
                elif tool_call.name == "sub_explorer":
                    try:
                        future = callbacks.start_sub_explorer(
                            focus_query=tool_call.arguments["focus_query"],
                            urls=tool_call.arguments.get("urls", []),
                            rationale=tool_call.arguments["rationale"],
                            trace_parent=tool_span.export(),
                        )
                        pending_invocations.append(
                            PendingToolInvocation(
                                index=index,
                                name=tool_call.name,
                                call_id=tool_call.call_id,
                                future=future,
                            )
                        )
                    except (KeyError, ValueError) as exc:
                        tool_outputs[index] = {"status": "rejected", "reason": str(exc)}
                else:
                    tool_outputs[index] = {
                        "status": "rejected",
                        "reason": f"Unsupported tool {tool_call.name}",
                    }

            for invocation in pending_invocations:
                try:
                    if invocation.name == "tinyfish_scrape":
                        tool_result = await invocation.future
                        tool_result = TinyFishToolResult.model_validate(tool_result)
                        output = tool_result.model_dump(mode="json")
                    elif invocation.name == "sub_explorer":
                        summary = await invocation.future
                        summary = BranchSummary.model_validate(summary)
                        output = {
                            "status": "completed",
                            "summary": summary.model_dump(mode="json"),
                        }
                    else:
                        output = {
                            "status": "rejected",
                            "reason": f"Unsupported tool {invocation.name}",
                        }
                except Exception as exc:
                    output = {"status": "error", "message": str(exc)}

                tool_outputs[invocation.index] = {
                    "type": "function_call_output",
                    "call_id": invocation.call_id,
                    "output": json.dumps(output, ensure_ascii=True),
                }

            response_input = [item for item in tool_outputs if item is not None]
            continue

        outcome = parse_branch_outcome(response)
        if outcome is None:
            fallback = build_fallback_outcome(
                branch,
                note="OpenAI returned a non-JSON final message; falling back to candidate URLs.",
            )
            outcome = fallback

        published = 0
        for draft in outcome.results[: branch.limits.max_results]:
            await callbacks.publish_result(draft)
            published += 1
        return BranchSummary(
            branch_id=branch.branch_id,
            depth=branch.depth,
            coverage_assessment=outcome.coverage_assessment or "partial",
            notes=outcome.notes or "",
            result_count=published,
            follow_up_queries=outcome.follow_up_queries,
        )

    fallback = build_fallback_outcome(
        branch,
        note="Explorer hit its iteration budget and returned fallback candidates.",
    )
    for draft in fallback.results[: branch.limits.max_results]:
        await callbacks.publish_result(draft)
    return BranchSummary(
        branch_id=branch.branch_id,
        depth=branch.depth,
        coverage_assessment=fallback.coverage_assessment,
        notes=fallback.notes,
        result_count=len(fallback.results[: branch.limits.max_results]),
        follow_up_queries=fallback.follow_up_queries,
    )


@explorer_workflow.main(name="run")
async def run_explorer(ctx: restate.WorkflowContext, branch: ExplorerBranchInput) -> BranchSummary:
    branch = ExplorerBranchInput.model_validate(branch)
    settings = get_settings()
    is_root = branch.parent_branch_id is None
    seed_repository = MockSeedUrlRepository()

    # For root branches, create a job-level span that groups all traces for this search job.
    # Sub-explorer branches receive trace_parent from their parent's tool span instead.
    job_span = None
    if is_root:
        job_span = braintrust.start_span(
            name=f"search_job:{branch.job_id}",
            input={
                "job_id": branch.job_id,
                "query": branch.normalized_query.query_text,
                "keywords": branch.normalized_query.keywords,
            },
        )
        branch = branch.model_copy(update={"trace_parent": job_span.export()})

    try:
        summary = await _run_explorer_inner(ctx, branch, settings, is_root, seed_repository)
        if job_span:
            job_span.log(
                output={
                    "status": "completed",
                    "result_count": summary.result_count,
                    "coverage_assessment": summary.coverage_assessment,
                },
            )
        return summary
    except Exception as exc:
        if job_span:
            job_span.log(output={"status": "failed", "error": str(exc)})
        raise
    finally:
        if job_span:
            job_span.end()


async def _run_explorer_inner(
    ctx: restate.WorkflowContext,
    branch: ExplorerBranchInput,
    settings,
    is_root: bool,
    seed_repository: MockSeedUrlRepository,
) -> BranchSummary:
    if is_root:
        await ctx.object_call(
            initialize,
            key=branch.job_id,
            arg=JobInitializeRequest(
                raw_query=branch.normalized_query.raw_query,
                normalized_query=branch.normalized_query,
                limits=branch.limits,
                stream_tinyfish=branch.stream_tinyfish,
            ),
        )
        await ctx.object_call(
            mark_running,
            key=branch.job_id,
            arg=JobStatusUpdate(branch_id=branch.branch_id),
        )

        seeds = seed_repository.search(branch.normalized_query, branch.limits.seed_limit)
        if seeds:
            await ctx.object_call(
                append_event,
                key=branch.job_id,
                arg=EventAppendRequest(
                    event_type="seeds.ready",
                    branch_id=branch.branch_id,
                    payload={"seeds": [seed.model_dump(mode="json") for seed in seeds]},
                ),
            )
        domains = enumerate_candidate_urls(
            branch.normalized_query.keywords,
            settings.explorer_enum_tlds,
            branch.limits.domain_limit,
        )
        await ctx.object_call(
            append_event,
            key=branch.job_id,
            arg=EventAppendRequest(
                event_type="domains.ready",
                branch_id=branch.branch_id,
                payload={"domains": domains},
            ),
        )

        branch = branch.model_copy(
            update={
                "candidate_urls": list(
                    dict.fromkeys(
                        branch.candidate_urls + [seed.url for seed in seeds] + domains
                    )
                )
            }
        )

    await ctx.object_call(
        append_event,
        key=branch.job_id,
        arg=EventAppendRequest(
            event_type="branch.started",
            branch_id=branch.branch_id,
            payload={
                "depth": branch.depth,
                "candidate_urls": branch.candidate_urls[: branch.limits.max_results],
            },
        ),
    )

    try:
        summary = await _run_openai_loop(ctx, branch)
        await ctx.object_call(
            append_event,
            key=branch.job_id,
            arg=EventAppendRequest(
                event_type="branch.completed",
                branch_id=branch.branch_id,
                payload={"summary": summary.model_dump(mode="json")},
            ),
        )
        if is_root:
            snapshot = await ctx.object_call(
                mark_completed,
                key=branch.job_id,
                arg=JobStatusUpdate(
                    branch_id=branch.branch_id,
                    payload={"coverage_assessment": summary.coverage_assessment},
                ),
            )
            snapshot_data = snapshot.model_dump(mode="json") if hasattr(snapshot, "model_dump") else snapshot
            embedding = await generate_embedding(branch.normalized_query.query_text, settings)
            await save_search_job(snapshot_data, query_embedding=embedding)
        return summary
    except Exception as exc:
        if is_root:
            snapshot = await ctx.object_call(
                mark_failed,
                key=branch.job_id,
                arg=JobError(
                    code="explorer_failed",
                    message=str(exc),
                    retryable=False,
                    details={"branch_id": branch.branch_id},
                ),
            )
            snapshot_data = snapshot.model_dump(mode="json") if hasattr(snapshot, "model_dump") else snapshot
            await save_search_job(snapshot_data)
        raise


SERVICES = [greeter, search_job_state, explorer_workflow, tinyfish_tasks]
