"""Regression: one failed Prowlarr endpoint must not block unrelated releases."""
import ast
from pathlib import Path
import re
import sqlite3
import sys
import unittest
from urllib.parse import urlencode, urlparse
from unittest.mock import Mock
import prowlarr_identity
from patch_prowlarr_identity import patched

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None


def url(release, key='secret', file='title'):
    return 'http://indexer.example/1/download?' + urlencode({'link': release, 'apikey': key, 'file': file})


class IdentityTest(unittest.TestCase):
    def test_distinct_releases_and_credential_independence(self):
        first = prowlarr_identity.release_id(url('release-one'))
        self.assertNotEqual(first, prowlarr_identity.release_id(url('release-two')))
        self.assertEqual(first, prowlarr_identity.release_id(url('release-one', 'rotated', 'renamed')))
        self.assertNotIn('secret', first)
        self.assertNotIn('release-one', first)
        self.assertIsNone(prowlarr_identity.release_id('https://example/api?t=get&id=abc'))
        self.assertIsNone(prowlarr_identity.release_id('https://example/1/download?apikey=secret'))

    def test_legacy_failure_only_blocks_matching_release(self):
        connection = sqlite3.connect(':memory:')
        connection.execute('CREATE TABLE failed (ID TEXT, NZBName TEXT, Status TEXT)')
        connection.execute("INSERT INTO failed VALUES ('download','Old.Release','Failed')")
        database = Mock(selectone=lambda sql, args: connection.execute(sql, args))
        identity = prowlarr_identity.release_id(url('new-release'))
        self.assertIsNone(prowlarr_identity.failed_record(database, identity, 'New.Release'))
        self.assertEqual(prowlarr_identity.failed_record(database, identity, 'Old.Release')[2], 'Failed')
        connection.execute('INSERT INTO failed VALUES (?,?,?)', (identity, 'New.Release', 'Failed'))
        self.assertEqual(prowlarr_identity.failed_record(database, identity, 'New.Release')[2], 'Failed')
        connection.close()

    @unittest.skipUnless(SOURCE, 'Native source fixture not supplied')
    def test_native_generate_id_and_checked_patch(self):
        for name in ('search.py', 'Failed.py'):
            source = patched(name, (SOURCE / name).read_text())
            self.assertEqual(patched(name, source), source)
            ast.parse(source)
        tree = ast.parse(patched('search.py', (SOURCE / 'search.py').read_text()))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'generate_id')
        module = ast.Module(body=[node], type_ignores=[])
        namespace = {'prowlarr_identity': prowlarr_identity, 'logger': Mock(), 'urlparse': urlparse, 're': re}
        exec(compile(module, '<native>', 'exec'), namespace)
        self.assertEqual(namespace['generate_id']('newznab', url('release-one'), 'Series'),
                         prowlarr_identity.release_id(url('release-one')))
        self.assertEqual(namespace['generate_id']('32P', '123', 'Series'), '123')


if __name__ == '__main__':
    unittest.main()
