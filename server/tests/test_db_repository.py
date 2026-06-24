import pytest

from app.db.repository import JobRepository
from app.db.session import init_db, make_engine, make_sessionmaker
from app.pipelines.base import Finding
from app.pipelines.explain import Attribution, Explanation


@pytest.fixture
async def repo():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    return JobRepository(make_sessionmaker(engine))


async def test_create_and_get(repo):
    job_id = await repo.create_job("desc", "tiktok", "http://x", {"a": 1}, "/buf/v.mp4")
    job = await repo.get_job(job_id)
    assert job.description == "desc"
    assert job.buffer_path == "/buf/v.mp4"
    assert job.status == "queued"


async def test_status_priority_risk(repo):
    job_id = await repo.create_job("d", None, None, {})
    await repo.set_priority(job_id, 0.8)
    await repo.set_status(job_id, "processing")
    await repo.set_risk(job_id, 0.9, "gambling")
    job = await repo.get_job(job_id)
    assert (job.priority, job.status, job.risk_score, job.category) == (0.8, "processing", 0.9, "gambling")


async def test_findings_and_explanations(repo):
    job_id = await repo.create_job("d", None, None, {})
    await repo.add_findings(job_id, [Finding(modality="text", signal_type="kw", confidence=0.5, evidence={"k": "v"})])
    await repo.add_explanations(job_id, [Explanation(scope="aggregate", method="shap",
        attributions=[Attribution(feature="casino", value=1.0, weight=0.4)], summary="s")])
    findings = await repo.get_findings(job_id)
    exps = await repo.get_explanations(job_id)
    assert findings[0].signal_type == "kw"
    assert exps[0].payload["attributions"][0]["feature"] == "casino"


async def test_review_queue_orders_by_risk(repo):
    a = await repo.create_job("a", None, None, {})
    b = await repo.create_job("b", None, None, {})
    c = await repo.create_job("c", None, None, {})  # no risk set -> NULL, must sort last
    await repo.set_risk(a, 0.2, "clean")
    await repo.set_risk(b, 0.95, "gambling")
    ids = [j.id for j in await repo.review_queue()]
    assert ids[:2] == [b, a]
    assert ids[-1] == c  # NULL risk_score sorts after scored jobs


async def test_get_job_by_hash(repo):
    job_id = await repo.create_job("d", None, None, {}, content_hash="abc123")
    found = await repo.get_job_by_hash("abc123")
    assert found is not None and found.id == job_id
    assert await repo.get_job_by_hash("missing") is None
