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
    assert job["scanner_confidences"]["text_nlp"] >= 0.5
    assert "visual_cv" in job["scanner_confidences"]

    exps = (await client.get(f"/jobs/{job_id}/explanations")).json()["explanations"]
    assert any(e["scope"] == "aggregate" for e in exps)

    review = (await client.get("/review-queue")).json()["items"]
    assert review[0]["job_id"] == job_id


async def test_disabled_scanner_does_not_emit_scanner_confidence(app_client):
    client, components = app_client
    disabled = await client.post("/architecture/node/visual_cv", json={"enabled": False})
    assert disabled.status_code == 200

    files = {"video": ("clip.mp4", b"\x00\x01\x02", "video/mp4")}
    data = {"description": "casino 100%"}
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
    assert "text_nlp" in job["scanner_confidences"]
    assert "ocr_text" in job["scanner_confidences"]
    assert "visual_cv" not in job["scanner_confidences"]
