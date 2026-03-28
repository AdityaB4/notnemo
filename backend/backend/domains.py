from __future__ import annotations

from itertools import permutations

from backend.utils import canonicalize_url, dedupe_preserve_order, slugify_keyword


def enumerate_candidate_urls(
    keywords: list[str], tlds: tuple[str, ...], limit: int
) -> list[str]:
    if limit <= 0:
        return []

    slugs = dedupe_preserve_order(
        [slugify_keyword(keyword) for keyword in keywords if slugify_keyword(keyword)]
    )[:4]
    if len(slugs) < 2:
        return []

    urls: list[str] = []
    for left, right in permutations(slugs, 2):
        stems = (f"{left}{right}", f"{left}-{right}")
        for stem in stems:
            for tld in tlds:
                urls.append(canonicalize_url(f"https://{stem}.{tld}"))
                if len(urls) >= limit * 2:
                    break
            if len(urls) >= limit * 2:
                break
        if len(urls) >= limit * 2:
            break

    return dedupe_preserve_order(urls)[:limit]

