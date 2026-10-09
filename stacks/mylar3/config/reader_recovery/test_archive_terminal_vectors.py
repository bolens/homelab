"""Finite namespace tests; declarations are fixtures, never typed SDK proof."""
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).parent))
import comic_archive_terminal_vectors as v

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.sdk={'publication_api.py':'a'*64};self.mounts=[dict(host=str(self.root),child='/proofs',write=False)]
  self.sources={p:dict(path=p,sha256='b'*64,signature9=[1,2,3,4,5,0o100644,1000,1000,1]) for p in ('/app/mylar3/Mylar.py','/app/mylar3/mylar/config.py')}
  self.report=dict(kind='archive-one-independent-terminal-observation',outcome='observed-forward',reader_index_acceptance=False,ordinary_import_grant=False,publication_acceptance=False,mutation_authority=False,automatic_replay=False,original_vectors={'files':[['/app/mylar3/mylar/publication_api.py',[1,2,3,4,5,0o100644,1000,1000,1]],['/proofs/db',[1,3,3,4,5,0o100644,1000,1000,1]]],'nodes':[['/',[1,2,0o40755,0,0]],['/app',[1,3,0o40755,0,0]],['/proofs',[1,4,0o40700,1000,1000]]],'claims':[['/proofs/missing',None]],'censuses':[['/proofs',['db']]],'absent':['/proofs/sidecar']})
 def map(self,path):
  p=Path(path)
  if p==Path('/proofs') or Path('/proofs') in p.parents:return str(self.root/p.relative_to('/proofs'))
  raise ValueError('unmapped')
 def go(self):return v.partition(self.report,path_mapper=self.map,sdk_map=self.sdk,mounts=self.mounts,image_sources=self.sources)
 def test_actual_finite_namespace_separation(self):
  result=self.go();self.assertEqual(set(result['child_image_files']),{'/app/mylar3/mylar/publication_api.py'});self.assertIn(str(self.root/'db'),result['files']);self.assertIn('/',result['child_image_nodes']);self.assertNotIn('/',result['nodes']);self.assertFalse(result['publication_acceptance'])
 def test_image_overlay_holds(self):
  for target in ('/','/app','/app/mylar3','/app/mylar3/mylar/publication_api.py','/lsiopy','/lsiopy/bin/python3','/usr','/usr/lib','/lib','/lib64','/bin','/sbin'):
   with self.subTest(target=target):self.mounts.append(dict(host=str(self.root),child=target,write=False));self.assertRaises(v.Held,self.go);self.mounts.pop()
 def test_unknown_image_filename_holds(self):
  self.report['original_vectors']['files'][0][0]='/app/mylar3/mylar/unlisted.py';self.assertRaises(ValueError,self.go)
 def test_unknown_leaf_never_excluded(self):
  self.report['original_vectors']['files'].append(['/foreign/db',[1,2,3,4,5,0o100644,1000,1000,1]]);self.assertRaises(ValueError,self.go)
 def test_unknown_ancestor_holds(self):
  self.report['original_vectors']['nodes'].append(['/foreign',[1,2,0o40755,0,0]]);self.assertRaises(v.Held,self.go)
 def test_image_claim_never_excluded(self):
  self.report['original_vectors']['claims'].append(['/app/mylar3/mylar/publication_api.py',None]);self.assertRaises(ValueError,self.go)
 def test_complete_claim_absence_preserved(self):
  result=self.go();self.assertIsNone(result['claims'][str(self.root/'missing')]);self.assertEqual(result['absent'],(str(self.root/'sidecar'),))
 def test_bool_vector_alias_holds(self):
  self.report['original_vectors']['files'][0][1][0]=True;self.assertRaises(v.Held,self.go)
 def test_census_foreign_name_holds(self):
  self.report['original_vectors']['censuses'][0][1].append('../escape');self.assertRaises(v.Held,self.go)
 def test_rights_identity_holds(self):
  self.report['mutation_authority']=0;self.assertRaises(v.Held,self.go)
 def test_original_vectors_frozen_before_mapping(self):
  original=self.map;changed=[]
  def mapper(path):
   if not changed:changed.append(True);self.report['original_vectors']['files'][1][1][0]=999
   return original(path)
  result=v.partition(self.report,path_mapper=mapper,sdk_map=self.sdk,mounts=self.mounts,image_sources=self.sources);self.assertEqual(result['files'][str(self.root/'db')][0],1)

 def test_tool_and_loader_overlays_refused(self):
  for target in ('/opt','/opt/archiving-utils','/opt/archiving-utils/lib','/etc','/etc/ld.so.preload'):
   with self.subTest(target=target):
    self.mounts.append(dict(host=str(self.root),child=target,write=False));self.assertRaises(v.Held,self.go);self.mounts.pop()

if __name__=='__main__':unittest.main()
