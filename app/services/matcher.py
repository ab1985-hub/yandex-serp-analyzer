from __future__ import annotations

from typing import Literal


MatchLevel = Literal["STRONG", "NEAR", "PARTIAL", "NONE"]


def coverage(key_lemmas: list[str], text_lemmas: list[str]) -> float:
    if not key_lemmas:
        return 0.0
    text_set = set(text_lemmas)
    matched = sum(1 for lemma in key_lemmas if lemma in text_set)
    return matched / len(key_lemmas)


def level_by_coverage(value: float) -> MatchLevel:
    if value >= 1.0:
        return "STRONG"
    if value >= 0.75:
        return "NEAR"
    if value >= 0.4:
        return "PARTIAL"
    return "NONE"
