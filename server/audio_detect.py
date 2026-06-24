from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path


os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
warnings.filterwarnings("ignore", message="A NumPy version .*", category=UserWarning)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*", category=UserWarning)


DEFAULT_WHISPER_MODEL = "base"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


FINANCE_TERMS: dict[str, float] = {
    "деньги": 1.0,
    "кредит": 1.4,
    "кредиты": 1.4,
    "долг": 1.2,
    "долги": 1.2,
    "заработок": 1.0,
    "заработать": 1.0,
    "заработал": 0.7,
    "доход": 1.2,
    "пассивный доход": 1.5,
    "быстрые деньги": 1.8,
    "легкие деньги": 1.8,
    "деньги из воздуха": 1.7,
    "схема": 1.2,
    "секретная схема": 1.8,
    "рабочая схема": 1.5,
    "банк": 0.4,
    "карта": 0.3,
    "кредитная карта": 0.8,
    "проценты": 0.5,
}


CALL_TO_ACTION_TERMS: dict[str, float] = {
    "напиши": 1.2,
    "написать": 1.0,
    "комментариях": 1.2,
    "пиши в комментарии": 2.1,
    "написать комментариях": 2.2,
    "напиши в комментариях": 2.2,
    "оставь комментарий": 1.8,
    "пиши слово": 1.9,
    "напиши сумму": 2.4,
    "сумму в комментариях": 2.2,
    "личные сообщения": 1.5,
    "напиши мне": 1.5,
    "пиши в директ": 1.8,
    "актуал": 0.4,
    "в актуале": 0.6,
    "подробнее в актуале": 0.8,
    "ссылка в профиле": 1.4,
}


PROMISE_TERMS: dict[str, float] = {
    "выберу": 1.4,
    "выберу следующих": 2.2,
    "закину": 2.2,
    "закину деньги": 2.7,
    "закину эти деньги": 2.8,
    "переведу деньги": 2.3,
    "получи деньги": 2.2,
    "раздам деньги": 2.5,
    "розыгрыш денег": 2.4,
    "погасить кредит": 1.8,
    "закрыть кредит": 2.2,
    "погашу кредит": 2.8,
    "погасит твой кредит": 2.8,
    "погасили свои кредиты": 3.0,
    "кредит будет погашен": 3.0,
    "будет погашен": 2.6,
    "сегодня": 0.8,
    "уже сегодня": 1.6,
    "прямо сейчас": 1.3,
    "без вложений": 2.4,
    "без опыта": 1.6,
    "гарантированно": 2.0,
    "гарантия": 1.5,
    "бесплатно": 1.2,
    "тебе нужны деньги": 2.1,
    "нужны деньги": 1.6,
}


NEGATIVE_TERMS: dict[str, float] = {
    "дизайн": 1.5,
    "карточки товара": 1.8,
    "товар": 1.2,
    "заказчик": 1.3,
    "техническое задание": 1.7,
    "правки": 1.3,
    "инфографика": 1.4,
    "материалы": 0.8,
    "конкурентов": 0.8,
    "фото товаров": 1.4,
    "создаем заказ": 1.2,
}


@dataclass(frozen=True)
class Transcript:
    video_path: Path
    text_path: Path
    text: str


@dataclass(frozen=True)
class KeywordHit:
    term: str
    count: int
    weight: float
    contribution: float


@dataclass(frozen=True)
class DetectionResult:
    video_path: Path
    transcript_path: Path
    scam_probability: float
    predicted_label: str
    scam_similarity: float
    finance_score: float
    cta_score: float
    promise_score: float
    positive_score: float
    negative_score: float
    matched_terms: list[KeywordHit]


def normalize_text(text: str) -> str:
    text = text.lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text).strip()


def strip_transcript_metadata(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("# source:"):
        while lines and lines[0].startswith("#"):
            lines.pop(0)
        if lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip()


def safe_cache_name(path: Path) -> str:
    absolute = path.resolve()
    drive = absolute.drive.replace(":", "").replace("\\", "_")
    parts = [drive, *absolute.parts[1:]]
    safe = "__".join(part.replace(" ", "_") for part in parts)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", safe)
    return f"{safe}.txt"


def collect_video_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]

    if input_path.is_dir():
        return sorted(
            path
            for path in input_path.iterdir()
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        )

    raise FileNotFoundError(f"Input video or directory not found: {input_path}")


def stable_sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)

    z = math.exp(value)
    return z / (1.0 + z)


class WhisperTranscriber:
    def __init__(
        self,
        model_name: str,
        language: str | None,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> None:
        self.model_name = model_name
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.local_files_only = local_files_only
        self._model = None

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            print(
                f"Loading Whisper model: {self.model_name} "
                f"(device={self.device}, compute_type={self.compute_type})"
            )
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
                local_files_only=self.local_files_only,
            )

        return self._model

    def transcribe(
        self,
        video_path: Path,
        transcripts_dir: Path,
        force: bool,
    ) -> Transcript:
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        text_path = transcripts_dir / safe_cache_name(video_path)

        if text_path.exists() and not force:
            text = strip_transcript_metadata(text_path.read_text(encoding="utf-8"))
            return Transcript(video_path=video_path, text_path=text_path, text=text)

        model = self._load_model()
        print(f"Transcribing: {video_path}")

        segments, info = model.transcribe(
            str(video_path),
            language=self.language,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=True,
        )

        lines = [segment.text.strip() for segment in segments if segment.text.strip()]
        text = "\n".join(lines).strip()
        if not text:
            raise ValueError(f"No speech text was recognized in: {video_path}")

        header = (
            f"# source: {video_path.resolve()}\n"
            f"# whisper_model: {self.model_name}\n"
            f"# language: {info.language}\n"
            f"# language_probability: {info.language_probability:.6f}\n\n"
        )
        text_path.write_text(header + text + "\n", encoding="utf-8")

        return Transcript(video_path=video_path, text_path=text_path, text=text)


class RussianScamKeywordDetector:
    def __init__(
        self,
        finance_terms: dict[str, float],
        call_to_action_terms: dict[str, float],
        promise_terms: dict[str, float],
        negative_terms: dict[str, float],
        threshold: float,
        temperature: float,
    ) -> None:
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        if temperature <= 0:
            raise ValueError("temperature must be greater than 0")

        self.finance_terms = {
            normalize_text(term): weight
            for term, weight in finance_terms.items()
        }
        self.call_to_action_terms = {
            normalize_text(term): weight
            for term, weight in call_to_action_terms.items()
        }
        self.promise_terms = {
            normalize_text(term): weight
            for term, weight in promise_terms.items()
        }
        self.negative_terms = {
            normalize_text(term): weight
            for term, weight in negative_terms.items()
        }
        self.threshold = threshold
        self.temperature = temperature

    def _term_hits(self, text: str, terms: dict[str, float]) -> list[KeywordHit]:
        hits: list[KeywordHit] = []

        for term, weight in terms.items():
            pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
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

    def _tfidf_similarity(self, text: str) -> float:
        from sklearn.feature_extraction.text import TfidfVectorizer

        profile_terms = {
            **self.finance_terms,
            **self.call_to_action_terms,
            **self.promise_terms,
        }
        scam_profile = " ".join(
            f"{term} " * max(1, round(weight))
            for term, weight in profile_terms.items()
        )
        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            lowercase=True,
            norm="l2",
            sublinear_tf=True,
        )
        matrix = vectorizer.fit_transform([text, scam_profile])
        return float((matrix[0] @ matrix[1].T).toarray()[0, 0])

    def classify(self, transcript: Transcript) -> DetectionResult:
        text = normalize_text(transcript.text)
        if not text:
            raise ValueError(f"Transcript is empty: {transcript.video_path}")

        finance_hits = self._term_hits(text, self.finance_terms)
        call_to_action_hits = self._term_hits(text, self.call_to_action_terms)
        promise_hits = self._term_hits(text, self.promise_terms)
        negative_hits = self._term_hits(text, self.negative_terms)

        word_count = max(1, len(text.split()))
        word_scale = math.sqrt(word_count)

        finance_score = sum(hit.contribution for hit in finance_hits)
        call_to_action_score = sum(hit.contribution for hit in call_to_action_hits)
        promise_score = sum(hit.contribution for hit in promise_hits)
        positive_score = finance_score + call_to_action_score + promise_score
        negative_score = sum(hit.contribution for hit in negative_hits)

        finance_norm = finance_score / word_scale
        call_to_action_norm = call_to_action_score / word_scale
        promise_norm = promise_score / word_scale
        negative_norm = negative_score / word_scale
        scam_similarity = self._tfidf_similarity(text)

        # Scam examples usually combine money/debt language with a CTA or a
        # promise. Generic financial talk alone should not be enough.
        cta_promise_synergy = math.sqrt(call_to_action_norm * promise_norm)
        raw_score = (
            (0.45 * finance_norm)
            + (1.35 * call_to_action_norm)
            + (1.55 * promise_norm)
            + (2.20 * cta_promise_synergy)
            + (2.00 * scam_similarity)
            - (0.90 * negative_norm)
        )
        if not call_to_action_hits and not promise_hits:
            raw_score -= 0.8

        scam_probability = stable_sigmoid((raw_score - 1.1) / self.temperature)
        predicted_label = "scam" if scam_probability >= self.threshold else "not_scam"
        matched_terms = sorted(
            [*promise_hits, *call_to_action_hits, *finance_hits],
            key=lambda hit: hit.contribution,
            reverse=True,
        )

        return DetectionResult(
            video_path=transcript.video_path,
            transcript_path=transcript.text_path,
            scam_probability=scam_probability,
            predicted_label=predicted_label,
            scam_similarity=scam_similarity,
            finance_score=finance_score,
            cta_score=call_to_action_score,
            promise_score=promise_score,
            positive_score=positive_score,
            negative_score=negative_score,
            matched_terms=matched_terms,
        )


def result_to_dict(result: DetectionResult) -> dict[str, object]:
    return {
        "video": str(result.video_path),
        "transcript": str(result.transcript_path),
        "scam_probability": result.scam_probability,
        "predicted_label": result.predicted_label,
        "scam_similarity": result.scam_similarity,
        "finance_score": result.finance_score,
        "cta_score": result.cta_score,
        "promise_score": result.promise_score,
        "positive_score": result.positive_score,
        "negative_score": result.negative_score,
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


def print_table(results: list[DetectionResult], top_terms: int) -> None:
    print()
    print(
        f"{'video':<28} {'p_scam':>8} {'label':<9} "
        f"{'sim':>7} {'fin':>7} {'cta':>7} {'prom':>7} {'neg':>7} matched_terms"
    )
    print("-" * 110)

    for result in results:
        # terms = ", ".join(
        #     f"{hit.term}({hit.count})"
        #     for hit in result.matched_terms[:top_terms]
        # )
        terms = ""
        print(
            f"{result.video_path.name:<28} "
            f"{result.scam_probability:>7.1%} "
            f"{result.predicted_label:<9} "
            f"{result.scam_similarity:>7.3f} "
            f"{result.finance_score:>7.2f} "
            f"{result.cta_score:>7.2f} "
            f"{result.promise_score:>7.2f} "
            f"{result.negative_score:>7.2f} "
            f"{terms}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Transcribe video audio and estimate scam probability by comparing "
            "the full Russian transcript with a built-in scam vocabulary. "
            "This version does not compare videos with videos and does not split "
            "transcripts into chunks."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("videos"),
        help="Video file or directory with videos to classify. Default: videos",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output") / "scam_detector_v2",
        help="Directory for cached transcripts. Default: output/scam_detector_v2",
    )
    parser.add_argument(
        "--whisper-model",
        default=DEFAULT_WHISPER_MODEL,
        help="faster-whisper model name or local path. Default: base",
    )
    parser.add_argument(
        "--language",
        default="ru",
        help="Whisper language code. Default: ru",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda"],
        help="Device for Whisper. Default: cpu",
    )
    parser.add_argument(
        "--compute-type",
        default=None,
        help="Whisper compute type. Default: int8 on CPU, float16 on CUDA.",
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
        default=0.6,
        help="Temperature for converting score into probability. Default: 0.6",
    )
    parser.add_argument(
        "--force-transcribe",
        action="store_true",
        help="Ignore cached transcripts and transcribe videos again.",
    )
    parser.add_argument(
        "--allow-model-downloads",
        action="store_true",
        help=(
            "Allow Hugging Face model downloads. By default Whisper is loaded "
            "from the local cache only."
        ),
    )
    parser.add_argument(
        "--top-terms",
        type=int,
        default=6,
        help="Number of matched terms to show in table output. Default: 6",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    compute_type = args.compute_type or ("float16" if args.device == "cuda" else "int8")
    local_files_only = not args.allow_model_downloads

    if local_files_only:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

    videos = [path.resolve() for path in collect_video_files(args.input)]
    transcripts_dir = args.output_dir / "transcripts"

    transcriber = WhisperTranscriber(
        model_name=args.whisper_model,
        language=args.language,
        device=args.device,
        compute_type=compute_type,
        local_files_only=local_files_only,
    )
    detector = RussianScamKeywordDetector(
        finance_terms=FINANCE_TERMS,
        call_to_action_terms=CALL_TO_ACTION_TERMS,
        promise_terms=PROMISE_TERMS,
        negative_terms=NEGATIVE_TERMS,
        threshold=args.threshold,
        temperature=args.temperature,
    )

    results: list[DetectionResult] = []
    for video_path in videos:
        transcript = transcriber.transcribe(
            video_path=video_path,
            transcripts_dir=transcripts_dir,
            force=args.force_transcribe,
        )
        results.append(detector.classify(transcript))

    if args.json:
        print(json.dumps([result_to_dict(result) for result in results], ensure_ascii=False, indent=2))
    else:
        print_table(results, top_terms=args.top_terms)
        print()
        print(f"Cached transcripts: {transcripts_dir.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
