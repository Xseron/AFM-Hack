from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import architecture, dedup, health, investigation, jobs, parser, pipelines, review, ui, videos
from app.config import Settings, get_settings
from app.db.repository import JobRepository
from app.db.session import init_db, make_engine, make_sessionmaker
from app.dedup.neardup import NearDupIndex, NullNearDupIndex
from app.parser_control import AutoScanState, ParserController
from app.pipelines.architecture import PipelineArchitecture
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
    parser: ParserController
    auto_scan: AutoScanState
    architecture: PipelineArchitecture
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

    from app.pipelines import aggregator
    aggregator.DEFAULT_THRESHOLD = settings.scam_threshold  # startup default scam threshold

    arch = PipelineArchitecture(registry, settings.pipeline_plugins_dir)
    arch.reload_plugins()  # hot-load any checker plugins into the live registry

    return Components(
        settings=settings,
        engine=engine,
        repo=repo,
        queue=queue,
        storage=storage,
        registry=registry,
        extractor=StubExtractor(),
        neardup=NullNearDupIndex(),
        parser=ParserController(
            parser_dir=settings.parser_dir,
            server_url=settings.parser_server_url,
            chrome_path=settings.parser_chrome_path,
            cdp_port=settings.parser_cdp_port,
            chrome_profile_dir=settings.parser_chrome_profile_dir,
        ),
        auto_scan=AutoScanState(
            enabled=settings.auto_scan_enabled,
            max_reels=settings.auto_scan_max_reels,
            thresholds={
                "semantic": settings.auto_scan_threshold_semantic,
                "ocr": settings.auto_scan_threshold_ocr,
                "clip": settings.auto_scan_threshold_clip,
                "audio": settings.auto_scan_threshold_audio,
            },
        ),
        architecture=arch,
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
        make_analysis_handler(
            components.repo,
            components.registry,
            components.extractor,
            controller=components.parser,
            auto_scan=components.auto_scan,
            settings=components.settings,
        ),
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

    for module in (ui, health, videos, jobs, review, pipelines, dedup, parser, architecture, investigation):
        app.include_router(module.router)

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app


app = create_app()
