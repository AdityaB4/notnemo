import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

os.environ["RESTATE_AUTO_REGISTER"] = "false"

from backend.config import get_settings

get_settings.cache_clear()

from main import app


class SearchApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_create_search_job_returns_accepted_response(self) -> None:
        with patch(
            "backend.routes.RestateIngressClient.call_virtual_object",
            new=AsyncMock(return_value=None),
        ), patch(
            "backend.routes.RestateIngressClient.submit_workflow",
            new=AsyncMock(return_value={"invocation_id": "inv_123"}),
        ):
            response = self.client.post(
                "/api/search",
                json={"query": "embroidered denim underground brands"},
            )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "queued")
        self.assertIn("/api/search/", body["snapshot_url"])
        self.assertIn("/events", body["events_url"])

    def test_get_search_job_returns_snapshot(self) -> None:
        snapshot = {
            "job_id": "search_123",
            "status": "running",
            "query": {
                "raw_query": {"text": "embroidered denim underground brands"},
                "normalized": {
                    "raw_query": {"text": "embroidered denim underground brands"},
                    "query_text": "embroidered denim underground brands",
                    "profile": {},
                    "keywords": ["embroidered", "denim", "underground", "brands"],
                },
            },
            "results": [],
            "errors": [],
            "created_at": "2026-03-28T12:00:00+00:00",
            "updated_at": "2026-03-28T12:00:01+00:00",
        }
        with patch(
            "backend.routes.RestateIngressClient.call_virtual_object",
            new=AsyncMock(return_value=snapshot),
        ):
            response = self.client.get("/api/search/search_123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "running")

    def test_stream_search_events_emits_sse(self) -> None:
        event = {
            "seq": 1,
            "event_type": "result.item",
            "event_id": "evt_1",
            "job_id": "search_123",
            "branch_id": "root",
            "payload": {
                "result": {
                    "result_id": "result_1",
                    "url": "https://example.com",
                    "description": "Example result",
                    "source_kind": "web_search",
                    "why_matched": "Matches the niche query.",
                    "tags": ["denim"],
                    "confidence": 0.7,
                    "branch_id": "root",
                    "tinyfish": None,
                }
            },
            "created_at": "2026-03-28T12:00:00+00:00",
        }
        payloads = [
            {"job_id": "search_123", "status": "running", "events": [event], "next_seq": 1},
            {"job_id": "search_123", "status": "completed", "events": [], "next_seq": 1},
        ]

        with patch(
            "backend.routes.RestateIngressClient.call_virtual_object",
            new=AsyncMock(side_effect=payloads),
        ), patch(
            "backend.routes.asyncio.sleep",
            new=AsyncMock(return_value=None),
        ):
            with self.client.stream("GET", "/api/search/search_123/events") as response:
                chunks = list(response.iter_text())

        body = "".join(chunks)
        self.assertEqual(response.status_code, 200)
        self.assertIn("event: result.item", body)
        self.assertIn("\"url\": \"https://example.com\"", body)


if __name__ == "__main__":
    unittest.main()
