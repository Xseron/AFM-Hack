from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Iterable


os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
warnings.filterwarnings("ignore", message="A NumPy version .*", category=UserWarning)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*", category=UserWarning)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/distilbert-base-nli-stsb-mean-tokens"
DEFAULT_TESSDATA_DIR = Path("models") / "tessdata"
COMMON_TESSERACT_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


SCAM_PROFILE: dict[str, float] = {
    "обналичка": 3.3,
    "обналичить": 2.8,
    "обнал": 2.4,
    "каспи ред обналичка": 4.0,
    "kaspi red": 3.2,
    "каспи ред": 3.2,
    "каспи кредит": 3.0,
    "каспи рассрочка": 2.7,
    "кредит на покупки": 2.5,
    "автокредит без первоначального взноса": 4.0,
    "без первоначального взноса": 3.1,
    "фридом банк обналичка": 3.5,
    "евразийский банк обналичка": 3.5,
    "хоум банк обналичка": 3.4,
    "жусан банк обналичка": 3.4,
    "халык банк обналичка": 3.4,
    "форте банк обналичка": 3.4,
    "пиши номер карты": 4.2,
    "номер карты": 3.2,
    "карта": 1.0,
    "закину": 3.4,
    "закину деньги": 4.0,
    "закину на шоколадку": 3.8,
    "помощь": 1.5,
    "реальная помощь": 3.3,
    "по реальной помощи": 3.0,
    "в комментарии": 2.8,
    "комментарии": 1.5,
    "пиши в комментарии": 3.3,
    "оставь комментарий": 2.7,
    "напиши": 1.5,
    "подписка лайк репост": 2.8,
    "подписка": 1.0,
    "лайк": 0.8,
    "репост": 1.2,
    "деньги": 1.5,
    "кредит": 1.6,
    "долг": 1.4,
    "погашу кредит": 3.4,
    "закрою кредит": 3.2,
    "переведу деньги": 3.1,
    "бесплатно": 1.3,
    "сегодня": 0.8,
}


CLEAN_PROFILE: dict[str, float] = {
    "дизайн": 1.8,
    "товар": 1.5,
    "карточка товара": 2.0,
    "техническое задание": 2.0,
    "инфографика": 1.6,
    "заказчик": 1.5,
    "правки": 1.4,
    "фото товара": 1.4,
    "магазин": 1.0,
    "описание": 0.9,
    "доставка": 0.8,
}


@dataclass(frozen=True)
class OcrResult:
    source_path: Path
    text_path: Path
    text: str
    frame_count: int


@dataclass(frozen=True)
class KeywordHit:
    term: str
    count: int
    weight: float
    contribution: float


@dataclass(frozen=True)
class DetectionResult:
    source_path: Path
    ocr_text_path: Path
    scam_probability: float
    predicted_label: str
    scam_similarity: float
    clean_similarity: float
    keyword_score: float
    frame_count: int
    matched_terms: list[KeywordHit]
    ocr_text: str


def normalize_text(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = text.replace("|", " ").replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def strip_ocr_metadata(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("# source:"):
        while lines and lines[0].startswith("#"):
            lines.pop(0)
        if lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip()


def stable_sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)

    z = math.exp(value)
    return z / (1.0 + z)


def safe_cache_name(path: Path) -> str:
    absolute = path.resolve()
    drive = absolute.drive.replace(":", "").replace("\\", "_")
    parts = [drive, *absolute.parts[1:]]
    safe = "__".join(part.replace(" ", "_") for part in parts)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", safe)
    return f"{safe}.txt"


def collect_media_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]

    if input_path.is_dir():
        return sorted(
            path
            for path in input_path.iterdir()
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
        )

    raise FileNotFoundError(f"Input image/video or directory not found: {input_path}")


def find_tesseract_cmd(explicit_path: Path | None) -> str:
    if explicit_path is not None:
        if explicit_path.exists():
            return str(explicit_path)
        raise FileNotFoundError(f"Tesseract binary not found: {explicit_path}")

    path_cmd = which("tesseract")
    if path_cmd:
        return path_cmd

    for candidate in COMMON_TESSERACT_PATHS:
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError(
        "Tesseract binary was not found. Install Tesseract OCR or pass "
        "--tesseract-cmd C:\\path\\to\\tesseract.exe."
    )


def profile_text(profile: dict[str, float]) -> str:
    pieces: list[str] = []
    for term, weight in profile.items():
        repeats = max(1, round(weight))
        pieces.extend([term] * repeats)
    return " ".join(pieces)


def unique_lines(texts: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []

    for text in texts:
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if len(line) < 2:
                continue
            key = normalize_text(line)
            if key not in seen:
                seen.add(key)
                lines.append(line)

    return lines


def preprocess_for_tesseract(image):
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def crop_frame(frame, crop_top: float, crop_bottom: float, crop_left: float, crop_right: float):
    height, width = frame.shape[:2]
    top = int(height * crop_top)
    bottom = height - int(height * crop_bottom)
    left = int(width * crop_left)
    right = width - int(width * crop_right)
    if top >= bottom or left >= right:
        raise ValueError("Crop percentages remove the whole frame")
    return frame[top:bottom, left:right]


class TesseractOcrEngine:
    def __init__(
        self,
        tesseract_cmd: str,
        lang: str,
        tessdata_dir: Path | None,
        psm_values: list[int],
    ) -> None:
        import pytesseract

        self.pytesseract = pytesseract
        self.pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        self.lang = lang
        self.psm_values = psm_values
        self.tessdata_dir = tessdata_dir.resolve() if tessdata_dir else None

    def read_text(self, frame) -> str:
        import cv2
        from PIL import Image

        variants = [
            cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
            preprocess_for_tesseract(frame),
        ]
        texts: list[str] = []

        for variant in variants:
            image = Image.fromarray(variant)
            for psm in self.psm_values:
                config_parts = [f"--psm {psm}"]
                if self.tessdata_dir is not None:
                    config_parts.append(f"--tessdata-dir {self.tessdata_dir.as_posix()}")
                config = " ".join(config_parts)
                try:
                    texts.append(
                        self.pytesseract.image_to_string(
                            image,
                            lang=self.lang,
                            config=config,
                        )
                    )
                except self.pytesseract.TesseractError as error:
                    raise RuntimeError(
                        f"Tesseract OCR failed with lang={self.lang}. "
                        "Check that the requested traineddata files exist."
                    ) from error

        return "\n".join(unique_lines(texts))


class EasyOcrEngine:
    def __init__(
        self,
        languages: list[str],
        gpu: bool,
        model_storage_directory: Path | None,
        download_enabled: bool,
    ) -> None:
        try:
            import easyocr
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "EasyOCR is installed incompletely. In this environment it needs "
                "torchvision; install torchvision or use --ocr-backend tesseract."
            ) from error

        self.reader = easyocr.Reader(
            languages,
            gpu=gpu,
            model_storage_directory=str(model_storage_directory) if model_storage_directory else None,
            download_enabled=download_enabled,
            verbose=False,
        )

    def read_text(self, frame) -> str:
        results = self.reader.readtext(frame, detail=0, paragraph=False)
        return "\n".join(unique_lines(str(item) for item in results))


class RapidOcrEngine:
    def __init__(self, min_confidence: float, lang: str) -> None:
        if not 0 <= min_confidence <= 1:
            raise ValueError("rapidocr_min_confidence must be between 0 and 1")

        try:
            from rapidocr import EngineType, LangRec, ModelType, OCRVersion, RapidOCR
        except ModuleNotFoundError as error:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ModuleNotFoundError:
                raise RuntimeError(
                    "RapidOCR is not installed. Install it with: "
                    "python -m pip install rapidocr onnxruntime"
                ) from error

            self.engine = RapidOCR()
            self.legacy_output = True
        else:
            lang_value = getattr(LangRec, lang.upper(), lang)
            try:
                self.engine = RapidOCR(
                    params={
                        "Rec.engine_type": EngineType.ONNXRUNTIME,
                        "Rec.lang_type": lang_value,
                        "Rec.model_type": ModelType.MOBILE,
                        "Rec.ocr_version": OCRVersion.PPOCRV5,
                    }
                )
            except ModuleNotFoundError as error:
                raise RuntimeError(
                    "RapidOCR needs ONNX Runtime. Install both with: "
                    "python -m pip install rapidocr onnxruntime"
                ) from error
            self.legacy_output = False

        self.min_confidence = min_confidence

    def read_text(self, frame) -> str:
        result = self.engine(frame)
        if not self.legacy_output and hasattr(result, "txts"):
            texts = [
                str(text)
                for text, score in zip(result.txts or (), result.scores or ())
                if score is None or float(score) >= self.min_confidence
            ]
            return "\n".join(unique_lines(texts))

        detections = result[0] if isinstance(result, tuple) else result
        if not detections:
            return ""

        texts: list[str] = []
        for detection in detections:
            text, confidence = self._parse_detection(detection)
            if not text:
                continue
            if confidence is not None and confidence < self.min_confidence:
                continue
            texts.append(text)

        return "\n".join(unique_lines(texts))

    @staticmethod
    def _parse_detection(detection) -> tuple[str, float | None]:
        if isinstance(detection, dict):
            text = detection.get("text") or detection.get("txt") or ""
            confidence = detection.get("score")
            return str(text), float(confidence) if confidence is not None else None

        if hasattr(detection, "text"):
            text = getattr(detection, "text")
            confidence = getattr(detection, "score", None)
            return str(text), float(confidence) if confidence is not None else None

        if isinstance(detection, (list, tuple)) and len(detection) >= 2:
            confidence = detection[2] if len(detection) >= 3 else None
            return str(detection[1]), float(confidence) if confidence is not None else None

        return str(detection), None


class MediaOcrExtractor:
    def __init__(
        self,
        engine,
        output_dir: Path,
        force: bool,
        frame_interval: float,
        max_frames: int,
        crop_top: float,
        crop_bottom: float,
        crop_left: float,
        crop_right: float,
    ) -> None:
        if frame_interval <= 0:
            raise ValueError("frame_interval must be greater than 0")
        if max_frames <= 0:
            raise ValueError("max_frames must be greater than 0")

        self.engine = engine
        self.output_dir = output_dir
        self.force = force
        self.frame_interval = frame_interval
        self.max_frames = max_frames
        self.crop_top = crop_top
        self.crop_bottom = crop_bottom
        self.crop_left = crop_left
        self.crop_right = crop_right

    def extract(self, source_path: Path) -> OcrResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        text_path = self.output_dir / safe_cache_name(source_path)

        if text_path.exists() and not self.force:
            text = strip_ocr_metadata(text_path.read_text(encoding="utf-8"))
            frame_count = self._read_cached_frame_count(text_path)
            return OcrResult(
                source_path=source_path,
                text_path=text_path,
                text=text,
                frame_count=frame_count,
            )

        suffix = source_path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            frame_texts, frame_count = self._extract_image(source_path), 1
        elif suffix in VIDEO_EXTENSIONS:
            frame_texts, frame_count = self._extract_video(source_path)
        else:
            raise ValueError(f"Unsupported file extension: {source_path.suffix}")

        lines = unique_lines(frame_texts)
        text = "\n".join(lines).strip()
        header = (
            f"# source: {source_path.resolve()}\n"
            f"# frames_ocrd: {frame_count}\n\n"
        )
        text_path.write_text(header + text + "\n", encoding="utf-8")

        return OcrResult(
            source_path=source_path,
            text_path=text_path,
            text=text,
            frame_count=frame_count,
        )

    def _read_cached_frame_count(self, text_path: Path) -> int:
        for line in text_path.read_text(encoding="utf-8").splitlines()[:5]:
            if line.startswith("# frames_ocrd:"):
                try:
                    return int(line.split(":", 1)[1].strip())
                except ValueError:
                    return 0
        return 0

    def _crop(self, frame):
        return crop_frame(
            frame,
            crop_top=self.crop_top,
            crop_bottom=self.crop_bottom,
            crop_left=self.crop_left,
            crop_right=self.crop_right,
        )

    def _extract_image(self, image_path: Path) -> list[str]:
        import cv2

        frame = cv2.imread(str(image_path))
        if frame is None:
            raise ValueError(f"Could not read image: {image_path}")

        frame = self._crop(frame)
        print(f"OCR image: {image_path}")
        return [self.engine.read_text(frame)]

    def _extract_video(self, video_path: Path) -> tuple[list[str], int]:
        import cv2

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        frame_total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_total / fps if frame_total else 0.0

        if duration > 0:
            timestamps = [
                min(duration, 0.25 + index * self.frame_interval)
                for index in range(self.max_frames)
                if 0.25 + index * self.frame_interval <= duration
            ]
        else:
            timestamps = [index * self.frame_interval for index in range(self.max_frames)]

        if not timestamps:
            timestamps = [0.0]

        print(f"OCR video: {video_path} ({len(timestamps)} sampled frame(s))")
        texts: list[str] = []
        frames_read = 0

        for timestamp in timestamps[: self.max_frames]:
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            frames_read += 1
            texts.append(self.engine.read_text(self._crop(frame)))

        capture.release()
        return texts, frames_read


class VisualScamEmbeddingDetector:
    def __init__(
        self,
        backend: str,
        embedding_model: str,
        local_files_only: bool,
        device: str | None,
        threshold: float,
        temperature: float,
        keyword_weight: float,
    ) -> None:
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        if temperature <= 0:
            raise ValueError("temperature must be greater than 0")
        if keyword_weight < 0:
            raise ValueError("keyword_weight cannot be negative")

        if local_files_only:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")

        self.backend = backend
        self.embedding_model = embedding_model
        self.local_files_only = local_files_only
        self.device = device
        self.threshold = threshold
        self.temperature = temperature
        self.keyword_weight = keyword_weight
        self.sentence_model = None

        if backend in {"sentence-transformers", "hybrid"}:
            from sentence_transformers import SentenceTransformer

            print(f"Loading embedding model: {embedding_model}")
            self.sentence_model = SentenceTransformer(
                embedding_model,
                device=device,
                local_files_only=local_files_only,
            )

        self.scam_profile_text = normalize_text(profile_text(SCAM_PROFILE))
        self.clean_profile_text = normalize_text(profile_text(CLEAN_PROFILE))

    def classify(self, ocr: OcrResult) -> DetectionResult:
        text = normalize_text(ocr.text)
        if not text:
            return DetectionResult(
                source_path=ocr.source_path,
                ocr_text_path=ocr.text_path,
                scam_probability=0.0,
                predicted_label="not_scam",
                scam_similarity=0.0,
                clean_similarity=0.0,
                keyword_score=0.0,
                frame_count=ocr.frame_count,
                matched_terms=[],
                ocr_text=ocr.text,
            )

        scam_similarity, clean_similarity = self._similarities(text)
        matched_terms = self._keyword_hits(text)
        keyword_score = sum(hit.contribution for hit in matched_terms)
        normalized_keyword_score = keyword_score / math.sqrt(max(1, len(text.split())))

        gap = scam_similarity - clean_similarity
        raw_score = gap + (self.keyword_weight * normalized_keyword_score)
        if not matched_terms:
            raw_score -= 0.08
        probability = stable_sigmoid((raw_score - 0.02) / self.temperature)
        predicted_label = "scam" if probability >= self.threshold else "not_scam"

        return DetectionResult(
            source_path=ocr.source_path,
            ocr_text_path=ocr.text_path,
            scam_probability=probability,
            predicted_label=predicted_label,
            scam_similarity=scam_similarity,
            clean_similarity=clean_similarity,
            keyword_score=keyword_score,
            frame_count=ocr.frame_count,
            matched_terms=matched_terms,
            ocr_text=ocr.text,
        )

    def _similarities(self, text: str) -> tuple[float, float]:
        if self.backend == "tfidf":
            return self._tfidf_similarities(text)
        if self.backend == "sentence-transformers":
            return self._sentence_similarities(text)
        if self.backend == "hybrid":
            tfidf_scam, tfidf_clean = self._tfidf_similarities(text)
            sent_scam, sent_clean = self._sentence_similarities(text)
            return (
                (0.75 * tfidf_scam) + (0.25 * sent_scam),
                (0.75 * tfidf_clean) + (0.25 * sent_clean),
            )
        raise ValueError(f"Unsupported embedding backend: {self.backend}")

    def _tfidf_similarities(self, text: str) -> tuple[float, float]:
        from sklearn.feature_extraction.text import TfidfVectorizer

        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            lowercase=True,
            norm="l2",
            sublinear_tf=True,
        )
        matrix = vectorizer.fit_transform(
            [text, self.scam_profile_text, self.clean_profile_text]
        )
        scam_similarity = float((matrix[0] @ matrix[1].T).toarray()[0, 0])
        clean_similarity = float((matrix[0] @ matrix[2].T).toarray()[0, 0])
        return scam_similarity, clean_similarity

    def _sentence_similarities(self, text: str) -> tuple[float, float]:
        if self.sentence_model is None:
            raise RuntimeError("SentenceTransformers model is not loaded")

        embeddings = self.sentence_model.encode(
            [text, self.scam_profile_text, self.clean_profile_text],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        scam_similarity = float(embeddings[0] @ embeddings[1])
        clean_similarity = float(embeddings[0] @ embeddings[2])
        return scam_similarity, clean_similarity

    def _keyword_hits(self, text: str) -> list[KeywordHit]:
        hits: list[KeywordHit] = []
        for term, weight in SCAM_PROFILE.items():
            normalized_term = normalize_text(term)
            pattern = rf"(?<!\w){re.escape(normalized_term)}(?!\w)"
            count = len(re.findall(pattern, text))
            if count:
                contribution = weight * (1.0 + math.log(count))
                hits.append(
                    KeywordHit(
                        term=term,
                        count=count,
                        weight=weight,
                        contribution=contribution,
                    )
                )

        return sorted(hits, key=lambda hit: hit.contribution, reverse=True)


def make_ocr_engine(args: argparse.Namespace):
    backend = args.ocr_backend

    if backend == "auto":
        if (
            importlib.util.find_spec("rapidocr") is not None
            or importlib.util.find_spec("rapidocr_onnxruntime") is not None
        ):
            backend = "rapidocr"
            tesseract_cmd = ""
        else:
            try:
                tesseract_cmd = find_tesseract_cmd(args.tesseract_cmd)
                backend = "tesseract"
            except FileNotFoundError:
                backend = "easyocr"
                tesseract_cmd = ""
    else:
        tesseract_cmd = ""

    if backend == "rapidocr":
        return RapidOcrEngine(
            min_confidence=args.rapidocr_min_confidence,
            lang=args.rapidocr_lang,
        )

    if backend == "tesseract":
        if not tesseract_cmd:
            tesseract_cmd = find_tesseract_cmd(args.tesseract_cmd)
        tessdata_dir = args.tessdata_dir if args.tessdata_dir.exists() else None
        return TesseractOcrEngine(
            tesseract_cmd=tesseract_cmd,
            lang=args.ocr_lang,
            tessdata_dir=tessdata_dir,
            psm_values=args.psm,
        )

    if backend == "easyocr":
        return EasyOcrEngine(
            languages=args.easyocr_lang,
            gpu=args.device == "cuda",
            model_storage_directory=args.easyocr_model_dir,
            download_enabled=args.allow_ocr_downloads,
        )

    raise ValueError(f"Unsupported OCR backend: {args.ocr_backend}")


def result_to_dict(result: DetectionResult, include_text: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "source": str(result.source_path),
        "ocr_text_path": str(result.ocr_text_path),
        "scam_probability": result.scam_probability,
        "predicted_label": result.predicted_label,
        "scam_similarity": result.scam_similarity,
        "clean_similarity": result.clean_similarity,
        "keyword_score": result.keyword_score,
        "frames_ocrd": result.frame_count,
        "matched_terms": [
            {
                "term": hit.term,
                "count": hit.count,
                "weight": hit.weight,
                "contribution": hit.contribution,
            }
            for hit in result.matched_terms
        ],
    }
    if include_text:
        payload["ocr_text"] = result.ocr_text
    return payload


def print_table(results: list[DetectionResult], top_terms: int) -> None:
    print()
    print(
        f"{'source':<28} {'p_scam':>8} {'label':<9} "
        f"{'scam':>7} {'clean':>7} {'kw':>7} {'frames':>6} matched_terms"
    )
    print("-" * 120)

    for result in results:
        terms = ", ".join(
            f"{hit.term}({hit.count})"
            for hit in result.matched_terms[:top_terms]
        )
        print(
            f"{result.source_path.name:<28} "
            f"{result.scam_probability:>7.1%} "
            f"{result.predicted_label:<9} "
            f"{result.scam_similarity:>7.3f} "
            f"{result.clean_similarity:>7.3f} "
            f"{result.keyword_score:>7.2f} "
            f"{result.frame_count:>6} "
            f"{terms}"
        )


def parse_percent(value: str) -> float:
    number = float(value)
    if number < 0 or number >= 1:
        raise argparse.ArgumentTypeError("crop percentages must be >= 0 and < 1")
    return number


def parse_psm(value: str) -> list[int]:
    result = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not result:
        raise argparse.ArgumentTypeError("At least one PSM value is required")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect scam-like visual text in images or videos. The script OCRs "
            "frames, converts the full OCR text into embeddings, and compares it "
            "with a Russian scam text profile."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("videos"),
        help="Image file, video file, or directory. Default: videos",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output") / "scam_image_detector",
        help="Directory for cached OCR text. Default: output/scam_image_detector",
    )
    parser.add_argument(
        "--ocr-backend",
        choices=["auto", "rapidocr", "tesseract", "easyocr"],
        default="auto",
        help=(
            "OCR backend. Default: auto. RapidOCR installs with: "
            "python -m pip install rapidocr onnxruntime"
        ),
    )
    parser.add_argument(
        "--rapidocr-lang",
        default="cyrillic",
        help="RapidOCR recognition language. Default: cyrillic",
    )
    parser.add_argument(
        "--rapidocr-min-confidence",
        type=float,
        default=0.45,
        help="Minimum RapidOCR confidence to keep a text line. Default: 0.45",
    )
    parser.add_argument(
        "--tesseract-cmd",
        type=Path,
        default=None,
        help="Path to tesseract.exe if it is not in PATH.",
    )
    parser.add_argument(
        "--tessdata-dir",
        type=Path,
        default=DEFAULT_TESSDATA_DIR,
        help="Directory with Tesseract traineddata files. Default: models/tessdata",
    )
    parser.add_argument(
        "--ocr-lang",
        default="rus",
        help="Tesseract OCR language. Default: rus",
    )
    parser.add_argument(
        "--psm",
        type=parse_psm,
        default=[6, 11],
        help="Comma-separated Tesseract page segmentation modes. Default: 6,11",
    )
    parser.add_argument(
        "--easyocr-lang",
        nargs="+",
        default=["ru", "en"],
        help="EasyOCR languages. Default: ru en",
    )
    parser.add_argument(
        "--easyocr-model-dir",
        type=Path,
        default=None,
        help="Optional EasyOCR model directory.",
    )
    parser.add_argument(
        "--allow-ocr-downloads",
        action="store_true",
        help="Allow EasyOCR to download OCR models if missing.",
    )
    parser.add_argument(
        "--embedding-backend",
        choices=["tfidf", "sentence-transformers", "hybrid"],
        default="tfidf",
        help="Embedding backend for comparing OCR text to scam profile. Default: tfidf",
    )
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help="SentenceTransformers model for sentence-transformers/hybrid backend.",
    )
    parser.add_argument(
        "--allow-model-downloads",
        action="store_true",
        help="Allow Hugging Face model downloads for sentence-transformers backend.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda"],
        help="Device for EasyOCR and sentence-transformers. Default: cpu",
    )
    parser.add_argument(
        "--frame-interval",
        type=float,
        default=1.5,
        help="Seconds between sampled video frames. Default: 1.5",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=12,
        help="Maximum sampled frames per video. Default: 12",
    )
    parser.add_argument(
        "--crop-top",
        type=parse_percent,
        default=0.0,
        help="Crop this fraction from top before OCR. Default: 0",
    )
    parser.add_argument(
        "--crop-bottom",
        type=parse_percent,
        default=0.0,
        help="Crop this fraction from bottom before OCR. Default: 0",
    )
    parser.add_argument(
        "--crop-left",
        type=parse_percent,
        default=0.0,
        help="Crop this fraction from left before OCR. Default: 0",
    )
    parser.add_argument(
        "--crop-right",
        type=parse_percent,
        default=0.0,
        help="Crop this fraction from right before OCR. Default: 0",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Probability threshold for scam label. Default: 0.5",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.09,
        help="Temperature for converting similarity score to probability. Default: 0.09",
    )
    parser.add_argument(
        "--keyword-weight",
        type=float,
        default=0.04,
        help="Extra weight for exact scam phrase hits. Default: 0.04",
    )
    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="Ignore cached OCR text and OCR again.",
    )
    parser.add_argument(
        "--top-terms",
        type=int,
        default=8,
        help="Number of matched terms to show in table output. Default: 8",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table.",
    )
    parser.add_argument(
        "--include-ocr-text",
        action="store_true",
        help="Include full OCR text in JSON output.",
    )
    parser.add_argument(
        "--text",
        default=None,
        help="Classify this raw text directly instead of running OCR. Useful for debugging.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    local_model_files_only = not args.allow_model_downloads

    detector = VisualScamEmbeddingDetector(
        backend=args.embedding_backend,
        embedding_model=args.embedding_model,
        local_files_only=local_model_files_only,
        device=args.device,
        threshold=args.threshold,
        temperature=args.temperature,
        keyword_weight=args.keyword_weight,
    )

    if args.text is not None:
        text_path = args.output_dir / "raw_text_input.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(args.text, encoding="utf-8")
        ocr_results = [
            OcrResult(
                source_path=Path("<text>"),
                text_path=text_path,
                text=args.text,
                frame_count=0,
            )
        ]
    else:
        engine = make_ocr_engine(args)
        extractor = MediaOcrExtractor(
            engine=engine,
            output_dir=args.output_dir / "ocr",
            force=args.force_ocr,
            frame_interval=args.frame_interval,
            max_frames=args.max_frames,
            crop_top=args.crop_top,
            crop_bottom=args.crop_bottom,
            crop_left=args.crop_left,
            crop_right=args.crop_right,
        )
        ocr_results = [
            extractor.extract(path.resolve())
            for path in collect_media_files(args.input)
        ]

    results = [detector.classify(ocr) for ocr in ocr_results]

    if args.json:
        print(
            json.dumps(
                [
                    result_to_dict(result, include_text=args.include_ocr_text)
                    for result in results
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print_table(results, top_terms=args.top_terms)
        print()
        if args.text is None:
            print(f"Cached OCR text: {(args.output_dir / 'ocr').resolve()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
