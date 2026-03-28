from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from backend.config import Settings
from backend.tinyfish import TinyFishClient


def make_settings() -> Settings:
    return Settings(
        app_name="test",
        app_version="0.1.0",
        database_url=None,
        restate_admin_url="http://localhost:9070",
        restate_ingress_url="http://localhost:8080",
        self_url="http://localhost:8000",
        restate_auto_register=False,
        openai_api_key=None,
        openai_base_url="https://api.openai.com/v1",
        openai_explorer_model="gpt-4.1-mini",
        tinyfish_api_key="tinyfish_test_key",
        tinyfish_base_url="https://agent.tinyfish.ai",
        explorer_max_depth=1,
        explorer_max_subexplorers=2,
        explorer_max_results=10,
        explorer_seed_limit=8,
        explorer_domain_limit=24,
        explorer_sse_poll_ms=250,
        explorer_enum_tlds=("com", "org"),
        explorer_max_iterations=6,
        openapi_server_url=None,
    )


class _FakeStreamResponse:
    def __init__(self, lines: list[str]):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self._lines = kwargs.pop("_lines")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, *args, **kwargs):
        return _FakeStreamResponse(self._lines)


class TinyFishClientTests(unittest.TestCase):
    def test_run_scrape_forwards_live_events_individually(self) -> None:
        lines = [
            'data: {"type":"STARTED","runId":"run_1"}',
            'data: {"type":"STREAMING_URL","runId":"run_1","streamingUrl":"https://example.com/live"}',
            'data: {"type":"HEARTBEAT","runId":"run_1"}',
            'data: {"type":"PROGRESS","runId":"run_1","purpose":"Clicking submit"}',
            'data: {"type":"COMPLETE","runId":"run_1","status":"COMPLETED","resultJson":{"items":[1]}}',
        ]

        async def run_test() -> tuple[list[str], object]:
            client = TinyFishClient(make_settings())
            seen: list[str] = []

            async def on_event(trace_event) -> None:
                seen.append(trace_event.type)

            with patch(
                "backend.tinyfish.httpx.AsyncClient",
                side_effect=lambda *args, **kwargs: _FakeAsyncClient(
                    *args, _lines=lines, **kwargs
                ),
            ):
                artifact = await client.run_scrape(
                    "https://example.com/products",
                    "Extract product names",
                    on_event=on_event,
                )
            return seen, artifact

        seen, artifact = asyncio.run(run_test())

        self.assertEqual(
            seen,
            ["STARTED", "STREAMING_URL", "HEARTBEAT", "PROGRESS", "COMPLETE"],
        )
        self.assertEqual(artifact.result_json, {"items": [1]})
        self.assertEqual(len(artifact.trace), 5)


if __name__ == "__main__":
    unittest.main()
