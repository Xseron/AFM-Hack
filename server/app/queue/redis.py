from __future__ import annotations

import redis.asyncio as redis

from app.queue.base import ANALYSIS, QueueMessage

_GROUP = "media-watch"
_CONSUMER = "worker"


class RedisQueue:
    """intake -> Redis Stream (consumer group); analysis -> ZSET (priority)."""

    def __init__(self, redis_url: str) -> None:
        self._r = redis.from_url(redis_url, decode_responses=True)

    def _stream_key(self, lane: str) -> str:
        return f"mw:stream:{lane}"

    def _zset_key(self, lane: str) -> str:
        return f"mw:zset:{lane}"

    async def _ensure_group(self, lane: str) -> None:
        try:
            await self._r.xgroup_create(self._stream_key(lane), _GROUP, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(self, lane: str, job_id: str, *, priority: float = 0.0) -> None:
        if lane == ANALYSIS:
            await self._r.zadd(self._zset_key(lane), {job_id: priority})
        else:
            await self._r.xadd(self._stream_key(lane), {"job_id": job_id})

    async def dequeue(self, lane: str) -> QueueMessage | None:
        if lane == ANALYSIS:
            popped = await self._r.zpopmax(self._zset_key(lane), 1)
            if not popped:
                return None
            job_id, score = popped[0]
            return QueueMessage(lane=lane, job_id=job_id, receipt=f"{job_id}|{score}")
        await self._ensure_group(lane)
        resp = await self._r.xreadgroup(
            _GROUP, _CONSUMER, {self._stream_key(lane): ">"}, count=1, block=10
        )
        if not resp:
            return None
        _, entries = resp[0]
        msg_id, fields = entries[0]
        return QueueMessage(lane=lane, job_id=fields["job_id"], receipt=msg_id)

    async def ack(self, msg: QueueMessage) -> None:
        if msg.lane == ANALYSIS:
            return
        await self._r.xack(self._stream_key(msg.lane), _GROUP, msg.receipt)
        await self._r.xdel(self._stream_key(msg.lane), msg.receipt)

    async def nack(self, msg: QueueMessage) -> None:
        if msg.lane == ANALYSIS:
            job_id, score = msg.receipt.split("|", 1)
            await self._r.zadd(self._zset_key(msg.lane), {job_id: float(score)})
