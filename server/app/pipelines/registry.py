from __future__ import annotations

from app.pipelines.base import Pipeline


class PipelineRegistry:
    def __init__(self) -> None:
        self._pipelines: dict[str, Pipeline] = {}

    def register(self, pipeline: Pipeline) -> Pipeline:
        self._pipelines[pipeline.name] = pipeline
        return pipeline

    def all(self) -> list[Pipeline]:
        return list(self._pipelines.values())

    def by_modality(self, modality: str) -> list[Pipeline]:
        return [p for p in self._pipelines.values() if p.modality == modality]

    def triage_pipelines(self) -> list[Pipeline]:
        return self.by_modality("triage")

    def analysis_pipelines(self) -> list[Pipeline]:
        return [p for p in self._pipelines.values() if p.modality != "triage"]
