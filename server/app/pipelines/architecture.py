"""Live, mutable view of the analysis pipeline ("the architecture").

The orchestrator runs whatever pipelines are in the shared
:class:`PipelineRegistry`, and the aggregator scores findings using the module
globals in :mod:`app.pipelines.aggregator`. This class is the single editing
surface over both: it can enable/disable nodes (register/remove on the live
registry), retune per-checker scam thresholds and the default threshold (mutate
the aggregator globals in place), and hot-load checker plugins from a folder.

Everything here mutates process-wide state that the inline workers already read
on every job, so edits take effect on the next analyzed reel — no restart.
"""
from __future__ import annotations

from pathlib import Path

from app.pipelines import aggregator
from app.pipelines.plugins import PluginLoad, discover_plugins
from app.pipelines.registry import PipelineRegistry

# Internal modality -> the dashboard "checker" column it feeds. Kept in sync
# with app.api.serializers.method_confidences.
MODALITY_CHECKER: dict[str, str] = {
    "triage": "semantic",
    "text": "semantic",
    "ocr": "ocr",
    "visual": "clip",
    "audio": "audio",
}


class PipelineArchitecture:
    def __init__(self, registry: PipelineRegistry, plugins_dir: str = "") -> None:
        self.registry = registry
        self.plugins_dir = self._resolve_dir(plugins_dir)
        # Master catalog of every pipeline instance we can (re-)register, even
        # while disabled (a disabled node is absent from the registry).
        self._known: dict[str, object] = {p.name: p for p in registry.all()}
        self._builtin_names: set[str] = set(self._known)
        self._plugin_loads: list[PluginLoad] = []

    @staticmethod
    def _resolve_dir(plugins_dir: str) -> Path:
        if plugins_dir:
            return Path(plugins_dir)
        # app/pipelines/architecture.py -> parents[2] == <server>
        return Path(__file__).resolve().parents[2] / "plugins"

    # ---- plugins -------------------------------------------------------
    def reload_plugins(self) -> list[PluginLoad]:
        """Re-scan the plugins folder; (un)register checkers to match the files."""
        # Drop everything we registered last time so deleted files disappear.
        for load in self._plugin_loads:
            if load.pipeline is not None:
                self.registry.remove(load.pipeline.name)
                self._known.pop(load.pipeline.name, None)
        self._plugin_loads = discover_plugins(self.plugins_dir)
        for load in self._plugin_loads:
            if load.pipeline is not None:
                self._known[load.pipeline.name] = load.pipeline
                self.registry.register(load.pipeline)
        return self._plugin_loads

    def _plugin_names(self) -> set[str]:
        return {load.pipeline.name for load in self._plugin_loads if load.pipeline is not None}

    # ---- node helpers --------------------------------------------------
    def _stage_of(self, pipeline) -> str:
        return "triage" if getattr(pipeline, "modality", "") == "triage" else "scanner"

    def _node(self, pipeline) -> dict:
        modality = getattr(pipeline, "modality", "")
        name = pipeline.name
        return {
            "id": name,
            "label": name,
            "stage": self._stage_of(pipeline),
            "modality": modality,
            "checker": MODALITY_CHECKER.get(modality, modality or "?"),
            "source": "plugin" if name in self._plugin_names() else "builtin",
            "enabled": name in self.registry,
            "threshold": aggregator.threshold_for(name),
            "removable": name in self._plugin_names(),
            "error": "",
        }

    # ---- graph ---------------------------------------------------------
    def graph(self, auto_scan=None) -> dict:
        plugin_names = self._plugin_names()
        triage_nodes: list[dict] = []
        scanner_nodes: list[dict] = []
        for name, pipeline in self._known.items():
            node = self._node(pipeline)
            (triage_nodes if node["stage"] == "triage" else scanner_nodes).append(node)
        # Plugin files that failed to import -> show as broken nodes.
        for load in self._plugin_loads:
            if load.pipeline is None:
                scanner_nodes.append({
                    "id": load.file,
                    "label": load.file,
                    "stage": "scanner",
                    "modality": "",
                    "checker": "",
                    "source": "plugin",
                    "enabled": False,
                    "threshold": None,
                    "removable": False,
                    "error": load.error,
                })

        aggregate_node = {
            "id": "aggregate",
            "label": "Aggregator",
            "default_threshold": aggregator.DEFAULT_THRESHOLD,
        }
        investigate_node = {"id": "investigate", "label": "Investigator"}
        if auto_scan is not None:
            investigate_node.update(auto_scan.as_dict())

        stages = [
            {"id": "parse", "label": "Parsing", "kind": "info",
             "note": "Reels bot records video + caption and uploads to the server."},
            {"id": "triage", "label": "Light recognizer", "kind": "pipelines", "nodes": triage_nodes},
            {"id": "priority", "label": "Priority queue", "kind": "info",
             "note": "Triage score orders jobs; higher-risk reels are analyzed first."},
            {"id": "scanner", "label": "Scanners", "kind": "pipelines", "nodes": scanner_nodes},
            {"id": "aggregate", "label": "Aggregator", "kind": "aggregate", "nodes": [aggregate_node]},
            {"id": "investigate", "label": "Investigator", "kind": "investigate", "nodes": [investigate_node]},
        ]
        return {
            "stages": stages,
            "default_threshold": aggregator.DEFAULT_THRESHOLD,
            "plugins_dir": str(self.plugins_dir),
        }

    # ---- edits ---------------------------------------------------------
    def set_node(self, node_id: str, enabled: bool | None = None, threshold: float | None = None) -> dict:
        pipeline = self._known.get(node_id)
        if pipeline is None:
            raise KeyError(node_id)
        if enabled is not None:
            if enabled and node_id not in self.registry:
                self.registry.register(pipeline)
            elif not enabled and node_id in self.registry:
                self.registry.remove(node_id)
        if threshold is not None:
            aggregator.SCANNER_THRESHOLDS[node_id] = max(0.0, min(1.0, float(threshold)))
        return self._node(pipeline)

    def remove_node(self, node_id: str) -> None:
        if node_id not in self._plugin_names():
            raise ValueError("only plugin checkers can be removed; disable built-ins instead")
        self.registry.remove(node_id)
        self._known.pop(node_id, None)
        aggregator.SCANNER_THRESHOLDS.pop(node_id, None)
        self._plugin_loads = [
            load for load in self._plugin_loads
            if not (load.pipeline is not None and load.pipeline.name == node_id)
        ]

    def set_default_threshold(self, value: float) -> float:
        aggregator.DEFAULT_THRESHOLD = max(0.0, min(1.0, float(value)))
        return aggregator.DEFAULT_THRESHOLD
