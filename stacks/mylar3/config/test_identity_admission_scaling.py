"""Actual adopted authority: bound repeated physical-pair projection per read.

All SQLite/ledger/Writer files are disposable. Historical device identities are
fixture genesis only, never operational migration or cache authorization.
"""
import json
import unittest
from unittest.mock import patch

from test_identity_tagger import HistoricalFixture, guard, adoption, fixture


class AdmissionScaling(HistoricalFixture):
    def setUp(self):
        super().setUp()
        self.ledger_file.unlink()
        self.ledger.rmdir()
        # Rebuild PUBLIC fixture genesis with fourteen committed witnesses using
        # one historical physical pair, matching the incident's measured shape.
        self.state.identity = self.old['database_identity']
        self.state.writer_binding = self.old['writer_identity']
        fixture.RegistryTests.seed(self, [self.record(i) for i in range(13)])
        with self.store.connection() as db:
            db.executemany('INSERT INTO records VALUES(?,?,?,?)',
                          [('observation', str(i), json.dumps({'fixture': 'x' * 1024}), 0)
                           for i in range(6000)])
        self.ledger.mkdir(mode=0o700)
        with self.store.connection() as db:
            db.execute('BEGIN')
            plan = adoption.prepare_plan(db, self.old, self.current, self.evidence)
        token = adoption.digest(adoption.encoded(plan))
        self.ledger_file = self.ledger / (token + '.json')
        self.ledger_file.write_bytes(adoption.encoded(dict(
            version=1, kind='committed-device-identity-edge', token=token,
            accepted=True, plan=plan)))
        self.ledger_file.chmod(0o600)
        self.rows_original = self.rows()
        self.marker_original = self.marker.read_bytes()

    def test_fourteen_witnesses_validate_one_pair_once_per_fresh_read(self):
        before = self.store.path.read_bytes()
        ledger = self.ledger_file.read_bytes()
        with patch.object(guard, 'historical_identity', wraps=guard.historical_identity) as projection:
            self.assertEqual(guard.registry_snapshot(self.store.path, self.marker)[0]['revision'], 13)
        # One unique committed-witness pair, plus the independent final marker
        # projection. Every call remains genuine durable ledger/SQLite reading.
        self.assertEqual(projection.call_count, 2)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(self.ledger_file.read_bytes(), ledger)
        self.assertEqual(self.marker.read_bytes(), self.marker_original)
        # There is no cross-call cached authorization: a malformed new ledger
        # entry is immediately refused by the next complete fresh read.
        unknown = self.ledger / ('0' * 64 + '.json')
        unknown.write_bytes(b'{}')
        unknown.chmod(0o600)
        with self.assertRaises(guard.Unavailable):
            guard.registry_snapshot(self.store.path, self.marker)
        self.assertEqual(self.rows(), self.rows_original)

    def test_distinct_future_binding_is_not_folded_into_historical_pair(self):
        self.assertEqual(self.register(13)['revision'], 14)
        before = self.rows()
        ledger = self.ledger_file.read_bytes()
        with patch.object(guard, 'historical_identity', wraps=guard.historical_identity) as projection:
            self.assertEqual(guard.registry_snapshot(self.store.path, self.marker)[0]['revision'], 14)
        self.assertEqual(projection.call_count, 3)
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.ledger_file.read_bytes(), ledger)

    def test_direct_witness_validates_every_intent_before_projection(self):
        token = sorted(key for kind, key in self.rows() if kind == 'publication_intent')[-1]
        original = self.store.get('publication_intent', token)
        changed = dict(original, accepted=False)
        with self.store.connection() as db:
            db.execute('BEGIN')
            census, _ = guard.complete_census(db)
            db.execute("UPDATE records SET value=? WHERE kind='publication_intent' AND key=?",
                       (json.dumps(changed), token))
            with (patch.object(guard, 'historical_identity', wraps=guard.historical_identity) as projection,
                  self.assertRaises(guard.Unavailable)):
                guard.initialization_witness(db, self.initialization, census,
                    self.current['database_identity'], self.current['writer_identity'],
                    ledger_dir=self.ledger)
            projection.assert_not_called()
            db.rollback()
        self.assertEqual(self.rows(), self.rows_original)

    def test_direct_last_intent_ledger_change_is_seen_before_admission(self):
        with self.store.connection() as db:
            db.execute('BEGIN')
            census, _ = guard.complete_census(db)
            actual = guard.intent_record
            calls = []
            unknown = self.ledger / ('0' * 64 + '.json')
            def changed_at_tail(key, value):
                plan = actual(key, value)
                calls.append(key)
                if len(calls) == 14:
                    unknown.write_bytes(b'{}')
                    unknown.chmod(0o600)
                return plan
            with (patch.object(guard, 'intent_record', side_effect=changed_at_tail),
                  self.assertRaises(guard.Unavailable)):
                guard.initialization_witness(db, self.initialization, census,
                    self.current['database_identity'], self.current['writer_identity'],
                    ledger_dir=self.ledger)
            self.assertEqual(len(calls), 14)
        unknown.unlink()  # Disposable fixture only, before testing a fresh call.
        with self.store.connection() as db:
            db.execute('BEGIN')
            census, _ = guard.complete_census(db)
            guard.initialization_witness(db, self.initialization, census,
                self.current['database_identity'], self.current['writer_identity'],
                ledger_dir=self.ledger)
        self.assertEqual(self.rows(), self.rows_original)

    def test_last_witness_malformed_token_or_outcome_cannot_hide_in_group(self):
        rows = self.rows()
        token = sorted(key for kind, key in rows if kind == 'publication_intent'
                       and key != self.initialization)[-1]
        original = rows['publication_intent', token]
        for changes in ({'outcome': 'accepted'}, {'accepted': False}):
            value = json.loads(original)
            value.update(changes)
            with self.store.connection() as db:
                db.execute("UPDATE records SET value=? WHERE kind='publication_intent' AND key=?",
                           (json.dumps(value), token))
            with self.assertRaises(guard.Unavailable):
                guard.registry_snapshot(self.store.path, self.marker)
        with self.store.connection() as db:
            db.execute("UPDATE records SET value=? WHERE kind='publication_intent' AND key=?",
                       (original, token))
        self.assertEqual(self.rows(), self.rows_original)
        self.assertEqual(guard.registry_snapshot(self.store.path, self.marker)[0]['revision'], 13)


if __name__ == '__main__':
    unittest.main()
