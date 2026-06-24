from sqlalchemy import select

from app.db.models import Job
from app.db.session import init_db, make_engine, make_sessionmaker


async def test_create_and_read_job():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    Session = make_sessionmaker(engine)
    async with Session() as s:
        s.add(Job(id="j1", description="hello", content_hash="hash-1", source_meta={"platform": "tiktok"}))
        await s.commit()
    async with Session() as s:
        job = (await s.execute(select(Job).where(Job.id == "j1"))).scalar_one()
        assert job.status == "queued"
        assert job.priority == 0.0
        assert job.source_meta["platform"] == "tiktok"
        assert job.risk_score is None
        assert job.content_hash == "hash-1"
