from pathlib import Path

from app.storage.local import LocalStorage


async def _chunks(parts):
    for p in parts:
        yield p


async def test_save_stream_writes_file(tmp_path):
    storage = LocalStorage(str(tmp_path))
    path = await storage.save_stream("job1/video.mp4", _chunks([b"abc", b"def"]))
    assert Path(path).read_bytes() == b"abcdef"
    assert Path(path).name == "video.mp4"


async def test_save_stream_creates_nested_dirs(tmp_path):
    storage = LocalStorage(str(tmp_path))
    path = await storage.save_stream("a/b/c.bin", _chunks([b"x"]))
    assert Path(path).exists()


async def test_delete_removes_file(tmp_path):
    storage = LocalStorage(str(tmp_path))
    path = await storage.save_stream("d/x.bin", _chunks([b"x"]))
    await storage.delete("d/x.bin")
    assert not Path(path).exists()


async def test_delete_missing_is_noop(tmp_path):
    storage = LocalStorage(str(tmp_path))
    await storage.delete("nope/missing.bin")  # must not raise
