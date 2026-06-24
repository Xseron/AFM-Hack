from aimw.domain import RISK_CATEGORIES

# Lowercase RU + KZ terms per category. Substring match on lowercased text.
LEXICON: dict[str, list[str]] = {
    "illegal_gambling": [
        "казино", "ставки", "ставка", "букмекер", "1xbet", "мостбет", "mostbet",
        "1вин", "1win", "слоты", "игровые автоматы", "бонус на депозит",
        "casino", "бәс тігу", "ойын автоматы", "ставкалар",
    ],
    "financial_pyramid": [
        "пирамида", "финансовая пирамида", "вложи и получи", "пассивный доход",
        "удвоим ваши деньги", "матрица", "млм", "mlm", "ақшаңды салып",
    ],
    "guaranteed_income": [
        "гарантированный доход", "гарантированная прибыль", "доход 100%",
        "без риска", "100% прибыль", "стабильный заработок", "кепілдендірілген табыс",
        "тәуекелсіз",
    ],
    "aggressive_investment": [
        "инвестируй сейчас", "успей вложить", "иксы", "x2 за день", "×2 за день",
        "крипта взлетит", "профит", "только сегодня вход", "инвестиция",
        "инвестициялаңыз",
    ],
    "referral_scheme": [
        "реферал", "реферальн", "приглашай друзей", "промокод", "по моей ссылке",
        "бонус за регистрацию", "достарыңды шақыр", "сілтеме",
    ],
    "hidden_engagement": [
        "пиши в личку", "в лс", "напиши мне", "закрытый канал", "переходи по ссылке",
        "доступ по запросу", "жекеге жаз", "жабық канал",
    ],
}


def prefilter_text(text: str) -> dict:
    low = (text or "").lower()
    matched_categories: list[str] = []
    matched_terms: list[str] = []
    for category in RISK_CATEGORIES:
        for term in LEXICON[category]:
            if term in low:
                matched_terms.append(term)
                if category not in matched_categories:
                    matched_categories.append(category)
    return {
        "is_suspicious": bool(matched_categories),
        "matched_categories": matched_categories,
        "matched_terms": matched_terms,
    }
