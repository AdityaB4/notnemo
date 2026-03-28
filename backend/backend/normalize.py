from __future__ import annotations

import re
from typing import Any

from backend.models import NormalizedQuery
from backend.utils import dedupe_preserve_order, slugify_keyword, stable_json_dumps

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "want",
    "with",
    "you",
    "your",
}


def _collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(_collect_strings(item))
        return strings
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(_collect_strings(item))
        return strings
    return []


def _extract_query_text(raw_query: Any) -> str:
    if isinstance(raw_query, str):
        return raw_query.strip()
    if isinstance(raw_query, dict):
        for key in ("text", "query", "prompt"):
            value = raw_query.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        collected = [item.strip() for item in _collect_strings(raw_query) if item.strip()]
        if collected:
            return " ".join(dedupe_preserve_order(collected))
    elif isinstance(raw_query, list):
        collected = [item.strip() for item in _collect_strings(raw_query) if item.strip()]
        if collected:
            return " ".join(dedupe_preserve_order(collected))
    return stable_json_dumps(raw_query)


def _extract_profile(raw_query: Any) -> dict[str, Any]:
    if isinstance(raw_query, dict):
        profile = raw_query.get("profile")
        if isinstance(profile, dict):
            return profile
    return {}


def _extract_explicit_keywords(raw_query: Any) -> list[str]:
    if not isinstance(raw_query, dict):
        return []
    keywords = raw_query.get("keywords")
    if not isinstance(keywords, list):
        return []
    normalized = []
    for keyword in keywords:
        if not isinstance(keyword, str):
            continue
        slug = slugify_keyword(keyword)
        if slug:
            normalized.append(slug)
    return dedupe_preserve_order(normalized)[:4]


def _extract_keywords(query_text: str) -> list[str]:
    keywords: list[str] = []
    for token in re.findall(r"[a-z0-9][a-z0-9-]{1,}", query_text.lower()):
        token = token.strip("-")
        if token in STOPWORDS or len(token) < 3:
            continue
        slug = slugify_keyword(token)
        if slug:
            keywords.append(slug)
    return dedupe_preserve_order(keywords)[:4]


def normalize_query(raw_query: Any) -> NormalizedQuery:
    query_text = _extract_query_text(raw_query)
    profile = _extract_profile(raw_query)
    keywords = _extract_explicit_keywords(raw_query) or _extract_keywords(query_text)
    if not query_text.strip():
        query_text = "niche discovery query"
    return NormalizedQuery(
        raw_query=raw_query,
        query_text=query_text,
        profile=profile,
        keywords=keywords,
    )

