"""Synthetic detached summaries only; no actual reader records or database access."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
P=Path(str(Path(__file__).with_name('comic_reader_timestamp_summary.py')))
spec=importlib.util.spec_from_file_location('summary',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):
  self.ids=['synthetic-'+str(i) for i in range(11)]
  rows={x:[['text',x],['null'],['text','2020-01-01 12:00:00.123456'],['null'],['text','opaque-name'],['text','opaque-url'],['null'],['null'],['null'],['null'],['null'],['null'],['null'],['null']] for x in self.ids}
  observations={x:{'LAST_MODIFIED_DATE':'text','DELETED_DATE':'null'} for x in self.ids}
  self.report={'version':1,'kind':'reader-restored-eleven-row-observation','source_sha256':m.SOURCE,'observation_verified':False,'final_ack_required':True,'timestamp_encoding_approved':False,'mutation_authority':False,'publication_acceptance':False,'selected_ids':self.ids,'databases':{k:{'schema_sha256':v,'selected_rows':rows if k=='database.sqlite' else {},'timestamp_observations':observations if k=='database.sqlite' else {}} for k,v in m.SCHEMAS.items()}}
 def args(self):
  raw=json.dumps(self.report).encode();ack=json.dumps({'backup_verified':True,'targeted_eleven_row_observation_verified':True,'rows_report_sha256':m.digest(raw),'mutation_authority':False,'publication_acceptance':False}).encode();return raw,m.digest(raw),ack,m.digest(ack)
 def go(self):return m.project(*self.args())
 def test_exact_selected_values_only_and_no_approval(self):
  value=self.go();self.assertEqual(value['selected_count'],11);self.assertEqual(value['storage_counts']['DELETED_DATE'],{'null':11});self.assertFalse(value['timestamp_encoding_approved']);self.assertIsNone(value['chosen_mutation_timestamp']);self.assertNotIn('opaque-url',json.dumps(value));self.assertNotIn('opaque-name',json.dumps(value))
 def test_input_immutable(self):
  old=copy.deepcopy(self.report);self.go();self.assertEqual(old,self.report)
 def test_changed_report_digest_holds(self):
  a=list(self.args());a[0]+=b' ';self.assertRaisesRegex(m.Held,'accepted-digests',m.project,*a)
 def test_pending_ack_holds(self):
  a=list(self.args());v=json.loads(a[2]);v['backup_verified']=False;a[2]=json.dumps(v).encode();a[3]=m.digest(a[2]);self.assertRaisesRegex(m.Held,'root-terminal-ack',m.project,*a)
 def test_wrong_source_holds(self):
  self.report['source_sha256']='a'*64;self.assertRaisesRegex(m.Held,'rows-envelope',self.go)
 def test_historical_rows_label_with_valid_joined_hashes_holds(self):
  self.report['source_sha256']='f6b03a162bc4f34dfa1e8f754491d658557fb264bcc7e4ec01247c504155822d'
  self.assertRaisesRegex(m.Held,'rows-envelope',self.go)
 def test_schema_drift_holds(self):
  self.report['databases']['database.sqlite']['schema_sha256']='a'*64;self.assertRaisesRegex(m.Held,'actual-schemas',self.go)
 def test_selected_missing_holds(self):
  del self.report['databases']['database.sqlite']['selected_rows'][self.ids[0]];self.assertRaisesRegex(m.Held,'selected-census',self.go)
 def test_foreign_row_holds(self):
  self.report['databases']['database.sqlite']['selected_rows'][self.ids[0]][0]=['text','foreign'];self.assertRaisesRegex(m.Held,'row-owner',self.go)
 def test_typeof_mismatch_holds(self):
  self.report['databases']['database.sqlite']['timestamp_observations'][self.ids[0]]['DELETED_DATE']='text';self.assertRaisesRegex(m.Held,'storage-cross-binding',self.go)
 def test_blob_and_integer_preserved_not_text_approved(self):
  main=self.report['databases']['database.sqlite'];main['selected_rows'][self.ids[0]][11]=['blob','YWJj'];main['timestamp_observations'][self.ids[0]]['DELETED_DATE']='blob';main['selected_rows'][self.ids[1]][2]=['integer','42'];main['timestamp_observations'][self.ids[1]]['LAST_MODIFIED_DATE']='integer';v=self.go();self.assertFalse(v['timestamps'][0]['DELETED_DATE']['utc_text_syntax']);self.assertEqual(v['timestamps'][1]['LAST_MODIFIED_DATE']['typed_value'],['integer','42']);self.assertFalse(v['timestamp_encoding_approved'])
 def test_duplicate_keys_held(self):
  self.assertRaisesRegex(m.Held,'duplicate',m.decode,b'{"a":1,"a":2}')
 def test_default_off(self):
  r=subprocess.run([sys.executable,str(P)],capture_output=True,check=True);self.assertFalse(json.loads(r.stdout)['execute'])
if __name__=='__main__':unittest.main()
