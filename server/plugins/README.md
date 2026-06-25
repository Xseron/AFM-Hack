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
  (`triage`/`text` → Semantic, `ocr` → OCR, `visual` → CLIP, `audio` → Audio).
  A custom modality (e.g. `deepfake`) is fine — it just won't map to one of the
  four dashboard columns, but it still appears as a node and in the findings.
- Files starting with `_` are ignored (use that for templates — see
  `_example_template.py`). `deepfake_detector.py` is a shipped example scanner.
- An import/format error is shown on the node instead of crashing startup.

## Detection rule & editing from the UI

A reel is flagged **scam** when **any** checker's confidence reaches that
checker's **threshold** (`confidence >= threshold`). On the *Pipeline* tab each
node can be toggled on/off, have its scam threshold set, and (for plugins) be
removed from the running pipeline. The Aggregator node sets the default
threshold for checkers without an explicit one; the Investigator node tunes the
per-checker auto-scan thresholds. These edits are live but in-memory; set `MW_*`
env vars (e.g. `MW_SCAM_THRESHOLD`) for the defaults applied at startup.
