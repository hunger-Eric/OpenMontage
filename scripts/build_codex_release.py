"""Build a source-only Codex bundle from exact committed repository revisions."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.venv', 'venv', 'node_modules', 'projects', 'artifacts',
            '.backlot', '.runtime', '.codegraph', '__pycache__', '.cache', '.tmp'}


def allowed(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or any(p in EXCLUDED for p in path.parts):
        return False
    if path.name == 'config.local.yaml' or path.name == '.env' or path.name.endswith('.env'):
        return False
    if path.name.startswith('.env.') and not path.name.endswith('.example'):
        return False
    return True


def snapshot(root: Path) -> tuple[str, dict[str, bytes]]:
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    raw = subprocess.check_output(['git', 'archive', '--format=zip', sha], cwd=root)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()
                 if not name.endswith('/') and allowed(name)}
    return sha, files


def build_bundle(root: Path, flow_root: Path, output: Path) -> dict:
    sha, files = snapshot(root)
    # Pin is read from the release commit, never from uncommitted local changes.
    pin = json.loads(files['portable-release.json'])
    flow_sha, flow_files = snapshot(flow_root)
    if flow_sha != pin['flow_revision']:
        raise ValueError('Flow checkout does not match portable-release.json; refusing to package it.')
    for required in ('INSTALL_FOR_AGENT.md', 'scripts/codex_setup.py', 'docs/CODEX_PORTABILITY.md'):
        if required not in files:
            raise ValueError(f'Release commit is missing {required}')
    combined = {f'OpenMontage/{name}': data for name, data in files.items()}
    combined.update({f'google-flow-mcp-v4/{name}': data for name, data in flow_files.items()})
    manifest = {'openmontage_revision': sha, 'flow_repository': pin['flow_repository'],
                'flow_revision': flow_sha, 'files': {
                    name: hashlib.sha256(data).hexdigest() for name, data in sorted(combined.items())}}
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'OpenMontage-Codex.zip'
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(combined.items()):
            archive.writestr(name, data)
        archive.writestr('READ-ME-FIRST.txt',
                         '解压后在 Codex 打开 OpenMontage 文件夹，将 INSTALL_FOR_AGENT.md 交给智能体执行。\n')
        archive.writestr('SOURCE-MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError('Release ZIP integrity check failed')
        for name, digest in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError(f'Release readback failed: {name}')
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    receipt = dict(manifest, package=target.name, package_sha256=digest,
                   package_bytes=target.stat().st_size, zip_integrity='passed')
    (output / 'release-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    (output / 'SHA256SUMS.txt').write_text(f'{digest}  {target.name}\n', encoding='utf-8')
    (output / 'RELEASE_NOTES.md').write_text(
        '# Codex 源码安装包\n\n下载 **OpenMontage-Codex.zip**，解压后在 Codex 打开 '
        '`OpenMontage` 文件夹，将 `INSTALL_FOR_AGENT.md` 交给智能体配置。\n\n'
        '包含 OpenMontage、安装说明和固定版本的 Flow 桥源码；不包含账号、密钥、'
        '浏览器登录、虚拟环境或生成媒体。依赖在接收电脑安装，账号由接收方登录。\n\n'
        f'OpenMontage commit: `{sha}`\n\nFlow commit: `{flow_sha}`\n\n'
        '附件提供 SHA-256 校验和及完整源码清单。新电脑的真实安装和生成仍需现场验证。\n',
        encoding='utf-8')
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flow-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build_bundle(ROOT, args.flow_root.resolve(), args.output.resolve())
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()
