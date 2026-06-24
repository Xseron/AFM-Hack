from app.pipelines.base import JobContext
from app.pipelines.extract import StubExtractor


async def test_extract_emits_units():
    ex = StubExtractor(n_frames=2, n_audio=1)
    units = await ex.extract(JobContext(job_id="j", description="hello", source_meta={}))
    kinds = [u.kind for u in units]
    assert kinds == ["text", "frame", "frame", "audio"]
    text_unit = units[0]
    assert text_unit.payload["text"] == "hello"
