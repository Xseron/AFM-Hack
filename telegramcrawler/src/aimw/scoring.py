from aimw.domain import PostAssessment

_WEIGHTS = {
    "illegal_gambling": 1.0,
    "financial_pyramid": 1.0,
    "guaranteed_income": 0.7,
    "aggressive_investment": 0.7,
    "referral_scheme": 0.7,
    "hidden_engagement": 0.7,
}


def _weight(category: str) -> float:
    return _WEIGHTS.get(category, 0.7)


def aggregate(assessments: list[PostAssessment]) -> dict:
    if not assessments:
        return {
            "risk_score": 0,
            "categories": [],
            "explanation": "Подозрительных постов не обнаружено.",
        }

    peak = 0.0
    volume = 0.0
    categories: list[str] = []
    for a in assessments:
        post_peak = 0.0
        for cat in a.categories:
            w = _weight(cat)
            post_peak = max(post_peak, w * a.confidence)
            if cat not in categories:
                categories.append(cat)
        peak = max(peak, post_peak)
        volume += post_peak

    # Base from the single strongest signal, plus a bounded volume bonus.
    base = peak * 90.0
    bonus = min(10.0, volume * 5.0)
    score = int(min(100, round(base + bonus)))

    explanation = (
        f"Обнаружено {len(assessments)} подозрительных постов. "
        f"Категории: {', '.join(categories)}."
    )
    return {"risk_score": score, "categories": categories, "explanation": explanation}
