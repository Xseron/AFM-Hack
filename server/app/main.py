from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

from app.api import health, jobs, pipelines, review, videos
from app.config import Settings, get_settings
from app.db.repository import JobRepository
from app.db.session import init_db, make_engine, make_sessionmaker
from app.dedup.neardup import NearDupIndex, NullNearDupIndex
from app.pipelines.extract import Extractor, StubExtractor
from app.pipelines.registry import PipelineRegistry
from app.pipelines.stubs import build_registry
from app.queue.factory import build_queue
from app.storage.base import BlobStorage
from app.storage.factory import build_storage


@dataclass
class Components:
    settings: Settings
    engine: object
    repo: JobRepository
    queue: object
    storage: BlobStorage
    registry: PipelineRegistry
    extractor: Extractor
    neardup: NearDupIndex
    models: object | None = None


def build_components(settings: Settings) -> Components:
    engine = make_engine(settings.database_url)
    repo = JobRepository(make_sessionmaker(engine))
    queue = build_queue(settings)
    storage = build_storage(settings)

    models = None
    if settings.models_enabled:
        # Lazy import so torch/transformers are only pulled in when models are on.
        from app.models.loader import load_models
        from app.pipelines.real import build_real_registry

        models = load_models(settings)
        registry = build_real_registry(models)
    else:
        registry = build_registry(settings.enabled_pipeline_list or None)

    return Components(
        settings=settings,
        engine=engine,
        repo=repo,
        queue=queue,
        storage=storage,
        registry=registry,
        extractor=StubExtractor(),
        neardup=NullNearDupIndex(),
        models=models,
    )


async def init_components(components: Components) -> None:
    await init_db(components.engine)


def _start_inline_workers(components: Components) -> list[asyncio.Task]:
    """Run triage + analysis workers as background tasks in the API process."""
    from app.queue.base import ANALYSIS, INTAKE
    from app.worker.base import Worker
    from app.worker.handlers import make_analysis_handler, make_triage_handler

    triage = Worker(
        components.queue,
        INTAKE,
        make_triage_handler(components.repo, components.registry, components.queue),
    )
    analysis = Worker(
        components.queue,
        ANALYSIS,
        make_analysis_handler(components.repo, components.registry, components.extractor),
    )
    return [
        asyncio.create_task(triage.run_forever()),
        asyncio.create_task(analysis.run_forever()),
    ]


def create_app(settings: Settings | None = None, components: Components | None = None) -> FastAPI:
    settings = settings or get_settings()
    components = components or build_components(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_components(components)
        worker_tasks = _start_inline_workers(components) if components.settings.run_workers_inline else []
        try:
            yield
        finally:
            for task in worker_tasks:
                task.cancel()

    app = FastAPI(title="AI Media Watch", lifespan=lifespan)
    app.state.components = components

    for module in (health, videos, jobs, review, pipelines):
        app.include_router(module.router)
    return app


app = create_app()
