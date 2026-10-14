from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from PIL import Image

from tools.base_tool import ToolStatus
from tools.feishu_base_client import FeishuApiError, FeishuBaseClient, FeishuCredentials
from tools.feishu_video_plan import FeishuVideoPlan


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        if "files" in kwargs:
            kwargs["file_bytes"] = kwargs["files"]["file"][1].read()
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(status_code=response[0], json=lambda: response[1])


def ok(data):
    return 200, {"code": 0, "data": data}


def client(session, identity="user", brand="feishu"):
    return FeishuBaseClient(lambda selected: FeishuCredentials("cli_test", identity, "test-secret", brand), session)


def test_python_http_works_without_path_or_any_native_command(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("native command discovery/execution is forbidden")

    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(shutil, "which", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    session = Session(ok({"tables": [{"id": "tbl_one", "name": "表一"}], "total": 1}))
    tool = FeishuVideoPlan(client(session))
    assert tool._request("list_tables", {"identity": "user", "base_token": "base_one"}, tmp_path) == {
        "tables": [{"id": "tbl_one", "name": "表一"}]}
    method, url, options = session.calls[0]
    assert method == "GET"
    assert url == "https://open.feishu.cn/open-apis/base/v3/bases/base_one/tables"
    assert options["headers"] == {"Authorization": "Bearer test-secret", "X-App-Id": "cli_test"}
    assert options["allow_redirects"] is False
    assert options["timeout"] == (10, 60)


def test_copy_uses_json_not_shell_and_preserves_template_and_title(tmp_path):
    session = Session(ok({"base_token": "new", "url": "https://example.test/new"}))
    title = '中文 "title" ; $(not-a-command)'
    result = client(session).call("copy_base", {"identity": "user", "base_token": "old", "name": title}, tmp_path)
    assert result["base"]["base_token"] == "new"
    assert session.calls[0][0] == "POST"
    assert session.calls[0][1].endswith("/bases/old/copy")
    assert session.calls[0][2]["json"] == {"name": title, "without_content": True, "time_zone": "Asia/Shanghai"}


def test_v3_batch_values_and_order_are_preserved(tmp_path):
    session = Session(ok({"record_id_list": ["rec_one", "rec_two"]}))
    rows = [{"台词": "原文", "参考资产": [{"id": "rec_asset"}]}, {"台词": "第二段"}]
    result = client(session).call("create_records", {"identity": "user", "base_token": "base", "table_id": "tbl", "records": rows}, tmp_path)
    assert result == {"record_id_list": ["rec_one", "rec_two"]}
    assert session.calls[0][1].endswith("/tables/tbl/records/batch_create")
    assert session.calls[0][2]["json"] == {"create_records": rows}


def test_real_v3_batch_get_matrix_is_preserved(tmp_path):
    matrix = {"record_id_list": ["rec_one"], "field_id_list": ["fld_image"],
              "field_type_list": ["attachment"], "fields": ["实际图片"],
              "data": [[[{"file_token": "uploaded_file", "size": 341}]]], "has_more": False}
    session = Session(ok(matrix))
    result = client(session).call("get_records", {"identity": "user", "base_token": "base",
        "table_id": "tbl", "record_ids": ["rec_one"]}, tmp_path)
    assert result == matrix
    assert session.calls[0][2]["json"] == {"record_id_list": ["rec_one"]}


def test_utf8_chinese_fields_survive_a_legacy_response_charset(tmp_path):
    response = requests.Response()
    response.status_code = 200
    response.encoding = "ISO-8859-1"
    response._content = json.dumps({"code": 0, "data": {"tables": [{"id": "tbl", "name": "参考资产"}]}}, ensure_ascii=False).encode("utf-8")
    session = SimpleNamespace(request=lambda *args, **kwargs: response)
    assert client(session).call("list_tables", {"identity": "user", "base_token": "base"}, tmp_path)["tables"][0]["name"] == "参考资产"


def test_pagination_reads_every_field_before_schema_validation(tmp_path):
    session = Session(ok({"items": [{"id": "one"}], "has_more": True}), ok({"items": [{"id": "two"}], "has_more": False}))
    result = client(session).call("list_fields", {"identity": "user", "base_token": "base", "table_id": "tbl"}, tmp_path)
    assert result == {"fields": [{"id": "one"}, {"id": "two"}]}
    assert [call[2]["params"]["offset"] for call in session.calls] == [0, 1]


def test_upload_sends_actual_image_then_appends_returned_token(tmp_path):
    path = tmp_path / "参考图.png"
    Image.new("RGB", (13, 17), "red").save(path)
    session = Session(ok({"file_token": "file_real"}), ok({}))
    result = client(session).call("upload_attachment", {"identity": "user", "base_token": "base", "table_id": "tbl", "record_id": "rec", "field_id": "fld", "file": path.name}, tmp_path)
    assert result["file_token"] == "file_real"
    assert session.calls[0][2]["file_bytes"] == path.read_bytes()
    assert session.calls[0][2]["data"] == {"file_name": path.name, "parent_type": "bitable_file", "parent_node": "base", "size": str(path.stat().st_size)}
    assert session.calls[1][1].endswith("/tables/tbl/append_attachments")
    assert session.calls[1][2]["json"] == {"attachments": {"rec": {"fld": [{"file_token": "file_real", "image_width": 13, "image_height": 17}]}}}


def test_upload_timeout_never_retries_or_appends(tmp_path):
    Image.new("RGB", (2, 2)).save(tmp_path / "ref.png")
    session = Session(requests.Timeout("test-secret"))
    with pytest.raises(FeishuApiError, match="trustworthy") as failure:
        client(session).call("upload_attachment", {"identity": "user", "base_token": "base", "table_id": "tbl", "record_id": "rec", "field_id": "fld", "file": "ref.png"}, tmp_path)
    assert "test-secret" not in str(failure.value)
    assert len(session.calls) == 1


@pytest.mark.parametrize("response", [(403, {"code": 99991672, "msg": "Bearer test-secret"}), (302, {"code": 0, "data": {}}), (200, {"code": 0}), (200, [])])
def test_invalid_or_rejected_responses_fail_once_without_secrets(tmp_path, response):
    session = Session(response)
    with pytest.raises(FeishuApiError) as failure:
        client(session).call("list_tables", {"identity": "user", "base_token": "base"}, tmp_path)
    assert len(session.calls) == 1
    assert "test-secret" not in json.dumps(failure.value.detail)


def test_copying_error_keeps_the_documented_transient_code(tmp_path):
    session = Session((400, {"code": 1254036, "msg": "arbitrary server content"}))
    with pytest.raises(FeishuApiError, match="base is copying") as failure:
        client(session).call("list_tables", {"identity": "user", "base_token": "base"}, tmp_path)
    assert failure.value.detail["code"] == 1254036


def test_missing_selected_identity_fails_before_receipt_or_network(tmp_path, monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.delenv("FEISHU_USER_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("FEISHU_TENANT_ACCESS_TOKEN", "bot-only-token")
    session = Session()
    tool = FeishuVideoPlan(FeishuBaseClient(session=session))
    result = tool.execute({"operation": "initialize", "identity": "user", "project_dir": str(tmp_path), "title": "title"})
    assert not result.success
    assert "credentials unavailable for user" in result.error
    assert not (tmp_path / "artifacts").exists()
    assert session.calls == []


def test_explicit_execution_app_binding_cannot_be_overridden(tmp_path, monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "other_app")
    monkeypatch.setenv("FEISHU_USER_ACCESS_TOKEN", "test-secret")
    monkeypatch.setenv("CODEX_LARK_APP_ID", "bound_app")
    session = Session()
    tool = FeishuVideoPlan(FeishuBaseClient(session=session))
    result = tool.execute({"operation": "initialize", "identity": "user", "project_dir": str(tmp_path), "title": "title"})
    assert not result.success and "execution binding" in result.error
    assert session.calls == []


def test_provider_cannot_switch_identity(tmp_path):
    session = Session()
    with pytest.raises(FeishuApiError, match="invalid identity"):
        client(session, "bot").call("list_tables", {"identity": "user", "base_token": "base"}, tmp_path)
    assert session.calls == []


def test_refreshing_provider_cannot_switch_application_mid_operation(tmp_path):
    values = iter([FeishuCredentials("one", "user", "first-token"), FeishuCredentials("two", "user", "second-token")])
    session = Session(ok({"items": [{"id": "one"}], "has_more": True}))
    api = FeishuBaseClient(lambda identity: next(values), session)
    with pytest.raises(FeishuApiError, match="binding changed"):
        api.call("list_tables", {"identity": "user", "base_token": "base"}, tmp_path)
    assert len(session.calls) == 1


def test_lark_brand_uses_its_own_official_origin(tmp_path):
    session = Session(ok({"tables": [], "total": 0}))
    client(session, brand="lark").call("list_tables", {"identity": "user", "base_token": "base"}, tmp_path)
    assert session.calls[0][1].startswith("https://open.larksuite.com/")


def test_capability_status_never_calls_credential_provider():
    def forbidden(identity):
        raise AssertionError("discovery must remain local")

    assert FeishuVideoPlan(FeishuBaseClient(forbidden)).get_status() == ToolStatus.AVAILABLE


def test_credentials_are_not_exposed_in_repr():
    assert "test-secret" not in repr(FeishuCredentials("cli_test", "user", "test-secret"))


def test_multipart_uses_server_chunk_plan_and_appends_only_after_finish(tmp_path, monkeypatch):
    path = tmp_path / "ref.png"
    Image.new("RGB", (13, 17), "red").save(path)
    content = path.read_bytes()
    block_size = len(content) // 2
    count = (len(content) + block_size - 1) // block_size
    session = Session(ok({"upload_id": "upload_one", "block_size": block_size, "block_num": count}),
                      *[ok({}) for _ in range(count)], ok({"file_token": "large_real"}), ok({}))
    api = client(session)
    monkeypatch.setattr(api, "SINGLE_PART_LIMIT", 1)
    api.call("upload_attachment", {"identity": "user", "base_token": "base", "table_id": "tbl", "record_id": "rec", "field_id": "fld", "file": path.name}, tmp_path)
    parts = [call for call in session.calls if call[1].endswith("/upload_part")]
    assert b"".join(call[2]["file_bytes"] for call in parts) == content
    assert [call[2]["data"]["seq"] for call in parts] == [str(i) for i in range(count)]
    assert session.calls[-2][1].endswith("/upload_finish")
    assert session.calls[-1][2]["json"]["attachments"]["rec"]["fld"][0]["file_token"] == "large_real"


def test_bot_preflight_rejects_missing_user_before_copy(tmp_path):
    session = Session()
    tool = FeishuVideoPlan(client(session, "bot"))
    result = tool.execute({"operation": "initialize", "identity": "bot", "project_dir": str(tmp_path), "title": "title"})
    assert not result.success and "explicitly bound user recipient" in result.error
    assert session.calls == [] and not (tmp_path / "artifacts").exists()


def test_bot_grants_only_the_bound_user_without_notification(tmp_path):
    session = Session(ok({"member": {"member_id": "ou_bound"}}))
    api = FeishuBaseClient(lambda identity: FeishuCredentials("cli_test", "bot", "bot-token", "feishu", "ou_bound"), session)
    result = api.call("grant_user_access", {"identity": "bot", "base_token": "copied"}, tmp_path)
    assert result["status"] == "granted"
    method, url, options = session.calls[0]
    assert method == "POST" and url.endswith("/permissions/copied/members")
    assert options["params"] == {"type": "bitable", "need_notification": "false"}
    assert options["json"] == {"member_type": "openid", "member_id": "ou_bound", "perm": "full_access", "type": "user"}
