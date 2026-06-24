from __future__ import annotations

import asyncio

from app.config import get_settings
from app.db.repository import JobRepository
from app.db.session import init_db, make_engine, make_sessionmaker
from app.pipelines.stubs import build_registry
from app.queue.base import INTAKE
from app.queue.factory import build_queue
from app.worker.base import Worker
from app.worker.handlers import make_triage_handler


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    await init_db(engine)
    repo = JobRepository(make_sessionmaker(engine))
    registry = build_registry(settings.enabled_pipeline_list or None)
    queue = build_queue(settings)
    worker = Worker(queue, INTAKE, make_triage_handler(repo, registry, queue))
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
