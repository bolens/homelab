"""Rename/link publication with real files, ACL attributes and crash recovery."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import tagger_adapter as base
import tagger_attributes as attributes
import tagger_nfs
import tagger_handoff
from tagger_archive import snapshot
from tagger_cli import TagResult

TOKEN = 'a'*32


def saved(path, metadata, **kwargs):
    with zipfile.ZipFile(path, 'a') as archive:
        archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Fixture</Series></ComicInfo>')
    return TagResult('saved')


class NFSPublicationTest(unittest.TestCase):
    def setUp(self):
        # Explicit fixture root permits the same tests on the actual media mount.
        self.temp = tempfile.TemporaryDirectory(prefix='.mylar-nfs-fixture-', dir=os.getenv('MYLAR_TEST_MEDIA_ROOT'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root/'comic.cbz'
        with zipfile.ZipFile(self.source, 'w') as archive:
            archive.writestr('001.png', b'page'); archive.writestr('credits.txt', b'extras')
            archive.comment = b'legacy comment'
        self.source.chmod(0o640)
        os.setxattr(self.source, 'user.fixture', b'preserved\x00attribute')
        self.original = self.source.read_bytes(); self.security = attributes.capture(self.source)
        self.publisher = tagger_nfs.Publisher(self.root/'state')

    def tag(self):
        with patch.object(base, 'save', side_effect=saved):
            return self.publisher.tag(self.source, {'series':'Fixture'}, token=TOKEN)

    def crash(self, stage):
        code = '''import os,sys
from pathlib import Path
import tagger_adapter as base, tagger_nfs
from test_tagger_nfs import saved,TOKEN
base.save=saved
base._checkpoint=lambda value: os._exit(71) if value==sys.argv[2] else None
root=Path(sys.argv[1])
tagger_nfs.Publisher(root/'state').tag(root/'comic.cbz',{'series':'Fixture'},token=TOKEN)
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.root), stage],
                                env=dict(os.environ, PYTHONPATH=str(Path(__file__).parent)), timeout=20)
        self.assertEqual(result.returncode, 71)

    def test_success_preserves_members_attributes_permissions_and_replay(self):
        before = snapshot(self.source)
        self.assertEqual(self.tag().state, 'committed')
        after = snapshot(self.source)
        self.assertEqual((before.members,before.comment,before.mode,before.uid,before.gid),
                         (after.members,after.comment,after.mode,after.uid,after.gid))
        self.assertEqual(attributes.capture(self.source),self.security)
        self.assertEqual(self.source.stat().st_nlink,1)
        with patch.object(base,'save',side_effect=AssertionError('No repeated write')):
            self.assertEqual(self.publisher.recover(TOKEN).state,'committed')
        self.assertFalse(list(self.root.glob('.mylar-tag-*')))

    def test_handoff_verifies_acl_and_rejects_later_changes(self):
        self.assertEqual(self.tag().state, 'committed')
        result = tagger_handoff.capture(self.publisher, TOKEN)
        self.assertTrue(result.valid_for(self.source))
        self.assertNotIn('preserved', repr(result))
        os.setxattr(self.source, 'user.fixture', b'changed')
        self.assertFalse(result.valid_for(self.source))
        self.assertEqual(self.publisher.recover(TOKEN).state, 'conflict')
        self.assertEqual(self.publisher.read(TOKEN)['state'], 'committed')

    @unittest.skipUnless(Path('/opt/comictagger/bin/comictagger').exists(), 'Pinned runtime image required')
    def test_real_cli_preserves_nfs_attributes_and_verified_handoff(self):
        before = snapshot(self.source)
        result = self.publisher.tag(self.source, {'series':'Fixture', 'issue':'1'}, token=TOKEN)
        self.assertEqual(result.state, 'committed')
        self.assertEqual(snapshot(self.source).members, before.members)
        self.assertEqual(attributes.capture(self.source), self.security)
        self.assertTrue(tagger_handoff.capture(self.publisher, TOKEN).valid_for(self.source))

    def test_crash_boundaries_restore_or_commit_without_repeating_cli(self):
        for stage in ('staged','before_exchange','after_displace','after_link','after_unlink','after_exchange'):
            with self.subTest(stage=stage):
                self.setUp();self.crash(stage)
                with patch.object(base,'save',side_effect=AssertionError('No repeated write')):
                    state=self.publisher.recover(TOKEN).state
                self.assertEqual(state,'committed' if stage in ('after_link','after_unlink','after_exchange') else 'failed')
                self.assertEqual(attributes.capture(self.source),self.security)
                self.assertEqual(self.source.stat().st_nlink,1)
                if state=='failed':self.assertEqual(self.source.read_bytes(),self.original)
                else:self.assertIsNotNone(snapshot(self.source).xml)
                self.assertEqual(list(self.publisher.recover_pending()),[])

    def test_competing_destination_is_never_overwritten(self):
        def checkpoint(stage):
            if stage=='after_displace':self.source.write_bytes(b'other writer')
        with patch.object(base,'_checkpoint',side_effect=checkpoint):
            self.assertEqual(self.tag().state,'conflict')
        self.assertEqual(self.source.read_bytes(),b'other writer')
        displaced=self.root/('.mylar-tag-'+TOKEN)/'displaced.cbz'
        self.assertEqual(displaced.read_bytes(),self.original)
        self.assertEqual(attributes.capture(displaced),self.security)

    def test_source_replaced_at_rename_is_restored_and_retained(self):
        rename=os.rename
        def race(source,target):
            incoming=self.root/'incoming';incoming.write_bytes(b'replacement writer')
            os.replace(incoming,source)
            rename(source,target)
        with patch.object(tagger_nfs.os,'rename',side_effect=race):
            self.assertEqual(self.tag().state,'conflict')
        self.assertEqual(self.source.read_bytes(),b'replacement writer')
        self.assertEqual((self.root/('.mylar-tag-'+TOKEN)/'original.cbz').read_bytes(),self.original)

    def test_rpc_error_after_successful_operations_is_reconciled(self):
        for operation in ('rename','link'):
            with self.subTest(operation=operation):
                self.setUp();real=getattr(os,operation)
                def uncertain(*args,**kwargs):
                    real(*args,**kwargs);raise OSError('ambiguous RPC result')
                with patch.object(tagger_nfs.os,operation,side_effect=uncertain):
                    result=self.tag()
                if result.state=='conflict':result=self.publisher.recover(TOKEN)
                self.assertIn(result.state,('failed','committed'))
                self.assertEqual(attributes.capture(self.source),self.security)
                self.assertEqual(self.source.stat().st_nlink,1)

    def test_acl_write_failure_leaves_source_unchanged(self):
        with patch.object(attributes,'apply',side_effect=PermissionError('denied')):
            self.assertEqual(self.tag().state,'failed')
        self.assertEqual(self.source.read_bytes(),self.original)
        self.assertEqual(attributes.capture(self.source),self.security)

    def test_changed_attributes_block_cleanup(self):
        self.crash('after_link')
        os.setxattr(self.source,'user.fixture',b'changed')
        self.assertEqual(self.publisher.recover(TOKEN).state,'conflict')
        self.assertTrue((self.root/('.mylar-tag-'+TOKEN)/'displaced.cbz').exists())

    def test_old_reader_rejects_v2_without_mutation(self):
        self.crash('staged');raw=self.publisher.receipt(TOKEN).read_bytes()
        with self.assertRaises(ValueError):base.Publisher(self.root/'state').recover(TOKEN)
        self.assertEqual(self.publisher.receipt(TOKEN).read_bytes(),raw)
        self.assertEqual(self.source.read_bytes(),self.original)
        self.assertEqual(self.publisher.recover(TOKEN).state,'failed')

    def test_invalid_attributes_are_rejected_before_recovery(self):
        self.crash('staged');record=self.publisher.read(TOKEN)
        record['attributes']={'security.capability':'AAAA'}
        self.publisher.receipt(TOKEN).write_text(json.dumps(record))
        with self.assertRaises(ValueError):self.publisher.recover(TOKEN)
        self.assertEqual(self.source.read_bytes(),self.original)


if __name__=='__main__':unittest.main()
