"""Production initialization opens the observer without making it a gate."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from backlot import __main__ as cli
from lib import checkpoint


def test_canonical_init_opens_after_identity_is_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "PROJECTS_DIR", tmp_path)
    observed = []

    def open_board(project_id):
        marker = json.loads((tmp_path / project_id / "project.json").read_text())
        observed.append((project_id, marker["execution_binding"]))
        return 0

    monkeypatch.setattr(cli, "cmd_open", open_board)
    for turn in ("first", "continued"):
        checkpoint.init_project("film", title="Film", pipeline_type="cinematic",
                                execution_binding={"codex_turn_id": turn})
    assert observed == [("film", {"codex_turn_id": "first"}),
                        ("film", {"codex_turn_id": "continued"})]


@pytest.mark.parametrize("failure", [1, RuntimeError("browser unavailable")])
def test_board_failure_preserves_project(tmp_path, monkeypatch, failure):
    opener = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
    monkeypatch.setattr(cli, "cmd_open", opener)
    root = checkpoint.init_project("film", title="Film", pipeline_type="cinematic",
                                   pipeline_dir=tmp_path, open_board=True)
    assert json.loads((root / "project.json").read_text())["project_id"] == "film"
    opener.assert_called_once_with("film")


def test_alternate_root_quiet_and_explicit_opt_out(tmp_path, monkeypatch):
    opener = Mock()
    monkeypatch.setattr(cli, "cmd_open", opener)
    checkpoint.init_project("isolated", title="Test", pipeline_type="cinematic", pipeline_dir=tmp_path)
    monkeypatch.setattr(checkpoint, "PROJECTS_DIR", tmp_path)
    checkpoint.init_project("opt-out", title="Test", pipeline_type="cinematic", open_board=False)
    opener.assert_not_called()


def test_existing_server_reused_and_correct_page_opened(monkeypatch):
    monkeypatch.setattr(cli, "_server_alive", lambda port: True)
    spawn = Mock()
    browser = Mock(return_value=True)
    monkeypatch.setattr(cli, "_spawn_server", spawn)
    monkeypatch.setattr(cli.webbrowser, "open", browser)
    monkeypatch.setattr(cli, "_port", lambda: 4750)
    assert cli.cmd_open("film") == 0
    spawn.assert_not_called()
    browser.assert_called_once_with("http://127.0.0.1:4750/p/film")


def test_detached_server_uses_repo_cwd(monkeypatch):
    spawn = Mock()
    monkeypatch.setattr(cli.subprocess, "Popen", spawn)
    cli._spawn_server(4750)
    args, kwargs = spawn.call_args
    assert args[0] == [cli.sys.executable, "-m", "backlot", "serve", "--port", "4750"]
    assert Path(kwargs["cwd"]) == Path(cli.__file__).resolve().parent.parent
    if cli.os.name == "nt":
        assert kwargs["creationflags"] & cli.subprocess.CREATE_NO_WINDOW


def test_browser_failure_reports_reopen_url(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_server_alive", lambda port: True)
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: False)
    assert cli.cmd_open("film") == 0
    assert "browser did not open automatically" in capsys.readouterr().out


def test_foreign_health_endpoint_is_not_backlot(monkeypatch):
    import io
    response = io.StringIO('{"ok":true,"app":"other-service"}')
    response.status = 200
    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda *args, **kwargs: response)
    assert cli._server_alive(4750) is False
