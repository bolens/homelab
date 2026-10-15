"""Actual durable callers against projected fixture GENESIS, no remount grant."""
import json
from pathlib import Path
import sys
import unittest
HERE = Path(__file__).absolute().parent
sys.path.insert(0, str(HERE))
from test_identity_tagger import HistoricalFixture, guard, readers


class HistoricalCallerTests(HistoricalFixture):
    def test_real_bootstrap_registration_and_marker_readers_accept_only_committed_history(self):
        state = guard.RegistryState(self.store.path, self.writer)
        registration = guard.RegistrationState(self.store.path, self.writer)
        with self.store.connection() as db:
            db.execute('BEGIN')
            self.assertEqual(state._record(db, self.initialization), self.bootstrap_original)
            token = next(key for kind, key in self.rows_original
                         if kind == 'publication_intent' and key != self.initialization)
            self.assertEqual(registration._record(db, token)['outcome'], 'committed')
        self.assertEqual(guard.registry_snapshot(self.store.path, self.marker)[0]['revision'], 2)
        self.assertEqual(self.rows(), self.rows_original)
        self.assertEqual(self.marker.read_bytes(), self.marker_original)

    def test_old_prepared_accepted_and_aborted_bootstrap_cannot_borrow_adoption(self):
        state = guard.RegistryState(self.store.path, self.writer)
        for outcome in ('prepared', 'accepted', 'aborted'):
            record = dict(self.bootstrap_original, outcome=outcome, accepted=outcome != 'prepared')
            with self.store.connection() as db:
                db.execute("UPDATE records SET value=? WHERE kind='publication_intent' AND key=?",
                           (json.dumps(record), self.initialization))
            with self.subTest(outcome=outcome), self.store.connection() as db:
                db.execute('BEGIN')
                with self.assertRaisesRegex(guard.Unavailable, 'identity-noncommitted-physical-mismatch'):
                    state._record(db, self.initialization)
        with self.store.connection() as db:
            db.execute("UPDATE records SET value=? WHERE kind='publication_intent' AND key=?",
                       (self.rows_original[('publication_intent', self.initialization)], self.initialization))
        self.assertEqual(self.rows(), self.rows_original)

    def test_old_noncommitted_registration_cannot_borrow_adoption(self):
        state = guard.RegistrationState(self.store.path, self.writer)
        token = next(key for kind, key in self.rows_original
                     if kind == 'publication_intent' and key != self.initialization)
        original = self.rows_original[('publication_intent', token)]
        for outcome in ('prepared', 'accepted', 'aborted'):
            record = dict(guard.decode_json(original), outcome=outcome, accepted=outcome != 'prepared')
            with self.store.connection() as db:
                db.execute("UPDATE records SET value=? WHERE kind='publication_intent' AND key=?", (json.dumps(record), token))
            with self.store.connection() as db:
                db.execute('BEGIN')
                with self.assertRaisesRegex(guard.Unavailable, 'identity-noncommitted-physical-mismatch'):
                    state._record(db, token)
        with self.store.connection() as db:
            db.execute("UPDATE records SET value=? WHERE kind='publication_intent' AND key=?", (original, token))
        self.assertEqual(self.rows(), self.rows_original)

    def test_absent_adoption_generic_old_mismatch_stays_refused(self):
        self.ledger_file.unlink()
        self.ledger.rmdir()
        with self.assertRaises(guard.Unavailable):
            guard.registry_snapshot(self.store.path, self.marker)
        with self.store.connection() as db:
            db.execute('BEGIN')
            with self.assertRaises(guard.Unavailable):
                readers.durable_identity(db, self.ledger, self.old, self.current, outcome='committed')
        self.assertEqual(self.rows(), self.rows_original)
        self.assertEqual(self.marker.read_bytes(), self.marker_original)


if __name__ == '__main__':
    unittest.main()
