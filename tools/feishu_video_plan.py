"""Publish a locked video plan to one isolated Feishu Base per project.

This is deliberately a small mechanical adapter.  It does not invent a plan,
choose a video model, or replace the existing Feishu bridge.  The caller first
creates a complete plan, then this tool creates (once) and fills its three
tables through the Python Base v3 HTTP client.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from tools.feishu_base_client import FeishuApiError, FeishuBaseClient

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class FeishuVideoPlan(BaseTool):
    """Create and publish an OpenMontage video-plan Base without silent retries."""

    name = "feishu_video_plan"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "publish"
    provider = "feishu_base"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API
    dependencies = ["python:requests", "python:keyring"]
    install_instructions = "Authorize the Python Feishu client for the same application and user, or inject explicit identity-bound credentials."
    agent_skills = ["ai-video-gen"]
    capabilities = ["initialize_video_plan_base", "publish_video_plan"]
    supports = {"operations": ["initialize", "publish"], "isolated_project_base": True}
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, disk_mb=8, network_required=True)
    side_effects = ["copies an isolated Feishu Base template", "creates Base records", "uploads supplied attachments"]
    user_visible_verification = ["Open the returned Base URL and inspect the copied video-plan board and three plan tables."]

    OVERVIEW = "方案总览"
    ASSETS = "参考资产"
    SEGMENTS = "生成片段"
    RECEIPT = "feishu-video-plan-delivery.json"
    TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "docs" / "templates" / "feishu-video-plan-base.json"
    COPY_READ_TIMEOUT_SECONDS = 20
    COPY_READ_INTERVAL_SECONDS = 1

    _overview_fields = [
        ("标题", "text"), ("产品", "text"), ("受众", "text"), ("总时长", "text"),
        ("画幅", "text"), ("视觉方向", "text"), ("声音方向", "text"), ("故事主线", "text"),
    ]
    _asset_fields = [
        ("资产编号", "text"), ("类型", "text"), ("名称", "text"), ("角度状态", "text"),
        ("设定用途", "text"), ("来源或图片准备提示", "text"), ("实际图片", "attachment"),
    ]
    _segment_fields = [
        ("片段编号", "text"), ("名称", "text"), ("整片位置", "text"), ("建议规格", "text"),
        ("关联分镜", "text"), ("场景动作与起止状态", "text"), ("参考图序与用途", "text"),
        ("口播对白", "text"), ("屏幕文字", "text"), ("完整视频提示词", "text"),
        ("前后衔接", "text"), ("关键画面准备", "text"),
    ]

    input_schema = {
        "type": "object",
        "required": ["operation", "project_dir", "identity"],
        "properties": {
            "operation": {"enum": ["initialize", "publish"]},
            "project_dir": {"type": "string"},
            "identity": {"enum": ["user", "bot"]},
            "title": {"type": "string"},
            "template_base_token": {"type": "string"},
            "plan_path": {"type": "string"},
            "plan": {"type": "object"},
        },
    }

    def __init__(self, client: FeishuBaseClient | None = None) -> None:
        self._client = client or FeishuBaseClient()

    def get_status(self) -> ToolStatus:
        # Status is local-only: it must not issue a Base read or write request.
        return ToolStatus.AVAILABLE if self._client.available() else ToolStatus.UNAVAILABLE

    def _prepare(self, identity: str) -> None:
        credentials = self._client.prepare(identity)
        if identity == "bot" and not credentials.user_open_id:
            raise FeishuApiError({"type": "configuration", "message": "bot Base copy requires an explicitly bound user recipient"})

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        try:
            operation = inputs.get("operation")
            if operation not in {"initialize", "publish"}:
                return self._failure("operation must be initialize or publish")
            identity = inputs.get("identity")
            if identity not in {"user", "bot"}:
                return self._failure("identity must be explicitly user or bot")
            raw_project = inputs.get("project_dir")
            if not isinstance(raw_project, str) or not raw_project.strip():
                return self._failure("project_dir is required and must be an existing directory")
            project = Path(raw_project).expanduser().resolve()
            if not project.is_dir():
                return self._failure("project_dir must be an existing directory")
            # Credential/configuration failures are local and must not create an
            # ambiguous write receipt. Never discover or launch a CLI fallback.
            self._prepare(identity)
            return self._with_lock(project, operation, identity, inputs, started)
        except FeishuApiError as exc:
            return self._failure(exc.detail["message"])
        except Exception as exc:  # do not expose command arguments or credentials
            return self._failure(f"feishu video plan failed: {type(exc).__name__}")

    def _with_lock(self, project: Path, operation: str, identity: str, inputs: dict[str, Any], started: float) -> ToolResult:
        artifacts = project / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        lock = artifacts / ".feishu-video-plan.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return self._failure("another feishu video plan operation is already active for this project")
        try:
            os.close(fd)
            receipt_path = artifacts / self.RECEIPT
            receipt = self._load_receipt(receipt_path)
            if receipt.get("inflight"):
                return self._failure("previous Base request has an unknown result; resolve its receipt before retrying")
            if operation == "initialize":
                return self._initialize(project, receipt_path, receipt, identity, str(inputs.get("title", "")), inputs.get("template_base_token"), started)
            return self._publish(project, receipt_path, receipt, identity, inputs, started)
        finally:
            try:
                lock.unlink()
            except FileNotFoundError:
                pass

    def _initialize(self, project: Path, receipt_path: Path, receipt: dict[str, Any], identity: str, title: str, template_base_token: Any, started: float) -> ToolResult:
        title = title.strip()
        if not title:
            return self._failure("title is required for initialize")
        copy_read_deadline = self._copy_read_deadline(receipt)
        locked_template = receipt.get("template")
        locked_template_token = locked_template.get("base_token") if isinstance(locked_template, dict) else None
        if template_base_token is not None and receipt.get("base_token"):
            if not isinstance(locked_template_token, str) or template_base_token != locked_template_token:
                return self._failure("template_base_token cannot change an existing project Base source")
        if receipt.get("base_token") and set(receipt.get("tables", {})) == {self.OVERVIEW, self.ASSETS, self.SEGMENTS}:
            if receipt.get("identity") != identity:
                return self._failure("existing project Base uses a different locked identity")
            granted = self._grant_user_access(project, receipt_path, receipt, identity)
            if isinstance(granted, ToolResult):
                return granted
            verified = self._verify_fields(project, receipt_path, receipt, identity, copy_read_deadline)
            if isinstance(verified, ToolResult):
                return verified
            receipt["schema_verified"] = True
            self._save_receipt(receipt_path, receipt)
            return self._success(receipt, reused=True, started=started)
        if receipt.get("identity") and receipt.get("identity") != identity:
            return self._failure("existing project Base uses a different locked identity")
        if not receipt.get("base_token"):
            restored = self._restore_legacy_base_create(receipt_path, receipt)
            if isinstance(restored, ToolResult):
                return restored
            if template_base_token is not None and receipt.get("base_token"):
                return self._failure("template_base_token cannot change an existing project Base source")
        if not receipt.get("base_token"):
            try:
                template = self._load_template(template_base_token)
            except ValueError as exc:
                return self._failure(str(exc))
            if not receipt:
                receipt = {"version": 1, "identity": identity, "title": title, "steps": {}, "template": template}
            else:
                receipt.setdefault("version", 1)
                receipt.setdefault("identity", identity)
                receipt.setdefault("title", title)
                receipt.setdefault("steps", {})
                receipt.setdefault("template", template)
            response = self._effect(receipt_path, receipt, "base-copy", project, "copy_base", {
                "base_token": template["base_token"], "name": title, "identity": identity,
            })
            if isinstance(response, ToolResult):
                return response
            base_token, url = self._parse_base_copy(response)
            if not base_token or not self._is_openable_base_url(url):
                return self._ambiguous(receipt_path, receipt, "base-copy", "Base copy response omitted a required ID or openable HTTPS URL")
            receipt.update({"base_token": base_token, "url": url})
            self._save_receipt(receipt_path, receipt)
            copy_read_deadline = time.monotonic() + self.COPY_READ_TIMEOUT_SECONDS
        granted = self._grant_user_access(project, receipt_path, receipt, identity)
        if isinstance(granted, ToolResult):
            return granted
        if set(receipt.get("tables", {})) != {self.OVERVIEW, self.ASSETS, self.SEGMENTS}:
            tables = self._discover_template_tables(project, receipt, identity, copy_read_deadline)
            if isinstance(tables, ToolResult):
                return tables
            receipt["tables"] = tables
            self._save_receipt(receipt_path, receipt)
        verified = self._verify_fields(project, receipt_path, receipt, identity, copy_read_deadline)
        if isinstance(verified, ToolResult):
            return verified
        receipt["schema_verified"] = True
        self._save_receipt(receipt_path, receipt)
        return self._success(receipt, reused=False, started=started)

    def _copy_read_deadline(self, receipt: dict[str, Any]) -> float | None:
        """One total readiness budget belongs to a copied template initialization."""
        if receipt.get("base_token") and isinstance(receipt.get("template"), dict):
            return time.monotonic() + self.COPY_READ_TIMEOUT_SECONDS
        return None

    def _grant_user_access(self, project: Path, receipt_path: Path, receipt: dict[str, Any], identity: str):
        if identity == "bot":
            return self._effect(receipt_path, receipt, "grant-user-access", project, "grant_user_access", {
                "base_token": receipt["base_token"], "identity": identity,
            })
        return None

    def _restore_legacy_base_create(self, receipt_path: Path, receipt: dict[str, Any]) -> None | ToolResult:
        """Project old deterministic create receipts before considering a template copy."""
        steps = receipt.get("steps")
        prior = steps.get("base-create") if isinstance(steps, dict) else None
        if not isinstance(prior, dict) or not prior.get("complete"):
            return None
        response = prior.get("response")
        if not isinstance(response, dict):
            return self._ambiguous(receipt_path, receipt, "base-create", "legacy Base creation receipt omitted its response")
        base_token, url, overview_table = self._parse_base_create(response)
        if not base_token or not overview_table or not self._is_openable_base_url(url):
            return self._ambiguous(receipt_path, receipt, "base-create", "legacy Base creation receipt omitted a required ID or openable HTTPS URL")
        tables = {self.OVERVIEW: overview_table}
        for name in (self.ASSETS, self.SEGMENTS):
            table_step = steps.get(f"table-create:{name}")
            table_response = table_step.get("response") if isinstance(table_step, dict) and table_step.get("complete") else None
            if isinstance(table_response, dict):
                table_id = self._parse_table_create(table_response)
                if not table_id:
                    return self._ambiguous(receipt_path, receipt, f"table-create:{name}", "legacy table creation receipt omitted table_id")
                tables[name] = table_id
        receipt.update({"base_token": base_token, "url": url, "tables": tables})
        self._save_receipt(receipt_path, receipt)
        return None

    def _create_table(self, project: Path, receipt_path: Path, receipt: dict[str, Any], name: str, fields: list[tuple[str, str]], identity: str, *, link_table: str | None = None) -> dict[str, Any] | ToolResult:
        schema: list[dict[str, Any]] = []
        for field_name, kind in fields:
            item: dict[str, Any] = {"name": field_name, "type": kind}
            if kind == "link":
                item["link_table"] = link_table
            schema.append(item)
        response = self._effect(receipt_path, receipt, f"table-create:{name}", project, "create_table", {
            "base_token": receipt["base_token"], "name": name, "fields": schema, "identity": identity,
        })
        if isinstance(response, ToolResult):
            return response
        table_id = self._parse_table_create(response)
        if not table_id:
            return self._ambiguous(receipt_path, receipt, f"table-create:{name}", "table creation response omitted table_id")
        receipt["tables"][name] = table_id
        self._save_receipt(receipt_path, receipt)
        return response

    def _load_template(self, override: Any) -> dict[str, Any]:
        """Load the checked-in structural template, allowing an explicit ID override."""
        try:
            value = json.loads(self.TEMPLATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("video-plan template configuration is unreadable") from exc
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError("video-plan template configuration is invalid")
        required = ("base_token", "url", "title", "page_name", "public_without_credentials")
        if any(key not in value for key in required) or value.get("public_without_credentials") is not True:
            raise ValueError("video-plan template configuration is incomplete")
        token = override if override is not None else value.get("base_token")
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9]{10,}", token):
            raise ValueError("template_base_token must be a Base token")
        if not self._is_openable_base_url(value.get("url")) or not all(isinstance(value.get(key), str) and value[key].strip() for key in ("title", "page_name")):
            raise ValueError("video-plan template configuration is incomplete")
        return {"version": 1, "base_token": token, "title": value["title"], "page_name": value["page_name"]}

    def _discover_template_tables(self, project: Path, receipt: dict[str, Any], identity: str, copy_read_deadline: float | None) -> dict[str, str] | ToolResult:
        data = self._read_after_copy(project, "list_tables", {"base_token": receipt["base_token"], "identity": identity}, copy_read_deadline)
        if isinstance(data, ToolResult):
            return data
        rows = self._list_value(data, "items", "tables")
        found: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            name, table_id = row.get("name"), row.get("id") or row.get("table_id")
            if name not in {self.OVERVIEW, self.ASSETS, self.SEGMENTS} or not isinstance(table_id, str) or not table_id:
                continue
            if name in found:
                return self._failure(f"template Base contains duplicate required table {name}")
            found[name] = table_id
        if set(found) != {self.OVERVIEW, self.ASSETS, self.SEGMENTS}:
            return self._failure("copied template Base is missing a required video-plan table")
        return found

    def _publish(self, project: Path, receipt_path: Path, receipt: dict[str, Any], identity: str, inputs: dict[str, Any], started: float) -> ToolResult:
        if not receipt.get("base_token") or set(receipt.get("tables", {})) != {self.OVERVIEW, self.ASSETS, self.SEGMENTS}:
            return self._failure("initialize must complete before publish")
        if receipt.get("identity") != identity:
            return self._failure("publish identity differs from the initialized project Base")
        try:
            plan = self._load_plan(project, inputs)
            normalized = self._validate_plan(project, plan)
        except ValueError as exc:
            return self._failure(str(exc))
        payload_hash = self._payload_hash(normalized)
        locked_hash = receipt.get("locked_payload_hash")
        if locked_hash and locked_hash != payload_hash:
            return self._failure("a different plan cannot continue this partially published Base")
        completed = receipt.get("published")
        if completed:
            if completed.get("payload_hash") == payload_hash:
                return self._success(receipt, reused=True, started=started)
            return self._failure("a different plan was already published; this tool never overwrites Base records")
        if not locked_hash:
            receipt["locked_payload_hash"] = payload_hash
            self._save_receipt(receipt_path, receipt)

        fields = self._verify_fields(project, receipt_path, receipt, identity)
        if isinstance(fields, ToolResult):
            return fields
        overview = self._create_records(project, receipt_path, receipt, self.OVERVIEW, [self._overview_row(normalized["overview"])], identity)
        if isinstance(overview, ToolResult):
            return overview
        assets = self._create_records(project, receipt_path, receipt, self.ASSETS, [self._asset_row(asset) for asset in normalized["assets"]], identity)
        if isinstance(assets, ToolResult):
            return assets
        asset_ids = dict(zip([a["id"] for a in normalized["assets"]], assets, strict=True))
        for asset in normalized["assets"]:
            try:
                frozen_image = self._freeze_image(project, asset)
            except ValueError as exc:
                return self._failure(str(exc))
            upload = self._effect(receipt_path, receipt, f"attachment:{asset['id']}", project, "upload_attachment", {
                "base_token": receipt["base_token"], "table_id": receipt["tables"][self.ASSETS],
                "record_id": asset_ids[asset["id"]], "field_id": fields[self.ASSETS]["实际图片"],
                "file": str(frozen_image.relative_to(project)), "identity": identity,
            })
            if isinstance(upload, ToolResult):
                return upload
        segments = self._create_records(project, receipt_path, receipt, self.SEGMENTS, [self._segment_row(segment, asset_ids) for segment in normalized["segments"]], identity)
        if isinstance(segments, ToolResult):
            return segments
        receipt["published"] = {"payload_hash": receipt["locked_payload_hash"], "record_ids": {"overview": overview, "assets": asset_ids, "segments": segments}}
        self._save_receipt(receipt_path, receipt)
        return self._success(receipt, reused=False, started=started)

    def _verify_fields(self, project: Path, receipt_path: Path, receipt: dict[str, Any], identity: str, copy_read_deadline: float | None = None) -> dict[str, dict[str, str]] | ToolResult:
        wanted = {self.OVERVIEW: self._overview_fields, self.ASSETS: self._asset_fields, self.SEGMENTS: self._segment_fields + [("参考资产", "link")]}
        found: dict[str, dict[str, str]] = {}
        for table, expected in wanted.items():
            data = self._read_after_copy(project, "list_fields", {"base_token": receipt["base_token"], "table_id": receipt["tables"][table], "identity": identity}, copy_read_deadline)
            if isinstance(data, ToolResult):
                return data
            rows = self._list_value(data, "items", "fields")
            by_name = {str(row.get("name")): row for row in rows if isinstance(row, dict)}
            actual: dict[str, str] = {}
            for name, kind in expected:
                row = by_name.get(name)
                field_id = row.get("id") if isinstance(row, dict) else None
                if not isinstance(field_id, str) or not field_id:
                    field_id = row.get("field_id") if isinstance(row, dict) else None
                if not row or row.get("type") != kind or not isinstance(field_id, str) or not field_id:
                    return self._failure(f"Base field verification failed for {table}.{name}")
                if table == self.SEGMENTS and name == "参考资产" and self._link_target_table(row) != receipt["tables"][self.ASSETS]:
                    return self._failure("Base link verification failed for 生成片段.参考资产")
                actual[name] = field_id
            found[table] = actual
        return found

    @staticmethod
    def _link_target_table(field: dict[str, Any]) -> str | None:
        """Read the documented link target from a field-list row without guessing."""
        for key in ("table_id", "link_table"):
            value = field.get(key)
            if isinstance(value, str) and value:
                return value
        for key in ("property", "link"):
            nested = field.get(key)
            if isinstance(nested, dict):
                for target_key in ("table_id", "link_table"):
                    value = nested.get(target_key)
                    if isinstance(value, str) and value:
                        return value
        return None

    def _create_records(self, project: Path, receipt_path: Path, receipt: dict[str, Any], table: str, rows: list[dict[str, Any]], identity: str) -> list[str] | ToolResult:
        results: list[str] = []
        for index in range(0, len(rows), 200):
            batch = rows[index:index + 200]
            payload_path = project / "artifacts" / f".feishu-video-plan-{self._safe_name(table)}-{index // 200}.json"
            self._write_json_atomic(payload_path, {"create_records": batch})
            response = self._effect(receipt_path, receipt, f"records:{table}:{index // 200}", project, "create_records", {
                "base_token": receipt["base_token"], "table_id": receipt["tables"][table],
                "records": batch, "identity": identity,
            })
            if isinstance(response, ToolResult):
                return response
            ids = self._list_value(response, "record_id_list")
            if len(ids) != len(batch) or not all(isinstance(v, str) and v for v in ids):
                return self._ambiguous(receipt_path, receipt, f"records:{table}:{index // 200}", "record batch response omitted ordered record IDs")
            results.extend(ids)
        return results

    @staticmethod
    def _overview_row(value: dict[str, Any]) -> dict[str, str]:
        return {"标题": value["title"], "产品": value["product"], "受众": value["audience"], "总时长": value["duration"], "画幅": value["aspect_ratio"], "视觉方向": value["visual_direction"], "声音方向": value["sound_direction"], "故事主线": value["storyline"]}

    @staticmethod
    def _asset_row(value: dict[str, Any]) -> dict[str, str]:
        return {"资产编号": value["id"], "类型": value["kind"], "名称": value["name"], "角度状态": value["state"], "设定用途": value["description"], "来源或图片准备提示": value.get("source") or value.get("preparation") or ""}

    @staticmethod
    def _segment_row(value: dict[str, Any], asset_ids: dict[str, str]) -> dict[str, Any]:
        ref_text = "；".join(f"{item['asset_id']}：{item['role']}" for item in value["references"])
        return {"片段编号": value["id"], "名称": value["name"], "整片位置": value["position"], "建议规格": value["spec"], "关联分镜": "、".join(value["shot_ids"]), "场景动作与起止状态": value["action"], "参考图序与用途": ref_text, "口播对白": value["dialogue"], "屏幕文字": value["screen_text"], "完整视频提示词": value["prompt"], "前后衔接": value["continuity"], "关键画面准备": value["key_image_preparation"], "参考资产": [{"id": asset_ids[item["asset_id"]]} for item in value["references"]]}

    def _load_plan(self, project: Path, inputs: dict[str, Any]) -> dict[str, Any]:
        if isinstance(inputs.get("plan"), dict) and inputs.get("plan_path"):
            raise ValueError("provide exactly one of plan or plan_path")
        if isinstance(inputs.get("plan"), dict):
            return inputs["plan"]
        path_value = inputs.get("plan_path")
        if not isinstance(path_value, str) or not path_value:
            raise ValueError("publish requires plan or plan_path")
        path = self._inside(project, path_value, "plan_path")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("plan_path must be a readable JSON object") from exc
        if not isinstance(value, dict):
            raise ValueError("plan JSON must be an object")
        return value

    def _validate_plan(self, project: Path, value: dict[str, Any]) -> dict[str, Any]:
        overview = value.get("overview")
        assets = value.get("assets")
        segments = value.get("segments")
        if not isinstance(overview, dict) or not isinstance(assets, list) or not isinstance(segments, list):
            raise ValueError("plan requires overview object, assets list, and segments list")
        if not assets:
            raise ValueError("plan requires at least one asset with an actual image")
        if not segments:
            raise ValueError("plan requires at least one generation segment")
        overview_keys = ("title", "product", "audience", "duration", "aspect_ratio", "visual_direction", "sound_direction", "storyline")
        clean_overview = {key: self._text(overview.get(key), f"overview.{key}") for key in overview_keys}
        clean_assets: list[dict[str, Any]] = []
        asset_ids: set[str] = set()
        for index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                raise ValueError(f"assets[{index}] must be an object")
            item = {key: self._text(asset.get(key), f"assets[{index}].{key}") for key in ("id", "kind", "name", "state", "description")}
            if item["id"] in asset_ids:
                raise ValueError("asset IDs must be unique")
            asset_ids.add(item["id"])
            source = asset.get("source")
            preparation = asset.get("preparation")
            if source is not None:
                item["source"] = self._text(source, f"assets[{index}].source")
            if preparation is not None:
                item["preparation"] = self._text(preparation, f"assets[{index}].preparation")
            image = asset.get("image_path")
            item["image_path"] = str(self._inside(project, self._text(image, f"assets[{index}].image_path"), "image_path").relative_to(project))
            image_file = project / item["image_path"]
            self._verify_image(image_file, f"assets[{index}].image_path")
            item["image_sha256"] = hashlib.sha256(image_file.read_bytes()).hexdigest()
            clean_assets.append(item)
        clean_segments: list[dict[str, Any]] = []
        segment_ids: set[str] = set()
        required = ("id", "name", "position", "spec", "action", "dialogue", "screen_text", "prompt", "continuity", "key_image_preparation")
        for index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                raise ValueError(f"segments[{index}] must be an object")
            item = {key: self._text(segment.get(key), f"segments[{index}].{key}") for key in required}
            if item["id"] in segment_ids:
                raise ValueError("segment IDs must be unique")
            segment_ids.add(item["id"])
            shots = segment.get("shot_ids")
            refs = segment.get("references")
            if not isinstance(shots, list) or not shots or not all(isinstance(v, str) and v.strip() for v in shots):
                raise ValueError(f"segments[{index}].shot_ids must be a non-empty string list")
            if not isinstance(refs, list) or not refs:
                raise ValueError(f"segments[{index}].references must be a non-empty list")
            item["shot_ids"] = [v.strip() for v in shots]
            item["references"] = []
            for ref_index, ref in enumerate(refs):
                if not isinstance(ref, dict):
                    raise ValueError(f"segments[{index}].references[{ref_index}] must be an object")
                asset_id = self._text(ref.get("asset_id"), f"segments[{index}].references[{ref_index}].asset_id")
                if asset_id not in asset_ids:
                    raise ValueError(f"segments[{index}] references unknown asset {asset_id}")
                item["references"].append({"asset_id": asset_id, "role": self._text(ref.get("role"), f"segments[{index}].references[{ref_index}].role")})
            clean_segments.append(item)
        return {"overview": clean_overview, "assets": clean_assets, "segments": clean_segments}

    @staticmethod
    def _text(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be a non-empty string")
        return value

    @staticmethod
    def _inside(project: Path, supplied: str, label: str) -> Path:
        path = (project / supplied).resolve() if not Path(supplied).is_absolute() else Path(supplied).resolve()
        try:
            path.relative_to(project)
        except ValueError as exc:
            raise ValueError(f"{label} must stay inside project_dir") from exc
        return path

    @staticmethod
    def _verify_image(path: Path, label: str) -> None:
        if not path.is_file():
            raise ValueError(f"{label} does not exist")
        if not 0 < path.stat().st_size <= FeishuBaseClient.MAX_ATTACHMENT_BYTES:
            raise ValueError(f"{label} must be non-empty and at most 2 GiB")
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError(f"{label} must be PNG, JPEG, or WebP")
        try:
            from PIL import Image

            with Image.open(path) as image:
                image.verify()
        except Exception as exc:
            raise ValueError(f"{label} is not a valid image") from exc

    def _freeze_image(self, project: Path, asset: dict[str, Any]) -> Path:
        """Copy the validated image bytes to an immutable receipt-side upload source."""
        source = project / asset["image_path"]
        expected = asset["image_sha256"]
        try:
            payload = source.read_bytes()
        except OSError as exc:
            raise ValueError(f"asset {asset['id']} image could not be re-read before upload") from exc
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"asset {asset['id']} image changed after plan validation; attachment upload was not attempted")
        original_name = Path(asset["image_path"]).name
        safe_asset_id = re.sub(r"[^A-Za-z0-9._-]", "_", asset["id"])
        target = project / "artifacts" / ".feishu-video-plan-media" / f"{safe_asset_id}-{expected[:16]}-{original_name}"
        if target.exists():
            try:
                frozen = target.read_bytes()
            except OSError as exc:
                raise ValueError(f"frozen image for asset {asset['id']} cannot be verified") from exc
            if hashlib.sha256(frozen).hexdigest() != expected:
                raise ValueError(f"frozen image for asset {asset['id']} does not match its locked plan hash")
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_bytes(payload)
        os.replace(temp, target)
        return target

    @staticmethod
    def _is_openable_base_url(value: str | None) -> bool:
        return isinstance(value, str) and value.startswith("https://") and len(value) > len("https://")

    def _effect(self, receipt_path: Path, receipt: dict[str, Any], step: str, project: Path, operation: str, params: dict[str, Any]) -> dict[str, Any] | ToolResult:
        prior = receipt.get("steps", {}).get(step)
        if isinstance(prior, dict) and prior.get("complete") and isinstance(prior.get("response"), dict):
            return prior["response"]
        receipt["inflight"] = {"step": step}
        self._save_receipt(receipt_path, receipt)
        try:
            result = self._request(operation, params, project)
        except Exception as exc:
            # A network timeout, process interruption, or malformed response can have
            # reached Feishu.  Keep inflight so no follow-up call duplicates it.
            detail = exc.detail if isinstance(exc, FeishuApiError) else {"type": type(exc).__name__, "message": "request did not return a trustworthy result"}
            receipt["inflight"] = {"step": step, "error": detail}
            self._save_receipt(receipt_path, receipt)
            return self._failure(f"Base request outcome is unknown at {step}; its receipt is locked against retry: {detail['message']}")
        receipt.setdefault("steps", {})[step] = {"complete": True, "response": result}
        receipt.pop("inflight", None)
        self._save_receipt(receipt_path, receipt)
        return result

    def _read(self, project: Path, operation: str, params: dict[str, Any]) -> dict[str, Any] | ToolResult:
        try:
            return self._request(operation, params, project)
        except FeishuApiError as exc:
            return self._failure(f"could not verify Base fields: {exc.detail['message']}")
        except Exception:
            return self._failure("could not verify Base fields")

    def _read_after_copy(self, project: Path, operation: str, params: dict[str, Any], deadline: float | None) -> dict[str, Any] | ToolResult:
        """Re-read only the documented transient Base-copying server state."""
        if deadline is None:
            return self._read(project, operation, params)
        while True:
            try:
                return self._request(operation, params, project)
            except FeishuApiError as exc:
                if not self._is_copying_error(exc.detail):
                    return self._failure(f"could not verify copied Base: {exc.detail['message']}")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return self._failure(f"copied Base is still copying after {self.COPY_READ_TIMEOUT_SECONDS} seconds; no additional copy was submitted")
                self._wait_copy_retry(min(self.COPY_READ_INTERVAL_SECONDS, remaining))
            except Exception:
                return self._failure("could not verify copied Base")

    @staticmethod
    def _is_copying_error(detail: dict[str, Any]) -> bool:
        message = detail.get("message")
        return isinstance(message, str) and "base is copying" in message.casefold()

    @staticmethod
    def _wait_copy_retry(seconds: float) -> None:
        time.sleep(seconds)

    def _ambiguous(self, receipt_path: Path, receipt: dict[str, Any], step: str, message: str) -> ToolResult:
        receipt["inflight"] = {"step": step, "reason": message}
        self._save_receipt(receipt_path, receipt)
        return self._failure(message)

    def _request(self, operation: str, params: dict[str, Any], project: Path) -> dict[str, Any]:
        return self._client.call(operation, params, project)

    @staticmethod
    def _parse_base_create(value: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
        """Read only the documented v3 create shape, with narrow legacy support."""
        base = value.get("base")
        table = value.get("table")
        if isinstance(base, dict) and isinstance(table, dict):
            token = base.get("base_token")
            url = base.get("url")
            table_id = table.get("id")
            return (
                token if isinstance(token, str) and token else None,
                url if isinstance(url, str) and url else None,
                table_id if isinstance(table_id, str) and table_id else None,
            )
        # Existing isolated test callers used this pre-v3 mock shape.  Do not
        # recurse through arbitrary response values: an unrelated `id` must
        # never become a table ID.
        token = value.get("base_token")
        url = value.get("url")
        table_id = value.get("table_id")
        return (
            token if isinstance(token, str) and token else None,
            url if isinstance(url, str) and url else None,
            table_id if isinstance(table_id, str) and table_id else None,
        )

    @staticmethod
    def _parse_base_copy(value: dict[str, Any]) -> tuple[str | None, str | None]:
        """Read only the documented Base copy response, never an unrelated ID."""
        base = value.get("base")
        if isinstance(base, dict):
            token, url = base.get("base_token"), base.get("url")
        else:
            token, url = value.get("base_token"), value.get("url")
        return (
            token if isinstance(token, str) and token else None,
            url if isinstance(url, str) and url else None,
        )

    @staticmethod
    def _parse_table_create(value: dict[str, Any]) -> str | None:
        table = value.get("table")
        if isinstance(table, dict):
            table_id = table.get("id")
            return table_id if isinstance(table_id, str) and table_id else None
        legacy = value.get("table_id")
        return legacy if isinstance(legacy, str) and legacy else None

    @staticmethod
    def _list_value(value: dict[str, Any], *keys: str) -> list[Any]:
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, list):
                return candidate
        for nested in value.values():
            if isinstance(nested, dict):
                found = FeishuVideoPlan._list_value(nested, *keys)
                if found:
                    return found
        return []

    @staticmethod
    def _payload_hash(value: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_name(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _load_receipt(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("existing Feishu delivery receipt is unreadable") from exc
        if not isinstance(value, dict):
            raise ValueError("existing Feishu delivery receipt is invalid")
        return value

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        os.replace(temp, path)

    def _save_receipt(self, path: Path, receipt: dict[str, Any]) -> None:
        self._write_json_atomic(path, receipt)

    @staticmethod
    def _failure(message: str) -> ToolResult:
        return ToolResult(success=False, error=message)

    @staticmethod
    def _success(receipt: dict[str, Any], *, reused: bool, started: float) -> ToolResult:
        return ToolResult(success=True, data={"base_token": receipt.get("base_token"), "url": receipt.get("url"), "table_ids": receipt.get("tables", {}), "reused": reused, "published": receipt.get("published"), "verification": {"status": "structure_initialized_only", "reason": "The receipt verifies copied table structure only; native board pages and sharing permissions require separate UI verification."}}, duration_seconds=round(time.monotonic() - started, 3))
