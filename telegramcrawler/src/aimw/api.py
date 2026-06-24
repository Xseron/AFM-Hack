from fastapi import FastAPI, HTTPException

from aimw.schemas import AnalyzeRequest, ChannelReportOut


def create_app(repository, pipeline, lifespan=None) -> FastAPI:
    app = FastAPI(title="AI Media Watch — Telegram", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/channels", response_model=list[ChannelReportOut])
    async def analyze(req: AnalyzeRequest):
        results = []
        for username in req.channels:
            report = await pipeline.analyze_channel(username)
            repository.save_report(report)
            results.append(ChannelReportOut.from_domain(report))
        return results

    @app.get("/channels", response_model=list[ChannelReportOut])
    def list_channels(sort: str = "risk"):
        reports = repository.list_reports(sort_by_risk=(sort == "risk"))
        return [ChannelReportOut.from_domain(r) for r in reports]

    @app.get("/channels/{username}", response_model=ChannelReportOut)
    def get_channel(username: str):
        report = repository.get_report(username)
        if report is None:
            raise HTTPException(status_code=404, detail="channel not found")
        return ChannelReportOut.from_domain(report)

    return app


def get_app() -> FastAPI:
    """Factory for `uvicorn aimw.api:get_app --factory`. Wires real dependencies."""
    import logging
    from contextlib import asynccontextmanager

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from aimw.analyzer import Analyzer, build_client
    from aimw.config import get_settings
    from aimw.crawler import Crawler, build_telethon_client
    from aimw.pipeline import Pipeline
    from aimw.storage import Repository

    settings = get_settings()
    repository = Repository(settings.database_url)
    tg = build_telethon_client(settings)
    crawler = Crawler(tg)
    analyzer = Analyzer(build_client(settings), settings)
    pipeline = Pipeline(crawler, analyzer, settings.posts_per_channel)

    @asynccontextmanager
    async def lifespan(app):
        # Connect on uvicorn's running loop so request handlers can use the client.
        await tg.connect()
        if not await tg.is_user_authorized():
            raise RuntimeError(
                "Telegram не авторизован — сначала запусти scripts/login.py"
            )
        yield
        await tg.disconnect()

    return create_app(repository, pipeline, lifespan=lifespan)
