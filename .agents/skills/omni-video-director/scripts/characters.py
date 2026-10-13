"""Persistent, local named character cards. No provider or generation calls."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unicodedata
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit


def default_root() -> Path:
    codex_root = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')
    return codex_root / 'assets' / 'omni-characters'


def normalized(name: str) -> str:
    value = unicodedata.normalize('NFKC', name).strip().casefold()
    if not value:
        raise ValueError('Character name cannot be empty')
    return value


def records(root: Path) -> list[dict]:
    db = root / 'characters.sqlite3'
    if not db.exists():
        return []
    with closing(sqlite3.connect(db)) as connection, connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute('SELECT * FROM characters ORDER BY created_at, id').fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item.pop('name_key')
        item['card_path'] = str((root / item.pop('card_relative_path')).resolve())
        result.append(item)
    return result


def find(root: Path, key: str) -> dict:
    matches = [item for item in records(root)
               if item['id'] == key or normalized(item['name']) == normalized(key)]
    if len(matches) != 1:
        raise ValueError('Character not found; search/list first and use its exact name or ID')
    return matches[0]


def source_project(value: str | None) -> str | None:
    if not value:
        return None
    url = urlsplit(value)
    if url.scheme != 'https' or url.hostname not in ('flow.google.com', 'labs.google'):
        raise ValueError('source-project must be a Google Flow HTTPS project URL')
    # Retain provenance without signed queries or account information.
    return f'https://{url.hostname}{url.path}'


def register(root: Path, name: str, card: Path, description: str = '',
             project: str | None = None) -> dict:
    name_key = normalized(name)
    card = card.expanduser().resolve(strict=True)
    if not card.is_file() or card.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
        raise ValueError('card must be an existing PNG/JPEG/WebP image file')
    content = card.read_bytes()
    if not content:
        raise ValueError('Character card is empty')
    digest = hashlib.sha256(content).hexdigest()
    project = source_project(project)
    root.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(root / 'characters.sqlite3', timeout=15)) as connection, connection:
        connection.execute('''CREATE TABLE IF NOT EXISTS characters (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, name_key TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL, card_relative_path TEXT NOT NULL,
            sha256 TEXT NOT NULL, source_project TEXT, created_at TEXT NOT NULL)''')
        connection.execute('BEGIN IMMEDIATE')
        existing = connection.execute('SELECT id, sha256 FROM characters WHERE name_key=?', (name_key,)).fetchone()
        if existing:
            if existing[1] != digest:
                raise ValueError('This name belongs to another card; choose a different name or explicitly rename that character')
            return {'registered': False, 'reused': True, 'character': find(root, existing[0])}
        relative = Path('cards') / f'{digest}{card.suffix.lower()}'
        destination = root / relative
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise ValueError('Stored card bytes differ from their identity')
        else:
            fd, temporary = tempfile.mkstemp(dir=destination.parent, suffix='.tmp')
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(content)
                os.replace(temporary, destination)
            finally:
                if Path(temporary).exists():
                    Path(temporary).unlink()
        identity = str(uuid.uuid4())
        connection.execute('INSERT INTO characters VALUES (?,?,?,?,?,?,?,?)', (
            identity, name.strip(), name_key, description, relative.as_posix(), digest,
            project, datetime.now(timezone.utc).isoformat()))
    return {'registered': True, 'reused': False, 'character': find(root, identity)}


def rename(root: Path, key: str, name: str) -> dict:
    character = find(root, key)
    with closing(sqlite3.connect(root / 'characters.sqlite3', timeout=15)) as connection, connection:
        connection.execute('UPDATE characters SET name=?, name_key=? WHERE id=?',
                           (name.strip(), normalized(name), character['id']))
    return find(root, character['id'])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=default_root(), help='Override local library root (e.g. for tests)')
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('register')
    add.add_argument('--name', required=True)
    add.add_argument('--card', required=True, type=Path)
    add.add_argument('--description', default='')
    add.add_argument('--source-project')
    listing = commands.add_parser('list')
    listing.add_argument('--query', default='')
    show = commands.add_parser('show')
    show.add_argument('key')
    change = commands.add_parser('rename')
    change.add_argument('key')
    change.add_argument('--name', required=True)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    try:
        if args.command == 'register':
            result = register(root, args.name, args.card, args.description, args.source_project)
        elif args.command == 'show':
            result = find(root, args.key)
        elif args.command == 'rename':
            result = rename(root, args.key, args.name)
        else:
            query = unicodedata.normalize('NFKC', args.query).strip().casefold()
            result = [item for item in records(root) if query in unicodedata.normalize(
                'NFKC', item['name'] + ' ' + item['description']).casefold()]
        print(json.dumps({'ok': True, 'library_root': str(root), 'result': result}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
