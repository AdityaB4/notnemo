from __future__ import annotations

import argparse
import unittest

from backend.manual_cli import build_request_payload, parse_sse_messages


class ManualCliTests(unittest.TestCase):
    def test_build_request_payload_from_text_query(self) -> None:
        args = argparse.Namespace(
            payload_json=None,
            payload_file=None,
            query_text="embroidered denim underground brands",
            profile_json='{"style":["avant-garde"]}',
            stream_tinyfish=True,
            max_depth=1,
            max_subexplorers=None,
            max_results=5,
            seed_limit=None,
            domain_limit=None,
        )

        payload = build_request_payload(args)

        self.assertEqual(payload["query"]["text"], "embroidered denim underground brands")
        self.assertEqual(payload["query"]["profile"]["style"], ["avant-garde"])
        self.assertEqual(payload["limits"]["max_depth"], 1)
        self.assertEqual(payload["limits"]["max_results"], 5)
        self.assertTrue(payload["stream_tinyfish"])

    def test_parse_sse_messages_groups_event_frames(self) -> None:
        lines = [
            "id: 1",
            "event: result.item",
            'data: {"payload":{"result":{"url":"https://example.com"}}}',
            "",
            "event: job.completed",
            'data: {"payload":{"status":"completed"}}',
            "",
        ]

        events = list(parse_sse_messages(lines))

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["id"], "1")
        self.assertEqual(events[0]["event"], "result.item")
        self.assertIn("example.com", events[0]["data"])
        self.assertEqual(events[1]["event"], "job.completed")


if __name__ == "__main__":
    unittest.main()
