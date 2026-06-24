from app.models.loader import Models
from app.models import loader
from app.pipelines.real import build_real_registry


def test_real_registry_has_four_requested_methods():
    registry = build_real_registry(Models())

    names = {pipeline.name for pipeline in registry.all()}

    assert names == {
        "semantic_priority",
        "audio_scam",
        "ocr_scam",
        "casino_clip",
    }


def test_cuda_request_falls_back_when_torch_is_cpu_only(monkeypatch):
    class TorchStub:
        class cuda:
            @staticmethod
            def is_available():
                return False

    monkeypatch.setitem(__import__("sys").modules, "torch", TorchStub)

    assert loader._torch_device("cuda") == "cpu"


def test_cuda_whisper_falls_back_when_cudnn_missing(monkeypatch):
    monkeypatch.setattr(loader.shutil, "which", lambda name: None)

    assert loader._whisper_device("cuda") == "cpu"
