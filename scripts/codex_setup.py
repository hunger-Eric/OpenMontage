"""Portable Codex setup/doctor. Standard library only; no paid provider calls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
CORE_MODULES = ('yaml', 'pydantic', 'jsonschema', 'dotenv', 'PIL', 'numpy',
                'requests', 'fastapi', 'uvicorn', 'watchfiles')
PROVIDER_MODULES = ('google.genai', 'openai')


def python_path(root: Path) -> Path:
    return root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def initialize(root: Path) -> list[str]:
    """Never replace existing personal configuration, credentials or environments."""
    created = []
    for source, target in (('.env.example', '.env'),
                           ('config.local.example.yaml', 'config.local.yaml')):
        destination = root / target
        content = (root / source).read_text(encoding='utf-8')
        try:
            with destination.open('x', encoding='utf-8') as stream:
                stream.write(content)
            created.append(target)
        except FileExistsError:
            pass
    return created


def run(command: list[str], root: Path) -> None:
    subprocess.run(command, cwd=root, check=True)


def install(root: Path, *, skip_remotion: bool = False) -> None:
    initialize(root)
    interpreter = python_path(root)
    if not interpreter.exists():
        venv.EnvBuilder(with_pip=True).create(root / '.venv')
    run([str(interpreter), '-m', 'pip', 'install', '-r', 'requirements.txt'], root)
    if not skip_remotion:
        npm = shutil.which('npm')
        if not npm:
            raise RuntimeError('Install Node.js/npm, then rerun install; or use --skip-remotion for planning only.')
        # Windows .cmd launch needs cmd.exe; cwd and arguments are fixed, never shell-built.
        command = [npm, 'ci']
        if os.name == 'nt' and npm.lower().endswith('.cmd'):
            command = [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', npm, 'ci']
        run(command, root / 'remotion-composer')


def doctor(root: Path, *, require_flow: bool = False, planning_only: bool = False) -> dict:
    checks = []

    def add(name, ok, required, fix, **details):
        checks.append(dict(name=name, ok=bool(ok), required=required,
                           fix='' if ok else fix, **details))

    add('python_version', sys.version_info >= (3, 10), True, 'Install Python 3.10 or later.')
    interpreter = python_path(root)
    add('project_python', interpreter.is_file(), True, 'Run: python scripts/codex_setup.py install')
    if interpreter.is_file():
        # Import in the project interpreter, not whichever Python invoked doctor.
        code = ('import importlib,json; names=' + repr(CORE_MODULES + PROVIDER_MODULES) + '; missing=[]\n'
                'for name in names:\n'
                ' try: importlib.import_module(name)\n'
                ' except Exception: missing.append(name)\n'
                'print(json.dumps(missing))')
        try:
            result = subprocess.run([str(interpreter), '-c', code], cwd=root,
                                    capture_output=True, text=True, encoding='utf-8',
                                    errors='replace', timeout=60, check=False)
            missing = json.loads(result.stdout) if result.returncode == 0 else list(CORE_MODULES + PROVIDER_MODULES)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            missing = list(CORE_MODULES + PROVIDER_MODULES)
        core_missing = [name for name in missing if name in CORE_MODULES]
        add('core_imports', not core_missing, True,
            'Install requirements.txt with the project Python.', missing=core_missing)
        for name in PROVIDER_MODULES:
            add(name, name not in missing, False,
                'Install requirements.txt with the project Python if using this API provider.')
    for name in ('node', 'npm', 'ffmpeg', 'ffprobe'):
        executable = shutil.which(name)
        add(name, executable is not None, not planning_only,
            f'Install {name} and add it to PATH; reopen the Codex terminal.', path=executable)
    package = root / 'remotion-composer/node_modules/remotion/package.json'
    try:
        expected = json.loads((root / 'remotion-composer/package.json').read_text())['dependencies']['remotion']
        actual = json.loads(package.read_text())['version']
        matched = actual == expected
    except (OSError, ValueError, KeyError):
        expected, actual, matched = None, None, False
    add('remotion', matched, not planning_only, 'Run npm ci in remotion-composer.',
        expected_version=expected, installed_version=actual)
    for name in ('AGENTS.md', 'AGENT_GUIDE.md', 'pipeline_defs', 'skills', '.agents/skills'):
        add(name, (root / name).exists(), True, 'Use the complete OpenMontage source checkout.')
    add('local_env', (root / '.env').is_file(), False, 'Run init and configure only the providers you need.')
    # Read only the non-secret bridge locator; never print .env or API key values.
    flow_root = os.environ.get('GOOGLE_FLOW_MCP_ROOT', '').strip()
    if not flow_root and (root / '.env').exists():
        for line in (root / '.env').read_text(encoding='utf-8').splitlines():
            if line.strip().startswith('GOOGLE_FLOW_MCP_ROOT='):
                flow_root = line.split('=', 1)[1].strip().strip('\"\'')
    bridge = Path(flow_root).expanduser() if flow_root else root.parent / 'google-flow-mcp-v4'
    if not bridge.is_absolute():
        bridge = (root / bridge).resolve()
    built = (bridge / 'dist/index.js').is_file() and (bridge / 'dist/tools.js').is_file()
    add('flow_bridge', built, require_flow,
        'See docs/CODEX_PORTABILITY.md: install/build the bridge and set GOOGLE_FLOW_MCP_ROOT.',
        path=str(bridge), login='not_verified', generation='not_submitted')
    return dict(root=str(root), ready=all(c['ok'] for c in checks if c['required']),
                planning_only=planning_only, checks=checks,
                provider_accounts='not_verified', paid_generation=False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'install', 'doctor'))
    parser.add_argument('--skip-remotion', action='store_true', help='Install Python only, for planning.')
    parser.add_argument('--planning-only', action='store_true', help='Do not require rendering tools in doctor.')
    parser.add_argument('--require-flow', action='store_true', help='Require the optional built Flow bridge.')
    args = parser.parse_args(argv)
    try:
        if args.action == 'init':
            print(json.dumps({'created': initialize(ROOT), 'existing_files_preserved': True}))
        elif args.action == 'install':
            install(ROOT, skip_remotion=args.skip_remotion)
            print('Installed. Run doctor with the project Python; configure provider accounts separately.')
        else:
            report = doctor(ROOT, require_flow=args.require_flow, planning_only=args.planning_only)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report['ready'] else 1
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
