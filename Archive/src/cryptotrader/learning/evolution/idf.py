from __future__ import annotations

import math
from collections import defaultdict


def compute_idf(corpus_keywords: list[list[str]]) -> dict[str, float]:
    n_docs = len(corpus_keywords)
    if n_docs == 0:
        return {}

    # Document frequency: how many docs each keyword appears in
    df: dict[str, int] = defaultdict(int)
    for skill_kw in corpus_keywords:
        # Deduplicate (no double-counting within a single skill)
        unique = {kw.lower() for kw in skill_kw}
        for kw in unique:
            df[kw] += 1

    # IDF = log(N / df); df=0 cannot occur in theory (only counted if it appeared)
    return {kw: math.log(n_docs / count) for kw, count in df.items()}


def extract_query_keywords(snapshot: dict) -> set[str]:
    keywords: set[str] = set()

    def _add(value: object) -> None:
        if value is None:
            return
        if isinstance(value, str):
            stripped = value.strip().lower()
            if stripped:
                keywords.add(stripped)
        elif isinstance(value, int | float):
            keywords.add(str(value).lower())
        elif isinstance(value, dict):
            for k, v in value.items():
                keywords.add(str(k).lower())
                _add(v)
        elif isinstance(value, list | tuple):
            for item in value:
                _add(item)

    for key, val in snapshot.items():
        keywords.add(str(key).lower())
        _add(val)

    return keywords


def score_skill(
    skill_keywords: list[str],
    query_keywords: set[str],
    idf_table: dict[str, float],
) -> float:
    if not skill_keywords or not query_keywords:
        return 0.0

    total = 0.0
    for kw in skill_keywords:
        kw_lower = kw.lower()
        if kw_lower in query_keywords:
            total += idf_table.get(kw_lower, 0.0)
    return total
