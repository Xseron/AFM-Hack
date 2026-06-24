from app.queue.base import ANALYSIS, INTAKE
from app.worker.base import Worker
from app.worker.handlers import make_analysis_handler, make_triage_handler


async def test_full_pipeline(app_client):
    client, components = app_client
    files = {"video": ("clip.mp4", b"\x00\x01", "video/mp4")}
    data = {"description": "реклама casino, гарантированный доход 200%, реферальная ссылка"}
    job_id = (await client.post("/videos", files=files, data=data)).json()["job_id"]

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

    assert await triage.run_once() is True
    assert await analysis.run_once() is True

    job = (await client.get(f"/jobs/{job_id}")).json()
    assert job["status"] == "done"
    assert job["risk_score"] is not None
    assert job["category"] in {"gambling", "pyramid", "fraud"}
    assert len(job["findings"]) > 0

    exps = (await client.get(f"/jobs/{job_id}/explanations")).json()["explanations"]
    assert any(e["scope"] == "aggregate" for e in exps)

    review = (await client.get("/review-queue")).json()["items"]
    assert review[0]["job_id"] == job_id
