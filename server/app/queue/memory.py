from __future__ import annotations

import asyncio
import heapq
from collections import defaultdict, deque
from itertools import count

from app.queue.base import QueueMessage


class InMemoryQueue:
    """Single-process queue. FIFO for priority==0 lanes, max-heap otherwise."""

    def __init__(self) -> None:
        self._fifo: dict[str, deque[str]] = defaultdict(deque)
        self._heap: dict[str, list[tuple[float, int, str, float]]] = defaultdict(list)
        self._inflight: dict[str, tuple[str, str, float]] = {}
        self._seq = count(1)
        self._lock = asyncio.Lock()

    def _put(self, lane: str, job_id: str, priority: float) -> None:
        if priority:
            heapq.heappush(self._heap[lane], (-priority, next(self._seq), job_id, priority))
        else:
            self._fifo[lane].append(job_id)

    async def enqueue(self, lane: str, job_id: str, *, priority: float = 0.0) -> None:
        async with self._lock:
            self._put(lane, job_id, priority)

    async def dequeue(self, lane: str) -> QueueMessage | None:
        async with self._lock:
            if self._heap[lane]:
                _, _, job_id, priority = heapq.heappop(self._heap[lane])
            elif self._fifo[lane]:
                job_id, priority = self._fifo[lane].popleft(), 0.0
            else:
                return None
            receipt = str(next(self._seq))
            self._inflight[receipt] = (lane, job_id, priority)
            return QueueMessage(lane=lane, job_id=job_id, receipt=receipt)

    async def ack(self, msg: QueueMessage) -> None:
        async with self._lock:
            self._inflight.pop(msg.receipt, None)

    async def nack(self, msg: QueueMessage) -> None:
        async with self._lock:
            entry = self._inflight.pop(msg.receipt, None)
            if entry is not None:
                lane, job_id, priority = entry
                self._put(lane, job_id, priority)
