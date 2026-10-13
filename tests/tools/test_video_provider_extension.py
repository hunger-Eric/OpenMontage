"""Selected-provider request-adapter coverage for the video selector."""

from __future__ import annotations

from typing import Any

import pytest

from tools.base_tool import BaseTool, ToolResult, ToolRuntime, ToolStability, ToolStatus, ToolTier
from tools.video.video_selector import VideoSelector


class _FakeProvider(BaseTool):
    name = "fake_mcp_video"
    version = "test"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "fake_mcp"
    stability = ToolStability.BETA
    runtime = ToolRuntime.API
    supports = {"text_to_video": True, "image_to_video": True}
    input_schema = {"properties": {
        "prompt": {},
        "model": {"enum": ["locked-model", "fixed", "locked"]},
        "model_id": {"enum": ["fixed", "other"]},
        "image_url": {},
    }}

    def __init__(self, prepare=None) -> None:  # noqa: ANN001
        self._prepare = prepare
        self.calls: list[dict[str, Any]] = []

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def prepare_video_request(self, inputs: dict[str, object]) -> dict[str, object]:
        if self._prepare is None:
            return inputs
        return self._prepare(inputs)

    def execute(self, inputs: dict[str, object]) -> ToolResult:
        self.calls.append(inputs)
        return ToolResult(
            success=True,
            data={"native_receipt": {"job_id": "native-1"}, "model": "native-model"},
            model="result-model",
        )


class _LegacyProvider(_FakeProvider):
    name = "legacy_api_video"
    provider = "legacy_api"
    prepare_video_request = None  # type: ignore[assignment]


class _MutatingLegacyProvider(_LegacyProvider):
    def execute(self, inputs: dict[str, object]) -> ToolResult:
        inputs["task_context"]["scene"]["id"] = "provider-mutated"  # type: ignore[index]
        return ToolResult(success=True)


class _NoModelResultProvider(_FakeProvider):
    def execute(self, inputs: dict[str, object]) -> ToolResult:
        self.calls.append(inputs)
        return ToolResult(success=True, data={"native_receipt": {"job_id": "native-2"}})


class _Score:
    tool_name = "fake_mcp_video"
    provider = "fake_mcp"
    weighted_score = 1.0

    def explain(self) -> str:
        return "fake selected"

    def to_dict(self) -> dict[str, object]:
        return {"tool_name": self.tool_name, "provider": self.provider, "weighted_score": self.weighted_score}


class _ExplosiveEquality:
    def __eq__(self, other):  # noqa: ANN001
        raise RuntimeError("comparison details must not escape")


@pytest.fixture()
def selector(monkeypatch):  # noqa: ANN001
    def rank(candidates, context):  # noqa: ANN001
        score = _Score()
        score.tool_name = candidates[0].name
        score.provider = candidates[0].provider
        return [score]

    monkeypatch.setattr("lib.scoring.rank_providers", rank)
    return VideoSelector()


def _select(selector: VideoSelector, provider: BaseTool) -> None:
    selector._providers = lambda: [provider]  # type: ignore[assignment]


def test_selected_provider_hook_adds_alias_before_generic_upload(selector, monkeypatch, tmp_path):
    reference = tmp_path / "source.jpg"
    reference.write_bytes(b"image")
    def prepare(values):  # noqa: ANN001
        return {**values, "image_url": "https://provider.example/image.jpg"}

    provider = _FakeProvider(prepare)
    _select(selector, provider)
    monkeypatch.setattr("tools.video._shared.upload_image_fal", lambda path: pytest.fail("generic upload must be skipped"))

    result = selector.execute({
        "prompt": "motion", "operation": "image_to_video", "reference_image_path": str(reference),
        "model": "locked-model", "idempotency_key": "attempt-1",
    })

    assert result.success
    assert provider.calls == [{
        "prompt": "motion", "operation": "image_to_video", "reference_image_path": str(reference),
        "model": "locked-model", "idempotency_key": "attempt-1",
        "image_url": "https://provider.example/image.jpg",
    }]
    assert result.data["selected_tool"] == provider.name
    assert result.data["selected_provider"] == provider.provider
    assert result.data["selected_model"] == "result-model"
    assert result.data["native_receipt"] == {"job_id": "native-1"}


def test_legacy_provider_keeps_original_fields_and_nested_caller_inputs(selector):
    provider = _LegacyProvider()
    _select(selector, provider)
    request = {"prompt": "motion", "model": "fixed", "task_context": {"scene": {"id": "s-1"}}}

    result = selector.execute(request)

    assert result.success
    assert provider.calls == [request]
    assert request == {"prompt": "motion", "model": "fixed", "task_context": {"scene": {"id": "s-1"}}}


def test_selected_model_falls_back_to_model_id_when_native_result_omits_model(selector):
    provider = _NoModelResultProvider()
    _select(selector, provider)

    result = selector.execute({"prompt": "motion", "model_id": "fixed"})

    assert result.success
    assert result.data["selected_model"] == "fixed"


def test_provider_execute_cannot_mutate_nested_caller_inputs(selector):
    provider = _MutatingLegacyProvider()
    _select(selector, provider)
    request = {"prompt": "motion", "model": "fixed", "task_context": {"scene": {"id": "s-1"}}}

    assert selector.execute(request).success
    assert request["task_context"]["scene"]["id"] == "s-1"


def test_hook_cannot_remove_or_mutate_nested_existing_input(selector):
    def prepare(values):  # noqa: ANN001
        values["task_context"]["scene"]["id"] = "hook-mutated"
        del values["idempotency_key"]
        return values

    provider = _FakeProvider(prepare)
    _select(selector, provider)
    request = {
        "prompt": "motion", "model": "locked", "idempotency_key": "attempt-1",
        "task_context": {"scene": {"id": "s-1"}},
    }

    result = selector.execute(request)

    assert not result.success
    assert provider.calls == []
    assert request["task_context"]["scene"]["id"] == "s-1"


def test_hook_comparison_error_is_a_closed_failure(selector):
    provider = _FakeProvider(lambda values: values)
    _select(selector, provider)

    result = selector.execute({"prompt": "motion", "model": "locked", "opaque": _ExplosiveEquality()})

    assert not result.success
    assert provider.calls == []
    assert "comparison details" not in (result.error or "")


@pytest.mark.parametrize("field, value", [
    ("model", "other"),
    ("model_id", "other"),
    ("model_name", "other"),
    ("model_variant", "other"),
    ("preferred_tool", "other_video"),
    ("preferred_provider", "other"),
    ("hosting_provider", "other-host"),
    ("allowed_providers", ["other"]),
    ("attempt_id", "other-attempt"),
    ("idempotency_key", "other-key"),
])
def test_hook_cannot_add_or_change_frozen_request_identity(selector, field, value):  # noqa: ANN001
    provider = _FakeProvider(lambda values: {**values, field: value})
    _select(selector, provider)

    result = selector.execute({"prompt": "motion", "model": "locked"})

    assert not result.success
    assert provider.calls == []
    assert result.data["fallback_used"] is False


def test_fixed_model_rejects_conflicting_model_id_before_hook(selector):
    called = False

    def prepare(values):  # noqa: ANN001
        nonlocal called
        called = True
        return values

    provider = _FakeProvider(prepare)
    provider.supports = {
        "text_to_video": True,
        "image_to_video": True,
        "usage_conditions": {"fixed_model": "fixed"},
    }
    _select(selector, provider)

    result = selector.execute({"prompt": "motion", "model_id": "other"})

    assert not result.success
    assert "model_id=other" in (result.error or "")
    assert not called
    assert provider.calls == []


@pytest.mark.parametrize("prepare", [
    lambda values: [values],
    lambda values: {**values, "model": "changed"},
    lambda values: (_ for _ in ()).throw(RuntimeError("secret=value")),
])
def test_invalid_or_failing_hook_does_not_execute_or_fallback(selector, prepare):  # noqa: ANN001
    provider = _FakeProvider(prepare)
    _select(selector, provider)

    result = selector.execute({"prompt": "motion", "model": "locked"})

    assert not result.success
    assert provider.calls == []
    assert result.data == {
        "selected_tool": provider.name,
        "selected_provider": provider.provider,
        "selected_model": "locked",
        "fallback_used": False,
    }
    assert "secret" not in (result.error or "")
