"""Real disposable observation custody; no installed factory positive is claimed."""
import hashlib
import importlib.util
from pathlib import Path
import unittest
import tempfile
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

fixture=load('observation_controls',ROOT/'test_negative_terminal_observer.py')
provider=load('terminal_provider',ROOT/'comic_negative_reader_action.py')

class Controls(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.Controls('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def observe(self):
        return fixture.m.observe_with_originals(self.fixture.manifest_ref,
            source_sha256=hashlib.sha256(Path(fixture.m.__file__).read_bytes()).hexdigest())

    def test_originals_cover_real_sqlite_and_restore_and_false_rights(self):
        result,originals=self.observe()
        for path in (self.fixture.current/'database.sqlite',self.fixture.current/'tasks.sqlite',self.fixture.restore/'database.sqlite',self.fixture.restore/'tasks.sqlite'):
            self.assertEqual(originals['files'][str(path)],tuple(fixture.m.nine(path.lstat())))
        self.assertEqual(result,self.fixture.go())
        self.assertTrue(all(result[key] is False for key in ('publication_acceptance','mutation_authority','reader_resume_authority','recovery_capability','application_quiescence_verified')))
        provider.raw_terminal_originals(originals)

    def test_late_current_database_metadata_change_refuses(self):
        _result,originals=self.observe()
        (self.fixture.current/'database.sqlite').chmod(0o640)
        with self.assertRaisesRegex(provider.Held,'original-file-final'):
            provider.raw_terminal_originals(originals)

    def test_late_actual_ancestor_change_refuses(self):
        _result,originals=self.observe()
        self.fixture.current.chmod(0o750)
        with self.assertRaisesRegex(provider.Held,'original-node-final'):
            provider.raw_terminal_originals(originals)

    def test_late_absent_source_reappearance_refuses(self):
        _result,originals=self.observe()
        Path(self.fixture.members[0]['source']).write_bytes(self.fixture.original_bytes(0))
        with self.assertRaisesRegex(provider.Held,'original-absence-final'):
            provider.raw_terminal_originals(originals)

    def test_late_phase_namespace_extra_refuses(self):
        _result,originals=self.observe()
        (self.fixture.journal/'foreign.json').write_text('{}')
        with self.assertRaisesRegex(provider.Held,'original-census-final'):
            provider.raw_terminal_originals(originals)

    def test_main_last_terminal_helper_drift_cannot_emit_ack(self):
        # Setup factories are explicit doubles; this proves real main's terminal
        # closure over actual observer SQLite, not a canonical factory positive.
        result,originals=self.observe()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);root.chmod(0o700);op=root/'verify-terminal';op.mkdir(mode=0o700)
            digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            mapping=root/'map.json';mapping.write_bytes(provider.encoded({'publication_reader_admission.py':'a'*64}));mapping.chmod(0o600)
            plan=dict(action='negative-five',operation=str(op),nonce='b'*64,sdk_map=dict(path=str(mapping),sha256=digest(mapping)),admission_source_sha256='a'*64)
            inp=root/'input.json';inp.write_bytes(provider.encoded(plan));inp.chmod(0o600)
            source=Path(provider.__file__);source_hash=digest(source)
            life=SimpleNamespace(invocation_binding=lambda:dict(provider_sha256=source_hash),revalidate_stopped=lambda:None)
            real=provider.raw_terminal_originals;fired=[];frames=[];realwrite=os.write
            def late(value):
                real(value);(self.fixture.current/'database.sqlite').chmod(0o640);fired.append(True)
            args=[str(source),'--phase','verify-terminal','--input',str(inp),'--input-sha256',digest(inp),'--source-sha256',source_hash]
            with patch.object(sys,'argv',args),patch.object(provider,'actual_command'),patch.object(provider,'sdk',return_value=({}, {}, {})),patch.object(provider,'born_lifecycle',return_value=life),patch.object(provider,'verify_terminal_existing',return_value=(result,originals)),patch.object(provider,'raw_terminal_originals',late),patch.object(provider.os,'write',side_effect=lambda fd,data:(frames.append(data) or len(data)) if fd==1 else realwrite(fd,data)):
                with self.assertRaisesRegex(provider.Held,'terminal-ACK-file-final'):provider.main()
            self.assertTrue(fired);self.assertFalse(frames)

    def test_boolean_or_receipt_is_not_lifecycle(self):
        # Actual owning class definition, uninstantiated: no class/type rewrite.
        life=load('actual_lifecycle_source',ROOT/'_terminal_reconstruction_fixtures/publication_reader_lifecycle.py')
        for receipt in (True,{},object()):
            with self.assertRaisesRegex(provider.Held,'terminal-exact-lifecycle'):
                provider.verify_terminal_existing({},receipt,{'publication_reader_lifecycle':life})

if __name__=='__main__':unittest.main()
