"""Complete owning prepare/NativeBatch/Writer; API replies are fixture inputs."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from maintenance import Maintenance
from publication_guard import NativeBatch,Unavailable
from media_writer import Writer
class SelectedPrepare(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.writer=Writer(self.root/'media-writer',create=True)
  self.worker=SimpleNamespace(config={'writer_state':str(self.writer.root)},reader=SimpleNamespace(books=Mock(return_value={'book':{'id':'book','seriesId':'series','media':{},'readProgress':{}}})))
  self.m=object.__new__(Maintenance);self.m.worker=self.worker;self.m.last_run=0;self.m.settings={'pack_import':True};self.calls=[]
  def api(command,**kw):
   self.calls.append((command,kw));return {'command':command}
  self.m.mylar=api
 def test_selected_exact_calls_omit_unrelated_cursor_and_keep_reader_batch(self):
  batch=self.m.prepare('a'*64,'274610');self.assertIs(type(batch),NativeBatch);self.assertEqual(self.calls,[('getHealth',{}),('packWork',{'pack_id':'a'*64,'ddl_id':'274610'})]);self.worker.reader.books.assert_called_once_with();self.assertEqual(json.loads(self.m.reader_snapshot[2]),{'book':{'id':'book','seriesId':'series','media':{},'readProgress':{}}});self.assertEqual(batch.read(self.worker,'packWork'),{'command':'packWork'})
  with self.assertRaises(Unavailable):batch.read(self.worker,'workflowCommands')
  with self.assertRaises(Unavailable):batch.read(SimpleNamespace(),'packWork')
 def test_normal_cycle_preserves_original_commands_and_arguments(self):
  batch=self.m.prepare();self.assertEqual(self.calls,[('getHealth',{}),('workflowCommands',{}),('packWork',{})]);self.assertEqual(batch.read(self.worker,'workflowCommands'),{'command':'workflowCommands'})
 def test_selected_failure_never_falls_back_to_commands(self):
  def api(command,**kw):
   self.calls.append((command,kw))
   if command=='packWork':raise RuntimeError('fixture API unavailable')
   return {'command':command}
  self.m.mylar=api;batch=self.m.prepare('a'*64,'274610');self.assertEqual([v[0] for v in self.calls],['getHealth','packWork']);self.worker.reader.books.assert_called_once_with()
  with self.assertRaises(Unavailable):batch.read(self.worker,'packWork')
  with self.assertRaises(Unavailable):batch.read(self.worker,'workflowCommands')
 def test_partial_or_invalid_selection_refuses_before_any_api(self):
  for p,d in [('a'*64,None),(None,'274610'),('foreign','274610'),('a'*64,True)]:
   with self.assertRaises(ValueError):self.m.prepare(p,d)
  self.assertEqual(self.calls,[]);self.worker.reader.books.assert_not_called()
 def test_real_held_writer_reader_collection_still_refuses(self):
  with self.writer.hold(),self.assertRaises(Unavailable):self.m.prepare('a'*64,'274610')
  self.worker.reader.books.assert_not_called()
if __name__=='__main__':unittest.main()

class SelectedContention(unittest.TestCase):
 setUp=SelectedPrepare.setUp
 def test_selected_remote_contention_propagates_at_each_readonly_api(self):
  from publication_guard import RemoteWriterBusy
  for failed in ('getHealth','packWork'):
   self.calls.clear();self.worker.reader.books.reset_mock()
   def api(command,**kw):
    self.calls.append((command,kw))
    if command==failed:raise RemoteWriterBusy('remote admission')
    return {'command':command}
   self.m.mylar=api
   with self.subTest(command=failed),self.assertRaises(RemoteWriterBusy):self.m.prepare('a'*64,'274610')
   self.worker.reader.books.assert_not_called()
   self.assertEqual(self.calls,[('getHealth',{})]if failed=='getHealth'else[('getHealth',{}),('packWork',{'pack_id':'a'*64,'ddl_id':'274610'})])
 def test_unfiltered_and_recurring_prepare_do_not_gain_retry_authority(self):
  from publication_guard import RemoteWriterBusy
  for kwargs in ({},{'packs_only':True}):
   self.calls.clear()
   def api(command,**kw):
    self.calls.append((command,kw));raise RemoteWriterBusy('remote admission')
   self.m.mylar=api;batch=self.m.prepare(**kwargs)
   self.assertTrue(self.calls)
   with self.assertRaises(Unavailable):batch.read(self.worker,'packWork')
 def test_real_remote_probe_in_selected_api_is_not_swallowed(self):
  import fcntl,os
  from publication_guard import remote_unlocked,RemoteWriterBusy
  fd=os.open(self.writer.lock,os.O_RDWR);self.addCleanup(os.close,fd)
  for failed in ('getHealth','packWork'):
   self.calls.clear();self.worker.reader.books.reset_mock()
   def api(command,**kw):
    if command==failed:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:remote_unlocked(self.worker)
    finally:fcntl.flock(fd,fcntl.LOCK_UN)
    self.calls.append((command,kw));return {'command':command}
   self.m.mylar=api
   with self.subTest(command=failed),self.assertRaises(RemoteWriterBusy):self.m.prepare('a'*64,'274610')
   self.assertEqual(self.calls,[]if failed=='getHealth'else[('getHealth',{})]);self.worker.reader.books.assert_not_called()
