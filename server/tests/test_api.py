async def test_health(app_client):
    client, _ = app_client
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_pipelines_listed(app_client):
    client, _ = app_client
    resp = await client.get("/pipelines")
    names = {p["name"] for p in resp.json()["pipelines"]}
    assert "triage_keyword" in names


async def test_post_video_creates_job(app_client):
    client, _ = app_client
    files = {"video": ("clip.mp4", b"\x00\x01\x02", "video/mp4")}
    data = {"description": "казино и доход"}
    resp = await client.post("/videos", files=files, data=data)
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["duplicate"] is False
    assert body["near_duplicates"] == []


async def test_post_duplicate_video_short_circuits(app_client):
    client, _ = app_client
    payload = {"video": ("clip.mp4", b"\x00\x01\x02\x03", "video/mp4")}
    first = await client.post("/videos", files=payload, data={"description": "казино"})
    first_body = first.json()
    assert first_body["duplicate"] is False
    again = {"video": ("renamed.mp4", b"\x00\x01\x02\x03", "video/mp4")}
    second = await client.post("/videos", files=again, data={"description": "казино"})
    second_body = second.json()
    assert second_body["duplicate"] is True
    assert second_body["job_id"] == first_body["job_id"]


async def test_post_video_rejects_empty_description(app_client):
    client, _ = app_client
    files = {"video": ("clip.mp4", b"\x00", "video/mp4")}
    resp = await client.post("/videos", files=files, data={"description": "   "})
    assert resp.status_code == 422


async def test_get_missing_job_404(app_client):
    client, _ = app_client
    resp = await client.get("/jobs/nope")
    assert resp.status_code == 404
