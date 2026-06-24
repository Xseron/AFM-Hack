from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path


os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
warnings.filterwarnings("ignore", message="A NumPy version .*", category=UserWarning)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
DEFAULT_CLIP_MODEL = "openai/clip-vit-base-patch32"


CASINO_PROMPTS = [
    "a screenshot of an online casino website",
    "a mobile online casino app interface",
    "a slot machine gambling game screen with a spin button",
    "an online gambling website with roulette, slots, jackpot or bonus",
    "a casino advertisement with deposit bonus and gambling games",
    "a betting or casino platform screen",
    "a roulette or blackjack online gambling interface",
    "a colorful slot game with coins, balance and win amount",
]


NON_CASINO_PROMPTS = [
    "a normal social media post without gambling",
    "a banking or finance advertisement without casino gambling",
    "a shopping website or product advertisement",
    "a person outdoors in a normal video",
    "a regular mobile phone screenshot",
    "a text poster or informational graphic without gambling",
    "a normal video game unrelated to casino gambling",
    "a business advertisement without casino games",
]


@dataclass(frozen=True)
class FramePrediction:
    frame_index: int | None
    timestamp_seconds: float | None
    casino_probability: float
    top_prompt: str
    top_prompt_probability: float


@dataclass(frozen=True)
class DetectionResult:
    source_path: Path
    media_type: str
    casino_probability: float
    predicted_label: str
    analyzed_frames: int
    frame_predictions: list[FramePrediction]


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


def source_seed(path: Path, seed: int) -> int:
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).digest()
    path_seed = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return path_seed ^ seed


def load_image(path: Path):
    from PIL import Image

    with Image.open(path) as image:
        return image.convert("RGB")


def sample_video_frames(
    path: Path,
    frame_count: int,
    seed: int,
) -> list[tuple[object, int, float]]:
    import cv2
    from PIL import Image

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {path}")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)

    if total_frames <= 0:
        raise ValueError(f"Could not read frame count from video: {path}")

    rng = random.Random(source_seed(path, seed))
    sample_count = min(frame_count, total_frames)
    frame_indices = sorted(rng.sample(range(total_frames), sample_count))
    frames: list[tuple[object, int, float]] = []

    for frame_index in frame_indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok or frame is None:
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb).convert("RGB")
        timestamp = frame_index / fps if fps > 0 else 0.0
        frames.append((image, frame_index, timestamp))

    capture.release()

    if not frames:
        raise ValueError(f"Could not read sampled frames from video: {path}")

    return frames


class ClipCasinoDetector:
    def __init__(
        self,
        model_name: str,
        device: str,
        local_files_only: bool,
        threshold: float,
        aggregation: str,
    ) -> None:
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")

        if local_files_only:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")

        import torch
        from transformers import CLIPModel, CLIPProcessor

        self.torch = torch
        self.device = device
        self.threshold = threshold
        self.aggregation = aggregation
        self.prompts = [*CASINO_PROMPTS, *NON_CASINO_PROMPTS]
        self.casino_prompt_count = len(CASINO_PROMPTS)

        print(f"Loading CLIP model: {model_name}")
        self.model = CLIPModel.from_pretrained(
            model_name,
            local_files_only=local_files_only,
        ).to(device)
        self.processor = CLIPProcessor.from_pretrained(
            model_name,
            local_files_only=local_files_only,
            backend="pil",
        )
        self.model.eval()

        with self.torch.no_grad():
            text_inputs = self.processor(
                text=self.prompts,
                return_tensors="pt",
                padding=True,
                truncation=True,
            ).to(device)
        
            text_outputs = self.model.text_model(
                input_ids=text_inputs["input_ids"],
                attention_mask=text_inputs.get("attention_mask"),
            )
        
            text_features = self.model.text_projection(
                text_outputs.pooler_output
            )
        
            self.text_features = text_features / text_features.norm(
                dim=-1,
                keepdim=True,
            )
        
            self.logit_scale = self.model.logit_scale.exp()

    def predict_image(
        self,
        image,
        frame_index: int | None = None,
        timestamp_seconds: float | None = None,
    ) -> FramePrediction:
        with self.torch.no_grad():
            image_inputs = self.processor(
                images=image,
                return_tensors="pt",
            ).to(self.device)
            vision_outputs = self.model.vision_model(
                pixel_values=image_inputs["pixel_values"],
            )
            
            image_features = self.model.visual_projection(
                vision_outputs.pooler_output
            )

            image_features = image_features / image_features.norm(
                dim=-1,
                keepdim=True,
            )
            logits = self.logit_scale * (image_features @ self.text_features.T)
            probabilities = logits.softmax(dim=-1)[0]

        casino_probability = float(probabilities[: self.casino_prompt_count].sum().item())
        top_index = int(probabilities.argmax().item())

        return FramePrediction(
            frame_index=frame_index,
            timestamp_seconds=timestamp_seconds,
            casino_probability=casino_probability,
            top_prompt=self.prompts[top_index],
            top_prompt_probability=float(probabilities[top_index].item()),
        )

    def classify_predictions(
        self,
        path: Path,
        media_type: str,
        frame_predictions: list[FramePrediction],
    ) -> DetectionResult:
        probabilities = [prediction.casino_probability for prediction in frame_predictions]
        if self.aggregation == "max":
            casino_probability = max(probabilities)
        elif self.aggregation == "mean":
            casino_probability = sum(probabilities) / len(probabilities)
        else:
            raise ValueError(f"Unsupported aggregation: {self.aggregation}")

        predicted_label = "online_casino" if casino_probability >= self.threshold else "not_casino"

        return DetectionResult(
            source_path=path,
            media_type=media_type,
            casino_probability=casino_probability,
            predicted_label=predicted_label,
            analyzed_frames=len(frame_predictions),
            frame_predictions=frame_predictions,
        )


def classify_file(
    detector: ClipCasinoDetector,
    path: Path,
    video_frames: int,
    seed: int,
) -> DetectionResult:
    suffix = path.suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        image = load_image(path)
        prediction = detector.predict_image(image)
        return detector.classify_predictions(
            path=path,
            media_type="image",
            frame_predictions=[prediction],
        )

    if suffix in VIDEO_EXTENSIONS:
        sampled_frames = sample_video_frames(
            path=path,
            frame_count=video_frames,
            seed=seed,
        )
        predictions = [
            detector.predict_image(
                image,
                frame_index=frame_index,
                timestamp_seconds=timestamp_seconds,
            )
            for image, frame_index, timestamp_seconds in sampled_frames
        ]
        return detector.classify_predictions(
            path=path,
            media_type="video",
            frame_predictions=predictions,
        )

    raise ValueError(f"Unsupported file extension: {path.suffix}")


def result_to_dict(result: DetectionResult) -> dict[str, object]:
    return {
        "source": str(result.source_path),
        "media_type": result.media_type,
        "casino_probability": result.casino_probability,
        "predicted_label": result.predicted_label,
        "analyzed_frames": result.analyzed_frames,
        "frames": [
            {
                "frame_index": prediction.frame_index,
                "timestamp_seconds": prediction.timestamp_seconds,
                "casino_probability": prediction.casino_probability,
                "top_prompt": prediction.top_prompt,
                "top_prompt_probability": prediction.top_prompt_probability,
            }
            for prediction in result.frame_predictions
        ],
    }


def print_table(results: list[DetectionResult]) -> None:
    print()
    print(
        f"{'source':<28} {'type':<6} {'p_casino':>9} "
        f"{'label':<14} {'frames':>6} top_frame_prompt"
    )
    print("-" * 110)

    for result in results:
        top_frame = max(
            result.frame_predictions,
            key=lambda prediction: prediction.casino_probability,
        )
        print(
            f"{result.source_path.name:<28} "
            f"{result.media_type:<6} "
            f"{result.casino_probability:>8.1%} "
            f"{result.predicted_label:<14} "
            f"{result.analyzed_frames:>6} "
            f"{top_frame.top_prompt}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect whether images or videos show an online casino using CLIP "
            "zero-shot image-text similarity. Videos are analyzed from random frames."
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
        "--clip-model",
        default=DEFAULT_CLIP_MODEL,
        help=f"CLIP model name or local path. Default: {DEFAULT_CLIP_MODEL}",
    )
    parser.add_argument(
        "--allow-model-downloads",
        action="store_true",
        help="Allow Hugging Face model downloads. Default loads from local cache only.",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cpu",
        help="Device for CLIP. Default: cpu",
    )
    parser.add_argument(
        "--video-frames",
        type=int,
        default=3,
        help="Number of random frames to analyze per video. Default: 3",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible video frame sampling. Default: 42",
    )
    parser.add_argument(
        "--aggregation",
        choices=["max", "mean"],
        default="max",
        help="How to aggregate frame probabilities for videos. Default: max",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Probability threshold for online_casino label. Default: 0.5",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.video_frames != 3:
        print(
            f"Using {args.video_frames} random video frame(s); default is 3.",
            file=sys.stderr,
        )

    detector = ClipCasinoDetector(
        model_name=args.clip_model,
        device=args.device,
        local_files_only=not args.allow_model_downloads,
        threshold=args.threshold,
        aggregation=args.aggregation,
    )

    results = [
        classify_file(
            detector=detector,
            path=path.resolve(),
            video_frames=args.video_frames,
            seed=args.seed,
        )
        for path in collect_media_files(args.input)
    ]

    if args.json:
        print(json.dumps([result_to_dict(result) for result in results], ensure_ascii=False, indent=2))
    else:
        print_table(results)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
