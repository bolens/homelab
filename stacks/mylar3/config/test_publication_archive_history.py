"""Real owning cap/SQLite/files; predecessor host SDK/lifecycle origins explicit.

These controls do not establish installed or protected runtime acceptance.
"""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import test_publication_archive_adoption as fixture
from test_publication_archive_adoption import o, load

history = load('publication_archive_history')
verifier = load('publication_archive_verifier')
rollback = load('publication_archive_rollback')


class History(unittest.TestCase):
    def setUp(self):
        self.owner = fixture.Tests('runTest')
        self.owner.setUp()
        self.addCleanup(self.owner.doCleanups)
        self.c = self.owner.c
        self.path = history.initialize(self.c.controller, self.c.writer)

    def cap(self):
        return self.owner.cap()

    def observed(self, cap, *, reverse=False):
        baseline = cap.journal / 'baseline.json'
        original = self.owner.life.vectors
        def bound():
            files, nodes, absent = original()
            files[baseline] = o.signature(baseline)
            return files, nodes, absent
        def fixture_binding(controller, writer, custody, scope, owner, operation_id, path):
            # Original owning cap facts, not a claim of actual installed binding.
            metadata=cap.preparation._operation/'preparation.json'
            original={'files9':[(str(baseline),tuple(cap._files[baseline])),
                                (str(metadata),tuple(cap.preparation._files[metadata]['signature9'])),
                                (str(cap.preparation._operation),tuple(cap.preparation._directory))],
                      'nodes5':[(str(p),tuple(v)) for p,v in cap.preparation._nodes.items()],
                      'absent':(), 'namespaces':(), 'claims':()}
            return original,{'baseline':{'sha256':cap._contents[baseline]}}
        with patch.object(verifier, 'installed'), patch.object(self.owner.life, 'vectors', bound), patch.object(history,'_bind',fixture_binding):
            return history.observe_terminal(self.c.controller, self.c.writer,
                                            self.owner.life, None, self.c.owner, self.c.operation_id, baseline, self.owner.scratch,
                                            rollback=reverse)

    def test_typed_preparation_then_completed_effect_then_fresh_forward(self):
        cap = self.cap()
        prepared = history.prepared(cap.preparation)
        cap.install(); cap.complete()
        executed = history.executed(cap)
        self.assertEqual(history.status(self.c.controller,self.c.writer,self.c.owner,self.c.operation_id)['outcome'],'execute-observed')
        observed = self.observed(cap)
        result=history.status(self.c.controller,self.c.writer,self.c.owner,self.c.operation_id)
        self.assertEqual(result['outcome'],'terminal-observed')
        self.assertIs(result['ordinary_import_grant'],False)
        for ref in (prepared, executed, observed):
            self.assertTrue(Path(ref['path']).is_file())
            value = history.decode(Path(ref['path']).read_bytes())
            self.assertIs(value['ordinary_import_grant'], False)
            self.assertIs(value['publication_acceptance'], False)

    def test_default_terminal_binder_refuses_untyped_scope_and_custody(self):
        with self.assertRaises(o.Held):
            history._bind(self.c.controller,self.c.writer,self.owner.life,None,self.c.owner,self.c.operation_id,self.path/'baseline.json')

    def test_wrong_preparation_and_cap_types_rejected(self):
        for value in ({}, object(), True):
            with self.assertRaises(o.Held): history.prepared(value)
            with self.assertRaises(o.Held): history.executed(value)

    def test_completed_rollback_remains_false_import(self):
        cap = self.cap(); history.prepared(cap.preparation)
        cap.install(); cap.reverse()
        with patch.object(rollback, 'installed'):
            rollback.from_reversed(cap).clear()
        history.executed(cap)
        observed = self.observed(cap, reverse=True)
        value = history.decode(Path(observed['path']).read_bytes())
        self.assertEqual(value['kind'], 'rollback-observed')
        self.assertEqual(history.status(self.c.controller,self.c.writer,self.c.owner,self.c.operation_id)['outcome'],'rollback-observed')
        self.assertIs(value['ordinary_import_grant'], False)

    def test_no_existing_journal_does_not_create_during_prepared(self):
        self.path.rmdir()
        cap = self.cap()
        with self.assertRaises(FileNotFoundError): history.prepared(cap.preparation)
        self.assertFalse(self.path.exists())

    def test_unknown_journal_file_holds(self):
        (self.path / 'foreign').write_bytes(b'foreign')
        cap = self.cap()
        with self.assertRaises(o.Held): history.prepared(cap.preparation)

    def test_lost_fsync_retains_stage_and_partial_history(self):
        cap = self.cap()
        with patch.object(history.os, 'fsync', side_effect=OSError('fixture-lost-write')):
            with self.assertRaises(OSError): history.prepared(cap.preparation)
        self.assertTrue((cap.preparation._operation / 'preparation.json').exists())
        self.assertTrue(tuple(self.path.iterdir()))
        with self.assertRaises(o.Held): history.prepared(cap.preparation)

    def test_output_mode_change_in_fsync_cannot_be_adopted(self):
        cap = self.cap(); real = os.fsync
        def late(fd):
            real(fd)
            if os.fstat(fd).st_mode & 0o170000 == 0o100000: os.fchmod(fd, 0o640)
        with patch.object(history.os, 'fsync', late):
            with self.assertRaises(o.Held): history.prepared(cap.preparation)
        self.assertTrue((cap.preparation._operation / 'preparation.json').exists())

    def test_original_created_fd_survives_write_callback_path_replacement(self):
        cap = self.cap(); real = os.write; fired = []
        def late(fd, data):
            count = real(fd, data)
            if not fired:
                target = next(self.path.iterdir())
                target.rename(self.path / 'aside')
                target.write_bytes(bytes(data)); target.chmod(0o600)
                fired.append(True)
            return count
        with patch.object(history.os, 'write', late):
            with self.assertRaises(o.Held): history.prepared(cap.preparation)
        self.assertTrue(fired)

    def test_existing_record_identity_closed_after_last_fsync(self):
        cap = self.cap(); original = history.prepared(cap.preparation)
        cap.install(); cap.complete()
        real = os.fsync; fired = []
        def late(fd):
            real(fd)
            if not fired and os.fstat(fd).st_mode & 0o170000 == 0o040000:
                os.chmod(original['path'], 0o640); fired.append(True)
        with patch.object(history.os, 'fsync', late):
            with self.assertRaises(o.Held): history.executed(cap)
        self.assertTrue(fired)

    def test_passive_terminal_read_does_not_grant_ordinary_import(self):
        cap = self.cap(); history.prepared(cap.preparation)
        cap.install(); cap.complete(); history.executed(cap); self.observed(cap)
        answer = history.status(self.c.controller,self.c.writer,self.c.owner,self.c.operation_id)
        for field in ('ordinary_import_grant','reader_index_acceptance','publication_acceptance',
                      'mutation_authority','automatic_replay','reader_preservation_verified'):
            self.assertIs(answer[field],False)

    def queued(self):
        import workflow_store
        body={'version':1,'action':'request-archive-repair-adoption','owner':self.c.owner,'operation_id':self.c.operation_id}
        with patch.object(fixture.d,'_store',side_effect=lambda c:workflow_store.Store(c.root,existing_only=True)):
            answer=fixture.d.dispatch(self.c.controller,self.c.writer,body)
        self.assertEqual(answer['outcome'],'queued-review')
        return dict(body,action='archive-repair-adoption-status')

    def test_native_passive_status_consumes_actual_fresh_terminal_only(self):
        import workflow_store
        body=self.queued();cap=self.cap();history.prepared(cap.preparation)
        cap.install();cap.complete();history.executed(cap);self.observed(cap)
        with patch.object(fixture.d,'_store',side_effect=lambda c:workflow_store.Store(c.root,existing_only=True)):
            answer=fixture.d.dispatch(self.c.controller,self.c.writer,body)
        self.assertEqual(answer['outcome'],'terminal-observed')
        self.assertIs(answer['reader_preservation_verified'],False)
        self.assertIs(answer['publication_acceptance'],False)

    def test_native_final_reader_callback_cannot_mutate_history(self):
        import workflow_store
        body=self.queued();cap=self.cap();history.prepared(cap.preparation)
        cap.install();cap.complete();history.executed(cap);ref=self.observed(cap)
        real=fixture.d.reader.direct;fired=[]
        def late(*args):
            real(*args);os.chmod(ref['path'],0o640);fired.append(True)
        with patch.object(fixture.d,'_store',side_effect=lambda c:workflow_store.Store(c.root,existing_only=True)), patch.object(fixture.d.reader,'direct',late):
            with self.assertRaises(o.Held):fixture.d.dispatch(self.c.controller,self.c.writer,body)
        self.assertTrue(fired)

    def test_native_prepare_emits_only_into_preinitialized_history(self):
        import json
        api=self.c.modules[0]
        request=api.request(json.dumps({'version':1,'action':'prepare-archive-repair',
                                       'owner':self.c.owner,'operation_id':self.c.operation_id}))
        answer=self.c.controller.dispatch(request)
        self.assertEqual(answer['outcome'],'prepared')
        factual=history.status(self.c.controller,self.c.writer,self.c.owner,self.c.operation_id)
        self.assertEqual(factual['outcome'],'prepared');self.assertIs(factual['ordinary_import_grant'],False)

    def test_foreign_namespace_catalog_cannot_rebase_original_child_vectors(self):
        cap=self.cap();history.prepared(cap.preparation)
        cap.install();cap.complete();history.executed(cap);self.observed(cap)
        other=History('runTest');other.setUp();self.addCleanup(other.doCleanups)
        for record in self.path.iterdir():
            target=other.path/record.name;target.write_bytes(record.read_bytes());target.chmod(0o600)
        # Explicit disposable namespace mismatch: the second genuine Controller
        # has its own DB/catalog/stage. Saved bytes retain FIRST namespace facts.
        with self.assertRaises(o.Held):history.status(other.c.controller,other.c.writer,self.c.owner,self.c.operation_id)

    def test_native_passive_same_instance_rollback_keeps_false_rights(self):
        import workflow_store
        body=self.queued();cap=self.cap();history.prepared(cap.preparation)
        cap.install();cap.reverse()
        with patch.object(rollback,'installed'):rollback.from_reversed(cap).clear()
        history.executed(cap);self.observed(cap,reverse=True)
        with patch.object(fixture.d,'_store',side_effect=lambda c:workflow_store.Store(c.root,existing_only=True)):
            answer=fixture.d.dispatch(self.c.controller,self.c.writer,body)
        self.assertEqual(answer['outcome'],'rollback-observed')
        self.assertIs(answer['reader_preservation_verified'],False);self.assertIs(answer['publication_acceptance'],False)

    def test_actual_queue_admission_initializes_before_owning_execute_and_fresh_verifier(self):
        import workflow_store
        self.path.rmdir();body=self.queued()
        self.assertEqual(self.path.stat().st_mode & 0o7777,0o700)
        self.assertFalse((self.c.controller.root/('archive-repair-'+self.c.operation_id)).exists())
        cap=self.cap();history.prepared(cap.preparation)
        cap.install();cap.complete();history.executed(cap);self.observed(cap)
        with patch.object(fixture.d,'_store',side_effect=lambda c:workflow_store.Store(c.root,existing_only=True)):
            answer=fixture.d.dispatch(self.c.controller,self.c.writer,body)
        self.assertEqual(answer['outcome'],'terminal-observed')
        self.assertIs(answer['mutation_authority'],False);self.assertIs(answer['publication_acceptance'],False)

    def test_first_sdk_callback_cannot_rebaseline_prepared_history(self):
        cap=self.cap();ref=history.prepared(cap.preparation);cap.install();cap.complete()
        target=Path(ref['path']);original=target.read_bytes();real=o.sdk;fired=[]
        def late():
            result=real()
            if not fired:
                value=history.decode(original);value['evidence']['preparation_token']='0'*64
                changed=history.encoded(value);self.assertEqual(len(changed),len(original))
                target.write_bytes(changed);fired.append(True)
            return result
        with patch.object(o,'sdk',late):
            with self.assertRaises(o.Held):history.executed(cap)
        self.assertTrue(fired)
        self.assertFalse((self.path/(self.c.operation_id+'.execute-observed.json')).exists())

    def test_status_first_sdk_callback_preserves_original_history_identity(self):
        cap=self.cap();ref=history.prepared(cap.preparation);real=o.sdk;fired=[]
        def late():
            result=real()
            if not fired:os.chmod(ref['path'],0o640);fired.append(True)
            return result
        with patch.object(o,'sdk',late):
            with self.assertRaises(o.Held):history.status(self.c.controller,self.c.writer,self.c.owner,self.c.operation_id)
        self.assertTrue(fired)

    def test_terminal_first_sdk_callback_preserves_prior_record(self):
        cap=self.cap();history.prepared(cap.preparation);cap.install();cap.complete()
        ref=history.executed(cap);real=o.sdk;fired=[]
        def late():
            result=real()
            if not fired:os.chmod(ref['path'],0o640);fired.append(True)
            return result
        with patch.object(o,'sdk',late):
            with self.assertRaises(o.Held):self.observed(cap)
        self.assertTrue(fired)
        self.assertFalse((self.path/(self.c.operation_id+'.terminal-observed.json')).exists())

    def test_initialize_cannot_refresh_existing_private_history(self):
        cap=self.cap();ref=history.prepared(cap.preparation);real=o.sdk;fired=[]
        def late():
            result=real()
            if not fired:os.chmod(ref['path'],0o640);fired.append(True)
            return result
        with patch.object(o,'sdk',late):
            with self.assertRaises(o.Held):history.initialize(self.c.controller,self.c.writer)
        self.assertTrue(fired)

    def test_queued_final_reader_callback_cannot_create_catalog_wal(self):
        target=Path(str(self.c.controller.native_database)+'-wal');real=fixture.d.reader.direct;fired=[]
        def late(*args):
            real(*args);target.write_bytes(b'foreign');fired.append(True)
        with patch.object(fixture.d.reader,'direct',late):
            with self.assertRaises(o.Held):self.queued()
        self.assertTrue(fired);self.assertTrue(target.exists())

    def test_no_history_status_final_reader_callback_cannot_create_catalog_wal(self):
        import workflow_store
        body=self.queued();target=Path(str(self.c.controller.native_database)+'-wal')
        real=fixture.d.reader.direct;fired=[]
        def late(*args):
            real(*args);target.write_bytes(b'foreign');fired.append(True)
        with patch.object(fixture.d,'_store',side_effect=lambda c:workflow_store.Store(c.root,existing_only=True)), patch.object(fixture.d.reader,'direct',late):
            with self.assertRaises(o.Held):fixture.d.dispatch(self.c.controller,self.c.writer,body)
        self.assertTrue(fired)

    def test_queued_final_reader_callback_cannot_change_database_mode(self):
        target=self.c.controller.native_database;real=fixture.d.reader.direct;fired=[]
        def late(*args):
            real(*args);os.chmod(target,0o640);fired.append(True)
        with patch.object(fixture.d.reader,'direct',late):
            with self.assertRaises(o.Held):self.queued()
        self.assertTrue(fired)

    def test_queued_final_reader_callback_cannot_add_terminal_marker(self):
        target=self.c.writer.root/fixture.d.adoption.TERMINAL;real=fixture.d.reader.direct;fired=[]
        def late(*args):
            real(*args);target.write_bytes(b'foreign');fired.append(True)
        with patch.object(fixture.d.reader,'direct',late):
            with self.assertRaises(o.Held):self.queued()
        self.assertTrue(fired)


if __name__ == '__main__': unittest.main()
