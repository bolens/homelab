"""Actual native typed finalizer exports; host API method adapter explicit."""
import hashlib
import json
import unittest
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import test_retained_delivery_api as fixture

@unittest.skipUnless((Path(fixture.fixture.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'public archive backend required for retained pack controls')
class Export(unittest.TestCase):
 def setUp(self):
  self.base=fixture.Endpoint('runTest');self.base.setUp();self.addCleanup(self.base.doCleanups)
  self.f=fixture.fixture.f;self.c=self.base.c.c
 def test_original_full_two_row_transition_export(self):
  before=self.c.database.read_bytes()
  with self.base.c.writer.hold():original=self.f.r._sql(self.c.database,tuple(self.f.o.signature(self.c.database)))
  answer=self.base.call()['data'];t=answer['transition']
  self.assertEqual(json.dumps(t['workflow_before'],sort_keys=True),json.dumps(original,sort_keys=True))
  self.assertNotEqual(before,self.c.database.read_bytes())
  self.assertEqual(t['pack_before_row'][:2],['pack',t['request']['pack_id']])
  self.assertEqual(t['pack_before_row'][3],t['pack_after_row'][3])
  self.assertEqual(hashlib.sha256(t['record_bytes'].encode()).hexdigest(),answer['record_sha256'])
  self.assertFalse(answer['cleanup_grant']);self.assertFalse(answer['ordinary_import_grant'])
  self.assertEqual({x['path'].split('/')[-1] for x in t['native_sources']},
    {'api.py','native_writers.py','publication_retained_api.py','publication_retained_delivery.py','publication_retained_finalize.py'})
 def test_actual_export_worker_independent_two_row_checker(self):
  with self.base.c.writer.hold():before=self.f.r._sql(self.c.database,tuple(self.f.o.signature(self.c.database)))
  answer=self.base.call()['data']
  with tempfile.TemporaryDirectory() as tmp:
   inp=Path(tmp)/'observed.json';inp.write_text(json.dumps(dict(answer=answer,before=before,
      target=json.loads(answer['transition']['record_bytes'])['target'],source=json.loads(answer['transition']['record_bytes'])['source'],database=str(self.c.database))))
   normalizer=Path(__file__).parent/'test_fixtures'/'retained_pack_worker'
   pins=json.loads((normalizer/'source-pins.json').read_bytes())
   self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in normalizer.glob('*.py')},pins)
   result=subprocess.run([sys.executable,'-I','-B',str(normalizer/'check_retained_pack_export.py'),str(inp)],
       cwd=normalizer,capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertEqual(json.loads(result.stdout),dict(actual_SQL_verified=True,negative_controls=6,mutation_authority=False))
 def test_same_daemon_status_export_is_identical(self):
  answer=self.base.call();self.assertEqual(self.base.call('retainedDeliveryStatus'),answer)
 def test_saved_export_cannot_mint_typed_receipt(self):
  answer=self.base.call()['data'];saved=json.loads(json.dumps(answer['transition']))
  self.assertEqual(saved,answer['transition'])
  with self.assertRaises(self.f.o.Held):self.f.RetainedFinalization(saved)
 def test_replaced_serializer_has_no_reply(self):
  original=self.base.handler._successResponse.__func__
  def late(handler,answer):
   raw=original(handler,answer);self.c.native_database.with_name(self.c.native_database.name+'-wal').write_bytes(b'foreign');return raw
  with patch.object(self.base.api.Api,'_successResponse',late):
   # Exact serializer ownership rejects the replaced method before encoding.
   self.assertFalse(self.base.call()['success'])
 def test_foreign_original_event_cannot_status_export(self):
  answer=self.base.call()['data'];key=(str(self.c.root),answer['token']);old=self.f._FINALS.pop(key)
  try:self.assertFalse(self.base.call('retainedDeliveryStatus')['success'])
  finally:self.f._FINALS[key]=old

if __name__=='__main__':unittest.main()
