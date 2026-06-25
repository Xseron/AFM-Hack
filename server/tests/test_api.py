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


async def test_clear_dedup_allows_same_video_again(app_client):
    client, _ = app_client
    payload = {"video": ("clip.mp4", b"\x10\x20\x30", "video/mp4")}
    first = await client.post("/videos", files=payload, data={"description": "casino"})
    first_body = first.json()

    duplicate = {"video": ("clip.mp4", b"\x10\x20\x30", "video/mp4")}
    assert (await client.post("/videos", files=duplicate, data={"description": "casino"})).json()["duplicate"] is True

    cleared = await client.post("/dedup/clear")
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] == 1

    after_clear = {"video": ("clip.mp4", b"\x10\x20\x30", "video/mp4")}
    after_body = (await client.post("/videos", files=after_clear, data={"description": "casino"})).json()
    assert after_body["duplicate"] is False
    assert after_body["job_id"] != first_body["job_id"]


async def test_ui_served(app_client):
    client, _ = app_client
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Upload and Check" in resp.text
    assert "/architecture-ui" in resp.text
    assert "Clear Dedup" in resp.text
    assert "Priority List" in resp.text
    assert "Recent Reels" in resp.text
    assert "Description" in resp.text


async def test_architecture_ui_served(app_client):
    client, _ = app_client
    resp = await client.get("/architecture-ui")
    assert resp.status_code == 200
    assert "Pipeline Architecture" in resp.text
    assert "Reload plugins" in resp.text


async def test_priority_list_includes_method_confidences(app_client):
    client, _ = app_client
    files = {"video": ("clip.mp4", b"\x44\x55\x66", "video/mp4")}
    created = await client.post(
        "/videos",
        files=files,
        data={
            "description": "casino 100%",
            "source_platform": "instagram",
            "source_url": "https://www.instagram.com/reel/abc123/",
            "source_meta": '{"shortcode":"abc123"}',
        },
    )
    assert created.status_code == 202

    resp = await client.get("/priority-list")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["job_id"] == created.json()["job_id"]
    assert item["source"]["platform"] == "instagram"
    assert item["source"]["shortcode"] == "abc123"
    assert item["source"]["url"] == "https://www.instagram.com/reel/abc123/"
    assert item["source"]["top_bar_url"] == "https://www.instagram.com/reel/abc123/"
    assert item["description"] == "casino 100%"
    assert item["method_confidences"] == {
        "semantic": 0.0,
        "ocr": 0.0,
        "clip": 0.0,
        "audio": 0.0,
    }
    assert item["scanner_confidences"] == {}


async def test_recent_jobs_sorted_newest_first_with_scores(app_client):
    client, _ = app_client
    first = await client.post(
        "/videos",
        files={"video": ("first.mp4", b"first", "video/mp4")},
        data={
            "description": "first",
            "source_platform": "instagram",
            "source_url": "https://www.instagram.com/reels/first/",
            "source_meta": '{"shortcode":"first","top_bar_url":"https://www.instagram.com/reels/first/","permalink":"https://www.instagram.com/reel/first/"}',
        },
    )
    second = await client.post(
        "/videos",
        files={"video": ("second.mp4", b"second", "video/mp4")},
        data={
            "description": "second",
            "source_platform": "instagram",
            "source_url": "https://www.instagram.com/reels/second/",
            "source_meta": '{"shortcode":"second","top_bar_url":"https://www.instagram.com/reels/second/","permalink":"https://www.instagram.com/reel/second/"}',
        },
    )

    resp = await client.get("/recent-jobs")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["job_id"] == second.json()["job_id"]
    assert items[1]["job_id"] == first.json()["job_id"]
    assert items[0]["source"]["top_bar_url"] == "https://www.instagram.com/reels/second/"
    assert items[0]["source"]["permalink"] == "https://www.instagram.com/reel/second/"
    assert items[0]["description"] == "second"
    assert set(items[0]["method_confidences"]) == {"semantic", "ocr", "clip", "audio"}
    assert "scanner_confidences" in items[0]
    assert items[0]["created_at"]


async def test_post_video_rejects_empty_description(app_client):
    client, _ = app_client
    files = {"video": ("clip.mp4", b"\x00", "video/mp4")}
    resp = await client.post("/videos", files=files, data={"description": "   "})
    assert resp.status_code == 422


async def test_get_missing_job_404(app_client):
    client, _ = app_client
    resp = await client.get("/jobs/nope")
    assert resp.status_code == 404
