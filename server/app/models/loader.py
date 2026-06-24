"""Load the real ML detectors once at server startup.

The detector classes live in the repo-root scripts (`audio_detect.py`,
`scam_image_detector.py`, `casino_clip_detector.py`). We add the repo root to
sys.path and import them. Each model is loaded inside its own try/except so a
missing dependency (e.g. faster-whisper or an OCR backend) disables only that
one pipeline instead of crashing the server.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings

log = logging.getLogger(__name__)

# app/models/loader.py -> parents[2] == server/ (where the *_detector scripts live)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass
class Models:
    whisper: object | None = None  # audio_detect.WhisperTranscriber (warmed)
    keyword_detector: object | None = None  # audio_detect.RussianScamKeywordDetector
    ocr_extractor: object | None = None  # scam_image_detector.MediaOcrExtractor
    visual_embed: object | None = None  # scam_image_detector.VisualScamEmbeddingDetector
    clip: object | None = None  # casino_clip_detector.ClipCasinoDetector
    transcripts_dir: Path | None = None

    def available(self) -> dict[str, bool]:
        return {
            "whisper": self.whisper is not None,
            "keyword_detector": self.keyword_detector is not None,
            "ocr_extractor": self.ocr_extractor is not None,
            "visual_embed": self.visual_embed is not None,
            "clip": self.clip is not None,
        }


def _make_ocr_engine(sid, settings: Settings):
    backend = settings.ocr_backend
    if backend in ("auto", "rapidocr"):
        return sid.RapidOcrEngine(min_confidence=0.45, lang="cyrillic")
    if backend == "easyocr":
        return sid.EasyOcrEngine(
            languages=["ru", "en"],
            gpu=settings.model_device == "cuda",
            model_storage_directory=None,
            download_enabled=settings.allow_model_downloads,
        )
    if backend == "tesseract":
        cmd = sid.find_tesseract_cmd(None)
        return sid.TesseractOcrEngine(tesseract_cmd=cmd, lang="rus", tessdata_dir=None, psm_values=[6, 11])
    raise ValueError(f"unknown ocr backend: {backend!r}")


def load_models(settings: Settings) -> Models:
    """Instantiate and warm the detectors that this environment supports."""
    transcripts_dir = Path(settings.transcripts_dir)
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    models = Models(transcripts_dir=transcripts_dir)
    local_only = not settings.allow_model_downloads

    # Russian scam keyword/TF-IDF detector (cheap; only needs scikit-learn).
    try:
        import audio_detect as ad

        models.keyword_detector = ad.RussianScamKeywordDetector(
            finance_terms=ad.FINANCE_TERMS,
            call_to_action_terms=ad.CALL_TO_ACTION_TERMS,
            promise_terms=ad.PROMISE_TERMS,
            negative_terms=ad.NEGATIVE_TERMS,
            threshold=0.5,
            temperature=0.6,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("keyword detector unavailable: %s", exc)

    # Whisper transcriber (needs faster-whisper). Warm the model now.
    try:
        import audio_detect as ad

        compute_type = "float16" if settings.model_device == "cuda" else "int8"
        whisper = ad.WhisperTranscriber(
            model_name=settings.whisper_model,
            language="ru",
            device=settings.model_device,
            compute_type=compute_type,
            local_files_only=local_only,
        )
        whisper._load_model()  # raises if faster-whisper / weights are missing
        models.whisper = whisper
    except Exception as exc:  # noqa: BLE001
        log.warning("whisper unavailable (pip install faster-whisper): %s", exc)

    # CLIP zero-shot casino detector (needs torch + transformers + weights).
    try:
        import casino_clip_detector as ccd

        models.clip = ccd.ClipCasinoDetector(
            model_name=settings.clip_model,
            device=settings.model_device,
            local_files_only=local_only,
            threshold=0.5,
            aggregation="max",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("CLIP detector unavailable: %s", exc)

    # OCR-text embedding scam detector (text side; tfidf needs only sklearn).
    try:
        import scam_image_detector as sid

        models.visual_embed = sid.VisualScamEmbeddingDetector(
            backend=settings.embedding_backend,
            embedding_model=sid.DEFAULT_EMBEDDING_MODEL,
            local_files_only=local_only,
            device=settings.model_device,
            threshold=0.5,
            temperature=0.09,
            keyword_weight=0.04,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("visual embedding detector unavailable: %s", exc)

    # OCR frame extractor (needs an OCR backend: rapidocr/tesseract/easyocr).
    try:
        import scam_image_detector as sid

        engine = _make_ocr_engine(sid, settings)
        models.ocr_extractor = sid.MediaOcrExtractor(
            engine=engine,
            output_dir=transcripts_dir.parent / "ocr",
            force=False,
            frame_interval=1.5,
            max_frames=12,
            crop_top=0.0,
            crop_bottom=0.0,
            crop_left=0.0,
            crop_right=0.0,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("OCR extractor unavailable (pip install rapidocr onnxruntime): %s", exc)

    log.info("models loaded: %s", models.available())
    return models
