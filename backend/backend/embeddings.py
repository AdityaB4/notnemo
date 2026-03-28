from __future__ import annotations

import logging

import httpx

from backend.config import Settings

logger = logging.getLogger(__name__)


async def generate_embedding(text: str, settings: Settings) -> list[float] | None:
    """Generate an embedding vector for the given text using OpenAI embeddings API."""
    if not settings.openai_api_key:
        logger.debug("No OpenAI API key configured, skipping embedding generation")
        return None

    endpoint = f"{settings.openai_base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_embedding_model,
        "input": text,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
    except Exception:
        logger.exception("Failed to generate embedding for query")
        return None
