"""
Единый модуль нормализации и фильтрации ключевых слов.
Используется в режимах Search API, Wordstat и Комбинированном.
"""
from __future__ import annotations

import re


def normalize_keywords(raw: list[str]) -> list[str]:
    """
    Нормализует список ключей:
    - убирает пустые строки
    - trim whitespace
    - удаляет дубли (case-insensitive, сохраняет оригинальный регистр первого вхождения)
    """
    seen: set[str] = set()
    result: list[str] = []
    for kw in raw:
        cleaned = re.sub(r"\s+", " ", kw).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def apply_minus_phrases(keywords: list[str], minus_phrases: list[str]) -> list[str]:
    """
    Фильтрует список ключей по минус-фразам (регистронезависимо).
    Ключ исключается, если содержит любую из минус-фраз.
    """
    if not minus_phrases:
        return keywords
    cleaned_minus = [m.strip().lower() for m in minus_phrases if m.strip()]
    if not cleaned_minus:
        return keywords

    result = []
    for kw in keywords:
        kw_lower = kw.lower()
        if not any(mp in kw_lower for mp in cleaned_minus):
            result.append(kw)
    return result


def parse_keywords_from_text(text: str) -> list[str]:
    """
    Разбирает текст из textarea:
    - по строкам
    - и/или через запятую (если в строке нет переносов)
    """
    lines = text.splitlines()
    keywords: list[str] = []
    for line in lines:
        if "," in line and "\n" not in line:
            for part in line.split(","):
                keywords.append(part.strip())
        else:
            keywords.append(line.strip())
    return normalize_keywords(keywords)


def parse_keywords_from_file_content(content: str, filename: str) -> list[str]:
    """
    Извлекает ключи из содержимого файла (.txt или .csv).
    Для .xlsx используется отдельный путь через pandas на стороне API.
    """
    keywords: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        # CSV: берём первую колонку
        parts = line.split(",")
        keywords.append(parts[0].strip())
    return normalize_keywords(keywords)
