from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools._google_flow_mcp.client import GoogleFlowMCPError
from tools._google_flow_mcp.video_project import FlowVideoProject, local_project_dir, project_identity

HOME = "https://flow.google.com/"
PROJECT = HOME + "project/first"


def test_project_root_is_inferred_above_nested_scene_and_retry_outputs(monkeypatch, tmp_path):
    import lib.events
    monkeypatch.setattr(lib.events, "PROJECTS_DIR", tmp_path/"projects")
    root = tmp_path/"projects"/"film"
    for suffix in ("assets/video/G01.mp4", "repairs/G01-v2.mp4"):
        assert local_project_dir(root/suffix) == root
    assert local_project_dir(tmp_path/"standalone"/"G01.mp4") == tmp_path/"standalone"
    with pytest.raises(GoogleFlowMCPError, match="outside"):
        local_project_dir(tmp_path/"elsewhere.mp4", root)


def test_duplicate_keys_share_local_owner_but_never_cross_productions(monkeypatch, tmp_path):
    import lib.events
    from tools.video.google_flow_mcp_video import GoogleFlowMCPVideo
    monkeypatch.setattr(lib.events, "PROJECTS_DIR", tmp_path/"projects")
    root = tmp_path/"projects/film"
    tool = GoogleFlowMCPVideo()
    inputs = {"prompt": "same text", "model": "Omni 1.1 Flash", "output_path": str(root/"assets/G01.mp4")}
    original = dict(inputs)
    key = tool.idempotency_key(inputs)
    assert key == tool.idempotency_key({**inputs, "project_dir": str(root), "output_path": str(root/"repairs/G01-v2.mp4")})
    assert key != tool.idempotency_key({**inputs, "output_path": str(tmp_path/"projects/other-film/assets/G01.mp4")})
    assert inputs == original


def test_binding_survives_new_session_and_isolated_productions(monkeypatch, tmp_path):
    first = tmp_path/"film-one"
    second = tmp_path/"film-two"
    with FlowVideoProject(first/"clip.mp4", HOME, first) as project:
        assert project.project_url is None
        project.bind(PROJECT)
    with FlowVideoProject(first/"next.mp4", HOME, first) as project:
        assert project.start_url == PROJECT
    with FlowVideoProject(second/"clip.mp4", HOME, second) as project:
        assert project.project_url is None
        project.bind(HOME+"project/second")


def test_interrupted_creation_is_not_a_license_to_create_again(tmp_path):
    with FlowVideoProject(tmp_path/"clip.mp4", HOME, tmp_path) as project:
        project.mark_opening()  # Simulate lost result after navigation was invoked.
    with pytest.raises(GoogleFlowMCPError, match="creation is unverified"):
        with FlowVideoProject(tmp_path/"next.mp4", HOME, tmp_path):
            pytest.fail("must not open browser")


def test_existing_binding_rejects_conflicting_project(tmp_path):
    with FlowVideoProject(tmp_path/"clip.mp4", HOME, tmp_path) as project:
        project.bind(PROJECT)
    with pytest.raises(GoogleFlowMCPError, match="conflicts"):
        with FlowVideoProject(tmp_path/"next.mp4", HOME+"project/other", tmp_path):
            pass
    stored = json.loads((tmp_path/"artifacts/google-flow-project.json").read_text())
    assert stored["project_url"] == PROJECT


def test_global_start_default_cannot_move_an_existing_production(tmp_path):
    with FlowVideoProject(tmp_path/"clip.mp4", HOME, tmp_path) as project:
        project.bind(PROJECT)
    with FlowVideoProject(tmp_path/"next.mp4", HOME+"project/global-default", tmp_path,
                          explicit_project_url=False) as project:
        assert project.start_url == PROJECT


def test_known_local_failure_before_navigation_does_not_leave_unknown_creation(tmp_path):
    with pytest.raises(RuntimeError):
        with FlowVideoProject(tmp_path/"clip.mp4", HOME, tmp_path):
            raise RuntimeError("local MCP startup failed")
    assert not (tmp_path/"artifacts/google-flow-project.json").exists()
    with FlowVideoProject(tmp_path/"next.mp4", HOME, tmp_path) as project:
        project.bind(PROJECT)


def test_simultaneous_project_creation_is_serialized(tmp_path):
    with FlowVideoProject(tmp_path/"clip.mp4", HOME, tmp_path) as first:
        with pytest.raises(GoogleFlowMCPError, match="already in use"):
            with FlowVideoProject(tmp_path/"other.mp4", HOME, tmp_path):
                pass
        first.bind(PROJECT)
    with FlowVideoProject(tmp_path/"next.mp4", HOME, tmp_path) as project:
        assert project.project_url == PROJECT


def _history(root, filename, url):
    path = root/"assets/video"/filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"project_url": url, "state": "submitted"}))
    return path


def test_historical_single_project_is_recovered_without_rewriting_receipt(tmp_path):
    receipt = _history(tmp_path, "G01.mp4.flow-attempt.json", PROJECT)
    frozen = receipt.read_bytes()
    with FlowVideoProject(tmp_path/"assets/video/G02.mp4", HOME, tmp_path) as project:
        assert project.start_url == PROJECT
        project.bind(PROJECT)
    assert receipt.read_bytes() == frozen


def test_historical_split_requires_explicit_continuation_then_remains_bound(tmp_path):
    _history(tmp_path, "G01.mp4.flow-attempt.json", PROJECT)
    _history(tmp_path, "G02.mp4.flow-attempt.json", HOME+"project/second")
    with pytest.raises(GoogleFlowMCPError, match="multiple projects"):
        with FlowVideoProject(tmp_path/"G03.mp4", HOME, tmp_path):
            pass
    with FlowVideoProject(tmp_path/"G03.mp4", PROJECT, tmp_path) as project:
        project.bind(PROJECT)
    with FlowVideoProject(tmp_path/"G04.mp4", HOME, tmp_path) as project:
        assert project.start_url == PROJECT


def test_invalid_binding_and_corrupt_history_never_replaced(tmp_path):
    receipt = _history(tmp_path, "G01.mp4.flow-attempt.json", PROJECT)
    receipt.write_text("{corrupt")
    with pytest.raises(ValueError):
        with FlowVideoProject(tmp_path/"G02.mp4", HOME, tmp_path):
            pass
    assert not (tmp_path/"artifacts/google-flow-project.json").exists()


def test_unknown_historical_project_cannot_trigger_new_project_creation(tmp_path):
    _history(tmp_path, "G01.mp4.flow-attempt.json", HOME)
    with pytest.raises(GoogleFlowMCPError, match="no verified project URL"):
        with FlowVideoProject(tmp_path/"G02.mp4", HOME, tmp_path):
            pass
    assert not (tmp_path/"artifacts/google-flow-project.json").exists()


@pytest.mark.parametrize("url", [HOME, "https://evil.example/project/first", "https://flow.google.com/project/first/extra", "https://user@flow.google.com/project/first"])
def test_only_real_project_routes_have_an_identity(url):
    assert project_identity(url) is None


def test_flow_project_host_aliases_preserve_identity():
    assert project_identity(PROJECT) == project_identity("https://labs.google/fx/tools/flow/project/first")
