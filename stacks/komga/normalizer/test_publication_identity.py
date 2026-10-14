"""Real SQLite historical fixture, no actual remount/bind-mount/backup grant."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from ordinary_observation_fixtures.identity_native.tests_tagger_identity import HistoricalFixture

PROGRAM='''import json,os,sqlite3,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import publication_evidence as guard
import publication_identity_readers as readers
import publication_filesystem_binding as filesystem
from media_writer import Writer
p=json.loads(sys.argv[2]); dbpath=Path(p['database']); writer=Writer(Path(p['writer']),create=False)
assert 'publication_guard' not in sys.modules and 'workflow_store' not in sys.modules
assert not hasattr(guard,'RegistryState') and not hasattr(filesystem,'identity_transaction_owned')
assert not hasattr(__import__('publication_identity_adoption'),'record_bytes')
identity=list(guard.database_stamp(dbpath)[:2]); pair=guard.writer_identity(writer)
with sqlite3.connect(dbpath.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
 db.execute('BEGIN')
 census,_=guard.complete_census(db)
 guard.initialization_witness(db,p['token'],census,identity,pair,ledger_dir=writer.root/'identity-adoptions-v1')
assert 'publication_guard' not in sys.modules and 'workflow_store' not in sys.modules
print('passive-committed-history')
'''

class WorkerAdoptionTests(HistoricalFixture):
    def run_worker(self):
        packet=dict(database=str(self.store.path),writer=str(self.writer.root),token=self.initialization)
        return subprocess.run([sys.executable,'-I','-B','-c',PROGRAM,str(HERE),json.dumps(packet)],capture_output=True,text=True,timeout=15)
    def test_generated_worker_reads_real_committed_adoption_without_native_import(self):
        result=self.run_worker()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'passive-committed-history')
        self.assertEqual(self.rows(),self.rows_original)
        self.assertEqual(self.marker.read_bytes(),self.marker_original)
    def test_generated_worker_accepts_genuine_future_registration_and_restart(self):
        self.register(2)
        first=self.run_worker(); second=self.run_worker()
        self.assertEqual(first.returncode,0,first.stderr)
        self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(self.binding.read_bytes(),self.binding_original)
    def test_full_registry_snapshot_matches_current_marker_and_preserves_history(self):
        packet=dict(database=str(self.store.path),writer=str(self.writer.root),token=self.initialization,
                    marker=str(self.marker))
        program=PROGRAM+"\ncensus,records=guard.registry_snapshot(dbpath,Path(p['marker']))\nassert census['revision']==2 and len(records)==2\nassert 'publication_guard' not in sys.modules and 'workflow_store' not in sys.modules\nprint('passive-current-marker')\n"
        result=subprocess.run([sys.executable,'-I','-B','-c',program,str(HERE),json.dumps(packet)],
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.splitlines(),['passive-committed-history','passive-current-marker'])
        self.assertEqual(self.rows(),self.rows_original)
        self.assertEqual(self.marker.read_bytes(),self.marker_original)
        self.assertEqual(self.binding.read_bytes(),self.binding_original)
    def test_uncommitted_envelope_refused(self):
        envelope=dict(self.envelope,accepted=False,kind='prepared-device-identity-edge')
        self.ledger_file.write_text(json.dumps(envelope))
        self.assertNotEqual(self.run_worker().returncode,0)
    def test_sidecar_refused_by_passive_reader(self):
        sidecar=Path(str(self.store.path)+'-journal')
        sidecar.write_bytes(b'public unresolved journal')
        try:self.assertNotEqual(self.run_worker().returncode,0)
        finally:sidecar.unlink()
    def test_generic_old_mismatch_without_adoption_refused(self):
        self.ledger_file.unlink(); self.ledger.rmdir()
        self.assertNotEqual(self.run_worker().returncode,0)

if __name__=='__main__':unittest.main()
