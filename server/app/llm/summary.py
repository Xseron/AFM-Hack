"""Short LLM summaries for flagged reels, via OpenRouter.

For a reel that the detectors marked scam / semi-scam, this asks an OpenRouter
chat model to write two short sentences for a human reviewer: what the video is
about, and why it was flagged. It is best-effort — if no API key is configured
or the call fails, ``summarize`` returns ``None`` and the job is unaffected.
"""
from __future__ import annotations

import logging

import httpx

from app.config import Settings
from app.pipelines.aggregator import VERDICT_IGNORED_PIPELINES

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a fraud analyst reviewing short-form videos (Instagram Reels / TikTok). "
    "You are given a video's caption and the automated scam-detector signals that fired. "
    "Reply with exactly two short sentences and nothing else:\n"
    "1) One sentence describing the topic of the video.\n"
    "2) One sentence explaining why it was flagged, citing the strongest signals.\n"
    "Write in the same language as the caption (Russian if the caption is Russian). "
    "No headings, no bullet points, no disclaimers."
)


def _signal_lines(findings) -> list[str]:
    lines: list[str] = []
    for f in findings:
        pipeline = (getattr(f, "evidence", None) or {}).get("_pipeline", "") or f.modality
        note = " (context only)" if pipeline in VERDICT_IGNORED_PIPELINES else ""
        lines.append(f"- {pipeline}/{f.signal_type}: {float(f.confidence or 0.0):.2f}{note}")
    return lines


def build_user_prompt(description: str, verdict: str, category: str, findings) -> str:
    caption = (description or "").strip() or "(no caption)"
    signals = "\n".join(_signal_lines(findings)) or "- (no individual signals)"
    return (
        f"Verdict: {verdict} (category: {category})\n"
        f"Caption:\n{caption}\n\n"
        f"Detector signals (name: confidence 0-1):\n{signals}"
    )


async def summarize(
    settings: Settings,
    description: str,
    verdict: str,
    category: str,
    findings,
) -> str | None:
    """Return a 2-sentence reviewer summary, or ``None`` if disabled/unavailable."""
    api_key = (settings.openrouter_api_key or "").strip()
    if not api_key:
        return None

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(description, verdict, category, findings)},
        ],
        "max_tokens": 220,
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # Optional OpenRouter attribution headers.
        "X-Title": "AI Media Watch",
    }
    url = settings.openrouter_base_url.rstrip("/") + "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=settings.openrouter_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip() or None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        log.warning("openrouter summary failed: %s", exc)
        return None
