"""Small JSON-RPC client for the local google-flow-mcp-v4 stdio server."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any


class GoogleFlowMCPError(RuntimeError):
    """Raised when the local MCP transport or a Flow tool fails."""


def google_flow_root() -> Path:
    configured = os.environ.get("GOOGLE_FLOW_MCP_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    workspace_parent = Path(__file__).resolve().parents[2].parent
    return (workspace_parent / "google-flow-mcp-v4").resolve()


def google_flow_server_entry() -> Path:
    return google_flow_root() / "dist" / "index.js"


def google_flow_node() -> str | None:
    configured = os.environ.get("GOOGLE_FLOW_MCP_NODE")
    if configured:
        return configured
    return shutil.which("node")


class GoogleFlowMCPClient:
    """One-process, one-request-stream MCP client.

    A fresh server is used for each provider execution so the browser and paid
    authorization state cannot leak between OpenMontage tool calls.
    """

    def __init__(self, *, timeout_seconds: int = 600) -> None:
        self.timeout_seconds = timeout_seconds
        self.process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr: deque[str] = deque(maxlen=20)
        self._next_id = 1
        self._initialized = False

    def __enter__(self) -> "GoogleFlowMCPClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self.process is not None:
            return
        node = google_flow_node()
        entry = google_flow_server_entry()
        if not node:
            raise GoogleFlowMCPError("Node.js is unavailable for Google Flow MCP")
        if not entry.is_file():
            raise GoogleFlowMCPError(f"Google Flow MCP server entry is missing: {entry}")

        env = os.environ.copy()
        env.setdefault("HEADLESS", "false")
        self.process = subprocess.Popen(
            [node, str(entry)],
            cwd=str(entry.parent.parent),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "openmontage", "version": "1.0.0"},
            },
            timeout_seconds=30,
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    def _read_stdout(self) -> None:
        process = self.process
        if not process or not process.stdout:
            return
        for line in process.stdout:
            text = line.strip()
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                self._messages.put(message)

    def _read_stderr(self) -> None:
        process = self.process
        if not process or not process.stderr:
            return
        for line in process.stderr:
            text = line.strip()
            if text:
                self._stderr.append(text)

    def _send(self, message: dict[str, Any]) -> None:
        process = self.process
        if not process or not process.stdin:
            raise GoogleFlowMCPError("Google Flow MCP process is not running")
        process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        process.stdin.flush()

    def _request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        deadline = time.monotonic() + (timeout_seconds or self.timeout_seconds)
        while time.monotonic() < deadline:
            process = self.process
            if process and process.poll() is not None and self._messages.empty():
                detail = self._stderr[-1] if self._stderr else f"exit code {process.returncode}"
                raise GoogleFlowMCPError(f"Google Flow MCP server exited: {detail}")
            try:
                message = self._messages.get(timeout=min(0.25, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message.get("error") or {}
                raise GoogleFlowMCPError(str(error.get("message") or error))
            result = message.get("result")
            if not isinstance(result, dict):
                raise GoogleFlowMCPError(f"MCP method {method} returned a non-object result")
            return result
        raise GoogleFlowMCPError(f"Timed out waiting for MCP method {method}")

    @staticmethod
    def _decode_tool_result(name: str, result: dict[str, Any]) -> dict[str, Any]:
        texts = [
            item.get("text", "")
            for item in result.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        combined = "\n".join(texts).strip()
        if result.get("isError"):
            raise GoogleFlowMCPError(combined or f"Google Flow MCP tool {name} failed")
        if not combined:
            return {}
        try:
            decoded = json.loads(combined)
        except json.JSONDecodeError:
            return {"text": combined}
        if not isinstance(decoded, dict):
            return {"value": decoded}
        return decoded

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        result = self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
            timeout_seconds=timeout_seconds,
        )
        return self._decode_tool_result(name, result)

    def list_tools(self) -> list[str]:
        result = self._request("tools/list", {}, timeout_seconds=30)
        return [
            str(tool.get("name"))
            for tool in result.get("tools", [])
            if isinstance(tool, dict) and tool.get("name")
        ]

    def close(self) -> None:
        process = self.process
        if process is None:
            return
        if self._initialized and process.poll() is None:
            try:
                self.call_tool("flow_close", {}, timeout_seconds=10)
            except Exception:
                pass
        try:
            if process.stdin:
                process.stdin.close()
        except Exception:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        self.process = None
        self._initialized = False
