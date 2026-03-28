from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual CLI for exercising the search API and inspecting inputs/results."
    )
    parser.add_argument(
        "query_text",
        nargs="?",
        help="Plain text query. Ignored when --payload-json or --payload-file is provided.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for the backend API.",
    )
    parser.add_argument(
        "--payload-json",
        help="Full POST /api/search request body as an inline JSON string.",
    )
    parser.add_argument(
        "--payload-file",
        help="Path to a JSON file containing the full POST /api/search request body.",
    )
    parser.add_argument(
        "--profile-json",
        help="Optional JSON object to include as query.profile when using plain text mode.",
    )
    parser.add_argument(
        "--stream-tinyfish",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable TinyFish streaming in the request body.",
    )
    parser.add_argument("--max-depth", type=int, help="Override limits.max_depth.")
    parser.add_argument(
        "--max-subexplorers", type=int, help="Override limits.max_subexplorers."
    )
    parser.add_argument("--max-results", type=int, help="Override limits.max_results.")
    parser.add_argument("--seed-limit", type=int, help="Override limits.seed_limit.")
    parser.add_argument("--domain-limit", type=int, help="Override limits.domain_limit.")
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Skip the SSE stream and fetch only the final snapshot once.",
    )
    parser.add_argument(
        "--show-keepalive",
        action="store_true",
        help="Print keepalive events from the SSE stream.",
    )
    parser.add_argument(
        "--raw-events",
        action="store_true",
        help="Print full parsed SSE event payloads instead of a concise summary.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout in seconds for each request.",
    )
    return parser.parse_args(argv)


def _load_json(label: str, raw_value: str) -> Any:
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON for {label}: {exc}") from exc


def build_request_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload_json and args.payload_file:
        raise SystemExit("Use either --payload-json or --payload-file, not both.")

    if args.payload_json:
        payload = _load_json("--payload-json", args.payload_json)
    elif args.payload_file:
        payload = _load_json(args.payload_file, Path(args.payload_file).read_text())
    else:
        if not args.query_text:
            raise SystemExit(
                "Provide a plain text query or supply --payload-json / --payload-file."
            )
        query: dict[str, Any] = {"text": args.query_text}
        if args.profile_json:
            profile = _load_json("--profile-json", args.profile_json)
            if not isinstance(profile, dict):
                raise SystemExit("--profile-json must decode to a JSON object.")
            query["profile"] = profile
        payload = {"query": query}

    if not isinstance(payload, dict):
        raise SystemExit("The request payload must be a JSON object.")

    payload["stream_tinyfish"] = args.stream_tinyfish

    limits = dict(payload.get("limits") or {})
    for field_name, value in (
        ("max_depth", args.max_depth),
        ("max_subexplorers", args.max_subexplorers),
        ("max_results", args.max_results),
        ("seed_limit", args.seed_limit),
        ("domain_limit", args.domain_limit),
    ):
        if value is not None:
            limits[field_name] = value
    if limits:
        payload["limits"] = limits

    if "query" not in payload:
        raise SystemExit("The request payload must include a top-level 'query' field.")

    return payload


def parse_sse_messages(lines: Iterable[str]) -> Iterator[dict[str, str]]:
    event_id = ""
    event_type = "message"
    data_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line:
            if data_lines:
                yield {
                    "id": event_id,
                    "event": event_type,
                    "data": "\n".join(data_lines),
                }
            event_id = ""
            event_type = "message"
            data_lines = []
            continue

        if line.startswith(":"):
            continue
        if line.startswith("id:"):
            event_id = line[3:].strip()
            continue
        if line.startswith("event:"):
            event_type = line[6:].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())

    if data_lines:
        yield {"id": event_id, "event": event_type, "data": "\n".join(data_lines)}


def print_section(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    if isinstance(payload, str):
        print(payload)
        return
    print(json.dumps(payload, indent=2, sort_keys=True))


def _summarize_event(event: dict[str, str], raw_events: bool) -> str:
    event_type = event.get("event", "message")
    try:
        payload = json.loads(event.get("data", "{}"))
    except json.JSONDecodeError:
        payload = {"raw": event.get("data", "")}

    if raw_events:
        return json.dumps({"event": event_type, "payload": payload}, indent=2, sort_keys=True)

    if event_type == "result.item":
        result = payload.get("payload", {}).get("result", {})
        return (
            f"{event_type}: {result.get('url', '<missing url>')} "
            f"({result.get('source_kind', 'unknown')})\n"
            f"  {result.get('description', '').strip()}\n"
            f"  why: {result.get('why_matched', '').strip()}"
        )
    if event_type == "tinyfish.progress":
        progress = payload.get("payload", {})
        trace = progress.get("trace", {})
        raw_event = trace.get("raw_event", {})
        parts = [
            f"{event_type}: {progress.get('url', '<missing url>')}",
            f"type={trace.get('type', 'unknown')}",
        ]
        if trace.get("status"):
            parts.append(f"status={trace['status']}")
        if trace.get("purpose"):
            parts.append(f"purpose={trace['purpose']}")
        if raw_event.get("streamingUrl"):
            parts.append(f"streamingUrl={raw_event['streamingUrl']}")
        return " ".join(parts)
    if event_type == "keepalive":
        return event_type
    return f"{event_type}: {json.dumps(payload.get('payload', payload), sort_keys=True)}"


def _print_results(snapshot: dict[str, Any]) -> None:
    results = snapshot.get("results", [])
    print(f"\nFinal status: {snapshot.get('status')} | results: {len(results)}")
    for index, result in enumerate(results, start=1):
        print(f"\n[{index}] {result.get('url', '<missing url>')}")
        print(f"source: {result.get('source_kind', 'unknown')}")
        print(result.get("description", "").strip())
        why_matched = result.get("why_matched", "").strip()
        if why_matched:
            print(f"why: {why_matched}")


def _resolve_url(base_url: str, path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return urljoin(base_url.rstrip("/") + "/", path_or_url.lstrip("/"))


def run_cli(args: argparse.Namespace) -> int:
    payload = build_request_payload(args)
    base_url = args.base_url.rstrip("/")
    print_section("Request Payload", payload)

    timeout = httpx.Timeout(args.timeout)
    with httpx.Client(timeout=timeout) as client:
        kickoff = client.post(f"{base_url}/api/search", json=payload)
        kickoff.raise_for_status()
        accepted = kickoff.json()
        print_section("Accepted Response", accepted)

        snapshot_url = _resolve_url(base_url, accepted["snapshot_url"])
        events_url = _resolve_url(base_url, accepted["events_url"])

        if not args.no_stream:
            print("\n=== SSE Events ===")
            with client.stream("GET", events_url, params={"since": 0}) as stream:
                stream.raise_for_status()
                for event in parse_sse_messages(stream.iter_lines()):
                    if event["event"] == "keepalive" and not args.show_keepalive:
                        continue
                    print(_summarize_event(event, raw_events=args.raw_events))
                    if event["event"] in {"job.completed", "job.failed"}:
                        break

        snapshot_response = client.get(snapshot_url)
        snapshot_response.raise_for_status()
        snapshot = snapshot_response.json()
        print_section("Final Snapshot", snapshot)
        _print_results(snapshot)

    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_cli(args)
    except httpx.HTTPStatusError as exc:
        response_text = exc.response.text.strip()
        print(
            f"Request failed with {exc.response.status_code} for {exc.request.method} "
            f"{exc.request.url}",
            file=sys.stderr,
        )
        if response_text:
            print(response_text, file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"HTTP request failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
