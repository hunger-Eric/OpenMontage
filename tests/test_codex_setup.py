"""Relocation and non-overwriting setup checks; no installs or provider calls."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('codex_setup', SOURCE / 'scripts/codex_setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def checkout(tmp_path):
    root = tmp_path / 'another computer with spaces' / 'OpenMontage'
    (root / 'scripts').mkdir(parents=True)
    for source in ('.env.example', 'config.local.example.yaml', 'scripts/codex_setup.py'):
        shutil.copyfile(SOURCE / source, root / source)
    return root


def test_relocated_cli_initializes_from_unrelated_cwd(tmp_path):
    root = checkout(tmp_path)
    command = [sys.executable, str(root / 'scripts/codex_setup.py'), 'init']
    first = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=True)
    assert set(json.loads(first.stdout)['created']) == {'.env', 'config.local.yaml'}
    (root / '.env').write_text('PRIVATE_VALUE=do-not-overwrite', encoding='utf-8')
    (root / 'config.local.yaml').write_text('personal: preserved', encoding='utf-8')
    second = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=True)
    assert json.loads(second.stdout)['created'] == []
    assert (root / '.env').read_text() == 'PRIVATE_VALUE=do-not-overwrite'
    assert (root / 'config.local.yaml').read_text() == 'personal: preserved'


def test_fresh_doctor_reports_missing_dependencies_without_leaking_env(tmp_path):
    root = checkout(tmp_path)
    setup.initialize(root)
    (root / '.env').write_text('SECRET=must-not-appear', encoding='utf-8')
    result = subprocess.run([sys.executable, str(root / 'scripts/codex_setup.py'), 'doctor'],
                            cwd=tmp_path, capture_output=True, text=True)
    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert report['root'] == str(root)
    assert report['ready'] is False
    assert report['paid_generation'] is False
    assert 'must-not-appear' not in result.stdout
    assert next(c for c in report['checks'] if c['name'] == 'project_python')['ok'] is False
    assert next(c for c in report['checks'] if c['name'] == 'flow_bridge')['login'] == 'not_verified'


def test_install_uses_checkout_paths_and_preserves_existing_venv(tmp_path, monkeypatch):
    root = checkout(tmp_path)
    interpreter = setup.python_path(root)
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text('existing interpreter')
    calls = []
    monkeypatch.setattr(setup, 'run', lambda command, cwd: calls.append((command, cwd)))
    setup.install(root, skip_remotion=True)
    assert calls == [([str(interpreter), '-m', 'pip', 'install', '-r', 'requirements.txt'], root)]
    assert interpreter.read_text() == 'existing interpreter'


@pytest.mark.parametrize('required', [False, True])
def test_bridge_locator_and_account_status(tmp_path, monkeypatch, required):
    root = checkout(tmp_path)
    bridge = tmp_path / 'custom bridge'
    (bridge / 'dist').mkdir(parents=True)
    (bridge / 'dist/index.js').write_text('')
    (bridge / 'dist/tools.js').write_text('')
    monkeypatch.setenv('GOOGLE_FLOW_MCP_ROOT', str(bridge))
    report = setup.doctor(root, require_flow=required, planning_only=True)
    check = next(c for c in report['checks'] if c['name'] == 'flow_bridge')
    assert check['ok'] is True
    assert check['required'] is required
    assert check['login'] == 'not_verified'
    assert check['path'] == str(bridge)


def test_optional_sdk_does_not_block_configured_flow(tmp_path, monkeypatch):
    root = checkout(tmp_path)
    for name in ('AGENTS.md', 'AGENT_GUIDE.md'):
        (root / name).write_text('entry')
    for name in ('pipeline_defs', 'skills', '.agents/skills'):
        (root / name).mkdir(parents=True)
    interpreter = setup.python_path(root)
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text('fixture interpreter')
    monkeypatch.setattr(setup.subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 0, '["openai"]', ''))
    report = setup.doctor(root, planning_only=True)
    assert report['ready'] is True
    check = next(c for c in report['checks'] if c['name'] == 'openai')
    assert check['ok'] is False and check['required'] is False
