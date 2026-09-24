"""Pending provider classification and persistent bounded-wait regressions."""
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cooldown_health
from health import assess
import queue_control


class CooldownTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 0
        self.state = queue_control.Store(self.temp.name, clock=lambda: self.now)
        self.rows = [{'status': 'Queued', 'link_type': 'GC-Main'}]
        self.state.data['providers'] = {'GC-Main': {'until': 900}}
        self.database = SimpleNamespace(select=lambda _: self.rows)
        self.addCleanup(patch.stopall)
        patch.object(queue_control, '_STORE', self.state).start()
        patch.dict(sys.modules, {'mylar': SimpleNamespace(queue_control=queue_control)}).start()
        self.value = {'enabled': ['DDL-QUEUE'], 'queues': {'DDL-QUEUE': {'alive': True, 'size': 1}},
                      'downloaded': 0, 'processing': False, 'ddl_active': [], 'ddl_useful': [0, 0]}

    def assess(self, previous=None):
        self.value['ddl_cooldown'] = cooldown_health.snapshot(self.database)
        return assess(self.value, previous or {}, self.now)

    def test_only_pending_providers_control_expected_wait(self):
        self.state.data['providers']['GC-Pixel'] = {'until': 0}
        result = cooldown_health.snapshot(self.database)
        self.assertEqual((result['status'], result['next_retry_at'], result['cooling']),
                         ('Waiting for provider cooldown', 900, 1))
        self.rows.append({'status': 'Queued', 'link_type': 'GC-Pixel'})
        result = cooldown_health.snapshot(self.database)
        self.assertEqual(result['ready'], 1)
        self.assertFalse(result['all_cooling'])

    def test_expiry_has_exact_two_minute_grace(self):
        previous = self.assess()['observations']
        for now in (899, 900, 1019):
            self.now = now
            result = self.assess(previous)
            self.assertFalse(result['errors'])
            previous = result['observations']
        self.now = 1020
        self.assertIn('DDL-QUEUE did not resume within two minutes of provider cooldown expiry', self.assess(previous)['errors'])

    def test_short_cooldown_expiry_not_hidden_by_generic_fifteen_minute_timer(self):
        self.state.data['providers']['GC-Main']['until'] = 30
        previous = self.assess()['observations']
        self.now = 150
        self.assertTrue(self.assess(previous)['errors'])

    def test_extensions_cannot_hide_one_hour_outage_and_state_survives_reload(self):
        previous = self.assess()['observations']
        for now in (800, 1600, 2400, 3599):
            self.now = now
            self.state.data['providers']['GC-Main']['until'] = now + 900
            self.state.save()
            queue_control._STORE = queue_control.Store(self.temp.name, clock=lambda: self.now)
            result = self.assess(previous)
            self.assertFalse(result['errors'])
            previous = result['observations']
        self.now = 3600
        self.assertIn('DDL-QUEUE has made no useful progress for one hour during provider cooldowns', self.assess(previous)['errors'])

    def test_useful_progress_resets_outage_and_idle_clears_wait(self):
        previous = self.assess()['observations']
        self.now = 3600
        self.state.data['providers']['GC-Main']['until'] = 4500
        self.value['ddl_useful'] = [1024, 0]
        result = self.assess(previous)
        self.assertFalse(result['errors'])
        self.rows.clear()
        self.value['queues']['DDL-QUEUE']['size'] = 0
        self.now = 99999
        self.assertFalse(self.assess(result['observations'])['errors'])

    def test_active_transfer_and_dead_worker_not_excused(self):
        self.rows[0]['status'] = 'Downloading'
        self.value['ddl_active'] = [['id', 1, 'date']]
        previous = self.assess()['observations']
        self.now = 900
        self.assertIn('DDL-QUEUE has made no progress for 15 minutes', self.assess(previous)['errors'])
        self.rows[0]['status'] = 'Queued'
        self.value['ddl_active'] = []
        self.state.data['providers']['GC-Main']['until'] = 1800
        self.value['queues']['DDL-QUEUE']['alive'] = False
        self.assertIn('DDL-QUEUE is down', self.assess(previous)['errors'])

    def test_bad_state_is_visible_without_raw_values(self):
        for value in ('private malformed value', float('nan'), True, None):
            self.state.data['providers']['GC-Main']['until'] = value
            result = self.assess()
            self.assertEqual(result['errors'], ['DDL cooldown state requires review'])
            self.assertFalse(self.value['ddl_cooldown']['valid'])
        self.state.path.write_text('invalid json')
        queue_control._STORE = None
        with patch.dict(sys.modules, {'mylar': SimpleNamespace(queue_control=queue_control, DATA_DIR=self.temp.name)}):
            self.assertFalse(cooldown_health.snapshot(self.database)['valid'])

    def test_new_ready_work_does_not_inherit_unexpired_wait(self):
        self.state.data['providers']['GC-Main']['until'] = 3000
        previous = self.assess()['observations']
        self.rows.append({'status': 'Queued', 'link_type': 'GC-Pixel'})
        self.now = 900
        self.assertIn('DDL-QUEUE has made no progress for 15 minutes', self.assess(previous)['errors'])

    def test_pending_database_rows_count_even_if_native_queue_is_empty(self):
        self.value['queues']['DDL-QUEUE']['size'] = 0
        previous = self.assess()['observations']
        self.now = 1020
        self.assertTrue(self.assess(previous)['errors'])


if __name__ == '__main__':
    unittest.main()
