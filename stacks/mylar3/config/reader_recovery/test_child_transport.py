"""Real inherited pipe/process controls; no Docker/NFS/canary positive claim."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('child',Path(__file__).with_name('comic_nfs_uid_child.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Transport(unittest.TestCase):
    def test_real_child_pipe_exchange(self):
        to_child,host_write=os.pipe();host_read,from_child=os.pipe();pid=os.fork()
        if pid==0:
            try:
                os.close(host_write);os.close(host_read)
                c=m.Channel(to_child,from_child,'a'*64,10)
                sequence=c.send('nfs-result',{'pid':os.getpid(),'uid':os.geteuid()})
                value=c.receive(sequence)
                m.need(value=={'operation':'release','stopped':False},'literal-release')
                c.send('nfs-done',None);os._exit(0)
            except BaseException:os._exit(2)
        os.close(to_child);os.close(from_child)
        try:
            stream=os.fdopen(host_read,'rb',buffering=0)
            first=m.decode(stream.readline(m.MAX));self.assertEqual(first['payload']['pid'],pid);self.assertEqual(first['payload']['uid'],os.geteuid())
            os.write(host_write,m.encode(dict(type='nfs-host',nonce='a'*64,sequence=1,payload={'operation':'release','stopped':False}))+b'\n')
            last=m.decode(stream.readline(m.MAX));self.assertEqual(last['type'],'nfs-done');self.assertEqual(last['sequence'],2)
            self.assertEqual(os.waitpid(pid,0)[1],0)
        finally:
            stream.close();os.close(host_write)
    def test_wrong_nonce_or_sequence_refused(self):
        for field,value in (('nonce','b'*64),('sequence',2)):
            read,write=os.pipe();other_read,other_write=os.pipe()
            try:
                c=m.Channel(read,other_write,'a'*64,2)
                packet=dict(type='nfs-host',nonce='a'*64,sequence=1,payload={});packet[field]=value
                os.write(write,m.encode(packet)+b'\n')
                with self.assertRaisesRegex(m.Held,'host-frame'):c.receive(1)
            finally:
                for fd in (read,write,other_read,other_write):os.close(fd)
    def test_replaced_pipe_descriptor_refused(self):
        read,write=os.pipe();other_read,other_write=os.pipe();foreign_read,foreign_write=os.pipe()
        try:
            c=m.Channel(read,other_write,'a'*64,2);os.dup2(foreign_read,read)
            with self.assertRaisesRegex(m.Held,'pipe-drift'):c.close()
        finally:
            for fd in (read,write,other_read,other_write,foreign_read,foreign_write):os.close(fd)
    def test_real_original_file_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'control';path.write_bytes(b'original');path.chmod(0o600)
            ref=dict(path=str(path),sha256=hashlib.sha256(b'original').hexdigest(),signature9=list(m.nine(os.lstat(path))))
            self.assertEqual(m.original(ref)[0],b'original')
            path.rename(Path(root)/'retained');path.symlink_to('retained')
            with self.assertRaises(OSError):m.original(ref)
    @unittest.skipUnless(os.geteuid()==1000 and os.getegid()==1000,'actual UID1000 entry required')
    def test_unbound_entry_refuses_before_source_compile(self):
        with tempfile.TemporaryDirectory() as root:
            directory=Path(root)
            def put(name,raw):
                p=directory/name;p.write_bytes(raw);p.chmod(0o600)
                return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),signature9=list(m.nine(os.lstat(p))))
            source=put('source.py',b"raise AssertionError('must not compile or invoke')\n")
            inp=put('input.json',b'{}');roles=put('roles.json',b'{}')
            packet=put('packet.json',m.encode(dict(version=1,kind='owning-nfs-retained-child-v1',nonce='a'*64,seconds=10,active_source=source,active_input=inp,roles=roles)))
            with self.assertRaisesRegex(m.Held,'default-unbound'):m.serve(packet)

    def test_default_active_source_is_unbound(self):
        self.assertIsNone(m.ACTIVE_SOURCE_SHA)

if __name__=='__main__':unittest.main()
