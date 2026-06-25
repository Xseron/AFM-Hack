"""Auto-discovery of code-backed checker plugins.

A plugin is a single ``*.py`` file dropped into the plugins folder (see
``MW_PIPELINE_PLUGINS_DIR``; default ``<server>/plugins``). The file must expose
a checker that implements the :class:`app.pipelines.base.Pipeline` protocol,
either as a module-level ``PIPELINE`` instance or via ``get_pipeline()``:

    from app.pipelines.base import Finding, JobContext, Unit

    class MyChecker:
        name = "my_checker"        # unique id shown in the Pipeline tab
        modality = "text"          # text | ocr | audio | visual | triage

        async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
            ...
        async def explain(self, ctx, findings):
            return None

    PIPELINE = MyChecker()

Files whose name starts with ``_`` are ignored, so ``_example.py`` ships as a
template without being loaded. Import errors are captured per-file and surfaced
in the UI instead of crashing startup.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from app.pipelines.base import Pipeline


@dataclass
class PluginLoad:
    """Result of trying to load one plugin file."""

    file: str
    name: str
    pipeline: Pipeline | None = None
    error: str = ""


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"mw_plugin_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_pipeline(module):
    obj = getattr(module, "PIPELINE", None)
    if obj is None and hasattr(module, "get_pipeline"):
        obj = module.get_pipeline()
    return obj


def discover_plugins(plugins_dir: str | Path) -> list[PluginLoad]:
    """Load every ``*.py`` checker in ``plugins_dir`` (non-recursive, ``_``-skipped)."""
    directory = Path(plugins_dir)
    if not directory.is_dir():
        return []
    loads: list[PluginLoad] = []
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            module = _load_module(path)
            obj = _extract_pipeline(module)
            if obj is None:
                raise ValueError("module must define a PIPELINE instance or get_pipeline()")
            if not isinstance(obj, Pipeline):
                raise TypeError(
                    "object does not implement the Pipeline protocol "
                    "(needs name, modality, async process(), async explain())"
                )
            loads.append(PluginLoad(file=path.name, name=obj.name, pipeline=obj))
        except Exception as exc:  # one bad file must not break discovery
            loads.append(PluginLoad(file=path.name, name=path.stem, error=f"{type(exc).__name__}: {exc}"))
    return loads
