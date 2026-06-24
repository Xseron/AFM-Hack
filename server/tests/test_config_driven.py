from app.config import Settings
from app.pipelines.stubs import build_registry


def test_enabled_pipeline_list_parses():
    s = Settings(enabled_pipelines="triage_keyword, text_nlp ,")
    assert s.enabled_pipeline_list == ["triage_keyword", "text_nlp"]


def test_build_registry_all_by_default():
    assert len(build_registry(None).all()) == 5


def test_build_registry_selects_configured_subset():
    reg = build_registry(["triage_keyword", "visual_cv"])
    assert {p.name for p in reg.all()} == {"triage_keyword", "visual_cv"}
    assert len(reg.triage_pipelines()) == 1
