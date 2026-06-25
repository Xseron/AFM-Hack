"""Deepfake scanner plugin (GenD CLIP-L/14).

Adapts gend_clip_deepfake_detector.py into a pipeline checker: samples frames
from the buffered video, optionally face-crops, and scores deepfake probability
with the GenD model (Hugging Face ``yermandy/GenD_CLIP_L_14``). The mean fake
probability becomes the finding confidence; a reel is flagged scam when it
reaches this node's threshold on the Pipeline tab.

Heavy dependencies (torch, opencv, the GenD repo + weights) are imported lazily,
so the node always loads. If anything is missing it logs once and emits no
finding rather than failing the job. Configure via env vars:

    MW_DEEPFAKE_MODEL_ID    HF model id (default yermandy/GenD_CLIP_L_14)
    MW_DEEPFAKE_GEND_ROOT   path to a cloned https://github.com/yermandy/GenD
                            (default third_party/GenD)
    MW_DEEPFAKE_DEVICE      auto | cpu | cuda:0   (default auto)
    MW_DEEPFAKE_FRAMES      frames sampled per video (default 16)
    MW_DEEPFAKE_BATCH       inference batch size (default 8)
    MW_DEEPFAKE_FACE_CROP   1/0 crop largest face before scoring (default 1)
    MW_DEEPFAKE_FACE_SCALE  crop scale around the face (default 1.3)
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.explain import Attribution, Explanation

log = logging.getLogger(__name__)

MODEL_ID = os.environ.get("MW_DEEPFAKE_MODEL_ID", "yermandy/GenD_CLIP_L_14")
GEND_ROOT = os.environ.get("MW_DEEPFAKE_GEND_ROOT", str(Path("third_party") / "GenD"))
DEVICE = os.environ.get("MW_DEEPFAKE_DEVICE", "auto")
NUM_FRAMES = int(os.environ.get("MW_DEEPFAKE_FRAMES", "16"))
BATCH_SIZE = int(os.environ.get("MW_DEEPFAKE_BATCH", "8"))
FACE_CROP = os.environ.get("MW_DEEPFAKE_FACE_CROP", "1").lower() not in ("0", "false", "no")
FACE_SCALE = float(os.environ.get("MW_DEEPFAKE_FACE_SCALE", "1.3"))


class DeepfakeDetector:
    name = "deepfake_gend"
    modality = "deepfake"
    whole_video = True  # analyze the buffered video file once

    def __init__(self) -> None:
        self._model = None
        self._device = None
        self._unavailable = False  # set once if the model can't be loaded

    # ---- model (lazy, cached) -----------------------------------------
    def _ensure_model(self) -> None:
        if self._model is not None or self._unavailable:
            return
        try:
            import sys

            import torch

            root = Path(GEND_ROOT).resolve()
            if not root.exists():
                raise FileNotFoundError(
                    f"GenD repo not found at {root}; clone https://github.com/yermandy/GenD "
                    "or set MW_DEEPFAKE_GEND_ROOT"
                )
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from src.hf.modeling_gend import GenD  # type: ignore

            if DEVICE == "auto":
                device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
            else:
                device = torch.device(DEVICE)
            model = GenD.from_pretrained(MODEL_ID)
            model.eval()
            model.to(device)
            self._model = model
            self._device = device
            log.info("deepfake_gend loaded (%s on %s)", MODEL_ID, device)
        except Exception as exc:
            self._unavailable = True
            log.warning("deepfake_gend disabled (model unavailable): %s", exc)

    # ---- pipeline API -------------------------------------------------
    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        path = ctx.buffer_path
        if not path or not Path(path).exists():
            return []
        self._ensure_model()
        if self._model is None:
            return []
        result = await asyncio.to_thread(self._run, Path(path))
        if result is None:
            return []
        probability, frames = result
        return [
            Finding(
                modality=self.modality,
                signal_type="deepfake_face",
                confidence=float(probability),
                evidence={
                    "deepfake_probability": round(float(probability), 4),
                    "frames_analyzed": frames,
                    "model": MODEL_ID,
                    "face_crop": FACE_CROP,
                },
            )
        ]

    def _run(self, path: Path):
        import cv2
        import numpy as np
        import torch
        from PIL import Image

        frames_bgr = self._sample_frames(path, cv2)
        if not frames_bgr:
            return None
        images = [Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)) for f in frames_bgr]
        if FACE_CROP:
            images = [self._face_crop(im, cv2, np) for im in images]

        probs: list[float] = []
        with torch.no_grad():
            for start in range(0, len(images), BATCH_SIZE):
                batch = images[start : start + BATCH_SIZE]
                tensors = torch.stack(
                    [self._model.feature_extractor.preprocess(im) for im in batch]
                ).to(self._device)
                logits = self._model(tensors)
                row = logits.softmax(dim=-1).detach().cpu().float().numpy()
                probs.extend(float(r[1]) for r in row)
        if not probs:
            return None
        return float(np.mean(probs)), len(images)

    @staticmethod
    def _even_indices(total: int, count: int) -> list[int]:
        count = min(count, total)
        if count <= 1:
            return [total // 2]
        return [round(i * (total - 1) / (count - 1)) for i in range(count)]

    @classmethod
    def _sample_frames(cls, path: Path, cv2):
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            return []
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        # MediaRecorder .webm clips (from the parser) carry no frame count in
        # their header, so CAP_PROP_FRAME_COUNT is 0 and frame seeking is
        # unreliable. Fall back to a streaming sampler that needs neither.
        if total <= 0:
            capture.release()
            return cls._sample_frames_streaming(path, cv2)
        frames = []
        for index in cls._even_indices(total, NUM_FRAMES):
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if ok and frame is not None:
                frames.append(frame)
        capture.release()
        return frames

    @classmethod
    def _sample_frames_streaming(cls, path: Path, cv2):
        """Sample evenly spaced frames without a header frame count or seeking.

        Pass 1 counts decodable frames with grab() (no decode). Pass 2 streams
        again and only decodes the target indices, so memory stays at NUM_FRAMES.
        """
        counter = cv2.VideoCapture(str(path))
        if not counter.isOpened():
            return []
        total = 0
        while counter.grab():
            total += 1
        counter.release()
        if total <= 0:
            return []

        targets = set(cls._even_indices(total, NUM_FRAMES))
        capture = cv2.VideoCapture(str(path))
        frames = []
        index = 0
        while capture.grab():
            if index in targets:
                ok, frame = capture.retrieve()
                if ok and frame is not None:
                    frames.append(frame)
            index += 1
        capture.release()
        return frames

    @staticmethod
    def _face_crop(image, cv2, np):
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(str(cascade_path))
        if detector.empty():
            return image
        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
        if len(faces) == 0:
            return image
        x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
        cx, cy = x + w / 2, y + h / 2
        size = max(w, h) * FACE_SCALE
        left = max(0, int(round(cx - size / 2)))
        top = max(0, int(round(cy - size / 2)))
        right = min(image.width, int(round(cx + size / 2)))
        bottom = min(image.height, int(round(cy + size / 2)))
        if right <= left or bottom <= top:
            return image
        return image.crop((left, top, right, bottom))

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        f = findings[0]
        return Explanation(
            scope="deepfake",
            method="gend_clip",
            attributions=[Attribution(feature="deepfake_probability", value=1.0, weight=f.confidence)],
            summary=f"deepfake probability {f.confidence:.2f} over {f.evidence.get('frames_analyzed', 0)} frame(s)",
        )


PIPELINE = DeepfakeDetector()
