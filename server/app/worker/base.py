from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from app.queue.base import JobQueue, QueueMessage

Handler = Callable[[QueueMessage], Awaitable[None]]


class Worker:
    def __init__(self, queue: JobQueue, lane: str, handler: Handler, poll_interval: float = 0.1) -> None:
        self._queue = queue
        self._lane = lane
        self._handler = handler
        self._poll = poll_interval

    async def run_once(self) -> bool:
        msg = await self._queue.dequeue(self._lane)
        if msg is None:
            return False
        try:
            await self._handler(msg)
            await self._queue.ack(msg)
        except Exception:
            await self._queue.nack(msg)
            raise
        return True

    async def run_forever(self) -> None:
        while True:
            did_work = await self.run_once()
            if not did_work:
                await asyncio.sleep(self._poll)
