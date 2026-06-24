import base64
import json
import logging
import os
import time

from openai import OpenAI

from aimw.domain import Post, PostAssessment, RISK_CATEGORIES

log = logging.getLogger("aimw.analyzer")

_SYSTEM_PROMPT = (
    "Ты модератор контента. Анализируй пост Telegram-канала (текст на русском или "
    "казахском, возможно с изображением) на признаки незаконного игорного бизнеса, "
    "финансовых пирамид и мошенничества. Верни СТРОГО JSON без пояснений вида: "
    '{"categories": [...], "confidence": 0..1, "evidence_quotes": [...], '
    '"explanation": "..."}. Допустимые категории: ' + ", ".join(RISK_CATEGORIES) + ". "
    "evidence_quotes — дословные цитаты из поста. explanation — кратко по-русски."
)


def build_client(settings) -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )


def _image_block(path: str) -> dict:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{data}"},
    }


class Analyzer:
    def __init__(self, client, settings):
        self._client = client
        self._settings = settings

    def analyze_post(self, post: Post) -> PostAssessment:
        has_media = bool(post.media_paths)
        model = (
            self._settings.openrouter_vision_model
            if has_media
            else self._settings.openrouter_text_model
        )
        content: list[dict] = [{"type": "text", "text": post.text or "(пустой текст)"}]
        for path in post.media_paths:
            if os.path.exists(path):
                content.append(_image_block(path))

        log.info(
            "OpenRouter: пост %d → модель %s (%s)",
            post.tg_message_id, model, "с картинкой" if has_media else "текст",
        )
        started = time.monotonic()
        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
            )
            raw = resp.choices[0].message.content
            log.info(
                "OpenRouter: пост %d готов за %.1f c", post.tg_message_id,
                time.monotonic() - started,
            )
            return self._parse(post, raw, model)
        except Exception as exc:  # noqa: BLE001 - never break the batch
            log.warning(
                "OpenRouter: ошибка на посте %d за %.1f c: %s",
                post.tg_message_id, time.monotonic() - started, exc,
            )
            return PostAssessment(
                tg_message_id=post.tg_message_id, categories=[], confidence=0.0,
                evidence_quotes=[], explanation=f"Ошибка анализа: {exc}",
                model_used=model,
            )

    def _parse(self, post: Post, raw: str, model: str) -> PostAssessment:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return PostAssessment(
                tg_message_id=post.tg_message_id, categories=[], confidence=0.0,
                evidence_quotes=[], explanation="Невалидный ответ модели.",
                model_used=model,
            )
        categories = [c for c in data.get("categories", []) if c in RISK_CATEGORIES]
        confidence = float(data.get("confidence", 0.0) or 0.0)
        return PostAssessment(
            tg_message_id=post.tg_message_id,
            categories=categories,
            confidence=confidence,
            evidence_quotes=list(data.get("evidence_quotes", [])),
            explanation=str(data.get("explanation", "")),
            model_used=model,
        )
