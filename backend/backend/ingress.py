from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from backend.config import Settings


class RestateIngressError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class RestateIngressClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def register_deployment(self) -> None:
        endpoint = f"{self._settings.restate_admin_url.rstrip('/')}/deployments"
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
            response = await client.post(
                endpoint,
                json={"uri": f"{self._settings.self_url.rstrip('/')}/restate", "use_http_11": True, "force": True},
            )
            self._raise_for_status(response)

    async def submit_workflow(
        self,
        workflow_name: str,
        key: str,
        payload: Any,
        *,
        send: bool,
    ) -> dict[str, Any]:
        suffix = "/send" if send else ""
        endpoint = (
            f"{self._settings.restate_ingress_url.rstrip('/')}/"
            f"{quote(workflow_name)}/{quote(key)}/run{suffix}"
        )
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            response = await client.post(endpoint, json=payload)
            self._raise_for_status(response)
            if response.content:
                return response.json()
            return {"invocation_id": response.headers.get("x-restate-id")}

    async def call_virtual_object(
        self,
        object_name: str,
        key: str,
        handler_name: str,
        payload: Any,
    ) -> Any:
        endpoint = (
            f"{self._settings.restate_ingress_url.rstrip('/')}/"
            f"{quote(object_name)}/{quote(key)}/{quote(handler_name)}"
        )
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            response = await client.post(endpoint, json=payload)
            self._raise_for_status(response)
            if not response.content:
                return None
            return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or exc.response.reason_phrase
            raise RestateIngressError(exc.response.status_code, detail) from exc

