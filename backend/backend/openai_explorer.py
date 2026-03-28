from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import braintrust
from openai import AsyncOpenAI

from backend.config import Settings
from backend.models import (
    BranchOutcome,
    ExplorerBranchInput,
    SearchResultDraft,
    SubExplorerToolRequest,
    TinyFishToolRequest,
)
from backend.utils import extract_json_object


SYSTEM_PROMPT = """
You are RestateExplorer, a niche-first discovery agent.

Requirements:
- Optimize for specific, non-obvious, high-signal results.
- Use web search first when the answer is not already obvious from the provided URLs.
- Call tinyfish_scrape only after web search has been attempted and only when the search evidence is insufficient or inconclusive.
- Call sub_explorer only for promising leads that need deeper coverage.
- If the profile contains "debug_force_tinyfish": true, you must perform web search first and then call tinyfish_scrape on the best concrete URL before returning final results.
- Stay within the provided recursion and result budget.
- Return JSON only.

JSON contract:
{
  "results": [
    {
      "url": "https://example.com",
      "description": "Why this source is relevant",
      "source_kind": "web_search",
      "why_matched": "Why it matches the user and query",
      "tags": ["tag1", "tag2"],
      "confidence": 0.71
    }
  ],
  "coverage_assessment": "Brief quality assessment",
  "notes": "Important caveats or observations",
  "follow_up_queries": ["optional deeper angle"]
}
""".strip()


@dataclass(slots=True)
class FunctionToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


class OpenAIResponseError(RuntimeError):
    pass


class OpenAIResponsesClient:
    """Thin wrapper around the official OpenAI SDK, traced via braintrust.wrap_openai."""

    def __init__(self, settings: Settings):
        self._settings = settings
        if settings.openai_api_key:
            self._client: AsyncOpenAI | None = braintrust.wrap_openai(
                AsyncOpenAI(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                    timeout=180.0,
                )
            )
        else:
            self._client = None

    async def create_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise OpenAIResponseError("OPENAI_API_KEY is not configured.")
        try:
            response = await self._client.responses.create(**payload)
            return response.model_dump(mode="json")
        except OpenAIResponseError:
            raise
        except Exception as exc:
            raise OpenAIResponseError(f"OpenAI Responses API error: {exc}") from exc


def build_initial_input(branch: ExplorerBranchInput) -> list[dict[str, Any]]:
    profile_text = (
        json.dumps(branch.normalized_query.profile, ensure_ascii=True)
        if branch.normalized_query.profile
        else "{}"
    )
    prompt = f"""
Query: {branch.normalized_query.query_text}
Keywords: {", ".join(branch.normalized_query.keywords) or "none"}
Profile: {profile_text}
Depth: {branch.depth}
Candidate URLs:
{json.dumps(branch.candidate_urls, ensure_ascii=True, indent=2)}

Find niche-first sources and return no more than {branch.limits.max_results} results.
""".strip()
    return [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": prompt}],
        },
    ]


def build_tool_definitions(settings: Settings) -> list[dict[str, Any]]:
    return [
        {"type": settings.openai_web_search_tool_type},
        {
            "type": "function",
            "name": "tinyfish_scrape",
            "description": (
                "Use TinyFish to scrape a URL and extract structured data when web search "
                "was insufficient or inconclusive."
            ),
            "parameters": TinyFishToolRequest.model_json_schema(),
        },
        {
            "type": "function",
            "name": "sub_explorer",
            "description": (
                "Recursively spawn another explorer branch for a focused angle or a smaller URL set."
            ),
            "parameters": SubExplorerToolRequest.model_json_schema(),
        },
    ]


def build_response_payload(
    settings: Settings,
    response_input: list[dict[str, Any]],
    previous_response_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": settings.openai_explorer_model,
        "input": response_input,
        "tools": build_tool_definitions(settings),
        "parallel_tool_calls": True,
    }
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    return payload


def extract_function_calls(response: dict[str, Any]) -> list[FunctionToolCall]:
    calls: list[FunctionToolCall] = []
    for item in response.get("output", []):
        if item.get("type") != "function_call":
            continue
        arguments = item.get("arguments") or "{}"
        parsed_arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
        calls.append(
            FunctionToolCall(
                call_id=item.get("call_id") or item.get("id") or "",
                name=item.get("name", ""),
                arguments=parsed_arguments or {},
            )
        )
    return calls


def saw_web_search(response: dict[str, Any]) -> bool:
    return any("web_search" in item.get("type", "") for item in response.get("output", []))


def extract_output_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def parse_branch_outcome(response: dict[str, Any]) -> BranchOutcome | None:
    payload = extract_json_object(extract_output_text(response))
    if not isinstance(payload, dict):
        return None
    try:
        return BranchOutcome.model_validate(payload)
    except Exception:
        return None


def build_fallback_outcome(
    branch: ExplorerBranchInput,
    note: str,
    source_kind: str = "enumerated_domain",
) -> BranchOutcome:
    results: list[SearchResultDraft] = []
    for url in branch.candidate_urls[: branch.limits.max_results]:
        results.append(
            SearchResultDraft(
                url=url,
                description=f"Candidate source related to {branch.normalized_query.query_text}.",
                source_kind=source_kind,  # type: ignore[arg-type]
                why_matched=(
                    "Included because it matches the query keywords or was generated as a likely domain."
                ),
                tags=branch.normalized_query.keywords[:3],
                confidence=0.34,
            )
        )
    return BranchOutcome(
        results=results,
        coverage_assessment="fallback",
        notes=note,
        follow_up_queries=[],
    )
