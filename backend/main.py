import os
import asyncpg
import httpx
import restate
from contextlib import asynccontextmanager
from fastapi import FastAPI

RESTATE_ADMIN_URL = os.environ.get("RESTATE_ADMIN_URL", "http://localhost:9070")
SELF_URL = os.environ.get("SELF_URL", "http://localhost:8000")
DATABASE_URL = os.environ.get("DATABASE_URL")

pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    if DATABASE_URL:
        pool = await asyncpg.create_pool(DATABASE_URL)
        async with pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding vector(3)
                )
            """)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{RESTATE_ADMIN_URL}/deployments",
                json={"uri": f"{SELF_URL}/restate"},
            )
            resp.raise_for_status()
    except Exception:
        pass

    yield

    if pool:
        await pool.close()


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


@app.get("/db")
async def db_check():
    if not pool:
        return {"error": "no database configured"}
    async with pool.acquire() as conn:
        version = await conn.fetchval("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        count = await conn.fetchval("SELECT COUNT(*) FROM items")
    return {"pgvector_version": version, "items_count": count}
