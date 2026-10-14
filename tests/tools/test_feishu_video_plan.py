from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from tools.base_tool import ToolStatus
from tools.feishu_base_client import FeishuApiError
from tools.feishu_video_plan import FeishuVideoPlan


class FakeFeishuVideoPlan(FeishuVideoPlan):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.fail_at: str | None = None
        self.structured_error_at: str | None = None
        self.mutate_after_asset_records: Path | None = None
        self.copy_base_token = "base_demo"
        self.copy_url = "https://example.test/base_demo"
        self.copy_tokens: list[str] = []
        self.omit_template_table: str | None = None
        self.link_target = "tbl_assets"
        self.copying_reads_remaining = 0
        self.copy_waits: list[float] = []

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def _prepare(self, identity: str) -> None:
        assert identity in {"user", "bot"}

    def _wait_copy_retry(self, seconds: float) -> None:  # type: ignore[override]
        self.copy_waits.append(seconds)

    def _request(self, command: str, params: dict, project: Path):  # type: ignore[override]
        self.calls.append((command, params))
        if self.fail_at and self.fail_at == command:
            raise TimeoutError("HTTP timeout")
        if self.structured_error_at and self.structured_error_at == command:
            raise FeishuApiError({"type": "authorization", "subtype": "missing_scope", "code": 999, "message": "missing Base scope", "missing_scopes": ["base:base"]})
        if command in {"list_tables", "list_fields"} and self.copying_reads_remaining:
            self.copying_reads_remaining -= 1
            raise FeishuApiError({"type": "server", "message": "base is copying, please try again"})
        if command == "copy_base":
            token = self.copy_tokens.pop(0) if self.copy_tokens else self.copy_base_token
            return {"base": {"base_token": token, "url": self.copy_url}, "copied": True}
        if command == "list_tables":
            rows = [
                {"id": "tbl_overview", "name": self.OVERVIEW},
                {"id": "tbl_assets", "name": self.ASSETS},
                {"id": "tbl_segments", "name": self.SEGMENTS},
            ]
            return {"items": [row for row in rows if row["name"] != self.omit_template_table]}
        if command == "create_table":
            return {"table": {"id": "tbl_assets" if params["name"] == self.ASSETS else "tbl_segments"}}
        if command == "list_fields":
            table = params["table_id"]
            schema = {
                "tbl_overview": self._overview_fields,
                "tbl_assets": self._asset_fields,
                "tbl_segments": self._segment_fields + [("参考资产", "link")],
            }[table]
            fields = [{"name": name, "type": kind, "id": f"fld_{name}"} for name, kind in schema]
            if table == "tbl_segments":
                next(field for field in fields if field["name"] == "参考资产")["property"] = {"table_id": self.link_target}
            return {"fields": fields}
        if command == "create_records":
            rows = params["records"]
            table = params["table_id"]
            prefix = {"tbl_overview": "rec_overview", "tbl_assets": "rec_asset", "tbl_segments": "rec_segment"}[table]
            if table == "tbl_assets" and self.mutate_after_asset_records:
                Image.new("RGB", (2, 2), color=(255, 0, 0)).save(self.mutate_after_asset_records)
            return {"record_id_list": [f"{prefix}_{index}" for index in range(len(rows))]}
        if command == "upload_attachment":
            return {"uploaded": True}
        if command == "grant_user_access":
            return {"status": "granted", "user_open_id": "ou_test"}
        raise AssertionError(command)


def plan() -> dict:
    return {
        "overview": {
            "title": "猫咪咖啡杯视频方案", "product": "猫咪咖啡杯", "audience": "办公室咖啡爱好者",
            "duration": "30秒", "aspect_ratio": "9:16", "visual_direction": "暖阳木桌", "sound_direction": "轻快原声", "storyline": "从晨间静物到人物互动",
        },
        "assets": [
            {"id": "P01", "kind": "产品", "name": "猫咪咖啡杯", "state": "正面", "description": "杯型与猫耳标识", "preparation": "干净产品图"},
            {"id": "R01", "kind": "角色", "name": "小安", "state": "坐姿", "description": "晨间用户", "source": "角色设定"},
        ],
        "segments": [
            {"id": "G01", "name": "晨光开场", "position": "0-10秒", "spec": "9:16，10秒", "shot_ids": ["S01", "S02"],
             "action": "小安拿起咖啡杯，由静到饮用", "references": [{"asset_id": "P01", "role": "产品外观"}, {"asset_id": "R01", "role": "人物身份"}],
             "dialogue": "早晨，也要喝得可爱。", "screen_text": "一杯醒来", "prompt": "暖阳下，小安拿起猫咪咖啡杯并微笑饮用，镜头缓慢推进。", "continuity": "承接桌面静物", "key_image_preparation": "按需合成小安与杯子同框起始画面"},
        ],
    }


def initialize(tool: FakeFeishuVideoPlan, project: Path):
    result = tool.execute({"operation": "initialize", "project_dir": str(project), "identity": "user", "title": "猫咪咖啡杯视频方案"})
    assert result.success, result.error
    return result


def materialize_images(project: Path, value: dict) -> dict:
    image_dir = project / "assets"
    image_dir.mkdir(exist_ok=True)
    for index, asset in enumerate(value["assets"]):
        path = image_dir / f"asset-{index}.png"
        Image.new("RGB", (2, 2), color=(index, 20, 30)).save(path)
        asset["image_path"] = str(path.relative_to(project))
    return value


def test_missing_image_after_initialize_has_zero_additional_cloud_calls(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    initialize(tool, tmp_path)
    initial_calls = len(tool.calls)
    broken = plan()
    broken["assets"][0]["image_path"] = "missing.png"
    result = tool.execute({"operation": "publish", "project_dir": str(tmp_path), "identity": "user", "plan": broken})
    assert not result.success
    assert len(tool.calls) == initial_calls


def test_unknown_reference_after_initialize_has_zero_additional_cloud_calls(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    initialize(tool, tmp_path)
    initial_calls = len(tool.calls)
    broken = materialize_images(tmp_path, plan())
    broken["segments"][0]["references"][0]["asset_id"] = "P404"
    result = tool.execute({"operation": "publish", "project_dir": str(tmp_path), "identity": "user", "plan": broken})
    assert not result.success
    assert len(tool.calls) == initial_calls


def test_empty_references_after_initialize_has_zero_additional_cloud_calls(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    initialize(tool, tmp_path)
    initial_calls = len(tool.calls)
    broken = materialize_images(tmp_path, plan())
    broken["segments"][0]["references"] = []
    result = tool.execute({"operation": "publish", "project_dir": str(tmp_path), "identity": "user", "plan": broken})
    assert not result.success
    assert len(tool.calls) == initial_calls


def test_publish_links_real_record_ids_and_preserves_copy(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    initialize(tool, tmp_path)
    expected = materialize_images(tmp_path, plan())
    result = tool.execute({"operation": "publish", "project_dir": str(tmp_path), "identity": "user", "plan": expected})
    assert result.success, result.error
    payloads = list((tmp_path / "artifacts").glob(".feishu-video-plan-*.json"))
    segment_payload = next(path for path in payloads if any("完整视频提示词" in row for row in json.loads(path.read_text(encoding="utf-8"))["create_records"]))
    row = json.loads(segment_payload.read_text(encoding="utf-8"))["create_records"][0]
    assert row["参考资产"] == [{"id": "rec_asset_0"}, {"id": "rec_asset_1"}]
    assert row["口播对白"] == expected["segments"][0]["dialogue"]
    assert row["完整视频提示词"] == expected["segments"][0]["prompt"]


def test_same_plan_never_repeats_cloud_side_effects(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    initialize(tool, tmp_path)
    request = {"operation": "publish", "project_dir": str(tmp_path), "identity": "user", "plan": materialize_images(tmp_path, plan())}
    assert tool.execute(request).success
    call_count = len(tool.calls)
    repeat = tool.execute(request)
    assert repeat.success and repeat.data["reused"] is True
    assert len(tool.calls) == call_count


def test_timeout_locks_receipt_and_never_retries(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    initialize(tool, tmp_path)
    tool.fail_at = "create_records"
    request = {"operation": "publish", "project_dir": str(tmp_path), "identity": "user", "plan": materialize_images(tmp_path, plan())}
    assert not tool.execute(request).success
    call_count = len(tool.calls)
    followup = tool.execute(request)
    assert not followup.success
    assert "unknown result" in (followup.error or "")
    assert len(tool.calls) == call_count


def test_project_lock_prevents_cross_topic_collision(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / ".feishu-video-plan.lock").write_text("active", encoding="utf-8")
    blocked = tool.execute({"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "A"})
    assert not blocked.success
    assert tool.calls == []
    other = tmp_path.parent / "other-project"
    other.mkdir()
    assert initialize(tool, other).success


def test_title_is_data_and_identity_is_explicit(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    title = 'A "title" ; $not-a-command'
    result = tool.execute({"operation": "initialize", "project_dir": str(tmp_path), "identity": "bot", "title": title})
    assert result.success
    create = tool.calls[0]
    assert create[1]["name"] == title
    assert create[1]["identity"] == "bot"


def test_status_is_local_only():
    tool = FakeFeishuVideoPlan()
    assert tool.get_status() == ToolStatus.AVAILABLE
    assert tool.calls == []


def test_changed_image_content_cannot_reuse_published_plan(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    initialize(tool, tmp_path)
    value = materialize_images(tmp_path, plan())
    request = {"operation": "publish", "project_dir": str(tmp_path), "identity": "user", "plan": value}
    assert tool.execute(request).success
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(tmp_path / value["assets"][0]["image_path"])
    changed = tool.execute(request)
    assert not changed.success
    assert "different plan" in (changed.error or "")


def test_changed_source_after_record_write_never_uploads_attachment(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    initialize(tool, tmp_path)
    value = materialize_images(tmp_path, plan())
    tool.mutate_after_asset_records = tmp_path / value["assets"][0]["image_path"]
    result = tool.execute({"operation": "publish", "project_dir": str(tmp_path), "identity": "user", "plan": value})
    assert not result.success
    assert "changed after plan validation" in (result.error or "")
    assert all(call[0] != "upload_attachment" for call in tool.calls)


def test_known_base_create_response_resumes_without_duplicate_creation(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    receipt = {
        "version": 1, "identity": "user", "title": "猫咪咖啡杯视频方案", "steps": {
            "base-create": {"complete": True, "response": {"base": {"base_token": "base_demo", "url": "https://example.test/base_demo"}, "table": {"id": "tbl_overview"}, "created": True}},
        },
    }
    (artifacts / tool.RECEIPT).write_text(json.dumps(receipt), encoding="utf-8")
    result = initialize(tool, tmp_path)
    assert result.success
    assert all(call[0] != "create_base" for call in tool.calls)
    assert all(call[0] != "copy_base" for call in tool.calls)


def test_structured_api_error_is_preserved_without_identity_fallback(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    tool.structured_error_at = "copy_base"
    result = tool.execute({"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试"})
    assert not result.success
    assert "missing Base scope" in (result.error or "")
    receipt = json.loads((tmp_path / "artifacts" / tool.RECEIPT).read_text(encoding="utf-8"))
    assert receipt["inflight"]["error"]["subtype"] == "missing_scope"
    assert tool.calls[0][1]["identity"] == "user"


def test_actual_v3_base_create_fixture_uses_table_id_not_unrelated_id():
    response = {
        "base": {"base_token": "Wx2HbJupyaVsF6s1bkvcWHkCn3f", "url": "https://my.feishu.cn/base/Wx2"},
        "table": {"id": "tblZYi1nAtRdntWB", "name": "方案总览"},
        "created": True,
        "id": "unrelated-resource-id",
    }
    assert FeishuVideoPlan._parse_base_create(response) == (
        "Wx2HbJupyaVsF6s1bkvcWHkCn3f", "https://my.feishu.cn/base/Wx2", "tblZYi1nAtRdntWB",
    )
    assert FeishuVideoPlan._parse_table_create({"table": {"id": "tblOnly"}, "id": "other"}) == "tblOnly"


def test_base_create_requires_openable_https_url(tmp_path: Path):
    tool = FakeFeishuVideoPlan()

    def missing_url(operation: str, params: dict, project: Path):
        tool.calls.append((operation, params))
        if operation == "copy_base":
            return {"base": {"base_token": "base_demo"}}
        raise AssertionError(operation)

    tool._request = missing_url  # type: ignore[method-assign]
    result = tool.execute({"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试"})
    assert not result.success
    receipt = json.loads((tmp_path / "artifacts" / tool.RECEIPT).read_text(encoding="utf-8"))
    assert receipt["inflight"]["step"] == "base-copy"


def test_initialize_copies_template_once_then_discovers_real_table_ids(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    tool.copy_base_token = "base_new_project"
    result = initialize(tool, tmp_path)
    assert result.data["base_token"] == "base_new_project"
    assert result.data["table_ids"] == {tool.OVERVIEW: "tbl_overview", tool.ASSETS: "tbl_assets", tool.SEGMENTS: "tbl_segments"}
    copy_calls = [call for call in tool.calls if call[0] == "copy_base"]
    assert len(copy_calls) == 1
    assert copy_calls[0][1]["base_token"]
    assert tool.calls[1][0] == "list_tables"
    repeated = initialize(tool, tmp_path)
    assert repeated.data["reused"] is True
    assert len([call for call in tool.calls if call[0] == "copy_base"]) == 1


def test_two_projects_receive_independent_template_copies(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    tool.copy_tokens = ["base_project_one", "base_project_two"]
    first_dir = tmp_path / "one"
    first_dir.mkdir()
    first = initialize(tool, first_dir)
    second_dir = tmp_path / "two"
    second_dir.mkdir()
    second = initialize(tool, second_dir)
    assert first.data["base_token"] != second.data["base_token"]
    assert len([call for call in tool.calls if call[0] == "copy_base"]) == 2


def test_copy_timeout_locks_receipt_and_never_retries(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    tool.fail_at = "copy_base"
    request = {"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试"}
    assert not tool.execute(request).success
    calls = len(tool.calls)
    followup = tool.execute(request)
    assert not followup.success
    assert "unknown result" in (followup.error or "")
    assert len(tool.calls) == calls


def test_copying_base_is_read_again_without_a_second_copy(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    tool.copying_reads_remaining = 1
    result = initialize(tool, tmp_path)
    assert result.success
    assert len([call for call in tool.calls if call[0] == "copy_base"]) == 1
    assert len([call for call in tool.calls if call[0] == "list_tables"]) == 2
    assert tool.copy_waits == [1]


def test_copying_base_timeout_preserves_copy_receipt_without_duplicate(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    tool.COPY_READ_TIMEOUT_SECONDS = 0
    tool.copying_reads_remaining = 1
    request = {"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试"}
    result = tool.execute(request)
    assert not result.success
    assert "still copying" in (result.error or "")
    receipt = json.loads((tmp_path / "artifacts" / tool.RECEIPT).read_text(encoding="utf-8"))
    assert receipt["base_token"] == "base_demo"
    assert not receipt.get("inflight")
    copies = len([call for call in tool.calls if call[0] == "copy_base"])
    assert copies == 1
    followup = tool.execute(request)
    assert followup.success
    assert len([call for call in tool.calls if call[0] == "copy_base"]) == copies


def test_publish_does_not_wait_for_a_template_copy_state(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    initialize(tool, tmp_path)
    tool.copying_reads_remaining = 1
    result = tool.execute({"operation": "publish", "project_dir": str(tmp_path), "identity": "user", "plan": materialize_images(tmp_path, plan())})
    assert not result.success
    assert tool.copy_waits == []
    assert all(call[0] != "create_records" for call in tool.calls)


def test_copied_template_missing_required_table_never_creates_replacement(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    tool.omit_template_table = tool.SEGMENTS
    result = tool.execute({"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试"})
    assert not result.success
    assert "missing a required" in (result.error or "")
    assert all(call[0] != "create_table" for call in tool.calls)


def test_template_schema_failure_never_falls_back_to_a_new_base(tmp_path: Path, monkeypatch):
    broken = tmp_path / "template.json"
    broken.write_text('{"version": 1}', encoding="utf-8")
    monkeypatch.setattr(FeishuVideoPlan, "TEMPLATE_PATH", broken)
    tool = FakeFeishuVideoPlan()
    result = tool.execute({"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试"})
    assert not result.success
    assert tool.calls == []


def test_template_override_is_explicit_and_does_not_change_default(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    result = tool.execute({"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试", "template_base_token": "AlternateTemplate123"})
    assert result.success
    copy = tool.calls[0]
    assert copy[1]["base_token"] == "AlternateTemplate123"
    receipt = json.loads((tmp_path / "artifacts" / tool.RECEIPT).read_text(encoding="utf-8"))
    assert receipt["template"]["base_token"] == "AlternateTemplate123"


def test_template_link_must_target_discovered_asset_table(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    tool.link_target = "tbl_wrong"
    result = tool.execute({"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试"})
    assert not result.success
    assert "link verification" in (result.error or "")


def test_failed_schema_verification_can_never_be_reused_as_initialized(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    tool.link_target = "tbl_wrong"
    request = {"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试"}
    assert not tool.execute(request).success
    initial_calls = len(tool.calls)
    repeated = tool.execute(request)
    assert not repeated.success
    assert "link verification" in (repeated.error or "")
    assert len(tool.calls) > initial_calls
    assert len([call for call in tool.calls if call[0] == "copy_base"]) == 1
    tool.link_target = "tbl_assets"
    recovered = tool.execute(request)
    assert recovered.success
    receipt = json.loads((tmp_path / "artifacts" / tool.RECEIPT).read_text(encoding="utf-8"))
    assert receipt["schema_verified"] is True


def test_existing_project_rejects_changed_template_source(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    assert tool.execute({"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试", "template_base_token": "TemplateOne123"}).success
    calls = len(tool.calls)
    changed = tool.execute({"operation": "initialize", "project_dir": str(tmp_path), "identity": "user", "title": "测试", "template_base_token": "TemplateTwo456"})
    assert not changed.success
    assert "cannot change" in (changed.error or "")
    assert len(tool.calls) == calls


def test_bot_user_grant_is_receipted_once_after_copy(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    request = {"operation": "initialize", "identity": "bot", "project_dir": str(tmp_path), "title": "bot plan"}
    assert tool.execute(request).success
    assert tool.execute(request).success
    assert len([call for call in tool.calls if call[0] == "copy_base"]) == 1
    assert len([call for call in tool.calls if call[0] == "grant_user_access"]) == 1


def test_failed_bot_grant_keeps_copied_base_without_submitting_another(tmp_path: Path):
    tool = FakeFeishuVideoPlan()
    tool.fail_at = "grant_user_access"
    request = {"operation": "initialize", "identity": "bot", "project_dir": str(tmp_path), "title": "bot plan"}
    assert not tool.execute(request).success
    calls = len(tool.calls)
    receipt = json.loads((tmp_path / "artifacts" / tool.RECEIPT).read_text(encoding="utf-8"))
    assert receipt["base_token"] == "base_demo"
    assert receipt["inflight"]["step"] == "grant-user-access"
    assert not tool.execute(request).success
    assert len(tool.calls) == calls
