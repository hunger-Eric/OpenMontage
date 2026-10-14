import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('codex_release', ROOT / 'scripts/build_codex_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def repository(root, files):
    root.mkdir()
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding='utf-8')
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    subprocess.run(['git', '-c', 'user.name=test', '-c', 'user.email=test@example.invalid',
                    'commit', '-qm', 'fixture'], cwd=root, check=True)
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()


def fixture(tmp_path, pinned=True):
    flow = tmp_path / 'flow'
    sha = repository(flow, {'src/index.ts': 'source', '.env': 'secret'})
    root = tmp_path / 'app'
    repository(root, {'portable-release.json': json.dumps({
        'flow_repository': 'test/flow', 'flow_revision': sha if pinned else '0' * 40}),
        'INSTALL_FOR_AGENT.md': 'install', 'scripts/codex_setup.py': 'setup',
        'docs/CODEX_PORTABILITY.md': 'instructions', '.env.example': 'KEY=',
        '.env': 'private', 'config.local.yaml': 'private preferences',
        'projects/sample/media.mp4': 'generated', 'node_modules/module.js': 'dependency'})
    return root, flow


def test_bundle_uses_commits_and_excludes_private_runtime_files(tmp_path):
    root, flow = fixture(tmp_path)
    (root / 'INSTALL_FOR_AGENT.md').write_text('uncommitted change')
    (root / 'untracked.secret').write_text('not in git')
    output = tmp_path / 'release'
    receipt = release.build_bundle(root, flow, output)
    with zipfile.ZipFile(output / 'OpenMontage-Codex.zip') as archive:
        assert archive.read('OpenMontage/INSTALL_FOR_AGENT.md') == b'install'
        assert 'OpenMontage/.env.example' in archive.namelist()
        assert not any(name.endswith('/.env') or '/projects/' in name or '/node_modules/' in name
                       or name.endswith('/config.local.yaml') or 'untracked.secret' in name
                       for name in archive.namelist())
    assert receipt['zip_integrity'] == 'passed'
    assert receipt['package_sha256'] in (output / 'SHA256SUMS.txt').read_text()
    with pytest.raises(FileExistsError):
        release.build_bundle(root, flow, output)


def test_bundle_rejects_wrong_flow_revision(tmp_path):
    root, flow = fixture(tmp_path, pinned=False)
    with pytest.raises(ValueError, match='does not match'):
        release.build_bundle(root, flow, tmp_path / 'release')
