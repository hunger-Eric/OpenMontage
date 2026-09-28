import sys
from types import SimpleNamespace

from tools.analysis.transcriber import Transcriber


def test_transcriber_uses_openai_whisper_when_faster_whisper_is_missing(
    monkeypatch, tmp_path
) -> None:
    class FakeModel:
        def transcribe(self, input_path, **kwargs):
            assert kwargs["word_timestamps"] is True
            return {
                "language": "zh",
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 1.25,
                        "text": " 你好 ",
                        "words": [
                            {
                                "word": "你好",
                                "start": 0.0,
                                "end": 1.25,
                                "probability": 0.98,
                            }
                        ],
                    }
                ],
            }

    monkeypatch.delitem(sys.modules, "faster_whisper", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "whisper",
        SimpleNamespace(load_model=lambda model_size, device: FakeModel()),
    )
    monkeypatch.setattr(
        Transcriber,
        "_available_backend",
        staticmethod(lambda: "openai-whisper"),
    )
    input_path = tmp_path / "audio.wav"
    input_path.write_bytes(b"fake")

    result = Transcriber().execute(
        {"input_path": str(input_path), "output_dir": str(tmp_path), "language": "zh"}
    )

    assert result.success, result.error
    assert result.data["backend"] == "openai-whisper"
    assert result.data["segments"][0]["text"] == "你好"
    assert result.data["word_timestamps"][0]["word"] == "你好"
    assert result.data["duration_seconds"] == 1.25


class _Info:
    language = "en"
    duration = 1.0


def test_transcriber_uses_ctranslate2_cuda_without_torch(monkeypatch, tmp_path) -> None:
    devices = []

    class FakeWhisperModel:
        def __init__(self, model_size, *, device, compute_type):
            devices.append((device, compute_type))

        def transcribe(self, *args, **kwargs):
            return iter(()), _Info()

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=FakeWhisperModel),
    )
    monkeypatch.setitem(
        sys.modules,
        "ctranslate2",
        SimpleNamespace(
            get_cuda_device_count=lambda: 1,
            get_supported_compute_types=lambda device: {"float16", "float32"},
        ),
    )
    input_path = tmp_path / "audio.wav"
    input_path.write_bytes(b"fake")

    result = Transcriber().execute({"input_path": str(input_path), "output_dir": str(tmp_path)})

    assert result.success, result.error
    assert devices == [("cuda", "float16")]
    assert result.data["device"] == "cuda"


def test_transcriber_falls_back_when_cuda_fails_during_iteration(monkeypatch, tmp_path) -> None:
    devices = []

    class FakeWhisperModel:
        def __init__(self, model_size, *, device, compute_type):
            self.device = device
            devices.append((device, compute_type))

        def transcribe(self, *args, **kwargs):
            if self.device == "cuda":
                def broken_iterator():
                    raise RuntimeError("cublas64_12.dll not found")
                    yield

                return broken_iterator(), _Info()
            return iter(()), _Info()

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=FakeWhisperModel),
    )
    monkeypatch.setitem(
        sys.modules,
        "ctranslate2",
        SimpleNamespace(
            get_cuda_device_count=lambda: 1,
            get_supported_compute_types=lambda device: {"float16"},
        ),
    )
    input_path = tmp_path / "audio.wav"
    input_path.write_bytes(b"fake")

    result = Transcriber().execute({"input_path": str(input_path), "output_dir": str(tmp_path)})

    assert result.success, result.error
    assert devices == [("cuda", "float16"), ("cpu", "int8")]
    assert result.data["device"] == "cpu"
    assert "cublas64_12.dll" in result.data["gpu_fallback_reason"]
