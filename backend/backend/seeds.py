from __future__ import annotations

from typing import Protocol

from backend.models import NormalizedQuery, SeedCandidate


class SeedUrlRepository(Protocol):
    def search(self, normalized_query: NormalizedQuery, limit: int) -> list[SeedCandidate]:
        ...


MOCK_SEEDS: tuple[SeedCandidate, ...] = (
    SeedCandidate(
        url="https://www.highsnobiety.com",
        description="Editorial coverage of independent labels, subcultures, and emerging fashion scenes.",
        tags=["fashion", "streetwear", "brands", "underground", "design"],
        rationale="Broad but still useful for filtering toward niche brands and aesthetics.",
    ),
    SeedCandidate(
        url="https://www.are.na",
        description="Community-driven collections that often surface niche aesthetics, makers, and scenes.",
        tags=["discovery", "aesthetics", "research", "niche", "community"],
        rationale="Strong source for highly specific subculture trails and independent references.",
    ),
    SeedCandidate(
        url="https://www.ssense.com",
        description="Retail/editorial mix with a long tail of avant-garde and independent designers.",
        tags=["fashion", "brands", "avant-garde", "designer"],
        rationale="Useful seed when the query implies independent labels with a recognizable product footprint.",
    ),
    SeedCandidate(
        url="https://www.hypebeast.com",
        description="Trend and release coverage that can lead to lesser-known brand names and collaborations.",
        tags=["fashion", "streetwear", "brands", "culture"],
        rationale="Good launch point when queries mix style trends and niche brand hunting.",
    ),
    SeedCandidate(
        url="https://www.discogs.com",
        description="Structured discography data and long-tail artist discovery.",
        tags=["music", "genres", "artists", "niche", "underground"],
        rationale="Useful for scene and similarity-driven music discovery prompts.",
    ),
    SeedCandidate(
        url="https://ra.co",
        description="Electronic music events, labels, and local scenes.",
        tags=["music", "events", "labels", "local", "underground"],
        rationale="Strong for local or scene-specific music exploration.",
    ),
    SeedCandidate(
        url="https://www.theinfatuation.com",
        description="Restaurant writing with neighborhood and niche recommendations.",
        tags=["food", "restaurants", "neighborhood", "guides"],
        rationale="Useful fallback seed for food queries when a local niche angle exists.",
    ),
    SeedCandidate(
        url="https://www.reddit.com",
        description="Community discussions that surface niche firsthand recommendations and long-tail sources.",
        tags=["community", "forums", "niche", "recommendations"],
        rationale="Helpful bridge to non-obvious communities and source trails.",
    ),
)


class MockSeedUrlRepository:
    def search(self, normalized_query: NormalizedQuery, limit: int) -> list[SeedCandidate]:
        if limit <= 0:
            return []

        query_terms = set(normalized_query.keywords)
        query_text = normalized_query.query_text.lower()
        scored: list[tuple[int, SeedCandidate]] = []

        for seed in MOCK_SEEDS:
            overlap = len(query_terms.intersection(tag.lower() for tag in seed.tags))
            text_bonus = int(any(tag.lower() in query_text for tag in seed.tags))
            score = overlap * 3 + text_bonus
            scored.append((score, seed))

        scored.sort(key=lambda item: (-item[0], item[1].url))
        winners = [seed for score, seed in scored if score > 0][:limit]
        if winners:
            return winners
        return list(MOCK_SEEDS[:limit])

