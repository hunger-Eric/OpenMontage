"""Exercise the real requests encoder and project receipt across a local server."""
from __future__ import annotations

import io
import json
import math
import shutil
import subprocess
import threading
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
import requests
from PIL import Image

from tools.feishu_base_client import FeishuBaseClient, FeishuCredentials
from tools.feishu_video_plan import FeishuVideoPlan
from tests.tools.test_feishu_video_plan import materialize_images, plan


@pytest.fixture
def local_base():
    state = {"calls": [], "records": {}, "files": {}, "parts": [], "append": [], "errors": [], "fail_append": False}
    schemas = {
        "overview": FeishuVideoPlan._overview_fields,
        "assets": FeishuVideoPlan._asset_fields,
        "segments": FeishuVideoPlan._segment_fields + [("参考资产", "link")],
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            try:
                assert self.headers["Authorization"] == "Bearer synthetic-user-token"
                assert self.headers["X-App-Id"] == "cli_local_test"
                path = urlsplit(self.path).path
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                body = json.loads(raw) if raw and "application/json" in self.headers.get("Content-Type", "") else None
                state["calls"].append((self.command, path))
                if self.command == "GET" and path.endswith("/tables"):
                    data = {"tables": [{"id": key, "name": name} for key, name in
                        zip(schemas, ["方案总览", "参考资产", "生成片段"], strict=True)], "total": 3}
                elif self.command == "GET" and path.endswith("/fields"):
                    table = path.split("/")[-2]
                    data = {"fields": [{"id": name, "name": name, "type": kind,
                        **({"property": {"table_id": "assets"}} if kind == "link" else {})}
                        for name, kind in schemas[table]]}
                elif path.endswith("/copy"):
                    assert body["without_content"] is True
                    data = {"base_token": "new_base", "url": "https://example.test/new_base"}
                elif path.endswith("/records/batch_create"):
                    table = path.split("/")[-3]
                    state["records"][table] = body["create_records"]
                    data = {"record_id_list": [f"{table}_{i}" for i in range(len(body["create_records"]))]}
                elif path.endswith("/upload_prepare"):
                    state["upload_name"] = body["file_name"]
                    state["parts"] = []
                    data = {"upload_id": "upload_local", "block_size": 32, "block_num": math.ceil(body["size"] / 32)}
                elif path.endswith(("/upload_all", "/upload_part")):
                    mime = BytesParser(policy=default).parsebytes(
                        ("Content-Type: " + self.headers["Content-Type"] + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + raw)
                    fields = {part.get_param("name", header="content-disposition"): part.get_payload(decode=True)
                              for part in mime.iter_parts()}
                    assert int(fields["size"]) == len(fields["file"])
                    if path.endswith("/upload_part"):
                        assert int(fields["seq"]) == len(state["parts"])
                        state["parts"].append(fields["file"])
                        data = {}
                    else:
                        assert fields["parent_type"] == b"bitable_file" and fields["parent_node"] == b"new_base"
                        token = "file_" + str(len(state["files"]))
                        state["files"][token] = fields["file"]
                        data = {"file_token": token}
                elif path.endswith("/upload_finish"):
                    assert body["block_num"] == len(state["parts"])
                    token = "file_" + str(len(state["files"]))
                    state["files"][token] = b"".join(state["parts"])
                    data = {"file_token": token}
                elif path.endswith("/append_attachments"):
                    if state["fail_append"]:
                        self.send_envelope(503, {"code": 999, "msg": "test failure"})
                        return
                    for fields in body["attachments"].values():
                        for attachments in fields.values():
                            for attachment in attachments:
                                with Image.open(io.BytesIO(state["files"][attachment["file_token"]])) as image:
                                    assert image.size == (attachment["image_width"], attachment["image_height"])
                    state["append"].append(body)
                    data = {}
                else:
                    raise AssertionError((self.command, path))
                self.send_envelope(200, {"code": 0, "data": data})
            except Exception as error:
                state["errors"].append(str(error))
                self.send_envelope(500, {"code": 1, "msg": "local fixture rejected request"})

        def send_envelope(self, status, data):
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    class LoopbackSession(requests.Session):
        def request(self, method, url, **kwargs):
            parsed = urlsplit(url)
            assert parsed.scheme == "https" and parsed.netloc == "open.feishu.cn"
            assert kwargs["allow_redirects"] is False
            return super().request(method, f"http://127.0.0.1:{server.server_port}" + parsed.path, **kwargs)

    session = LoopbackSession()
    session.trust_env = False
    client = FeishuBaseClient(lambda identity: FeishuCredentials("cli_local_test", identity, "synthetic-user-token"), session)
    try:
        yield client, state
    finally:
        session.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("multipart", [False, True])
def test_project_publish_uses_python_http_and_preserves_images_and_references(tmp_path, monkeypatch, local_base, multipart):
    client, state = local_base
    if multipart:
        client.SINGLE_PART_LIMIT = 1
    tool = FeishuVideoPlan(client)
    value = materialize_images(tmp_path, plan())
    expected_images = [(tmp_path / asset["image_path"]).read_bytes() for asset in value["assets"]]

    def forbidden(*args, **kwargs):
        raise AssertionError("native command discovery/execution forbidden")

    monkeypatch.setattr(shutil, "which", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    initialized = tool.execute({"operation": "initialize", "identity": "user", "project_dir": str(tmp_path), "title": "中文方案"})
    assert initialized.success, initialized.error
    request = {"operation": "publish", "identity": "user", "project_dir": str(tmp_path), "plan": value}
    result = tool.execute(request)
    assert result.success, result.error
    assert state["errors"] == []
    assert list(state["files"].values()) == expected_images
    assert len(state["append"]) == 2
    assert state["records"]["segments"][0]["参考资产"] == [{"id": "assets_0"}, {"id": "assets_1"}]
    assert state["records"]["segments"][0]["完整视频提示词"] == value["segments"][0]["prompt"]
    count = len(state["calls"])
    assert tool.execute(request).success
    assert len(state["calls"]) == count


def test_partial_upload_failure_is_locked_without_a_duplicate_http_request(tmp_path, local_base):
    client, state = local_base
    tool = FeishuVideoPlan(client)
    assert tool.execute({"operation": "initialize", "identity": "user", "project_dir": str(tmp_path), "title": "方案"}).success
    state["fail_append"] = True
    request = {"operation": "publish", "identity": "user", "project_dir": str(tmp_path), "plan": materialize_images(tmp_path, plan())}
    assert not tool.execute(request).success
    receipt = json.loads((tmp_path / "artifacts" / tool.RECEIPT).read_text(encoding="utf-8"))
    assert receipt["inflight"]["step"] == "attachment:P01"
    count = len(state["calls"])
    assert not tool.execute(request).success
    assert len(state["calls"]) == count and len(state["files"]) == 1
    assert state["errors"] == []
