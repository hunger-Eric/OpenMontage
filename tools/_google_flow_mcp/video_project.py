"""One durable Flow video project per local production, across MCP sessions."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from tools._google_flow_mcp.client import GoogleFlowMCPError


def project_identity(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        return None
    pattern = (r"/project/([\w-]+)/?" if parsed.hostname == "flow.google.com"
               else r"/(?:fx/)?tools/flow/project/([\w-]+)/?" if parsed.hostname == "labs.google" else "")
    match = re.fullmatch(pattern, parsed.path) if pattern else None
    return match[1] if match else None


def local_project_dir(output_path: Path, explicit: Path | None = None) -> Path:
    from lib.events import infer_project_dir

    output = output_path.resolve()
    root = explicit.resolve() if explicit is not None else (
        infer_project_dir({"output_path": str(output)}) or output.parent
    ).resolve()
    if not output.is_relative_to(root):
        raise GoogleFlowMCPError("Flow output_path is outside its local project_dir")
    return root


class FlowVideoProject:
    """Persist ownership before uploads/payment; never replace a lost project."""

    def __init__(self, output_path: Path, start_url: str, project_dir: Path | None = None,
                 *, explicit_project_url: bool = True):
        self.root = local_project_dir(output_path, project_dir)
        self.path = self.root / "artifacts" / "google-flow-project.json"
        self.lock = self.path.with_suffix(".lock")
        self.start_url = start_url
        self.project_url: str | None = None
        self.record: dict = {}
        self.explicit_project_url = explicit_project_url
        self.creation_invoked = False

    def _save(self):
        temporary = self.path.with_suffix(f".json.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(self.record, stream, ensure_ascii=False, indent=2)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.lock.open("x", encoding="utf-8") as stream:
                json.dump({"pid": os.getpid(), "project_dir": str(self.root)}, stream)
        except FileExistsError as exc:
            raise GoogleFlowMCPError("Flow project is already in use; reconcile its existing lock") from exc
        try:
            requested = project_identity(self.start_url)
            if self.path.exists():
                self.record = json.loads(self.path.read_text(encoding="utf-8"))
                if (self.record.get("schema_version") != "flow_video_project.v1"
                        or self.record.get("project_dir") != str(self.root)):
                    raise GoogleFlowMCPError("Flow project binding has an invalid local owner")
                self.project_url = self.record.get("project_url")
                if not self.project_url:
                    raise GoogleFlowMCPError("Previous Flow project creation is unverified; reconcile it, never create another")
                if not project_identity(self.project_url):
                    raise GoogleFlowMCPError("Stored Flow project URL is invalid; reconcile the binding")
                if self.explicit_project_url and requested and requested != project_identity(self.project_url):
                    raise GoogleFlowMCPError("Requested Flow project conflicts with the production's existing binding")
            else:
                # Recover existing production ownership rather than creating a
                # fresh remote project after an upgrade or a lost projection.
                historical: dict[str, str] = {}
                for receipt in self.root.rglob("*.flow-attempt.json"):
                    if not receipt.name.lower().endswith(".mp4.flow-attempt.json"):
                        continue
                    entry = json.loads(receipt.read_text(encoding="utf-8"))
                    url = entry.get("project_url")
                    identity = project_identity(url) if isinstance(url, str) else None
                    if not identity:
                        raise GoogleFlowMCPError("Historical Flow attempt has no verified project URL; reconcile it before creating a project")
                    historical[identity] = url
                if len(historical) > 1 and not requested:
                    raise GoogleFlowMCPError("Historical Flow clips span multiple projects; select their continuation project with project_url")
                if historical and requested and requested not in historical:
                    raise GoogleFlowMCPError("Requested Flow project conflicts with historical production receipts")
                self.project_url = self.start_url if requested else next(iter(historical.values()), None)
                self.record = {"schema_version": "flow_video_project.v1", "project_dir": str(self.root),
                               "provider": "google_flow", "project_url": self.project_url,
                               "state": "opening" if self.project_url else "creating",
                               "created_at": datetime.now(timezone.utc).isoformat(),
                               "historical_project_urls": list(historical.values())}
                self._save()
            if self.project_url:
                self.start_url = self.project_url
            return self
        except Exception:
            self.lock.unlink()
            raise

    def bind(self, observed_url: str):
        identity = project_identity(observed_url)
        if not identity or (self.project_url and identity != project_identity(self.project_url)):
            raise GoogleFlowMCPError("Flow opened a different project; refusing generation")
        self.project_url = observed_url
        self.record.update(project_url=observed_url, state="bound")
        self._save()

    def mark_opening(self):
        # Once navigation can create a remote project, a missing result is
        # unknown. A local MCP startup failure before this point creates none.
        self.creation_invoked = True

    def receipt(self) -> dict:
        return {"project_dir": str(self.root), "binding_path": str(self.path), "project_url": self.project_url}

    def __exit__(self, *_args):
        if not self.project_url and not self.creation_invoked:
            self.path.unlink()
        self.lock.unlink()
