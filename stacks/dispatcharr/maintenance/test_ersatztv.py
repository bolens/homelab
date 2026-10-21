"""ErsatzTV correctness/recovery fixtures without Docker or network access."""

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

from ersatztv import (compare_guides, definition_drift, derived_plan, online_backup,
                      xml_programmes)


BINDINGS = [{"guide_id": "etv-one", "output_number": "100"}]
ROWS = [(90, 150, "Series", "Episode 1"), (150, 230, "Series", "Episode 2")]


class GuideTests(unittest.TestCase):
    def compare(self, rows):
        return compare_guides(BINDINGS, {"etv-one": ROWS}, {"etv-one": ROWS},
                              {"100": rows}, 100, 200)

    def test_matching_real_episode_airings_pass(self):
        self.assertFalse(any(self.compare(ROWS).values()))

    def test_placeholder_title_missing_episode_and_stale_airtime_fail(self):
        for bad in [[(90, 230, "Channel name", "")],
                    [(90, 150, "Series", ""), ROWS[1]],
                    [(91, 150, "Series", "Episode 1"), ROWS[1]]]:
            self.assertEqual(self.compare(bad)["differences"], 1)

    def test_duplicate_airings_are_not_hidden_by_set_conversion(self):
        self.assertEqual(self.compare(ROWS + ROWS[:1])["differences"], 1)

    def test_native_gap_overlap_and_absent_channel_fail(self):
        for rows, key in [([(90, 140, "S", "E"), ROWS[1]], "gaps"),
                          ([(90, 160, "S", "E"), ROWS[1]], "overlaps"),
                          ([], "missing_channels")]:
            result = compare_guides(BINDINGS, {"etv-one": rows}, {}, {}, 100, 200)
            self.assertGreater(result[key], 0)

    def test_xmltv_preserves_episode_names_and_offset(self):
        _, rows = xml_programmes(b'<tv><channel id="a"><display-name>A</display-name></channel>'
            b'<programme channel="a" start="20261021090000 -0600" stop="20261021093000 -0600">'
            b'<title>Show &amp; Co</title><sub-title>Part 1</sub-title></programme></tv>')
        self.assertEqual(rows['a'][0][2:], ('Show & Co', 'Part 1'))
        self.assertEqual(rows['a'][0][1] - rows['a'][0][0], 1800)


class RecipeTests(unittest.TestCase):
    def test_derived_query_wraps_every_source_branch_and_retains_guards(self):
        original = {'Id': 1, 'Name': 'Source', 'Query': '(A OR B) AND NOT tag_full:"ETV Quarantine"'}
        target = {'Id': 2, 'Name': 'Target', 'Query': 'OLD'}
        recipe = {'definitions': {'SmartCollection': [original, target]},
                  'derived': [{'source_id': 1, 'target_id': 2, 'library_id': 9}]}
        changes = derived_plan(recipe, recipe['definitions'])
        self.assertEqual(changes[0]['query'], '(' + original['Query'] + ') AND type:movie AND library_id:9')
        actual = {'SmartCollection': [original, {**target, 'Query': 'independent edit'}]}
        with self.assertRaises(RuntimeError):
            derived_plan(recipe, actual)

    def test_unreviewed_source_or_target_name_drift_refuses_reconciliation(self):
        baseline = {'SmartCollection': [
            {'Id': 1, 'Name': 'Source', 'Query': 'A'},
            {'Id': 2, 'Name': 'Target', 'Query': 'OLD'}]}
        recipe = {'definitions': baseline,
                  'derived': [{'source_id': 1, 'target_id': 2, 'library_id': 9}]}
        for ident in (1, 2):
            actual = {'SmartCollection': [
                {**row, 'Name': 'UNREVIEWED'} if row['Id'] == ident else dict(row)
                for row in baseline['SmartCollection']]}
            with self.assertRaisesRegex(RuntimeError, 'non-query drift'):
                derived_plan(recipe, actual)

    def test_unrelated_definition_drift_is_detected(self):
        self.assertEqual(definition_drift({'Channel': [1], 'Schedule': [2]},
                                         {'Channel': [1], 'Schedule': [3]}), 1)


class PlexWindowTests(unittest.TestCase):
    def test_observer_filters_large_guide_to_requested_window(self):
        import xml.etree.ElementTree as ET
        from unittest.mock import Mock
        from ersatztv import ErsatzTV
        observer = object.__new__(ErsatzTV)
        observer.config = {'account_id': 1, 'source_id': 1, 'dvr_id': '2'}
        binding = {'guide_id': 'etv-one', 'output_number': '100', 'uuid': 'fixture'}
        observer.recipe = Mock(return_value={
            'definitions': {}, 'bindings': [binding], 'restrictions': []})
        observer.database = Mock(return_value=Mock(close=Mock()))
        observer.request = Mock(return_value=b'fixture XMLTV')
        observer.owner = Mock()
        observer.owner.django.return_value = {
            'bindings': [binding], 'programmes': [('etv-one', 200, 7400, 'Show', 'Episode')]}

        def plex(path, params=None):
            if path == '/livetv/dvrs':
                return ET.fromstring('<MediaContainer><Dvr key="2" epgIdentifier="fixture"/></MediaContainer>')
            # Plex parses the comparison operator from the parameter name. An
            # extra equals sign makes it ignore the bound and return the full guide.
            bounded = params.get('endsAt>') == 200 and params.get('beginsAt<') == 7400
            root = ET.Element('MediaContainer', totalSize='1' if bounded else '20566')
            video = ET.SubElement(root, 'Video', type='episode', grandparentTitle='Show', title='Episode')
            ET.SubElement(video, 'Media', channelVcn='100', beginsAt='200', endsAt='7400')
            return root

        observer.owner.plex_call.side_effect = plex
        with patch('ersatztv.definitions', return_value={}), patch(
                'ersatztv.xml_programmes', return_value=({}, {
                    'etv-one': [(200, 7400, 'Show', 'Episode')]})), patch(
                'ersatztv.time.time', return_value=80):
            self.assertEqual(observer.check()['guide_correct'], 1)


class RequestTests(unittest.TestCase):
    def test_api_session_reads_authenticate_without_adding_key_to_playlist_reads(self):
        from ersatztv import ErsatzTV
        with tempfile.TemporaryDirectory() as directory:
            observer = object.__new__(ErsatzTV)
            observer.root = Path(directory)
            observer.origin = 'http://fixture.invalid'
            (observer.root / 'api-secrets.json').write_text('{"ApiKey":"fixture-key"}')
            with patch('ersatztv.urllib.request.urlopen') as api:
                api.return_value.__enter__.return_value.read.return_value = b'[]'
                observer.request('/api/sessions')
                self.assertEqual(api.call_args.args[0].get_header('X-etv-api-key'), 'fixture-key')
                observer.request('/iptv/xmltv.xml')
                self.assertIsNone(api.call_args.args[0].get_header('X-etv-api-key'))


class BackupTests(unittest.TestCase):
    def make_source(self, root):
        root.mkdir()
        with closing(sqlite3.connect(root / 'ersatztv.sqlite3')) as connection:
            connection.execute('PRAGMA journal_mode=WAL')
            for table in ['Channel', 'SmartCollection', 'CollectionItem', 'MediaItem', 'PlayoutItem']:
                connection.execute('CREATE TABLE ' + table + '(Id INTEGER PRIMARY KEY)')
                connection.execute('INSERT INTO ' + table + ' VALUES(1)')
            connection.commit()
        (root / 'presentation').mkdir()
        (root / 'presentation/id.mp4').write_bytes(b'stable fixture asset')
        (root / 'api-secrets.json').write_text('{"ApiKey":"fixture-only"}')
        (root / 'search-index').mkdir()
        (root / 'search-index/write.lock').write_bytes(b'not a recoverable live index')

    def test_wal_database_and_assets_restore_without_opening_retained_sql(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch) / 'source'
            self.make_source(root)
            dest = Path(scratch) / 'backup'
            result = online_backup(root, dest)
            self.assertTrue(result['verified'])
            self.assertEqual(result['counts']['MediaItem'], 1)
            self.assertFalse((dest / 'search-index').exists())
            self.assertEqual({p.name for p in dest.glob('ersatztv.sqlite3*')}, {'ersatztv.sqlite3'})
            self.assertEqual(result['sqlite_sha256'], hashlib.sha256(
                (dest / 'ersatztv.sqlite3').read_bytes()).hexdigest())
            self.assertEqual((root / 'presentation/id.mp4').read_bytes(),
                             (dest / 'presentation/id.mp4').read_bytes())

    def test_configuration_symlink_refuses_capture(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch) / 'source'
            self.make_source(root)
            (root / 'secret-link').symlink_to(root / 'api-secrets.json')
            with self.assertRaises(RuntimeError):
                online_backup(root, Path(scratch) / 'backup')

    def test_asset_change_during_capture_refuses_verification(self):
        from ersatztv import asset_manifest
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch) / 'source'
            self.make_source(root)
            calls = 0
            def changed(path):
                nonlocal calls
                calls += 1
                result = asset_manifest(path)
                if calls == 2:
                    result['changed'] = 'different'
                return result
            with patch('ersatztv.asset_manifest', side_effect=changed):
                with self.assertRaises(RuntimeError):
                    online_backup(root, Path(scratch) / 'backup')


class ReconcileGuardTests(unittest.TestCase):
    def test_successful_apply_accepts_queries_without_absorbing_other_fields(self):
        from ersatztv import ErsatzTV
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            observer = object.__new__(ErsatzTV)
            observer.config = {'account_id': 1, 'source_id': 1}
            observer.owner = Mock()
            observer.owner.state = Path(directory)
            observer.owner.plex_call.return_value = []
            observer.owner.django.return_value = {'recordings': 0}
            baseline = {'SmartCollection': [
                {'Id': 1, 'Name': 'Source', 'Query': 'OLD SOURCE'},
                {'Id': 2, 'Name': 'Target', 'Query': 'OLD TARGET'}]}
            recipe = {'definitions': baseline,
                      'derived': [{'source_id': 1, 'target_id': 2, 'library_id': 9}]}
            actual = {'SmartCollection': [
                {**baseline['SmartCollection'][0], 'Query': 'NEW SOURCE'},
                dict(baseline['SmartCollection'][1])]}
            updated = {'SmartCollection': [dict(actual['SmartCollection'][0]),
                {**actual['SmartCollection'][1], 'Query': '(NEW SOURCE) AND type:movie AND library_id:9'}]}
            # A concurrent unrelated rename must remain drift after query admission.
            updated['SmartCollection'][0]['Name'] = 'UNREVIEWED'
            observer.recipe = Mock(return_value=recipe)
            observer.recipe_path = Path(directory) / 'recipe.json'
            observer.database = Mock(return_value=Mock(close=Mock()))
            observer.request = Mock(return_value=b'[]')
            observer.backup = Mock()
            with patch('ersatztv.definitions', side_effect=[actual, updated]), patch(
                    'runner.command', return_value=b'PID COMMAND\n1 server\n'):
                self.assertEqual(observer.reconcile(True)['updated_filters'], 1)
            saved = json.loads(observer.recipe_path.read_text())['definitions']
            self.assertEqual(saved['SmartCollection'][0]['Name'], 'Source')
            self.assertEqual(saved['SmartCollection'][0]['Query'], 'NEW SOURCE')
            self.assertEqual(definition_drift(saved, updated), 1)
            self.assertFalse(list(Path(directory).glob('.recipe-recovery-*')))

    def test_native_session_refuses_before_backup_or_filter_mutation(self):
        from ersatztv import ErsatzTV
        from unittest.mock import Mock
        observer = object.__new__(ErsatzTV)
        observer.config = {'account_id': 1, 'source_id': 1}
        observer.owner = Mock()
        observer.owner.plex_call.return_value = []
        observer.owner.django.return_value = {'recordings': 0}
        observer.recipe = Mock(return_value={})
        observer.database = Mock(return_value=Mock(close=Mock()))
        observer.request = Mock(return_value=b'[{"channelNumber":"fixture"}]')
        observer.backup = Mock()
        with patch('ersatztv.definitions', return_value={}), patch(
                'ersatztv.derived_plan', return_value=[{'id': 1}]):
            with self.assertRaisesRegex(RuntimeError, 'Native playback'):
                observer.reconcile(True)
        observer.request.assert_called_once_with('/api/sessions')
        observer.backup.assert_not_called()

    def test_viewing_or_scheduled_recordings_refuse_before_backup_or_put(self):
        from ersatztv import ErsatzTV
        from unittest.mock import Mock
        for activity in [[['viewer']], [[], ['recording']]]:
            observer = object.__new__(ErsatzTV)
            observer.owner = Mock()
            observer.owner.plex_call.side_effect = activity
            observer.recipe = Mock(return_value={})
            observer.database = Mock(return_value=Mock(close=Mock()))
            observer.request = Mock()
            observer.backup = Mock()
            with patch('ersatztv.definitions', return_value={}), patch(
                    'ersatztv.derived_plan', return_value=[{'id': 1}]):
                with self.assertRaises(RuntimeError):
                    observer.reconcile(True)
            observer.request.assert_not_called()
            observer.backup.assert_not_called()

    def test_dry_run_does_not_check_activity_or_mutate(self):
        from ersatztv import ErsatzTV
        from unittest.mock import Mock
        observer = object.__new__(ErsatzTV)
        observer.owner = Mock()
        observer.recipe = Mock(return_value={})
        observer.database = Mock(return_value=Mock(close=Mock()))
        observer.request = Mock()
        with patch('ersatztv.definitions', return_value={}), patch(
                'ersatztv.derived_plan', return_value=[{'id': 1}]):
            self.assertEqual(len(observer.reconcile(False)['changes']), 1)
        observer.owner.plex_call.assert_not_called()
        observer.request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
