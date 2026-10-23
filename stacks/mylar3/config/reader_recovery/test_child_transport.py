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
    def test_named_fifo_exchange_accepts_io_timestamp_changes(self):
        with tempfile.TemporaryDirectory() as root:
            paths=[Path(root)/name for name in ('input','output')]
            descriptors=[]
            try:
                for path in paths:
                    os.mkfifo(path,0o600)
                    descriptors.append(os.open(path,os.O_RDWR|os.O_NONBLOCK))
                read,write=descriptors
                channel=m.Channel(read,write,'a'*64,5)
                before=m.nine(os.fstat(write))
                sequence=channel.send('nfs-role-namespace',{})
                self.assertNotEqual(m.nine(os.fstat(write)),before)
                self.assertEqual(m.decode(os.read(write,m.MAX))['sequence'],sequence)
                os.write(read,m.encode(dict(type='nfs-host',nonce='a'*64,
                                           sequence=sequence,payload={'fixed':'reply'}))+b'\n')
                self.assertEqual(channel.receive(sequence),{'fixed':'reply'})
                channel.close()
            finally:
                for descriptor in descriptors:os.close(descriptor)

    def test_named_fifo_mode_change_still_refuses(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'fifo';os.mkfifo(path,0o600)
            descriptor=os.open(path,os.O_RDWR|os.O_NONBLOCK)
            try:
                channel=m.Channel(descriptor,descriptor,'a'*64,5)
                path.chmod(0o640)
                with self.assertRaisesRegex(m.Held,'pipe-drift'):channel.close()
            finally:os.close(descriptor)

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

    def test_failure_diagnostic_keeps_only_fixed_reason_and_bounded_callsites(self):
        def fail(depth):
            if depth:fail(depth-1)
            raise m.Held('child-lost-host')
        try:fail(12)
        except m.Held as error:raw=m.failure_diagnostic(error)
        value=m.decode(raw)
        self.assertEqual(value['reason'],'child-lost-host')
        self.assertEqual(value['exception'],'held')
        self.assertFalse(value['terminal_accepted']);self.assertFalse(value['automatic_replay'])
        self.assertEqual(value['frames'][0]['source'],'external')
        self.assertEqual(len(value['frames']),8);self.assertLess(len(raw),2048)

    def test_failure_diagnostic_redacts_exception_text_and_paths(self):
        for error in (m.Held('/private/key=secret'),OSError('/private/password'),
                      RuntimeError('credentials payload'),m.Held('child-lost-host secret')):
            raw=m.failure_diagnostic(error)
            self.assertIsNone(m.decode(raw)['reason'])
            for secret in (b'private',b'password',b'credentials',b'secret'):
                self.assertNotIn(secret,raw)

    def test_real_cli_reports_failed_original_without_disclosing_path(self):
        import subprocess
        with tempfile.TemporaryDirectory() as root:
            entry=Path(root)/'nfs-uid-child.py';entry.write_bytes(Path(m.__file__).read_bytes())
            result=subprocess.run([sys.executable,'-I','-B',str(entry),
                                   '--packet','/private/nonexistent-secret',
                                   '--packet-sha256','a'*64,'--packet9','[]'],
                                  capture_output=True,timeout=5)
        self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,b'')
        value=m.decode(result.stderr)
        self.assertEqual(value['kind'],'nfs-child-failure')
        self.assertTrue(value['frames'])
        self.assertTrue(all(row['source']=='nfs-uid-child.py' for row in value['frames']))
        self.assertNotIn(b'private',result.stderr);self.assertNotIn(b'secret',result.stderr)

    def test_closed_stderr_preserves_refusal_exit(self):
        import subprocess
        result=subprocess.run([sys.executable,'-I','-B',str(Path(m.__file__)),
                               '--packet','/private/nonexistent-secret',
                               '--packet-sha256','a'*64,'--packet9','[]'],
                              capture_output=True,timeout=5,preexec_fn=lambda:os.close(2))
        self.assertEqual(result.returncode,2)
        self.assertEqual(result.stdout,b'');self.assertEqual(result.stderr,b'')

    def test_default_active_source_is_unbound(self):
        self.assertIsNone(m.ACTIVE_SOURCE_SHA)

    def test_suppressed_original_context_retains_only_source_frames(self):
        scope={}
        exec(compile("def original():\n raise ValueError('credential-secret')\n",'/private/secret/comic_negative_nfs_active_parent.py','exec'),scope)
        try:
            try:scope['original']()
            except ValueError:raise RuntimeError('password-private') from None
        except RuntimeError as error:raw=m.failure_diagnostic(error)
        value=m.decode(raw)
        self.assertTrue(any(row==dict(source='comic_negative_nfs_active_parent.py',line=2) for row in value['contexts'][0]['frames']))
        for secret in (b'credential',b'secret',b'password',b'private'):self.assertNotIn(secret,raw)
        self.assertFalse(value['terminal_accepted']);self.assertFalse(value['automatic_replay'])

    def test_context_cycle_and_depth_are_bounded(self):
        errors=[ValueError('secret') for _ in range(12)]
        for first,second in zip(errors,errors[1:]):first.__context__=second
        value=m.decode(m.failure_diagnostic(errors[0]));self.assertEqual(len(value['contexts']),3)
        errors[1].__context__=errors[0]
        value=m.decode(m.failure_diagnostic(errors[0]));self.assertEqual(len(value['contexts']),1)

    def test_exception_subclass_attribute_callbacks_are_not_called(self):
        class Hostile(ValueError):
            def __getattribute__(self,name):raise AssertionError('attribute callback')
            @property
            def __traceback__(self):raise AssertionError('traceback property')
            @property
            def __context__(self):raise AssertionError('context property')
        error=Hostile('credential-secret');context=Hostile('password-secret')
        BaseException.__dict__['__context__'].__set__(error,context)
        raw=m.failure_diagnostic(error);value=m.decode(raw)
        self.assertEqual(value['exception'],'other');self.assertEqual(value['contexts'],[dict(frames=[])])
        self.assertNotIn(b'secret',raw)

    def test_traceback_examination_and_output_are_bounded(self):
        import types
        from unittest.mock import patch
        frame=sys._getframe();trace=None
        for _ in range(200):trace=types.TracebackType(trace,frame,frame.f_lasti,frame.f_lineno)
        error=ValueError('secret').with_traceback(trace);original=m.Path
        with patch.object(m,'Path',side_effect=original) as paths:
            value=m.decode(m.failure_diagnostic(error))
        self.assertEqual(paths.call_count,64);self.assertEqual(len(value['frames']),8)
        self.assertEqual(set(row['source'] for row in value['frames']),{'external'})

    def test_contexts_keep_original_fixed_transport_reason(self):
        error=m.Held('child-lost-host');error.__context__=OSError('/private/password')
        value=m.decode(m.failure_diagnostic(error))
        self.assertEqual(value['reason'],'child-lost-host');self.assertEqual(value['exception'],'held')
        self.assertEqual(value['contexts'],[dict(frames=[])])

if __name__=='__main__':unittest.main()
