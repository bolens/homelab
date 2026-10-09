"""Portable host geometry, explicitly synthetic runtime; no Docker or live NFS."""
import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).parent))
import test_nfs_current_source as fixture
P=fixture.P

class Geometry(fixture.LocalEnvironment):
 def rows(self,base):
  def state(running,pid):return dict(Status='running' if running else 'created',Running=running,Pid=pid,StartedAt='fixture',Paused=False,Restarting=False,Dead=False,OOMKilled=False)
  return [dict(Name='/mylar3',Id='a'*64,Image=P.NATIVE_IMAGE,State=state(True,11),Mounts=[dict(Destination='/data',Source=str(base),Type='bind',RW=True)]),dict(Name='/komga-comic-normalizer-1',Id='b'*64,Image=P.WORKER,State=state(False,0)),dict(Name='/komga',Id='c'*64,Image=P.KOMGA,State=state(True,12),Mounts=[dict(Destination='/data/'+name,Source=str(base/name),Type='bind',RW=False) for name in ('comics','manga')])]
 def media(self):
  t=tempfile.TemporaryDirectory(prefix='public-nfs-geometry-');self.addCleanup(t.cleanup);base=Path(t.name)/'arbitrary-media';base.mkdir(mode=0o700)
  for name in ('comics','manga'):(base/name).mkdir(mode=0o700)
  return base
 def test_arbitrary_host_media_root_joins_exact_public_destinations(self):
  base=self.media();value=P.live_mapping(self.rows(base),[base/'comics',base/'manga'])
  self.assertEqual({m['source'] for m in value['media_mounts']},{str(base/'comics'),str(base/'manga')})
 def test_reader_host_root_mismatch_refuses(self):
  base=self.media();rows=self.rows(base);rows[-1]['Mounts'][1]['Source']=str(base/'comics')
  with self.assertRaisesRegex(P.Held,'reader-media-map'):P.live_mapping(rows,[base/'comics',base/'manga'])
 def test_unprotected_reader_root_refuses(self):
  base=self.media()
  with self.assertRaisesRegex(P.Held,'all-reader-mounted-roots-forbidden'):P.live_mapping(self.rows(base),[base/'comics'])
 def config(self,nested=False):
  t=tempfile.TemporaryDirectory(prefix='public-nfs-native-config-');self.addCleanup(t.cleanup);base=Path(t.name);data=base/'nested' if nested else base
  if nested:data.mkdir(mode=0o700)
  writer=data/'media-writer';writer.mkdir(mode=0o700)
  mount=dict(Source=str(base),Destination='/config',Type='bind',RW=True)
  config=dict(path='/config/nested/config.ini' if nested else '/config/config.ini')
  return base,data,writer,mount,config
 def test_direct_config_DATA_writer_join(self):
  _,data,writer,mount,config=self.config();self.assertEqual(P.configured_writer_mapping([mount],config,writer),data)
 def test_nested_config_DATA_writer_join(self):
  _,data,writer,mount,config=self.config(True);self.assertEqual(P.configured_writer_mapping([mount],config,writer),data)
 def test_wrong_writer_root_and_outside_child_config_refuse(self):
  base,data,writer,mount,config=self.config(True)
  with self.assertRaisesRegex(P.Held,'same-actual-native-config-writer-mapping'):P.configured_writer_mapping([mount],config,base/'media-writer')
  with self.assertRaisesRegex(P.Held,'native-config-child-path'):P.configured_writer_mapping([mount],dict(path='/elsewhere/config.ini'),writer)

 def test_full_original_nested_mount_refuses_parent_only_writer(self):
  base,data,writer,mount,config=self.config(True);actual=base/'actual';actual.mkdir(mode=0o700);(actual/'media-writer').mkdir(mode=0o700)
  mounts=[mount,dict(Source=str(actual),Destination='/config/nested',Type='bind',RW=True)]
  with self.assertRaisesRegex(P.Held,'same-actual-native-config-writer-mapping'):P.configured_writer_mapping(mounts,config,writer)
  self.assertEqual(P.configured_writer_mapping(mounts,config,actual/'media-writer'),actual)
 def test_ambiguous_original_DATA_mount_refuses(self):
  base,data,writer,mount,config=self.config(True)
  mounts=[mount,dict(Source=str(data),Destination='/config/nested',Type='bind',RW=True),dict(Source=str(data),Destination='/config/nested',Type='bind',RW=True)]
  with self.assertRaisesRegex(P.Held,'native-config-ambiguous-or-readonly'):P.configured_writer_mapping(mounts,config,writer)
 def test_original_config_or_writer_leaf_shadow_refuses(self):
  base,data,writer,mount,config=self.config(True);other=base/'other';other.mkdir(mode=0o700);file=other/'config.ini';file.write_text('fixture')
  for source,destination in ((str(file),'/config/nested/config.ini'),(str(other),'/config/nested/media-writer')):
   with self.subTest(destination=destination):
    with self.assertRaisesRegex(P.Held,'native-config-leaf-or-writer-shadow'):P.configured_writer_mapping([mount,dict(Source=source,Destination=destination,Type='bind',RW=True)],config,writer)

if __name__=='__main__':unittest.main()
