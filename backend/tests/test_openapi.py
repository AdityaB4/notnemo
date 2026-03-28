import json
import os
import unittest
from pathlib import Path

import yaml
from openapi_spec_validator import validate

os.environ["RESTATE_AUTO_REGISTER"] = "false"

from backend.config import get_settings

get_settings.cache_clear()

from main import app


class OpenApiTests(unittest.TestCase):
    def test_runtime_openapi_contains_search_routes(self) -> None:
        schema = app.openapi()

        self.assertIn("/api/search", schema["paths"])
        self.assertIn("/api/search/{job_id}/events", schema["paths"])
        event_response = schema["paths"]["/api/search/{job_id}/events"]["get"]["responses"]["200"]
        self.assertIn("text/event-stream", event_response["content"])

    def test_committed_openapi_matches_runtime_and_validates(self) -> None:
        runtime_schema = app.openapi()
        openapi_dir = Path(__file__).resolve().parents[1] / "openapi"
        committed_json = json.loads((openapi_dir / "openapi.json").read_text(encoding="utf-8"))
        committed_yaml = yaml.safe_load((openapi_dir / "openapi.yaml").read_text(encoding="utf-8"))

        self.assertEqual(runtime_schema, committed_json)
        self.assertEqual(committed_json, committed_yaml)
        validate(committed_json)


if __name__ == "__main__":
    unittest.main()
