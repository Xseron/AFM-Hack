from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

INTAKE = "intake"
ANALYSIS = "analysis"


@dataclass
class QueueMessage:
    lane: str
    job_id: str
    receipt: str


class JobQueue(Protocol):
    async def enqueue(self, lane: str, job_id: str, *, priority: float = 0.0) -> None: ...

    async def dequeue(self, lane: str) -> QueueMessage | None: ...

    async def ack(self, msg: QueueMessage) -> None: ...

    async def nack(self, msg: QueueMessage) -> None: ...
