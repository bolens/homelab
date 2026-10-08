"""Actual existing Writer fences ordinary purposes before yielding or inventory."""
import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import media_writer as writers
import publication_guard as guard
import test_publication_archive_owned_api as routes
import test_publication_archive_admission as native

NAME='negative-retirement-v1.pending'
class WriterControls(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  self.writer=writers.Writer(Path(tmp.name)/'writer',create=True);self.marker=self.writer.root/NAME
  self.journal=Path(tmp.name)/'journal';self.journal.mkdir(mode=0o700)
 def test_absent_ordinary_writer_admits(self):
  with self.writer.hold(timeout=0):guard.ordinary_purpose(self.writer)
 def test_valid_or_malformed_marker_never_yields(self):
  for raw in (b'{}',b'{',json.dumps(dict(version=1,protocol='native-negative-retirement-phase-v1',nonce='a'*64,binding_sha256='b'*64,journal=str(self.journal))).encode()):
   self.marker.write_bytes(raw);yielded=[]
   with self.assertRaises(writers.Busy):
    with self.writer.hold(timeout=0):yielded.append(True)
   self.assertEqual(yielded,[]);self.assertEqual(self.marker.read_bytes(),raw)
 def test_all_existing_recovery_flags_cannot_bypass(self):
  self.marker.write_bytes(b'{}')
  with self.assertRaises(writers.Busy):
   with self.writer.hold(allow_pending=True,allow_tagger_pending=True,allow_release_pending=True,timeout=0):pass
 def test_dangling_symlink_marker_denies(self):
  self.marker.symlink_to(self.writer.root/'missing')
  with self.assertRaises(writers.Busy):
   with self.writer.hold(timeout=0):pass
 def test_directory_marker_denies(self):
  self.marker.mkdir()
  with self.assertRaises(writers.Busy):
   with self.writer.hold(timeout=0):pass
 def test_inaccessible_marker_lookup_denies(self):
  real=os.lstat
  def denied(p,*a,**kw):
   if Path(p)==self.marker:raise PermissionError('fixture')
   return real(p,*a,**kw)
  with patch.object(writers.os,'lstat',side_effect=denied),self.assertRaises(writers.Busy):
   with self.writer.hold(timeout=0):pass
 def test_after_flock_marker_creation_denies_before_yield(self):
  real=writers.fcntl.flock;fired=[]
  def late(fd,policy):
   result=real(fd,policy)
   if policy&writers.fcntl.LOCK_EX:self.marker.write_bytes(b'{}');fired.append(True)
   return result
  with patch.object(writers.fcntl,'flock',side_effect=late),self.assertRaises(writers.Busy):
   with self.writer.hold(timeout=0):pass
  self.assertTrue(fired)
 def test_nested_ordinary_hold_denies_new_marker(self):
  with self.writer.hold(timeout=0):
   self.marker.write_bytes(b'{}')
   with self.assertRaises(writers.Busy):
    with self.writer.hold(timeout=0):pass
 def test_guard_does_not_read_marker_payload(self):
  self.marker.write_bytes(b'secret payload')
  with patch.object(Path,'read_bytes',side_effect=AssertionError('unexpected marker read')):
   with self.assertRaisesRegex(guard.Unavailable,'^Negative retirement phase requires review$'):guard.ordinary_purpose(self.writer)

class OwningControls(unittest.TestCase):
 def setUp(self):
  self.case=routes.Controls();self.case.setUp();self.addCleanup(self.case.doCleanups)
 def test_prepare_and_missing_status_deny_present_marker(self):
  c=self.case;marker=c.case.writer.root/NAME;marker.write_bytes(b'{')
  for action in ('prepare-archive-repair','archive-repair-status'):
   with self.assertRaises((ValueError,RuntimeError)):c.call(action)
  self.assertFalse((c.case.root/('archive-repair-'+c.operation_id)).exists())
 def test_passive_authority_status_never_ready(self):
  c=self.case;(c.case.writer.root/NAME).write_bytes(b'{}')
  self.assertEqual(guard.authority_status(c.case.controller.database,c.case.writer.root)['state'],'held')
 def test_media_snapshot_denies_marker_before_catalog_read(self):
  c=self.case
  with c.case.writer.hold():
   (c.case.writer.root/NAME).write_bytes(b'{}')
   with patch.object(guard,'registry_snapshot',side_effect=AssertionError('catalog read forbidden')),self.assertRaises(guard.Unavailable):guard.media_snapshot(c.case.controller.database,c.case.writer.root/'publication-v1.json')
 def test_media_snapshot_late_cleanup_marker_denies(self):
  c=self.case;real=guard.cleanup_admission;fired=[]
  def late(*args,**kw):
   result=real(*args,**kw);(c.case.writer.root/NAME).write_bytes(b'{}');fired.append(True);return result
  with c.case.writer.hold(),patch.object(guard,'cleanup_admission',side_effect=late),self.assertRaises(guard.Unavailable):guard.media_snapshot(c.case.controller.database,c.case.writer.root/'publication-v1.json')
  self.assertTrue(fired)
 def test_full_status_denies_marker_without_changing_custody(self):
  c=self.case;c.call();op=c.case.root/('archive-repair-'+c.operation_id)
  before={p:p.read_bytes() for p in op.iterdir()};(c.case.writer.root/NAME).write_bytes(b'{}')
  with self.assertRaises((ValueError,RuntimeError)):c.call('archive-repair-status')
  self.assertEqual(before,{p:p.read_bytes() for p in op.iterdir()})
 def test_late_summary_marker_holds_before_return(self):
  c=self.case;real=routes.route.summary;fired=[]
  def late(*a,**kw):
   result=real(*a,**kw);(c.case.writer.root/NAME).write_bytes(b'{}');fired.append(True);return result
  with patch.object(routes.route,'summary',side_effect=late),self.assertRaises((ValueError,RuntimeError)):c.call()
  self.assertTrue(fired)

class NativeControls(unittest.TestCase):
 def test_inventory_never_runs_after_late_native_marker(self):
  c=native.Controls();c.setUp();self.addCleanup(c.doCleanups)
  with c.writer.hold():
   (c.writer.root/NAME).write_bytes(b'{}')
   with patch.object(native.guard,'inventory',side_effect=AssertionError('must not inventory')),self.assertRaises(native.native.Review) as held:native.native.require(c.incoming,issueid='123',comicid='456')
  self.assertIsNone(held.exception.archive_diagnostic)

if __name__=='__main__':unittest.main()
