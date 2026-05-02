from __future__ import annotations

import re
from functools import lru_cache

import pymorphy3 as pymorphy2

STOPWORDS = {
    "и",
    "в",
    "во",
    "на",
    "по",
    "с",
    "со",
    "к",
    "ко",
    "из",
    "за",
    "под",
    "для",
    "о",
    "об",
    "от",
    "у",
    "а",
}


@lru_cache(maxsize=1)
def morph() -> pymorphy2.MorphAnalyzer:
    return pymorphy2.MorphAnalyzer()


def normalize_text(text: str) -> str:
    lowered = text.lower().replace("ё", "е")
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    compact = re.sub(r"\s+", " ", cleaned).strip()
    return compact


def lemmatize_tokens(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    lemmas: list[str] = []
    analyzer = morph()
    for token in normalized.split():
        parse = analyzer.parse(token)
        lemma = parse[0].normal_form if parse else token
        lemmas.append(lemma)
    return lemmas


def extract_significant_lemmas(keyword: str) -> list[str]:
    lemmas = lemmatize_tokens(keyword)
    unique: list[str] = []
    for lemma in lemmas:
        if lemma in STOPWORDS:
            continue
        if lemma not in unique:
            unique.append(lemma)
    return unique
