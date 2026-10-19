"""Actual adopted authority: bound repeated physical-pair projection per read.

All SQLite/ledger/Writer files are disposable. Historical device identities are
fixture genesis only, never operational migration or cache authorization.
"""
import copy
import json
import threading
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


def inventory(n=512):
    rows=[dict(name=f'{i:04d}.jpg',bytes=3,directory=False,sha256='a'*64) for i in range(n)]
    pages=[r['name'] for r in rows]
    return dict(version=1,members=rows,pages=pages,payload=guard.token(rows,pages))


class RealAdoptedInventory(HistoricalFixture):
    def record(self,revision=0):
        row=super().record(revision)
        row['inventory']=inventory()
        return row

    def test_many_member_adopted_authority_reuses_only_inventory_validation(self):
        original=self.rows()
        with patch.object(guard,'_validate_inventory',wraps=guard._validate_inventory) as validation:
            self.assertEqual(guard.registry_snapshot(self.store.path,self.marker)[0]['revision'],2)
            self.assertEqual(validation.call_count,1)
            self.assertEqual(guard.registry_snapshot(self.store.path,self.marker)[0]['revision'],2)
            self.assertEqual(validation.call_count,2)
        with patch.object(guard,'_inventory_memo_key',return_value=None),patch.object(guard,'_validate_inventory',wraps=guard._validate_inventory) as uncached:
            self.assertEqual(guard.registry_snapshot(self.store.path,self.marker)[0]['revision'],2)
            # Eight outer validations plus four fresh prefix captures of eight.
            self.assertEqual(uncached.call_count,40)
        self.assertEqual(self.rows(),original)
        self.assertFalse(hasattr(guard._INVENTORY_VALIDATION,'memo'))


class InventoryMemo(unittest.TestCase):
    def scope(self,body):
        with patch.object(guard,'_registry_snapshot',side_effect=body):
            return guard.registry_snapshot('unused','unused')

    def test_changed_same_object_member_refused_within_invocation(self):
        value=inventory(2)
        def body(*args):
            guard.validate(value)
            value['members'][0]['sha256']='bad'
            with self.assertRaises(guard.Unavailable):guard.validate(value)
        self.scope(body)

    def test_changed_next_invocation_and_failed_validation_never_cached(self):
        value=inventory(2)
        self.scope(lambda *args:guard.validate(value))
        value['pages'].reverse()
        for unused in range(2):
            with self.assertRaises(guard.Unavailable):self.scope(lambda *args:guard.validate(value))
            self.assertFalse(hasattr(guard._INVENTORY_VALIDATION,'memo'))

    def test_non_json_aliases_bypass_memo(self):
        original=inventory(2)
        class Rows(list):pass
        class Number(int):pass
        aliases=[]
        for field,replacement in [('pages',tuple(original['pages'])),('members',Rows(original['members'])),('version',True),('version',Number(1))]:
            value=copy.deepcopy(original);value[field]=replacement;aliases.append(value)
        value=copy.deepcopy(original);value['members'][0]['bytes']=3.0;aliases.append(value)
        def body(*args):
            guard.validate(original)
            for value in aliases:
                self.assertIsNone(guard._inventory_memo_key(value))
                # Original behavior remains authoritative, including permitted subclasses.
                with patch.object(guard,'_validate_inventory',wraps=guard._validate_inventory) as raw:
                    try:guard.validate(value)
                    except guard.Unavailable:pass
                    self.assertEqual(raw.call_count,1)
        self.scope(body)

    def test_thread_and_nested_exception_scopes_clear(self):
        value=inventory(2);failures=[]
        def foreign():
            try:
                self.assertFalse(hasattr(guard._INVENTORY_VALIDATION,'memo'))
                with patch.object(guard,'_validate_inventory',wraps=guard._validate_inventory) as raw:
                    guard.validate(value);guard.validate(value)
                    self.assertEqual(raw.call_count,2)
            except BaseException as error:failures.append(error)
        def outer(*args):
            guard.validate(value);memo=guard._INVENTORY_VALIDATION.memo
            worker=threading.Thread(target=foreign);worker.start();worker.join()
            with patch.object(guard,'_registry_snapshot',side_effect=RuntimeError('fixture')):
                with self.assertRaises(RuntimeError):guard.registry_snapshot('nested','nested')
            self.assertIs(guard._INVENTORY_VALIDATION.memo,memo)
        self.scope(outer)
        self.assertEqual(failures,[])
        self.assertFalse(hasattr(guard._INVENTORY_VALIDATION,'memo'))

    def test_bounds_and_mutation_during_validation_do_not_store(self):
        value=inventory(2)
        def body(*args):
            with patch.object(guard,'_INVENTORY_MEMO_COUNT',1):
                guard.validate(value)
                other=inventory(3);guard.validate(other)
                self.assertEqual(len(guard._INVENTORY_VALIDATION.memo[0]),1)
            guard._INVENTORY_VALIDATION.memo=[set(),0]
            with patch.object(guard,'_INVENTORY_MEMO_BYTES',1):
                guard.validate(value)
                self.assertEqual(guard._INVENTORY_VALIDATION.memo,[set(),0])
            emoji=inventory(2);emoji['members'][0]['name']='😀'*100
            with patch.object(guard,'_INVENTORY_MEMO_BYTES',1000),patch.object(guard.json,'dumps',side_effect=AssertionError('serialization reached')):
                self.assertIsNone(guard._inventory_memo_key(emoji))
            huge=inventory(2);huge['version']=10**5000
            self.assertIsNone(guard._inventory_memo_key(huge))
            raw=guard._validate_inventory
            def mutate(v):
                raw(v);v['members'][0]['name']='changed.jpg'
            with patch.object(guard,'_validate_inventory',side_effect=mutate):guard.validate(value)
            self.assertEqual(guard._INVENTORY_VALIDATION.memo,[set(),0])
        self.scope(body)


class CapturedPrefixComparison(HistoricalFixture):
    def test_pure_original_capture_comparison_never_mutates_inputs(self):
        with self.store.connection() as db:
            db.execute('BEGIN');current=adoption.capture_prefix(db)
        prefix=copy.deepcopy(current);tape=adoption.encoded([current,prefix])
        self.assertIs(adoption._check_captured_prefix(current,prefix),current)
        self.assertEqual(adoption.encoded([current,prefix]),tape)
        for name in ('schema','epoch','bootstrap_token'):
            bad=copy.deepcopy(prefix);bad[name]='0'*64
            with self.subTest(name=name),self.assertRaises(guard.Unavailable):adoption._check_captured_prefix(current,bad)
        bad=copy.deepcopy(prefix);key=next(iter(bad['committed_intents']));bad['committed_intents'][key]='0'*64
        with self.assertRaises(guard.Unavailable):adoption._check_captured_prefix(current,bad)
        self.assertEqual(adoption.encoded([current,prefix]),tape)

    def test_public_wrapper_reads_current_rows_on_every_call(self):
        with self.store.connection() as db:
            db.execute('BEGIN');prefix=adoption.capture_prefix(db)
            with patch.object(adoption,'capture_prefix',wraps=adoption.capture_prefix)as capture:
                self.assertEqual(adoption.check_prefix(db,prefix),prefix)
                key,raw=db.execute("SELECT key,value FROM records WHERE kind='publication_attestation' LIMIT 1").fetchone()
                db.execute("UPDATE records SET value=? WHERE kind='publication_attestation' AND key=?",(raw+' ',key))
                with self.assertRaisesRegex(guard.Unavailable,'identity-adopted-history-prefix-changed'):adoption.check_prefix(db,prefix)
                self.assertEqual(capture.call_count,2)
            db.rollback()

    def two_edges(self):
        self.ledger_file.unlink();middle=copy.deepcopy(self.current)
        for field,indexes in(('database_identity',(0,)),('writer_identity',(0,2))):
            for index in indexes:middle[field][index]+=202
        with self.store.connection()as db:
            db.execute('BEGIN');first=adoption.prepare_plan(db,self.old,middle,self.evidence);token=adoption.digest(adoption.encoded(first));second=adoption.prepare_plan(db,middle,self.current,self.evidence,previous=token)
        for plan in(first,second):
            token=adoption.digest(adoption.encoded(plan));path=self.ledger/(token+'.json');path.write_bytes(adoption.encoded(dict(version=1,kind='committed-device-identity-edge',token=token,accepted=True,plan=plan)));path.chmod(0o600)

    def test_real_two_edge_history_captures_original_and_final_only(self):
        self.two_edges();rows=self.rows();marker=self.marker.read_bytes();ledger={p.name:p.read_bytes()for p in self.ledger.iterdir()}
        with self.store.connection()as db:
            db.execute('BEGIN')
            with patch.object(adoption,'capture_prefix',wraps=adoption.capture_prefix)as capture:
                self.assertEqual(adoption.resolve(db,self.ledger,self.old,self.current),self.current)
                self.assertEqual(capture.call_count,2)
        self.assertEqual(self.rows(),rows);self.assertEqual(self.marker.read_bytes(),marker);self.assertEqual({p.name:p.read_bytes()for p in self.ledger.iterdir()},ledger)

    def test_final_callback_drift_is_still_refused(self):
        original=copy.deepcopy(self.current)
        for kind in('authority-row','pending','ledger','input'):
            artifact=self.writer.root/'normalizer-v1.pending'if kind=='pending'else self.ledger/('0'*64+'.json')
            with self.subTest(kind=kind),self.store.connection()as db:
                db.execute('BEGIN')
                def changed():
                    if kind=='authority-row':
                        key,raw=db.execute("SELECT key,value FROM records WHERE kind='publication_attestation' LIMIT 1").fetchone();db.execute("UPDATE records SET value=? WHERE kind='publication_attestation' AND key=?",(raw+' ',key))
                    elif kind in('pending','ledger'):artifact.write_bytes(b'{}');artifact.chmod(0o600)
                    else:self.current['database_identity'][0]+=1
                try:
                    with self.assertRaises(guard.Unavailable):adoption.resolve(db,self.ledger,self.old,self.current,boundary=changed)
                finally:
                    db.rollback();self.current=copy.deepcopy(original)
                    if kind in('pending','ledger'):artifact.unlink()


if __name__ == '__main__':
    unittest.main()
