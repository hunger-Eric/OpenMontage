"""Exercise real CLI persistence using disposable libraries, without live assets."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('characters.py')
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j3ioAAAAASUVORK5CYII=')


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / 'library'
        self.card = self.root / 'source.png'
        self.card.write_bytes(PNG)

    def command(self, *args, succeeds=True):
        result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.library), *args],
                                capture_output=True, encoding='utf-8', cwd=self.root)
        self.assertEqual(result.returncode, 0 if succeeds else 1, result.stderr)
        return json.loads(result.stdout if succeeds else result.stderr)

    def add(self, name='小林'):
        return self.command('register', '--name', name, '--card', str(self.card),
                            '--description', '仓库导购')['result']

    def test_unicode_and_fresh_process_lookup_after_source_removed(self):
        added = self.add()['character']
        self.card.unlink()
        shown = self.command('show', '小林')['result']
        self.assertEqual(shown['id'], added['id'])
        self.assertEqual(Path(shown['card_path']).read_bytes(), PNG)
        self.assertEqual(shown['sha256'], hashlib.sha256(PNG).hexdigest())
        self.assertEqual(len(self.command('list', '--query', '仓库')['result']), 1)
        # Another working directory/project still resolves the same local card.
        other = self.root / 'another-project'
        other.mkdir()
        output = subprocess.check_output([sys.executable, str(SCRIPT), '--root', str(self.library),
                                          'show', shown['id']], cwd=other, encoding='utf-8')
        self.assertEqual(json.loads(output)['result']['card_path'], shown['card_path'])

    def test_idempotent_register_and_collision_preserve_identity(self):
        first = self.add()['character']
        repeated = self.add()
        self.assertTrue(repeated['reused'])
        self.assertEqual(repeated['character']['id'], first['id'])
        self.card.write_bytes(PNG + b'different')
        self.command('register', '--name', '小林', '--card', str(self.card), succeeds=False)
        self.assertEqual(self.command('show', '小林')['result']['sha256'], first['sha256'])
        self.assertEqual(Path(first['card_path']).read_bytes(), PNG)

    def test_rename_keeps_id_and_cannot_overwrite_other_role(self):
        first = self.add()['character']
        self.add('小周')
        renamed = self.command('rename', '小林', '--name', '林姐')['result']
        self.assertEqual(first['id'], renamed['id'])
        self.assertEqual(first['card_path'], renamed['card_path'])
        self.command('rename', '林姐', '--name', '小周', succeeds=False)
        self.assertEqual(self.command('show', '林姐')['result']['id'], first['id'])

    def test_empty_query_does_not_create_a_library(self):
        self.assertEqual(self.command('list')['result'], [])
        self.assertFalse(self.library.exists())
        self.command('show', '不存在', succeeds=False)
        self.assertFalse(self.library.exists())


if __name__ == '__main__':
    unittest.main()
