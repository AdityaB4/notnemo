from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from backend.config import get_settings
from backend.ingress import RestateIngressClient, RestateIngressError
from backend.openapi import configure_openapi
from backend.restate_services import SERVICES
from backend.routes import router

logger = logging.getLogger(__name__)


async def _register_with_retry(settings, attempts: int = 8, delay_seconds: float = 1.0) -> None:
    client = RestateIngressClient(settings)
    for attempt in range(1, attempts + 1):
        try:
            await client.register_deployment()
            logger.info("Registered Restate deployment on attempt %s", attempt)
            return
        except RestateIngressError as exc:
            logger.warning(
                "Restate deployment registration attempt %s/%s failed: %s",
                attempt,
                attempts,
                exc.message,
            )
            await asyncio.sleep(delay_seconds)

    logger.error("Restate deployment registration failed after %s attempts", attempts)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    registration_task: asyncio.Task[None] | None = None
    if settings.restate_auto_register:
        registration_task = asyncio.create_task(_register_with_retry(settings))
    yield
    if registration_task is not None and not registration_task.done():
        registration_task.cancel()
        with suppress(asyncio.CancelledError):
            await registration_task


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.mount("/restate", __import__("restate").app(services=SERVICES))
    app.include_router(router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    configure_openapi(app, settings)
    return app


app = create_app()
