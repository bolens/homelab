"""Actual Writer and pipe commit boundaries; authentication is an explicit double."""
import os
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from media_writer import Writer
import retained_pack_control as control


class SessionTypes(unittest.TestCase):
    def test_foreign_values_refuse_before_weak_lookup(self):
        calls=[]
        class Foreign:
            def __hash__(self):calls.append(True);raise AssertionError('foreign hash')
        for value in (object(),{},[],Foreign()):
            with self.subTest(type=type(value).__name__):
                with self.assertRaisesRegex(ValueError,'original-waiting-session'):control._close(value)
                with self.assertRaisesRegex(ValueError,'pack-original-authenticated-session'):
                    control._authenticated_complete(value,None,None,None,None)
        self.assertEqual(calls,[])


class WriterOriginals(unittest.TestCase):
    def test_actual_contextmanager_and_generator_are_retained(self):
        original=control._writer_hold_original(Writer.hold)
        control._check_writer_hold(original)
        self.assertIs(original[1],Writer.hold.__wrapped__)

    def test_same_wrapper_code_cannot_hide_generator_replacement(self):
        original=control._writer_hold_original(Writer.hold)
        generator=Writer.hold.__wrapped__;saved=generator.__code__
        def changed(self,**kwargs):yield self
        try:
            generator.__code__=changed.__code__
            self.assertIs(Writer.hold.__code__,original[2][0][1])
            with self.assertRaisesRegex(ValueError,'implementation'):control._check_writer_hold(original)
        finally:generator.__code__=saved

    def test_wrapper_closure_generator_replacement_refuses(self):
        original=control._writer_hold_original(Writer.hold)
        cell=Writer.hold.__closure__[0];saved=cell.cell_contents
        def changed(self,**kwargs):yield self
        try:
            cell.cell_contents=changed
            with self.assertRaisesRegex(ValueError,'implementation'):control._check_writer_hold(original)
        finally:cell.cell_contents=saved

    def test_generator_keyword_default_mutation_refuses(self):
        original=control._writer_hold_original(Writer.hold)
        defaults=Writer.hold.__wrapped__.__kwdefaults__;saved=defaults['allow_pending']
        try:
            defaults['allow_pending']=1
            with self.assertRaisesRegex(ValueError,'implementation'):control._check_writer_hold(original)
        finally:defaults['allow_pending']=saved

    def test_foreign_keyword_key_refuses_without_comparison_dispatch(self):
        original=control._writer_hold_original(Writer.hold);calls=[]
        class Hostile(str):
            def __lt__(self,other):calls.append(True);raise AssertionError('foreign comparison')
        defaults=Writer.hold.__wrapped__.__kwdefaults__;key=Hostile('foreign')
        try:
            defaults[key]=False
            with self.assertRaisesRegex(ValueError,'keyword-types'):control._check_writer_hold(original)
            self.assertEqual(calls,[])
        finally:defaults.pop(key)


class ReleaseCommit(unittest.TestCase):
    def test_real_writer_reacquired_after_body_suppresses_frame_delimiter(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'writer';writer=Writer(root,create=True)
            read_fd,write_fd=os.pipe();self.addCleanup(os.close,read_fd);self.addCleanup(os.close,write_fd)
            pipe=object.__new__(control.AuthenticatedPipe)
            pipe.write_fd=write_fd;pipe.nonce='a'*64;pipe.sequence=5;pipe.deadline=time.monotonic()+10
            class Binding:
                def child_frame(self,raw):pass  # Explicit auth double, never launch authority.
            binding=Binding();session=object()
            control._AUTH_PIPES[pipe]=(None,binding)
            control._RELEASE_SEND[pipe]=session
            self.addCleanup(control._AUTH_PIPES.pop,pipe,None)
            self.addCleanup(control._RELEASE_SEND.pop,pipe,None)
            held=[];write=os.write
            def actual_write(fd,data):
                count=write(fd,data)
                if not held:
                    manager=writer.hold(timeout=0);manager.__enter__();held.append(manager)
                return count
            def release_check(value,*,released=False):
                self.assertIs(value,session);self.assertTrue(released)
                if getattr(writer.local[1],'depth',0):raise ValueError('actual Writer reacquired')
            try:
                with patch.object(pipe,'close_originals'),patch.object(control,'_close',release_check),patch.object(control.os,'write',actual_write):
                    with self.assertRaisesRegex(ValueError,'actual Writer reacquired'):
                        pipe.send('observed-final-ACK','b'*64,{'writer_released':True})
                os.set_blocking(read_fd,False);raw=os.read(read_fd,65536)
                self.assertTrue(raw);self.assertNotIn(b'\n',raw);self.assertEqual(pipe.sequence,5)
            finally:
                for manager in reversed(held):manager.__exit__(None,None,None)


class Initialization(unittest.TestCase):
    def test_real_initialization_precedes_action_writer_and_keeps_class_original(self):
        from contextlib import ExitStack,contextmanager
        from normalize import Normalizer
        from maintenance import Maintenance
        import retained_pack_handoff as handoff
        import retained_pack_operations as operations
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);root.chmod(0o700)
            for name in ('state','library','completed','cache','native'):(root/name).mkdir(mode=0o700)
            Writer(root/'writer',create=True)
            config=dict(state=str(root/'state'),roots=[str(root/'library')],writer_state=str(root/'writer'),
                komga=dict(url='http://fixture.invalid',api_key='unused'),
                mylar=dict(url='http://fixture.invalid',config_dir=str(root/'native')),
                publication_roots=[dict(native=str(root/'library'),worker=str(root/'library'))],
                maintenance=dict(completed=str(root/'completed'),ddl_cache=str(root/'cache'),
                                 mylar_ddl_cache=str(root/'cache')))
            worker=Normalizer(config);maintenance=Maintenance(worker)
            source=root/'config.json';source.write_text(json.dumps(config));source.chmod(0o600)
            fds=(*os.pipe(),*os.pipe())
            for fd in fds:stack.callback(os.close,fd)
            pipe=control.Pipe(fds[0],fds[3],'a'*64,time.monotonic()+3600)
            lock=os.open(worker.state/'worker.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
            stack.callback(os.close,lock)
            # Explicit legacy activation/remote doubles; actual init, Writer,
            # source originals, journal, flock and pipe FDs remain genuine.
            stack.enter_context(patch.multiple(control,ENABLED=True,PARENT_SOURCE_SHA='b'*64))
            stack.enter_context(patch.object(handoff,'ENABLED',True))
            stack.enter_context(patch.object(handoff,'remote_unlocked'))
            stack.enter_context(patch.object(operations,'remote_unlocked'))
            value=control.initialize(maintenance,pipe,'b'*64,
                ((str(source),control.nine(source.stat())),),
                tuple((str(p),control.five(p.stat())) for p in source.parents),lock)
            state=control._close(value);owned=operations._core(state['session'])
            self.assertEqual(owned['phase'],'review');self.assertNotIn('writer',owned)
            self.assertTrue((maintenance.state/'retained-pack-handoffs').is_dir())
            @contextmanager
            def foreign(writer,**kwargs):yield writer
            with patch.object(Writer,'hold',foreign),self.assertRaisesRegex(ValueError,'Writer-class'):
                control._close(value)


if __name__=='__main__':unittest.main()
