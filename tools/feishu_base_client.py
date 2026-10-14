"""Python HTTP transport for the video-plan Base v3 operations.

No shell, executable discovery, CLI credential-store access or identity fallback.
The execution environment supplies credentials; a host may inject a refreshing
credential provider without exposing secrets in tool inputs or project receipts.
"""

from __future__ import annotations

import os
import io
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from PIL import Image


class FeishuApiError(RuntimeError):
    """A sanitized failure that may safely be recorded in the project receipt."""

    def __init__(self, detail: dict[str, Any]):
        self.detail = detail
        super().__init__(detail["message"])


@dataclass(frozen=True)
class FeishuCredentials:
    app_id: str
    identity: str
    access_token: str = field(repr=False)
    brand: str = "feishu"
    user_open_id: str = ""


def environment_credentials(identity: str) -> FeishuCredentials:
    """Use only explicit process credentials, never another desktop profile."""
    app_id = os.environ.get("FEISHU_APP_ID", "")
    token_key = {"user": "FEISHU_USER_ACCESS_TOKEN", "bot": "FEISHU_TENANT_ACCESS_TOKEN"}.get(identity)
    token = os.environ.get(token_key, "") if token_key else ""
    if not token and not any(os.environ.get(key) for key in ("FEISHU_USER_ACCESS_TOKEN", "FEISHU_TENANT_ACCESS_TOKEN")):
        from tools.feishu_auth import FeishuAuth, FeishuAuthError

        try:
            auth = FeishuAuth().credentials(identity)
            if app_id and app_id != auth.app_id:
                raise FeishuApiError({"type": "configuration", "message": "Python authorization differs from FEISHU_APP_ID"})
            return auth
        except FeishuAuthError as exc:
            raise FeishuApiError({"type": "configuration", "message": str(exc)}) from None
    if not app_id or not token:
        raise FeishuApiError({"type": "configuration", "message": f"Python Feishu credentials unavailable for {identity}; configure FEISHU_APP_ID and {token_key or 'an explicit identity'}"})
    expected_app = os.environ.get("CODEX_LARK_APP_ID")
    brand = os.environ.get("FEISHU_BRAND", "feishu")
    expected_brand = os.environ.get("CODEX_LARK_TENANT")
    if (expected_app and expected_app != app_id) or (expected_brand and expected_brand != brand):
        raise FeishuApiError({"type": "configuration", "message": "Python Feishu credentials differ from the execution binding"})
    return FeishuCredentials(app_id, identity, token, brand, os.environ.get("FEISHU_USER_OPEN_ID", ""))


class FeishuBaseClient:
    """Restricted Base API adapter; writes are never retried or redirected."""

    SINGLE_PART_LIMIT = 20 * 1024 * 1024
    MAX_ATTACHMENT_BYTES = 2 * 1024 * 1024 * 1024

    def __init__(self, credentials: Callable[[str], FeishuCredentials] = environment_credentials,
                 session: requests.Session | None = None):
        self._credentials = credentials
        self._session = session or requests.Session()
        self._binding: tuple[str, str, str, str] | None = None

    def prepare(self, identity: str) -> FeishuCredentials:
        auth = self._credentials(identity)
        if (identity not in {"user", "bot"} or auth.identity != identity or
                auth.brand not in {"feishu", "lark"} or not auth.app_id or not auth.access_token or
                any(c in auth.app_id + auth.access_token for c in "\r\n")):
            raise FeishuApiError({"type": "configuration", "message": "Python Feishu credentials have an invalid identity or binding"})
        if ((os.environ.get("CODEX_LARK_APP_ID") and os.environ["CODEX_LARK_APP_ID"] != auth.app_id) or
                (os.environ.get("CODEX_LARK_TENANT") and os.environ["CODEX_LARK_TENANT"] != auth.brand)):
            raise FeishuApiError({"type": "configuration", "message": "Python Feishu credentials differ from the execution binding"})
        binding = auth.app_id, auth.identity, auth.brand, auth.user_open_id
        if self._binding is not None and self._binding != binding:
            raise FeishuApiError({"type": "configuration", "message": "Python Feishu credential binding changed during the workflow"})
        self._binding = binding
        return auth

    def available(self) -> bool:
        # Local-only capability discovery must not fetch or refresh credentials.
        if self._credentials is not environment_credentials:
            return True
        from tools.feishu_auth import config_path

        return config_path().is_file() or bool(os.environ.get("FEISHU_APP_ID") and
                    (os.environ.get("FEISHU_USER_ACCESS_TOKEN") or os.environ.get("FEISHU_TENANT_ACCESS_TOKEN")))

    def _http(self, identity: str, method: str, path: str, **payload: Any) -> dict[str, Any]:
        auth = self.prepare(identity)
        host = "https://open.feishu.cn" if auth.brand == "feishu" else "https://open.larksuite.com"
        try:
            response = self._session.request(method, host + path,
                headers={"Authorization": "Bearer " + auth.access_token, "X-App-Id": auth.app_id},
                timeout=(10, 60), allow_redirects=False, **payload)
        except requests.RequestException:
            raise FeishuApiError({"type": "transport", "message": "Feishu HTTP request did not return a trustworthy result"}) from None
        try:
            # OpenAPI JSON is UTF-8 even when an intermediary supplies a
            # legacy text charset. Never decode Chinese fields through it.
            response.encoding = "utf-8"
            envelope = response.json()
        except ValueError:
            raise FeishuApiError({"type": "protocol", "message": "Feishu returned non-JSON"}) from None
        if not isinstance(envelope, dict):
            raise FeishuApiError({"type": "protocol", "message": "Feishu returned an invalid response"})
        if not 200 <= response.status_code < 300 or type(envelope.get("code")) is not int or envelope["code"] != 0:
            # Do not persist response bodies, headers or arbitrary server text.
            # Only this documented transient state is needed by the copy poller.
            code = envelope.get("code")
            message = "base is copying" if code == 1254036 else "Feishu API request failed"
            detail = {"type": "api", "message": message, "http_status": response.status_code}
            if type(code) is int:
                detail["code"] = code
            raise FeishuApiError(detail)
        data = envelope.get("data")
        if not isinstance(data, dict):
            raise FeishuApiError({"type": "protocol", "message": "Feishu response omitted data"})
        return data

    @staticmethod
    def _path(*parts: str) -> str:
        return "/open-apis/base/v3/" + "/".join(quote(part, safe="") for part in parts)

    def _list(self, identity: str, path: str, key: str) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        offset = 0
        for _ in range(100):
            data = self._http(identity, "GET", path, params={"offset": offset, "limit": 100})
            page = data.get("items", data.get(key))
            if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
                raise FeishuApiError({"type": "protocol", "message": "Feishu list response omitted items"})
            rows.extend(page)
            total = data.get("total")
            more = data.get("has_more") is True or (type(total) is int and len(rows) < total)
            if not more:
                return {key: rows}
            if not page:
                break
            offset += len(page)
        raise FeishuApiError({"type": "protocol", "message": "Feishu pagination did not terminate"})

    def call(self, operation: str, params: dict[str, Any], project: Path) -> dict[str, Any]:
        identity = params["identity"]
        base = params["base_token"]
        if operation == "copy_base":
            data = self._http(identity, "POST", self._path("bases", base, "copy"),
                json={"name": params["name"], "without_content": True, "time_zone": "Asia/Shanghai"})
            return {"base": data, "copied": True}
        if operation == "list_tables":
            return self._list(identity, self._path("bases", base, "tables"), "tables")
        if operation == "grant_user_access":
            recipient = self.prepare(identity).user_open_id
            if identity != "bot" or not recipient:
                raise ValueError("bot Base copy requires an explicitly bound user recipient")
            data = self._http(identity, "POST", "/open-apis/drive/v1/permissions/" + quote(base, safe="") + "/members",
                params={"type": "bitable", "need_notification": "false"},
                json={"member_type": "openid", "member_id": recipient, "perm": "full_access", "type": "user"})
            return {"status": "granted", "user_open_id": recipient, "response": data}
        if operation == "create_table":
            fields = [{"name": item["name"], "type": item["type"],
                       **({"property": {"table_id": item["link_table"]}} if item["type"] == "link" else {})}
                      for item in params["fields"]]
            data = self._http(identity, "POST", self._path("bases", base, "tables"),
                json={"name": params["name"], "fields": fields})
            return {"table": data}
        table = params["table_id"]
        if operation == "list_fields":
            return self._list(identity, self._path("bases", base, "tables", table, "fields"), "fields")
        if operation == "create_records":
            return self._http(identity, "POST", self._path("bases", base, "tables", table, "records", "batch_create"),
                json={"create_records": params["records"]})
        if operation == "get_records":
            return self._http(identity, "POST", self._path("bases", base, "tables", table, "records", "batch_get"),
                json={"record_id_list": params["record_ids"]})
        if operation == "upload_attachment":
            return self._upload(identity, base, table, params, project)
        raise ValueError("unsupported Python Feishu operation")

    def _upload(self, identity: str, base: str, table: str, params: dict[str, Any], project: Path) -> dict[str, Any]:
        path = (project / params["file"]).resolve()
        if not path.is_relative_to(project.resolve()) or not path.is_file():
            raise ValueError("attachment must be an existing project file")
        size = path.stat().st_size
        if not 0 < size <= self.MAX_ATTACHMENT_BYTES:
            raise ValueError("reference image must be non-empty and at most 2 GiB")
        with Image.open(path) as image:
            width, height = image.size
        with path.open("rb") as stream:
            if size <= self.SINGLE_PART_LIMIT:
                media = self._http(identity, "POST", "/open-apis/drive/v1/medias/upload_all",
                    data={"file_name": path.name, "parent_type": "bitable_file", "parent_node": base, "size": str(size)},
                    files={"file": (path.name, stream)})
            else:
                upload = self._http(identity, "POST", "/open-apis/drive/v1/medias/upload_prepare",
                    json={"file_name": path.name, "parent_type": "bitable_file", "parent_node": base, "size": size})
                block_size, block_num, upload_id = upload.get("block_size"), upload.get("block_num"), upload.get("upload_id")
                if (type(block_size) is not int or not 0 < block_size <= 20 * 1024 * 1024 or
                        type(block_num) is not int or block_num != (size + block_size - 1) // block_size or
                        not isinstance(upload_id, str) or not upload_id):
                    raise FeishuApiError({"type": "protocol", "message": "Feishu multipart plan is invalid"})
                for seq in range(block_num):
                    chunk = stream.read(block_size)
                    if len(chunk) != min(block_size, size - seq * block_size):
                        raise ValueError("reference image changed during multipart upload")
                    self._http(identity, "POST", "/open-apis/drive/v1/medias/upload_part",
                        data={"upload_id": upload_id, "seq": str(seq), "size": str(len(chunk))},
                        files={"file": (path.name, io.BytesIO(chunk))})
                media = self._http(identity, "POST", "/open-apis/drive/v1/medias/upload_finish",
                    json={"upload_id": upload_id, "block_num": block_num})
        token = media.get("file_token")
        if not isinstance(token, str) or not token:
            raise FeishuApiError({"type": "protocol", "message": "Feishu upload omitted file_token"})
        attachment = {"file_token": token, "image_width": width, "image_height": height}
        data = self._http(identity, "POST", self._path("bases", base, "tables", table, "append_attachments"),
            json={"attachments": {params["record_id"]: {params["field_id"]: [attachment]}}})
        return {**data, "uploaded": True, "file_token": token}
