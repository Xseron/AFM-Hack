import hashlib

from app.dedup.hashing import new_hasher, tee_sha256
from app.dedup.neardup import NullNearDupIndex
from app.pipelines.base import JobContext


async def _agen(parts):
    for p in parts:
        yield p


async def test_tee_sha256_passes_through_and_hashes():
    hasher = new_hasher()
    out = b"".join([chunk async for chunk in tee_sha256(_agen([b"ab", b"cd"]), hasher)])
    assert out == b"abcd"
    assert hasher.hexdigest() == hashlib.sha256(b"abcd").hexdigest()


async def test_null_neardup_returns_empty():
    idx = NullNearDupIndex()
    ctx = JobContext(job_id="j", description="d", source_meta={})
    assert await idx.find_similar(ctx) == []
    assert await idx.index(ctx) is None
