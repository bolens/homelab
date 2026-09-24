"""Real ZIP/CRC fixtures, interrupted writes, and HTTP resume safety."""
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import zipfile
import verified_transfer as transfer
import queue_control

if len(sys.argv)>1:
    sys.argv.pop(1)


class TransferTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.final = self.root/'comic.cbz'
        stream = io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr('001.png', b'image fixture')
        self.body = stream.getvalue()
        self.state = queue_control.Store(self.root)
        self.state.begin({'id':'1','issueid':'2','mainlink':'fixture'})
        self.database = MagicMock()
        mylar = SimpleNamespace(queue_control=SimpleNamespace(_LOCK=queue_control._LOCK,store=lambda:self.state),
                                db=SimpleNamespace(DBConnection=lambda:self.database))
        context = patch.dict(sys.modules, {'mylar':mylar});context.start();self.addCleanup(context.stop)

    def response(self, body=None, status=200, headers=None):
        body = self.body if body is None else body
        return SimpleNamespace(status_code=status,headers=headers or {'Content-Length':str(len(body))},iter_content=lambda **kw:iter([body]))

    def test_verified_transfer_promotes_only_complete_archive(self):
        transfer.receive(self.response(), self.final, None, '1')
        self.assertEqual(self.final.read_bytes(), self.body)
        self.assertFalse(self.final.with_suffix('.cbz.part').exists())

    def test_truncated_transfer_stays_partial(self):
        with self.assertRaises(ValueError):
            transfer.receive(self.response(self.body[:20],headers={'Content-Length':str(len(self.body))}),self.final,None,'1')
        self.assertFalse(self.final.exists())
        self.assertEqual(self.final.with_suffix('.cbz.part').read_bytes(),self.body[:20])

    def test_resume_checks_offset_and_preserves_prefix(self):
        partial = self.final.with_suffix('.cbz.part');partial.write_bytes(self.body[:20])
        headers={'Content-Range':'bytes 20-%s/%s'%(len(self.body)-1,len(self.body)), 'Content-Length':str(len(self.body)-20)}
        transfer.receive(self.response(self.body[20:],206,headers),self.final,20,'1')
        self.assertEqual(self.final.read_bytes(),self.body)

    def test_wrong_offset_and_ignored_range_retain_original(self):
        self.final.write_bytes(self.body[:20])
        with self.assertRaises(ValueError):
            transfer.receive(self.response(self.body,206,{'Content-Range':'bytes 0-99/100'}),self.final,20,'1')
        self.assertEqual(self.final.read_bytes(),self.body[:20])
        transfer.receive(self.response(),self.final,20,'1')
        self.assertEqual(self.final.read_bytes(),self.body)
        self.assertEqual(next(self.root.glob('*.retained-*')).read_bytes(),self.body[:20])

    def test_corrupt_archive_never_promoted(self):
        with self.assertRaises(ValueError):
            transfer.receive(self.response(b'<html>not a comic</html>'),self.final,None,'1')
        self.assertFalse(self.final.exists())
        self.assertTrue(self.final.with_suffix('.cbz.part').exists())

    def test_pack_validates_members_before_publishing(self):
        pack=self.root/'pack.zip'
        with zipfile.ZipFile(pack,'w') as z:z.writestr('comic.cbz',self.body)
        result=transfer.unpack('1',pack,pack.name)
        self.assertEqual((Path(result['path'])/'comic.cbz').read_bytes(),self.body)
        self.assertTrue(pack.exists())
        bad=self.root/'bad.zip'
        with zipfile.ZipFile(bad,'w') as z:z.writestr('bad.cbr',b'not a rar')
        with self.assertRaises(ValueError):transfer.unpack('2',bad,bad.name)
        self.assertTrue(bad.exists());self.assertFalse(bad.with_suffix('').exists())

    def test_unsafe_member_rejected_before_extraction(self):
        pack=self.root/'unsafe.zip'
        with zipfile.ZipFile(pack,'w') as z:z.writestr('../outside.cbz',self.body)
        with self.assertRaises(ValueError):transfer.unpack('1',pack,pack.name)
        self.assertFalse((self.root.parent/'outside.cbz').exists())

    def test_crc_failure_detected(self):
        data=bytearray(self.body);index=data.index(b'image fixture');data[index]^=1
        self.final.write_bytes(data)
        with self.assertRaises(ValueError):transfer.checked(self.final)


if __name__ == '__main__':
    unittest.main()
