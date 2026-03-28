from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(BASE_DIR / ".env.local", override=False)


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value)


def _env_csv(name: str, default: str) -> tuple[str, ...]:
    value = os.environ.get(name, default)
    parts = [item.strip().lower() for item in value.split(",")]
    return tuple(item for item in parts if item)


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    database_url: str | None
    restate_admin_url: str
    restate_ingress_url: str
    self_url: str
    restate_auto_register: bool
    openai_api_key: str | None
    openai_base_url: str
    openai_explorer_model: str
    openai_web_search_tool_type: str
    tinyfish_api_key: str | None
    tinyfish_base_url: str
    explorer_max_depth: int
    explorer_max_subexplorers: int
    explorer_max_results: int
    explorer_seed_limit: int
    explorer_domain_limit: int
    explorer_sse_poll_ms: int
    explorer_enum_tlds: tuple[str, ...]
    explorer_max_iterations: int
    openapi_server_url: str | None
    braintrust_api_key: str | None
    braintrust_project: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name="NotNemo Search API",
        app_version="0.1.0",
        database_url=os.environ.get("DATABASE_URL"),
        restate_admin_url=os.environ.get("RESTATE_ADMIN_URL", "http://localhost:9070"),
        restate_ingress_url=os.environ.get("RESTATE_INGRESS_URL", "http://localhost:8080"),
        self_url=os.environ.get("SELF_URL", "http://localhost:8000"),
        restate_auto_register=_env_bool("RESTATE_AUTO_REGISTER", True),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        openai_base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        openai_explorer_model=os.environ.get("OPENAI_EXPLORER_MODEL", "gpt-5"),
        openai_web_search_tool_type=os.environ.get(
            "OPENAI_WEB_SEARCH_TOOL_TYPE", "web_search"
        ),
        tinyfish_api_key=os.environ.get("TINYFISH_API_KEY"),
        tinyfish_base_url=os.environ.get("TINYFISH_BASE_URL", "https://agent.tinyfish.ai"),
        explorer_max_depth=_env_int("EXPLORER_MAX_DEPTH", 1),
        explorer_max_subexplorers=_env_int("EXPLORER_MAX_SUB_EXPLORERS", 2),
        explorer_max_results=_env_int("EXPLORER_MAX_RESULTS", 10),
        explorer_seed_limit=_env_int("EXPLORER_SEED_LIMIT", 8),
        explorer_domain_limit=_env_int("EXPLORER_DOMAIN_LIMIT", 24),
        explorer_sse_poll_ms=_env_int("EXPLORER_SSE_POLL_MS", 250),
        explorer_enum_tlds=_env_csv("EXPLORER_ENUM_TLDS", "com,org,net,co"),
        explorer_max_iterations=_env_int("EXPLORER_MAX_ITERATIONS", 6),
        openapi_server_url=os.environ.get("OPENAPI_SERVER_URL"),
        braintrust_api_key=os.environ.get("BRAINTRUST_API_KEY"),
        braintrust_project=os.environ.get("BRAINTRUST_PROJECT", "notnemo"),
    )
