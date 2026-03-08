"""Fuzzy string matching — score and highlight matched characters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FuzzyMatch:
    """Result of a fuzzy match, with score and matched character positions."""

    score: int
    positions: tuple[int, ...]


def fuzzy_match(query: str, target: str) -> FuzzyMatch | None:
    """Score *query* against *target* using fuzzy substring matching.

    Returns ``None`` if no match.  Higher scores are better.

    Scoring:
    - +10 per matched character
    - +5 bonus for consecutive matches
    - +10 bonus for matching at word start (after ``/ _ - .`` or uppercase)
    - +15 bonus for matching at string start
    """
    if not query:
        return FuzzyMatch(score=0, positions=())

    q = query.lower()
    t = target.lower()
    qi = 0
    positions: list[int] = []
    score = 0
    prev_matched = -2  # impossible index

    for ti, ch in enumerate(t):
        if qi < len(q) and ch == q[qi]:
            positions.append(ti)
            score += 10

            # Consecutive bonus
            if ti == prev_matched + 1:
                score += 5

            # Word-start bonus
            if ti == 0:
                score += 15
            elif ti > 0 and target[ti - 1] in "/_-. ":
                score += 10
            elif ti > 0 and target[ti].isupper() and target[ti - 1].islower():
                score += 10

            prev_matched = ti
            qi += 1

    if qi < len(q):
        return None  # not all query chars matched

    # Penalty for target length (prefer shorter matches)
    score -= len(target)

    return FuzzyMatch(score=score, positions=tuple(positions))


def fuzzy_filter(query: str, items: list[str]) -> list[tuple[str, FuzzyMatch]]:
    """Filter and sort *items* by fuzzy match score against *query*.

    Returns ``(item, match)`` pairs sorted by descending score.
    """
    if not query:
        return [(item, FuzzyMatch(score=0, positions=())) for item in items]

    results: list[tuple[str, FuzzyMatch]] = []
    for item in items:
        m = fuzzy_match(query, item)
        if m is not None:
            results.append((item, m))

    results.sort(key=lambda r: r[1].score, reverse=True)
    return results
