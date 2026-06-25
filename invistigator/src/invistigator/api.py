import logging
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException

from invistigator.config import Settings, get_settings
from invistigator.graph import build_graph
from invistigator.pipeline import Pipeline
from invistigator.schemas import AcceptedResponse, AnalyzeRequest, GraphData, JobStatus
from invistigator.storage import read_jsonl


def make_scraper_factory(settings: Settings):
    """Возвращает фабрику скрейпера по выбранному бэкенду (импорты ленивые)."""
    def factory():
        if settings.scraper_backend == "browser":
            from invistigator.scraper_browser import BrowserScraper

            return BrowserScraper(settings, headless=settings.browser_headless)
        from invistigator.scraper import Scraper

        return Scraper(settings)

    return factory


def create_app(pipeline: Pipeline | None = None) -> FastAPI:
    app = FastAPI(title="Investigator — Instagram")
    jobs: dict[str, dict] = {}

    def get_pipeline() -> Pipeline:
        nonlocal pipeline
        if pipeline is None:
            settings = get_settings()
            pipeline = Pipeline(settings, make_scraper_factory(settings))
        return pipeline

    def run_job(job_id: str, usernames: list[str]) -> None:
        job = jobs[job_id]
        try:
            get_pipeline().process_batch(usernames, sink=job["results"])
        finally:
            job["status"] = "done"

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/graph", response_model=GraphData)
    def graph(min_shared: int = 2):
        profiles = read_jsonl(get_settings().jsonl_path)
        return build_graph(profiles, min_shared=min_shared)

    @app.post("/accounts", response_model=AcceptedResponse)
    def accounts(req: AnalyzeRequest, background: BackgroundTasks):
        # Скрейпинг идёт в фоне — длинные анти-бан паузы не блокируют HTTP.
        job_id = uuid.uuid4().hex
        jobs[job_id] = {"status": "running", "accepted": len(req.usernames), "results": []}
        background.add_task(run_job, job_id, req.usernames)
        return AcceptedResponse(job_id=job_id, accepted=len(req.usernames))

    @app.get("/accounts/{job_id}", response_model=JobStatus)
    def job_status(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobStatus(
            job_id=job_id,
            status=job["status"],
            accepted=job["accepted"],
            done=len(job["results"]),
            results=job["results"],
        )

    return app


def get_app() -> FastAPI:
    """Factory для `uvicorn invistigator.api:get_app --factory`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return create_app()
