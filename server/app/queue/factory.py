from __future__ import annotations

from app.config import Settings
from app.queue.base import JobQueue
from app.queue.memory import InMemoryQueue
from app.queue.redis import RedisQueue


def build_queue(settings: Settings) -> JobQueue:
    backend = settings.queue_backend
    if backend == "memory":
        return InMemoryQueue()
    if backend == "redis":
        return RedisQueue(settings.redis_url)
    raise ValueError(f"unknown queue backend: {backend!r}")
