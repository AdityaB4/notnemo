import os
import httpx
import restate
from contextlib import asynccontextmanager
from fastapi import FastAPI

RESTATE_ADMIN_URL = os.environ.get("RESTATE_ADMIN_URL", "http://localhost:9070")
SELF_URL = os.environ.get("SELF_URL", "http://localhost:8000")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{RESTATE_ADMIN_URL}/deployments",
            json={"uri": f"{SELF_URL}/restate"},
        )
        resp.raise_for_status()

    yield


app = FastAPI(lifespan=lifespan)

greeter = restate.Service("Greeter")


@greeter.handler()
async def greet(ctx: restate.Context, name: str) -> str:
    return f"Hello, {name}!"


restate_app = restate.app(services=[greeter])

app.mount("/restate", restate_app)


@app.get("/health")
async def health():
    return {"status": "ok"}
