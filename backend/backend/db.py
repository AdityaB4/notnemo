from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

pool: asyncpg.Pool | None = None

# ---------------------------------------------------------------------------
# Desired schema: each entry is (table_name, [(column, type_with_constraints)])
# The first column of each table is treated as the PRIMARY KEY.
# On startup we CREATE TABLE IF NOT EXISTS with all columns, then
# ALTER TABLE ADD COLUMN IF NOT EXISTS for each column so that new columns
# added here are picked up automatically without a manual migration.
# ---------------------------------------------------------------------------
_TABLES: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "items",
        [
            ("id", "SERIAL PRIMARY KEY"),
            ("content", "TEXT NOT NULL"),
            ("embedding", "vector(3)"),
        ],
    ),
    (
        "search_jobs",
        [
            ("job_id", "TEXT PRIMARY KEY"),
            ("status", "TEXT NOT NULL"),
            ("input", "JSONB NOT NULL"),
            ("output", "JSONB NOT NULL"),
            ("created_at", "TIMESTAMPTZ NOT NULL"),
            ("completed_at", "TIMESTAMPTZ NOT NULL DEFAULT NOW()"),
            ("query_embedding", "vector(1536)"),
            ("cached_from", "TEXT"),
        ],
    ),
]

# Indexes to create after table migration.
_INDEXES: list[str] = [
    """
    CREATE INDEX IF NOT EXISTS search_jobs_embedding_idx
    ON search_jobs USING hnsw (query_embedding vector_cosine_ops)
    """,
]


async def _migrate_table(conn: asyncpg.Connection, table: str, columns: list[tuple[str, str]]) -> None:
    """Create the table if missing, then add any new columns."""
    col_defs = ", ".join(f"{name} {spec}" for name, spec in columns)
    await conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({col_defs})")

    # Fetch existing columns so we can add any that are missing.
    existing = {
        row["column_name"]
        for row in await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
            table,
        )
    }
    for name, spec in columns:
        if name not in existing:
            # Strip NOT NULL / DEFAULT for ADD COLUMN — Postgres won't accept
            # NOT NULL on a new column unless there's a DEFAULT.  We keep
            # DEFAULT if present, drop bare NOT NULL otherwise.
            add_spec = spec
            if "PRIMARY KEY" in spec.upper():
                continue  # PK column must already exist from CREATE TABLE
            if "DEFAULT" not in spec.upper():
                add_spec = spec.replace("NOT NULL", "").strip()
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {add_spec}")
            logger.info("Added column %s.%s (%s)", table, name, add_spec)


async def run_migrations() -> None:
    """Run all auto-migrations. Call once at startup after the pool is ready."""
    if pool is None:
        return
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        for table, columns in _TABLES:
            await _migrate_table(conn, table, columns)
        for index_sql in _INDEXES:
            await conn.execute(index_sql)
    logger.info("Database migrations complete")


# ---------------------------------------------------------------------------
# Search job persistence
# ---------------------------------------------------------------------------


async def save_search_job(
    snapshot: dict[str, Any],
    query_embedding: list[float] | None = None,
) -> None:
    """Persist a completed/failed search job snapshot to Postgres."""
    if pool is None:
        logger.debug("No database configured, skipping search job persistence")
        return

    job_id = snapshot["job_id"]
    status = snapshot["status"]
    created_at = snapshot["created_at"]

    job_input = {
        "query": snapshot.get("query"),
    }
    job_output = {
        "results": snapshot.get("results", []),
        "errors": snapshot.get("errors", []),
    }

    embedding_str: str | None = None
    if query_embedding is not None:
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO search_jobs (job_id, status, input, output, created_at, query_embedding)
                VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6::vector)
                ON CONFLICT (job_id) DO UPDATE
                    SET status = EXCLUDED.status,
                        output = EXCLUDED.output,
                        query_embedding = COALESCE(EXCLUDED.query_embedding, search_jobs.query_embedding),
                        completed_at = NOW()
                """,
                job_id,
                status,
                json.dumps(job_input),
                json.dumps(job_output),
                created_at,
                embedding_str,
            )
        logger.info("Saved search job %s (status=%s) to database", job_id, status)
    except Exception:
        logger.exception("Failed to save search job %s to database", job_id)


# ---------------------------------------------------------------------------
# Cache lookup
# ---------------------------------------------------------------------------


async def find_cached_job(
    query_embedding: list[float],
    threshold: float,
) -> dict[str, Any] | None:
    """Find the most similar completed search job using cosine similarity.

    Returns the row as a dict if similarity >= threshold, else None.
    """
    if pool is None:
        return None

    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT job_id, status, input, output, created_at, completed_at,
                       1 - (query_embedding <=> $1::vector) AS similarity
                FROM search_jobs
                WHERE query_embedding IS NOT NULL
                  AND status = 'completed'
                  AND cached_from IS NULL
                ORDER BY query_embedding <=> $1::vector
                LIMIT 1
                """,
                embedding_str,
            )
        if row is None:
            return None
        if row["similarity"] < threshold:
            logger.info(
                "Nearest cached job %s has similarity %.3f (threshold %.3f) — cache miss",
                row["job_id"],
                row["similarity"],
                threshold,
            )
            return None
        logger.info(
            "Cache hit: job %s with similarity %.3f",
            row["job_id"],
            row["similarity"],
        )
        return dict(row)
    except Exception:
        logger.exception("Cache lookup failed")
        return None


async def create_cached_job(
    job_id: str,
    cached_from_job_id: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    query_embedding: list[float],
    created_at: str,
) -> None:
    """Insert a new search_jobs row that replays results from a cached job."""
    if pool is None:
        return

    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO search_jobs
                    (job_id, status, input, output, created_at, completed_at, query_embedding, cached_from)
                VALUES ($1, 'completed', $2::jsonb, $3::jsonb, $4, NOW(), $5::vector, $6)
                ON CONFLICT (job_id) DO NOTHING
                """,
                job_id,
                json.dumps(input_data),
                json.dumps(output_data),
                created_at,
                embedding_str,
                cached_from_job_id,
            )
        logger.info("Created cached job %s (from %s)", job_id, cached_from_job_id)
    except Exception:
        logger.exception("Failed to create cached job %s", job_id)


async def get_job_snapshot(job_id: str) -> dict[str, Any] | None:
    """Load a search job from Postgres. Returns None if not found."""
    if pool is None:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT job_id, status, input, output, created_at, completed_at, cached_from
                FROM search_jobs
                WHERE job_id = $1
                """,
                job_id,
            )
        if row is None:
            return None
        return dict(row)
    except Exception:
        logger.exception("Failed to load job snapshot %s", job_id)
        return None
