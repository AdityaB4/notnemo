from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from backend.config import Settings
from backend.models import TinyFishArtifact, TinyFishTraceEvent
from backend.utils import canonicalize_url


class TinyFishError(RuntimeError):
    pass


ProgressCallback = Callable[[TinyFishTraceEvent], Awaitable[None]]


class TinyFishClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def run_scrape(
        self,
        url: str,
        goal: str,
        on_progress: ProgressCallback | None = None,
    ) -> TinyFishArtifact:
        normalized_url = canonicalize_url(url)

        if not self._settings.tinyfish_api_key:
            trace = TinyFishTraceEvent(
                type="COMPLETE",
                purpose="TinyFish API key not configured",
                status="SKIPPED",
                raw_event={"type": "COMPLETE", "status": "SKIPPED"},
            )
            return TinyFishArtifact(
                summary="TinyFish skipped because TINYFISH_API_KEY is not configured.",
                trace=[trace],
                result_json={"url": normalized_url, "status": "skipped"},
            )

        endpoint = f"{self._settings.tinyfish_base_url.rstrip('/')}/v1/automation/run-sse"
        headers = {
            "X-API-Key": self._settings.tinyfish_api_key,
            "Content-Type": "application/json",
        }
        payload = {"url": normalized_url, "goal": goal}

        trace: list[TinyFishTraceEvent] = []
        result_json: Any | None = None
        complete_status: str | None = None

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                endpoint,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    trace_event = TinyFishTraceEvent(
                        type=event.get("type", "UNKNOWN"),
                        purpose=event.get("purpose"),
                        status=event.get("status"),
                        raw_event=event,
                    )
                    trace.append(trace_event)
                    if trace_event.type == "PROGRESS" and on_progress is not None:
                        await on_progress(trace_event)
                    if trace_event.type == "COMPLETE":
                        complete_status = event.get("status")
                        if complete_status != "COMPLETED":
                            message = event.get("error", {}).get(
                                "message", "TinyFish automation failed."
                            )
                            raise TinyFishError(message)
                        result_json = event.get("resultJson")
                        break

        summary = (
            f"TinyFish extracted structured data from {normalized_url}."
            if complete_status == "COMPLETED"
            else f"TinyFish finished for {normalized_url}."
        )
        return TinyFishArtifact(summary=summary, trace=trace, result_json=result_json)

