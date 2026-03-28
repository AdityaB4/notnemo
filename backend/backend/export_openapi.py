from __future__ import annotations

import json
from pathlib import Path

import yaml

from backend.app import app


def main() -> None:
    schema = app.openapi()
    target_dir = Path(__file__).resolve().parent.parent / "openapi"
    target_dir.mkdir(parents=True, exist_ok=True)

    json_path = target_dir / "openapi.json"
    yaml_path = target_dir / "openapi.yaml"

    json_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    yaml_path.write_text(
        yaml.safe_dump(schema, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
