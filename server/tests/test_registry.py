from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.registry import PipelineRegistry


class _P:
    def __init__(self, name, modality):
        self.name = name
        self.modality = modality

    async def process(self, ctx, unit):
        return []

    async def explain(self, ctx, findings):
        return None


def test_register_and_query():
    reg = PipelineRegistry()
    reg.register(_P("t", "triage"))
    reg.register(_P("txt", "text"))
    reg.register(_P("vis", "visual"))
    assert {p.name for p in reg.all()} == {"t", "txt", "vis"}
    assert [p.name for p in reg.triage_pipelines()] == ["t"]
    assert {p.name for p in reg.analysis_pipelines()} == {"txt", "vis"}
    assert reg.by_modality("text")[0].name == "txt"
