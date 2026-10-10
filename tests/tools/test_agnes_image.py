"""Agnes protocol, integrity and duplicate-submit boundaries."""
import base64
import io
from types import SimpleNamespace

from PIL import Image

from tools.base_tool import ToolStatus
from tools.graphics.agnes_image import AgnesImage, DEFAULT_MODEL
from tools.graphics.image_selector import ImageSelector


def test_agnes_image_contract_and_idempotent_reuse(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    buffer = io.BytesIO()
    Image.new("RGB", (64, 128)).save(buffer, format="PNG")
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs["json"]))
        return SimpleNamespace(status_code=200, json=lambda: {"id": "image-1", "data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode()}]})
    monkeypatch.setattr("tools.graphics.agnes_image.requests.post", post)
    args = {"prompt": "test scene", "width": 64, "height": 128, "output_path": str(tmp_path / "sample.png")}
    tool = AgnesImage()
    first = tool.execute(args)
    assert first.success and first.data["dimensions"] == [64, 128]
    assert calls[0][1] == {"model": DEFAULT_MODEL, "prompt": "test scene", "n": 1, "size": "64x128"}
    assert tool.execute(args).success
    assert len(calls) == 1
    assert not tool.execute({**args, "prompt": "changed"}).success
    (tmp_path / "sample.png").write_bytes(b"corrupt")
    assert tool.execute(args).data["error_code"] == "artifact_integrity_failed"
    assert len(calls) == 1


def test_timeout_does_not_resubmit_or_expose_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    calls = []
    def post(*args, **kwargs):
        calls.append(1)
        raise TimeoutError("sensitive provider detail test-key")
    monkeypatch.setattr("tools.graphics.agnes_image.requests.post", post)
    args = {"prompt": "test scene", "output_path": str(tmp_path / "sample.png")}
    first = AgnesImage().execute(args)
    assert not first.success and "test-key" not in str(first)
    assert AgnesImage().execute(args).data["error_code"] == "existing_attempt_requires_inspection"
    assert len(calls) == 1


def test_portable_default_and_explicit_alternative(monkeypatch):
    from tools.graphics.minimax_image import MiniMaxImage
    agnes, alternative = AgnesImage(), MiniMaxImage()
    monkeypatch.setattr(agnes, "get_status", lambda: ToolStatus.AVAILABLE)
    monkeypatch.setattr(alternative, "get_status", lambda: ToolStatus.AVAILABLE)
    selector = ImageSelector()
    monkeypatch.setattr(selector, "_providers", lambda: [agnes, alternative])
    args = {"prompt": "test scene"}
    context = selector._prepare_task_context(args)
    assert selector._select_best_tool(args, [agnes, alternative], context)[0] in (agnes, alternative)
    assert selector._select_best_tool({**args, "preferred_provider": "agnes"}, [agnes, alternative], context)[0] is agnes
    monkeypatch.setattr(agnes, "get_status", lambda: ToolStatus.UNAVAILABLE)
    assert selector._select_best_tool(args, [agnes, alternative], context)[0] is alternative
    assert selector._select_best_tool({**args, "preferred_provider": "minimax"}, [agnes, alternative], context)[0] is alternative


def test_edit_reference_transport(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return SimpleNamespace(status_code=400)
    monkeypatch.setattr("tools.graphics.agnes_image.requests.post", post)
    result = AgnesImage().execute({"prompt": "edit", "generation_mode": "edit", "image_url": "https://example.org/image.png", "output_path": str(tmp_path / "sample.png")})
    assert not result.success
    assert calls[0]["extra_body"] == {"image": ["https://example.org/image.png"], "response_format": "url"}
    assert "response_format" not in calls[0]


def test_registry_retains_conditional_native_image_route(monkeypatch):
    from tools.tool_registry import ToolRegistry
    registry = ToolRegistry()
    monkeypatch.setattr(registry, "ensure_discovered", lambda: None)
    monkeypatch.setattr(registry, "provider_menu", lambda: {})
    registry.register(AgnesImage())
    registry.register(ImageSelector())
    from tools.video.video_selector import VideoSelector
    registry.register(VideoSelector())
    from tools.audio.tts_selector import TTSSelector
    registry.register(TTSSelector())
    menu = registry.provider_menu_summary()
    assert menu["production_defaults"] == {"image_provider": "auto", "video_provider": "auto", "tts_provider": "auto"}
    native = menu["agent_native_capabilities"][0]
    assert native["tool"] == "image_gen"
    assert native["availability"] == "check_current_session_tool_inventory"
    assert native["python_registry_tool"] is False


def test_explicit_codex_choice_never_submits_agnes(monkeypatch):
    monkeypatch.setattr(ImageSelector, "_providers", lambda self: (_ for _ in ()).throw(AssertionError("no provider discovery or generation for native delegation")))
    result = ImageSelector().execute({"prompt": "test", "preferred_provider": "codex_native"})
    assert not result.success
    assert result.data["error_code"] == "native_tool_required"
    assert result.data["required_tool"] == "image_gen"
    assert result.data["fallback_used"] is False


def _png_response():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 128)).save(buffer, format="PNG")
    return SimpleNamespace(status_code=200, json=lambda: {"data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode()}]})


def test_rate_limit_recovers_without_budget_input(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    responses = [SimpleNamespace(status_code=429, headers={"Retry-After": "5"}), _png_response()]
    calls, delays = [], []
    def post(*args, **kwargs):
        calls.append(kwargs["json"])
        return responses.pop(0)
    monkeypatch.setattr("requests.post", post)
    monkeypatch.setattr("time.sleep", delays.append)
    monkeypatch.setattr(ImageSelector, "_providers", lambda _: [AgnesImage()])
    result = ImageSelector().execute({"prompt": "scene", "preferred_provider": "agnes", "output_path": str(tmp_path / "image.png")})
    assert result.success and len(calls) == 2 and calls[0] == calls[1]
    assert delays == [5] and result.data["provider_request_count"] == 2
    assert result.data["retry_dispatched"] is True


def test_explicit_one_call_limit_and_permanent_errors_do_not_retry(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    calls = []
    def post(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(status_code=429 if len(calls) == 1 else 400)
    monkeypatch.setattr("requests.post", post)
    monkeypatch.setattr("time.sleep", lambda _: (_ for _ in ()).throw(AssertionError("no retry")))
    first = AgnesImage().execute({"prompt": "scene", "max_attempts": 1, "output_path": str(tmp_path / "first.png")})
    second = AgnesImage().execute({"prompt": "scene", "output_path": str(tmp_path / "second.png")})
    assert not first.success and not second.success and len(calls) == 2


def test_empty_response_then_success_and_exhaustion(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr("time.sleep", lambda _: None)
    responses = [SimpleNamespace(status_code=200, json=lambda: {"data": []}), _png_response()]
    monkeypatch.setattr("requests.post", lambda *a, **k: responses.pop(0))
    result = AgnesImage().execute({"prompt": "scene", "output_path": str(tmp_path / "ok.png")})
    assert result.success and result.data["provider_request_count"] == 2
    calls = []
    def empty(*a, **k):
        calls.append(1)
        return SimpleNamespace(status_code=200, json=lambda: {"data": []})
    monkeypatch.setattr("requests.post", empty)
    result = AgnesImage().execute({"prompt": "scene", "output_path": str(tmp_path / "fail.png")})
    assert not result.success and len(calls) == 3


def test_download_recovery_and_resume_never_regenerate(monkeypatch, tmp_path):
    import requests
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr("time.sleep", lambda _: None)
    posts, downloads = [], []
    def post(*a, **k):
        posts.append(1)
        return SimpleNamespace(status_code=200, json=lambda: {"id": "original", "data": [{"url": "https://example.org/original.png"}]})
    monkeypatch.setattr("requests.post", post)
    def unavailable(*a, **k):
        downloads.append(1)
        raise requests.Timeout("download timeout")
    monkeypatch.setattr("requests.get", unavailable)
    args = {"prompt": "scene", "output_path": str(tmp_path / "image.png")}
    assert not AgnesImage().execute(args).success
    assert len(posts) == 1 and len(downloads) == 3
    buffer = io.BytesIO()
    Image.new("RGB", (64, 128)).save(buffer, format="PNG")
    monkeypatch.setattr("requests.get", lambda *a, **k: SimpleNamespace(content=buffer.getvalue(), raise_for_status=lambda: None))
    result = AgnesImage().execute(args)
    assert result.success and len(posts) == 1
    assert result.data["response_id"] == "original"
    assert result.data["download_attempt_count"] == 4


def test_ambiguous_gateway_error_never_resubmits(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    calls = []
    def post(*a, **k):
        calls.append(1)
        return SimpleNamespace(status_code=502, json=lambda: {"id": "pending-task", "error": "gateway"})
    monkeypatch.setattr("requests.post", post)
    result = AgnesImage().execute({"prompt": "scene", "output_path": str(tmp_path / "image.png")})
    assert not result.success and result.data["status"] == "unknown" and len(calls) == 1


def test_known_server_rejection_retries_same_request(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr("time.sleep", lambda _: None)
    responses = [SimpleNamespace(status_code=503, json=lambda: {"error": {"code": "overloaded"}}), _png_response()]
    monkeypatch.setattr("requests.post", lambda *a, **k: responses.pop(0))
    result = AgnesImage().execute({"prompt": "scene", "output_path": str(tmp_path / "image.png")})
    assert result.success and result.data["provider_request_count"] == 2


def test_download_recovers_within_original_call(monkeypatch, tmp_path):
    import requests
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr("time.sleep", lambda _: None)
    posts, gets = [], []
    def post(*a, **k):
        posts.append(1)
        return SimpleNamespace(status_code=200, json=lambda: {"data": [{"url": "https://example.org/image.png"}]})
    def get(*a, **k):
        gets.append(1)
        if len(gets) == 1:
            raise requests.ConnectionError("temporary download failure")
        buffer = io.BytesIO()
        Image.new("RGB", (64, 128)).save(buffer, format="PNG")
        return SimpleNamespace(content=buffer.getvalue(), raise_for_status=lambda: None)
    monkeypatch.setattr("requests.post", post)
    monkeypatch.setattr("requests.get", get)
    result = AgnesImage().execute({"prompt": "scene", "output_path": str(tmp_path / "image.png")})
    assert result.success and len(posts) == 1 and len(gets) == 2
    assert result.data["download_retry_dispatched"]


def test_explicit_native_route_never_discovers_or_submits_python_provider(monkeypatch):
    monkeypatch.setattr(ImageSelector, "_providers", lambda _: (_ for _ in ()).throw(AssertionError("native default must not discover API providers")))
    result = ImageSelector().execute({"prompt": "scene", "preferred_provider": "codex_native"})
    assert not result.success and result.data["required_tool"] == "image_gen"
    assert result.data["selected_provider"] == "codex_native"
    ranked = ImageSelector().execute({"prompt": "scene", "operation": "rank", "preferred_provider": "codex_native"})
    assert ranked.success and ranked.data["rankings"][0]["provider"] == "codex_native"
