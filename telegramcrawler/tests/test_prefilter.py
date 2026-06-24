from aimw.prefilter import prefilter_text, LEXICON
from aimw.domain import RISK_CATEGORIES


def test_lexicon_covers_all_categories():
    assert set(LEXICON.keys()) == set(RISK_CATEGORIES)
    assert all(LEXICON[c] for c in RISK_CATEGORIES)


def test_gambling_ru_detected():
    r = prefilter_text("Лучшее онлайн казино, делай ставки и выигрывай!")
    assert r["is_suspicious"] is True
    assert "illegal_gambling" in r["matched_categories"]


def test_guaranteed_income_detected():
    r = prefilter_text("Гарантированный доход 100% каждый день")
    assert r["is_suspicious"] is True
    assert "guaranteed_income" in r["matched_categories"]


def test_referral_detected():
    r = prefilter_text("Приглашай друзей по реферальной ссылке и зарабатывай")
    assert "referral_scheme" in r["matched_categories"]


def test_kazakh_gambling_detected():
    r = prefilter_text("Ең жақсы онлайн казино, бәс тігіп ұтып ал")
    assert r["is_suspicious"] is True
    assert "illegal_gambling" in r["matched_categories"]


def test_clean_text_not_suspicious():
    r = prefilter_text("Сегодня хорошая погода, гуляли в парке с детьми")
    assert r["is_suspicious"] is False
    assert r["matched_categories"] == []
