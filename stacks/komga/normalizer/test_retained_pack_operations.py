"""Exact typed/default-off session negatives; no synthetic action positives."""
import unittest
import retained_pack_operations as ops

class Boundaries(unittest.TestCase):
 def test_default_disabled_initializer(self):
  with self.assertRaises(ValueError):ops.initialize(object())
 def test_no_constructor_grant(self):
  with self.assertRaises(ValueError):ops.RetainedPackSession()
 def test_saved_JSON_cannot_status_or_select(self):
  for value in ({'phase':'uncertain-review'},object()):
   with self.assertRaises(ValueError):ops.reconcile(value)
   with self.assertRaises(ValueError):ops.select(value,'a'*64,'b'*64)
   with self.assertRaises(ValueError):ops.execute(value)
 def test_saved_UI_view_cannot_rehydrate(self):
  with self.assertRaises(ValueError):ops.view({'retained_observed_members':1})

if __name__=='__main__':unittest.main()
