"""Сокращённый набор: ключевое поведение OSINT-модулей, графа и storage."""
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from PIL import Image

from invistigator.osint import contacts, domain, username_search, image, enrich
from invistigator.graph import build_graph
from invistigator import storage
from invistigator.schemas import ProfileData, OsintData
from invistigator.config import Settings


# ---- contacts -------------------------------------------------------
def test_contacts_extracts_mix():
    r = contacts.extract_contacts(
        "mail a@b.io tel +7 700 123 45 67 ETH 0x52908400098527886E0F7030069857D2E4169EE7 "
        "wa.me/77001234567 https://tiktok.com/@casino",
        None,
    )
    assert "a@b.io" in r["emails"]
    assert "+77001234567" in r["phones"]
    assert "0x52908400098527886E0F7030069857D2E4169EE7" in r["crypto_wallets"]
    assert "77001234567" in r["whatsapp"]
    assert any("tiktok.com/@casino" in s for s in r["other_socials"])


def test_contacts_empty():
    r = contacts.extract_contacts("текст без контактов", "", None)
    assert r == {"phones": [], "emails": [], "whatsapp": [], "crypto_wallets": [], "other_socials": []}


# ---- domain ---------------------------------------------------------
def test_domain_parses_redirect_and_whois():
    resp = MagicMock()
    resp.url = "https://casino-x.com/landing"
    resp.text = "<html><head><title>Win Big</title></head></html>"
    hist = MagicMock()
    hist.url = "https://linktr.ee/promo"
    resp.history = [hist]
    client = MagicMock()
    client.get.return_value = resp
    client.__enter__ = lambda s: client
    client.__exit__ = lambda *a: False

    rec = MagicMock()
    rec.creation_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rec.registrar = "NameCheap"

    with patch.object(domain.httpx, "Client", return_value=client), \
         patch.object(domain.whois, "whois", return_value=rec), \
         patch.object(domain.dns_resolver, "resolve", side_effect=Exception("skip")):
        r = domain.analyze_domain("https://linktr.ee/promo", timeout=3)

    assert r["domain"] == "casino-x.com"
    assert r["page_title"] == "Win Big"
    assert r["registrar"] == "NameCheap"
    assert isinstance(r["domain_age_days"], int)
    assert "https://linktr.ee/promo" in r["redirect_chain"]


def test_domain_empty_url():
    assert domain.analyze_domain(None)["domain"] is None


# ---- username_search ------------------------------------------------
def test_username_search_found_on_200():
    platforms = {"tiktok": "https://tiktok.com/@{u}", "vk": "https://vk.com/{u}"}

    def fake_get(url, **kw):
        r = MagicMock()
        r.status_code = 200 if "tiktok" in url else 404
        return r

    client = MagicMock()
    client.get.side_effect = fake_get
    client.__enter__ = lambda s: client
    client.__exit__ = lambda *a: False

    with patch.object(username_search.httpx, "Client", return_value=client):
        found = username_search.search_username("casino", platforms=platforms, timeout=2)

    assert "tiktok:https://tiktok.com/@casino" in found
    assert all("vk:" not in f for f in found)


# ---- image ----------------------------------------------------------
def test_image_phash(tmp_path):
    p = Path(tmp_path) / "a.png"
    Image.new("RGB", (64, 64), (10, 200, 50)).save(p)
    r = image.analyze_image(str(p))
    assert isinstance(r["avatar_phash"], str) and len(r["avatar_phash"]) >= 8


def test_image_missing_file():
    r = image.analyze_image("", profile_pic_url="https://cdn/pic.jpg")
    assert r["avatar_phash"] is None
    assert "pic.jpg" in r["reverse_image_url"]


# ---- enrich ---------------------------------------------------------
def test_enrich_isolates_failures():
    profile = ProfileData(username="x", biography="a@b.com")
    settings = Settings(ig_username="x", osint_timeout_sec=2)
    with patch("invistigator.osint.domain.analyze_domain", side_effect=Exception("boom")), \
         patch("invistigator.osint.username_search.search_username", return_value=[]), \
         patch("invistigator.osint.image.analyze_image",
               return_value={"avatar_phash": None, "reverse_image_url": None}):
        out = enrich(profile, settings)
    assert isinstance(out, OsintData)
    assert out.emails == ["a@b.com"]      # contacts отработал
    assert "domain" in (out.osint_error or "")  # domain упал, но изолированно


# ---- graph ----------------------------------------------------------
def test_graph_links_shared_domain():
    profiles = [
        ProfileData(username="a", osint=OsintData(domain="casino.com")),
        ProfileData(username="b", osint=OsintData(domain="casino.com")),
        ProfileData(username="c", osint=OsintData(domain="lonely.com")),
    ]
    g = build_graph(profiles, min_shared=2)
    domain_nodes = [n for n in g.nodes if n.type == "domain"]
    assert len(domain_nodes) == 1 and domain_nodes[0].id == "domain:casino.com"
    edges = {(e.source, e.target) for e in g.edges}
    assert ("account:a", "domain:casino.com") in edges
    assert ("account:b", "domain:casino.com") in edges
    assert all("lonely.com" not in e.target for e in g.edges)


# ---- api /graph -----------------------------------------------------
def test_graph_endpoint(monkeypatch):
    from fastapi.testclient import TestClient
    from invistigator.api import create_app

    monkeypatch.setenv("IG_USERNAME", "x")
    client = TestClient(create_app(pipeline=object()))  # pipeline не нужен для /graph
    profiles = [
        ProfileData(username="a", osint=OsintData(domain="casino.com")),
        ProfileData(username="b", osint=OsintData(domain="casino.com")),
    ]
    with patch("invistigator.api.read_jsonl", return_value=profiles):
        resp = client.get("/graph?min_shared=2")
    assert resp.status_code == 200
    body = resp.json()
    assert any(n["id"] == "domain:casino.com" for n in body["nodes"])
    assert len(body["edges"]) == 2


# ---- storage JSONL --------------------------------------------------
def test_jsonl_roundtrip_and_csv_osint(tmp_path):
    jsonl = str(tmp_path / "r.jsonl")
    csv_path = str(tmp_path / "r.csv")
    p = ProfileData(username="a", osint=OsintData(domain="casino.com", emails=["x@y.z"]))
    storage.append_jsonl(p, jsonl)
    storage.append_row(p, csv_path)

    loaded = storage.read_jsonl(jsonl)
    assert loaded[0].osint.domain == "casino.com"
    text = Path(csv_path).read_text(encoding="utf-8")
    assert "domain" in text.splitlines()[0] and "casino.com" in text and "x@y.z" in text
