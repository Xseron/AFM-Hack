from invistigator.linkdetect import find_telegram_links


def test_plain_tme_url():
    assert find_telegram_links("https://t.me/mychannel") == ["@mychannel"]


def test_telegram_me_and_dog():
    assert find_telegram_links("telegram.me/foochan") == ["@foochan"]
    assert find_telegram_links("telegram.dog/barchan") == ["@barchan"]


def test_with_at_sign():
    assert find_telegram_links("t.me/@somechan") == ["@somechan"]


def test_in_bio_text():
    bio = "Пиши мне в телегу 👉 t.me/best_casino_kz 💰"
    assert find_telegram_links(None, bio) == ["@best_casino_kz"]


def test_bare_mention_is_not_telegram():
    assert find_telegram_links("follow @someuser on insta") == []


def test_private_invite_skipped():
    assert find_telegram_links("t.me/joinchat/AAAA") == []
    assert find_telegram_links("t.me/+AbCdEf123") == []


def test_dedup_across_fields():
    assert find_telegram_links("t.me/dupchan", "t.me/dupchan t.me/other") == ["@dupchan", "@other"]


def test_multiple_sources():
    links = find_telegram_links("https://t.me/chan1", "see t.me/chan2")
    assert links == ["@chan1", "@chan2"]


def test_empty():
    assert find_telegram_links(None, "", "no links here") == []
