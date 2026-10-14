"""Node diagnostics stay readable even under a Windows GBK locale."""
import subprocess
import sys
import pytest
from tools.video.hyperframes_compose import HyperFramesCompose


@pytest.mark.parametrize("method", ["_node_major_version", "_resolve_npm_package", "_probe_cli"])
def test_node_probe_decodes_actual_utf8_diagnostics_under_gbk(monkeypatch, method):
    original = subprocess.run
    monkeypatch.setattr(subprocess, "_text_encoding", lambda: "cp936")
    monkeypatch.setattr("shutil.which", lambda _: sys.executable)
    monkeypatch.setattr(HyperFramesCompose, "_npm_resolve_cache", None)
    monkeypatch.setattr(HyperFramesCompose, "_cli_probe_cache", None)
    script = "import sys; sys.stdout.buffer.write(b'v22.0.0\\n'); sys.stderr.buffer.write('诊断：缺少运行环境 — error'.encode('utf-8')); sys.exit(%d)" % (0 if method == "_node_major_version" else 1)
    if method != "_node_major_version":
        script = script.replace("sys.stdout.buffer.write(b'v22.0.0\\n');", "")
    def run(_command, **kwargs):
        return original([sys.executable, "-c", script], **kwargs)
    monkeypatch.setattr(subprocess, "run", run)
    value = getattr(HyperFramesCompose, method)()
    if method == "_node_major_version":
        assert value == 22
    else:
        assert "诊断：缺少运行环境 — error" in value["error"]
