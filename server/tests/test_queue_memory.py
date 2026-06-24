from app.queue.base import ANALYSIS, INTAKE
from app.queue.memory import InMemoryQueue


async def test_fifo_order():
    q = InMemoryQueue()
    await q.enqueue(INTAKE, "a")
    await q.enqueue(INTAKE, "b")
    m1 = await q.dequeue(INTAKE)
    m2 = await q.dequeue(INTAKE)
    assert (m1.job_id, m2.job_id) == ("a", "b")
    assert await q.dequeue(INTAKE) is None


async def test_priority_order_highest_first():
    q = InMemoryQueue()
    await q.enqueue(ANALYSIS, "low", priority=0.1)
    await q.enqueue(ANALYSIS, "high", priority=0.9)
    await q.enqueue(ANALYSIS, "mid", priority=0.5)
    order = [(await q.dequeue(ANALYSIS)).job_id for _ in range(3)]
    assert order == ["high", "mid", "low"]


async def test_nack_requeues_with_priority():
    q = InMemoryQueue()
    await q.enqueue(ANALYSIS, "x", priority=0.7)
    msg = await q.dequeue(ANALYSIS)
    await q.nack(msg)
    again = await q.dequeue(ANALYSIS)
    assert again.job_id == "x"


async def test_ack_removes_inflight():
    q = InMemoryQueue()
    await q.enqueue(INTAKE, "x")
    msg = await q.dequeue(INTAKE)
    await q.ack(msg)
    await q.nack(msg)  # no-op after ack
    assert await q.dequeue(INTAKE) is None
