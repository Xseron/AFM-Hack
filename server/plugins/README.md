# Checker plugins

Drop a single `*.py` file in this folder to add a new checker to the analysis
pipeline. It is auto-discovered at server startup and whenever you press
**Reload plugins** on the *Pipeline* tab — no restart, no code changes elsewhere.

## Required format

The file must expose a `PIPELINE` instance (or a `get_pipeline()` function) that
implements the `Pipeline` protocol from `app.pipelines.base`:

```python
from app.pipelines.base import Finding, JobContext, Unit

class MyChecker:
    name = "my_checker"     # unique id (shown as the node label)
    modality = "text"       # text | ocr | audio | visual | triage

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        # return zero or more Findings; confidence is 0..1
        ...

    async def explain(self, ctx, findings):
        return None

PIPELINE = MyChecker()
```

- `modality` decides which dashboard column the score feeds
  (`triage`/`text` → Semantic, `ocr` → OCR, `visual` → CLIP, `audio` → Audio)
  and which aggregator weight applies.
- Files starting with `_` are ignored (use that for templates — see
  `_example_template.py`).
- An import/format error is shown on the node instead of crashing startup.

## Editing from the UI

On the *Pipeline* tab each node can be toggled on/off, have its modality weight
retuned, and (for plugins) be removed from the running pipeline. The aggregator's
category threshold and the per-checker auto-investigate thresholds are editable
there too. These edits are live but in-memory; set `MW_*` env vars for the
defaults applied at startup.
