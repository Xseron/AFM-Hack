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
    # New static app shell: sidebar nav + module bootstrap.
    assert "AI Media Watch" in resp.text
    assert 'data-nav="jobs"' in resp.text
    assert "/static/js/app.js" in resp.text


async def test_architecture_ui_redirects(app_client):
    client, _ = app_client
    resp = await client.get("/architecture-ui")
    assert resp.status_code == 307
    assert resp.headers["location"] == "/#/pipeline"


async def test_architecture_includes_tiktok_source(app_client):
    client, _ = app_client
    resp = await client.get("/architecture")
    assert resp.status_code == 200
    source = next(s for s in resp.json()["stages"] if s["id"] == "source")
    assert {n["id"] for n in source["nodes"]} == {"instagram", "tiktok"}


async def test_architecture_edge_remove_disables_scanner(app_client):
    client, _ = app_client
    removed = await client.post(
        "/architecture/edge/remove",
        json={"from_id": "priority", "to_id": "visual_cv"},
    )
    assert removed.status_code == 200
    graph = removed.json()
    scanner = next(s for s in graph["stages"] if s["id"] == "scanner")
    visual = next(n for n in scanner["nodes"] if n["id"] == "visual_cv")
    assert visual["enabled"] is False
    assert {"id": "priority->visual_cv", "from": "priority", "to": "visual_cv"} not in graph["edges"]


async def test_architecture_edge_connect_enables_scanner(app_client):
    client, _ = app_client
    await client.post(
        "/architecture/edge/remove",
        json={"from_id": "priority", "to_id": "visual_cv"},
    )
    connected = await client.post(
        "/architecture/edge",
        json={"from_id": "priority", "to_id": "visual_cv"},
    )
    assert connected.status_code == 200
    graph = connected.json()
    scanner = next(s for s in graph["stages"] if s["id"] == "scanner")
    visual = next(n for n in scanner["nodes"] if n["id"] == "visual_cv")
    assert visual["enabled"] is True
    assert {"id": "priority->visual_cv", "from": "priority", "to": "visual_cv"} in graph["edges"]


async def test_architecture_edge_remove_disables_investigator_path(app_client):
    client, _ = app_client
    enabled = await client.post("/parser/auto-scan", json={"enabled": True})
    assert enabled.status_code == 200
    removed = await client.post(
        "/architecture/edge/remove",
        json={"from_id": "aggregate", "to_id": "investigate"},
    )
    assert removed.status_code == 200
    graph = removed.json()
    assert {"id": "aggregate->investigate", "from": "aggregate", "to": "investigate"} not in graph["edges"]
    auto_scan = await client.get("/parser/auto-scan")
    assert auto_scan.json()["enabled"] is False


async def test_architecture_source_edge_can_be_removed_and_restored(app_client):
    client, _ = app_client
    edge = {"id": "tiktok->parse", "from": "tiktok", "to": "parse"}
    removed = await client.post(
        "/architecture/edge/remove",
        json={"from_id": "tiktok", "to_id": "parse"},
    )
    assert removed.status_code == 200
    assert edge not in removed.json()["edges"]

    connected = await client.post(
        "/architecture/edge",
        json={"from_id": "tiktok", "to_id": "parse"},
    )
    assert connected.status_code == 200
    assert edge in connected.json()["edges"]


async def test_parser_feed_routes_tiktok_platform(app_client):
    client, components = app_client

    class FakeParser:
        def __init__(self):
            self.calls = []

        def start_feed(self, max_reels=None, platform="instagram", max_video_seconds=None):
            self.calls.append(("feed", max_reels, platform, max_video_seconds))
            return {"running": True, "platform": platform, "channel": f"{platform} feed"}

    fake = FakeParser()
    components.parser = fake

    resp = await client.post(
        "/parser/feed", json={"platform": "tiktok", "max_reels": 2, "max_video_seconds": 9}
    )
    assert resp.status_code == 200
    assert resp.json()["platform"] == "tiktok"
    assert fake.calls == [("feed", 2, "tiktok", 9)]


async def test_parser_reel_infers_tiktok_platform(app_client):
    client, components = app_client

    class FakeParser:
        def __init__(self):
            self.calls = []

        def start_reel(self, reel_url, platform="instagram", max_video_seconds=None):
            self.calls.append((reel_url, platform, max_video_seconds))
            return {"running": True, "platform": platform, "channel": reel_url}

    fake = FakeParser()
    components.parser = fake

    url = "https://www.tiktok.com/@user6302021905958/video/1234567890123456789"
    resp = await client.post("/parser/reel", json={"reel_url": url})
    assert resp.status_code == 200
    assert resp.json()["platform"] == "tiktok"
    assert fake.calls == [(url, "tiktok", None)]


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
