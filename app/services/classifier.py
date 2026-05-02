from __future__ import annotations


# Score floor that matches each class (total_score scale).
# Used when a guardrail bumps the class up to ensure score ≥ floor.
CLASS_SCORE_FLOOR: dict[str, float] = {"A": 0.0, "B": 10.0, "C": 20.0, "D": 30.0}


def _class_rank(label: str) -> int:
    return {"A": 0, "B": 1, "C": 2, "D": 3}.get(label, 0)


def competition_class(weighted_competition: float) -> str:
    """
    Classify competition level based on weighted competition score.

    weighted_competition accumulates (competitive_weight × text-match-weight)
    for every organic result, so it naturally deflates when the SERP is
    dominated by informational or irrelevant pages.

      A – very low real competition   (score ≤ 2.0)
      B – moderate competition        (score ≤ 5.0)
      C – noticeable competition      (score ≤ 9.0)
      D – high competition            (score  > 9.0)
    """
    if weighted_competition <= 2.0:
        return "A"
    if weighted_competition <= 5.0:
        return "B"
    if weighted_competition <= 9.0:
        return "C"
    return "D"


def apply_deep_guardrails(
    current_class: str,
    direct_count: int,
    strong_intent_count: int,
    tool_like_count: int,
    serp_mix_label: str,
    total_results: int,
) -> tuple[str, str]:
    """
    Apply hard guardrails on top of the base weighted-competition class.
    Returns (adjusted_class, human_readable_reason).
    reason is empty string if no adjustment was made.

    Guardrails only *raise* the class (A→B, A→C, etc.) — never lower it.
    """
    if total_results == 0:
        return current_class, ""

    required_rank = _class_rank(current_class)
    reasons: list[str] = []
    homo = serp_mix_label == "HOMOGENEOUS"

    # ── Force D ────────────────────────────────────────────────────────────────
    if required_rank < 3:
        if direct_count >= 8:
            required_rank = 3
            reasons.append(f"direct={direct_count}≥8")
        elif direct_count >= 7 and strong_intent_count >= 7 and homo:
            required_rank = 3
            reasons.append(f"direct={direct_count}, strong_intent={strong_intent_count}, mix=HOMOGENEOUS")
        elif direct_count >= 6 and tool_like_count >= 8 and strong_intent_count >= 7 and homo:
            required_rank = 3
            reasons.append(f"direct={direct_count}, tool_like={tool_like_count}, strong_intent={strong_intent_count}, mix=HOMOGENEOUS")

    # ── Force C ────────────────────────────────────────────────────────────────
    if required_rank < 2:
        if direct_count >= 5 and strong_intent_count >= 5:
            required_rank = 2
            reasons.append(f"direct={direct_count}≥5, strong_intent={strong_intent_count}≥5")
        elif direct_count >= 5 and homo:
            required_rank = 2
            reasons.append(f"direct={direct_count}≥5, mix=HOMOGENEOUS")
        elif direct_count >= 4 and tool_like_count >= 6 and homo:
            required_rank = 2
            reasons.append(f"direct={direct_count}≥4, tool_like={tool_like_count}≥6, mix=HOMOGENEOUS")
        elif tool_like_count >= 7 and strong_intent_count >= 6 and homo:
            required_rank = 2
            reasons.append(f"tool_like={tool_like_count}≥7, strong_intent={strong_intent_count}≥6, mix=HOMOGENEOUS")

    # ── Force B (A forbidden) ──────────────────────────────────────────────────
    if required_rank < 1:
        if direct_count >= 4:
            required_rank = 1
            reasons.append(f"direct={direct_count}≥4")
        elif direct_count >= 3 and homo:
            required_rank = 1
            reasons.append(f"direct={direct_count}≥3, mix=HOMOGENEOUS")
        elif tool_like_count >= 6 and strong_intent_count >= 5:
            required_rank = 1
            reasons.append(f"tool_like={tool_like_count}≥6, strong_intent={strong_intent_count}≥5")
        elif strong_intent_count >= 6:
            required_rank = 1
            reasons.append(f"strong_intent={strong_intent_count}≥6")
        elif tool_like_count >= 7:
            required_rank = 1
            reasons.append(f"tool_like={tool_like_count}≥7")
        elif strong_intent_count >= 7:
            required_rank = 1
            reasons.append(f"strong_intent={strong_intent_count}≥7")

    new_class = ("A", "B", "C", "D")[required_rank]
    if new_class == current_class:
        return current_class, ""

    reason = f"Класс повышен {current_class}→{new_class}: {'; '.join(reasons)}"
    return new_class, reason


def recommendation(
    label: str,
    commercial_count: int,
    total_organic: int,
    serp_mix_label: str = "MIXED",
    direct_count: int = 0,
    strong_intent_count: int = 0,
) -> str:
    """
    Class-driven recommendation. direct_count / strong_intent_count are used
    to add factual context when available (deep analysis).
    """
    if total_organic == 0:
        return "Данных недостаточно для рекомендации"

    if label == "A":
        base = (
            "Низкая конкуренция: прямых конкурентов мало, выдача не закрыта "
            "плотными сервисами. Хороший кандидат для SEO-продвижения."
        )
    elif label == "B":
        base = (
            "Умеренная конкуренция: есть релевантные результаты, но выдача "
            "не полностью занята прямыми конкурентами. Можно брать в работу."
        )
    elif label == "C":
        base = (
            "Высокая конкуренция: в топе заметная доля прямых или близких "
            "конкурентов, заходить осторожно."
        )
    else:
        base = (
            "Очень высокая конкуренция: выдача плотно занята прямыми "
            "конкурентами, интент хорошо закрыт. Продвижение будет сложным."
        )

    # Factual appendix when deep data is available
    if direct_count > 0:
        base += f" Прямых конкурентов в топ-10: {direct_count}"
        if strong_intent_count > 0:
            base += f", из них сильно закрывают интент: {strong_intent_count}."
        else:
            base += "."

    # SERP-mix overlay
    if serp_mix_label == "STRONGLY_MIXED":
        base += " Выдача сильно смешанная — есть шанс занять нишу более точной страницей."
    elif serp_mix_label == "HOMOGENEOUS" and label in ("C", "D"):
        base += " Выдача однородная — конкуренция выше среднего."

    return base
