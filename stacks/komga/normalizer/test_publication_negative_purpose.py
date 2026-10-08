"""Worker ordinary evidence cannot enter a native negative retirement phase."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import publication_evidence as evidence
from publication_guard import Unavailable
from media_writer import Busy
from test_publication_guard import AuthorityFixture

NAME='negative-retirement-v1.pending'
class Controls(AuthorityFixture,unittest.TestCase):
 def test_present_marker_writer_never_yields(self):
  (self.writer.root/NAME).write_bytes(b'{')
  with self.assertRaises(Busy):
   with self.writer.hold(timeout=0):self.fail('ordinary marker admission')
 def test_marker_after_outer_hold_prevents_inventory(self):
  with self.writer.hold():
   (self.writer.root/NAME).write_bytes(b'{}')
   with patch.object(evidence,'inventory',side_effect=AssertionError('inventory prohibited')),self.assertRaises(Unavailable):self.authority.check(self.candidate,self.owner)
 def test_inaccessible_marker_after_hold_denies(self):
  real=os.lstat;target=self.writer.root/NAME
  def denied(p,*args,**kw):
   if Path(p)==target:raise PermissionError('fixture')
   return real(p,*args,**kw)
  with self.writer.hold(),patch.object(os,'lstat',side_effect=denied),self.assertRaises(Unavailable):self.authority.admission()
 def test_late_inventory_marker_cannot_admit(self):
  real=evidence.inventory;fired=[]
  def late(*args,**kw):
   result=real(*args,**kw);(self.writer.root/NAME).write_bytes(b'{}');fired.append(True);return result
  with self.writer.hold(),patch.object(evidence,'inventory',side_effect=late),self.assertRaises(Unavailable):self.authority.check(self.candidate,self.owner)
  self.assertTrue(fired)
if __name__=='__main__':unittest.main()
