"""Centralized human-like randomness: watch plans, delays, probability gates."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

from .cli import Config


@dataclass
class WatchPlan:
    skip_early: bool
    fraction: float | None  # of total duration to watch before skipping (if skip_early)


def watch_plan(cfg: Config) -> WatchPlan:
    """Decide whether to skip a reel before it finishes."""
    if random.random() < cfg.skip_early_prob:
        lo, hi = cfg.skip_fraction
        return WatchPlan(skip_early=True, fraction=random.uniform(lo, hi))
    return WatchPlan(skip_early=False, fraction=None)


def target_seconds(cfg: Config, plan: WatchPlan, duration: float) -> float:
    """How long to watch this reel, in seconds, bounded by the idle watchdog."""
    if duration and duration > 0:
        secs = duration * plan.fraction if plan.skip_early else duration * 0.98
    else:
        lo, hi = cfg.base_watch
        secs = random.uniform(lo, hi)
        if plan.skip_early:
            secs *= plan.fraction or 0.5
    return min(secs, cfg.max_dwell)


def sleep_range(rng: tuple) -> None:
    time.sleep(random.uniform(*rng))


def gate(prob: float) -> bool:
    return random.random() < prob
