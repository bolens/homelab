"""Exercise native provider selection against persisted cooldowns without network calls."""
import ast
import copy
from operator import itemgetter
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import queue_control as control
from patch_search_cooldown import patched_source

SOURCE = Path(sys.argv.pop(1)) / 'search.py'


class SearchCooldownTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.now = 1000
        self.state = control.Store(temporary.name, lambda: self.now)
        self.settings = SimpleNamespace(
            ENABLE_TORRENT_SEARCH=False, EXPERIMENTAL=False, NEWZNAB=True,
            EXTRA_NEWZNABS=[['One', 'https://one.invalid', '', '', '', 1],
                           ['Two', 'https://two.invalid', '', '', '', 1]],
            ENABLE_DDL=True, ENABLE_GETCOMICS=True, ENABLE_EXTERNAL_SERVER=False,
            ENABLE_AIRDCPP=False, USENET_RETENTION=1000,
            PROVIDER_ORDER={0: 'DDL(GetComics)', 1: 'One', 2: 'Two'})
        self.mylar = SimpleNamespace(CONFIG=self.settings, queue_control=control)
        self.logger = Mock()
        self.blocked = set()
        tree = ast.parse(SOURCE.read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('provider_order', 'provider_sequence')]
        namespace = {'mylar': self.mylar, 'logger': self.logger,
                     'helpers': SimpleNamespace(block_provider_check=lambda name: name in self.blocked),
                     'itemgetter': itemgetter}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), 'exec'), namespace)
        self.native = namespace['provider_order']
        self.original = ['DDL(GetComics)', 'newznab: One', 'newznab: Two']

    def order(self):
        with patch.dict(sys.modules, {'mylar': self.mylar}), patch.object(control, '_STORE', self.state):
            return self.native(initial_run=True)

    def cooling(self):
        self.state.data['providers'] = {
            name: {'failures': 2, 'until': self.now + 100}
            for name in ('GC-Main', 'GC-Mega', 'GC-Media', 'GC-Pixel')}

    def test_all_known_hosts_cooling_prefers_nzb_without_mutating_config_or_state(self):
        self.cooling()
        before = copy.deepcopy(self.state.data)
        configured = copy.deepcopy(self.settings.PROVIDER_ORDER)
        result = self.order()
        self.assertEqual(result['prov_order'], ['newznab: One', 'newznab: Two', 'DDL(GetComics)'])
        self.assertEqual(result['totalproviders'], 3)
        self.assertEqual([row['provider'] for row in result['newznab_info']], self.original[1:])
        self.assertEqual(before, self.state.data)
        self.assertEqual(configured, self.settings.PROVIDER_ORDER)
        self.assertFalse(self.state.path.exists())

    def test_exact_expiry_restores_original_order_without_restart(self):
        self.cooling()
        self.assertNotEqual(self.order()['prov_order'], self.original)
        self.now += 100
        self.assertEqual(self.order()['prov_order'], self.original)

    def test_one_available_host_keeps_normal_order(self):
        self.cooling()
        self.state.data['providers']['GC-Pixel']['until'] = 0
        self.assertEqual(self.order()['prov_order'], self.original)
        self.cooling()
        self.state.data['providers']['GC-Mirror'] = {'until': self.now}
        self.assertEqual(self.order()['prov_order'], self.original)

    def test_no_history_does_not_infer_a_cooldown(self):
        self.assertEqual(self.order()['prov_order'], self.original)
        self.state.data['providers']['Unrelated'] = {'until': self.now + 900}
        self.assertEqual(self.order()['prov_order'], self.original)

    def test_cooldowns_survive_reload(self):
        self.cooling()
        self.state.save()
        self.state = control.Store(self.state.root, lambda: self.now)
        self.assertEqual(self.order()['prov_order'][0], 'newznab: One')

    def test_healthy_independent_ddl_source_keeps_configured_preference(self):
        self.cooling()
        self.settings.ENABLE_EXTERNAL_SERVER = True
        self.settings.PROVIDER_ORDER[3] = 'DDL(External)'
        self.assertEqual(self.order()['prov_order'], self.original + ['DDL(External)'])

    def test_disabled_or_blocked_indexers_are_not_enabled_by_fallback(self):
        self.cooling()
        self.settings.EXTRA_NEWZNABS[0][5] = 0
        self.blocked.add('Two')
        self.assertEqual(self.order()['prov_order'], ['DDL(GetComics)'])
        self.blocked.clear()
        self.assertEqual(self.order()['prov_order'], ['newznab: Two', 'DDL(GetComics)'])
        self.blocked.add('DDL(GetComics)')
        self.assertEqual(self.order()['prov_order'], ['newznab: Two'])

    def test_patch_is_idempotent_and_rejects_unknown_source(self):
        source = SOURCE.read_text()
        self.assertEqual(patched_source(source), source)
        with self.assertRaises(ValueError):
            patched_source('def provider_order():\n    return {}\n')

    def test_unreadable_cooldown_state_does_not_abort_other_searches(self):
        with patch.object(control, 'store', side_effect=ValueError('invalid fixture')):
            self.assertEqual(self.order()['prov_order'], self.original)
        self.cooling()
        self.state.data['providers']['GC-Main']['until'] = None
        self.assertEqual(self.order()['prov_order'], self.original)


if __name__ == '__main__':
    unittest.main()
