from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from backend.config import Settings
from backend.models import (
    BranchCompletedEvent,
    BranchStartedEvent,
    DomainsReadyEvent,
    JobCompletedEvent,
    JobFailedEvent,
    JobStartedEvent,
    KeepAliveEvent,
    ResultItemEvent,
    SeedsReadyEvent,
    TinyFishProgressEvent,
)

EVENT_MODELS = (
    JobStartedEvent,
    SeedsReadyEvent,
    DomainsReadyEvent,
    BranchStartedEvent,
    TinyFishProgressEvent,
    ResultItemEvent,
    BranchCompletedEvent,
    JobCompletedEvent,
    JobFailedEvent,
    KeepAliveEvent,
)


def _hoist_component_defs(schema: dict[str, Any], component_schemas: dict[str, Any]) -> None:
    defs = schema.pop("$defs", {})
    for name, definition in defs.items():
        if name not in component_schemas:
            component_schemas[name] = definition
        if isinstance(component_schemas[name], dict):
            _hoist_component_defs(component_schemas[name], component_schemas)

    for value in schema.values():
        if isinstance(value, dict):
            _hoist_component_defs(value, component_schemas)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _hoist_component_defs(item, component_schemas)


def _build_event_examples() -> dict[str, Any]:
    return {
        "job.started": {
            "summary": "Search job started",
            "value": "event: job.started\ndata: {\"event_type\":\"job.started\"}\n\n",
        },
        "result.item": {
            "summary": "Result item",
            "value": (
                "event: result.item\n"
                "data: {\"event_type\":\"result.item\",\"payload\":{\"result\":{\"url\":\"https://example.com\"}}}\n\n"
            ),
        },
        "tinyfish.progress": {
            "summary": "TinyFish progress",
            "value": (
                "event: tinyfish.progress\n"
                "data: {\"event_type\":\"tinyfish.progress\",\"payload\":{\"url\":\"https://example.com\",\"purpose\":\"Extracting products\"}}\n\n"
            ),
        },
    }


def configure_openapi(app: FastAPI, settings: Settings) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=settings.app_name,
            version=settings.app_version,
            description="API for launching durable niche-discovery search jobs and streaming progress over SSE.",
            routes=app.routes,
        )

        if settings.openapi_server_url:
            schema["servers"] = [{"url": settings.openapi_server_url}]

        components = schema.setdefault("components", {})
        component_schemas = components.setdefault("schemas", {})
        for model in EVENT_MODELS:
            model_schema = model.model_json_schema(
                ref_template="#/components/schemas/{model}"
            )
            _hoist_component_defs(model_schema, component_schemas)
            component_schemas[model.__name__] = model_schema

        event_path = schema["paths"]["/api/search/{job_id}/events"]["get"]
        parameters = event_path.setdefault("parameters", [])
        if not any(parameter.get("name") == "Last-Event-ID" for parameter in parameters):
            parameters.append(
                {
                    "name": "Last-Event-ID",
                    "in": "header",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Resume the event stream after the provided sequence ID.",
                }
            )

        response = event_path["responses"]["200"]
        response["content"]["text/event-stream"] = {
            "schema": {"type": "string", "format": "event-stream"},
            "examples": _build_event_examples(),
        }
        response["description"] = (
            "Server-Sent Events stream. Each `data:` line contains a JSON SearchEvent envelope."
        )
        response["x-event-models"] = [
            {"$ref": f"#/components/schemas/{model.__name__}"} for model in EVENT_MODELS
        ]

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
