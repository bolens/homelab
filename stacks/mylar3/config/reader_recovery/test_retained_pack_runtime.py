"""Real runtime closure against a declared Docker transport double; no lifecycle calls."""
import copy
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_retained_pack_parent as parent


class PauseStreamDouble:
    """Explicit event-transport double; real pipe framing has separate tests."""
    def __init__(self,runtime):self.events=();self.closed=False;self.origin=object()
    def expect(self,action,window,deadline,original=None):self.events+=((action,window[0],b'fixture'),)
    def paused(self,original=None):
        if self.events!=((self.events[0] if self.events else None),) or self.events[0][0]!='pause':raise ValueError('native-event-foreign-transition')
    def finish(self,original=None):self.closed=True


class Epoch(unittest.TestCase):
    def setUp(self):
        observer=patch.object(parent,'_NativePauseEvents',PauseStreamDouble)
        observer.start();self.addCleanup(observer.stop)
        self.ids={role:digit*64 for role,digit in (('native','1'),('reader','2'),('worker','3'))}
        self.rows={}
        for index,(role,cid) in enumerate(self.ids.items(),1):
            active=role!='worker'
            state=dict(Running=active,Paused=False,Status='running' if active else 'exited',
                Pid=index if active else 0,StartedAt='original-start',FinishedAt='original-finish',
                Restarting=False,Dead=False,OOMKilled=False,ExitCode=0,Error='')
            if active:state['Health']=dict(Status='healthy',FailingStreak=0,Log=[dict(Start='first',End='first',ExitCode=0,Output='')])
            self.rows[cid]=dict(Id=cid,Name='/'+role,Path='/init',Args=[],Image='sha256:'+'a'*64,Config={},HostConfig={},Mounts=[],
                NetworkSettings=dict(Networks={}),State=state)
        def command(runtime,args):
            if args[0]=='inspect':return json.dumps([self.rows[args[1]]]).encode()
            self.assertEqual(args[0],'events');return b''
        self.transport=patch.object(parent.ConfiguredRuntime,'command',command)
        self.transport.start();self.addCleanup(self.transport.stop)
        self.runtime=parent.ConfiguredRuntime.observe(self.ids)
        self.addCleanup(parent._RUNTIMES.pop,self.runtime,None)
        self.addCleanup(parent._RUNTIME_ANCHORS.pop,self.runtime,None)
        self.addCleanup(parent._READER_RESUMES.pop,self.runtime,None)
        self.addCleanup(parent._QUIESCENCE_ATTEMPTS.pop,self.runtime,None)
        self.addCleanup(parent._TERMINALS.pop,self.runtime,None)
        self.baseline=copy.deepcopy(self.runtime.baseline)

    def test_health_log_churn_preserves_original_process_epoch(self):
        for role in ('native','reader'):
            self.rows[self.ids[role]]['State']['Health']['Log']=[dict(Start='later',End='later',ExitCode=0,Output='healthy')]
        self.runtime.close()
        self.assertEqual(self.runtime.baseline,self.baseline)

    def test_process_or_health_change_still_refuses(self):
        state=self.rows[self.ids['native']]['State'];original=copy.deepcopy(state)
        for key,value in (('Pid',99),('StartedAt','foreign'),('Restarting',True),('Error','foreign')):
            with self.subTest(field=key):
                state[key]=value
                with self.assertRaisesRegex(ValueError,'runtime-before-owned-quiescence'):self.runtime.close()
                state.clear();state.update(copy.deepcopy(original))
        for key,value in (('Status','unhealthy'),('FailingStreak',1),('foreign','value')):
            with self.subTest(health=key):
                state['Health'][key]=value
                with self.assertRaisesRegex(ValueError,'runtime-before-owned-quiescence'):self.runtime.close()
                state.clear();state.update(copy.deepcopy(original))

    def test_malformed_health_log_refuses(self):
        self.rows[self.ids['native']]['State']['Health']['Log']='foreign'
        with self.assertRaisesRegex(ValueError,'runtime-health-shape'):self.runtime.close()

    def lifecycle_transport(self,*,unknown=None):
        self.commands=[];original=parent.ConfiguredRuntime.command
        def command(runtime,args):
            self.commands.append(args)
            if args[0] in ('inspect','events'):return original(runtime,args)
            if args[0]=='pause':self.rows[self.ids['native']]['State']['Paused']=True
            elif args[0]=='unpause':self.rows[self.ids['native']]['State']['Paused']=False
            elif args[0]=='stop':self.rows[self.ids['reader']]['State'].update(Running=False,Pid=0,Status='exited',FinishedAt='owned-stop')
            elif args[0]=='start':self.rows[self.ids['reader']]['State'].update(Running=True,Pid=222,Status='running',StartedAt='owned-resume',FinishedAt='')
            else:self.fail(args)
            return b'unknown\n' if args[0]==unknown else (args[-1]+'\n').encode()
        context=patch.object(parent.ConfiguredRuntime,'command',command);context.start();self.addCleanup(context.stop)

    def terminal(self):
        # Explicit selected-exit fixture. Real Root data acceptance is tested by
        # the owning broker; this suite tests the actual lifecycle mechanism.
        self.lifecycle_transport();self.runtime.quiesce();self.runtime.open_native()
        selected='4'*64;row=copy.deepcopy(self.rows[self.ids['worker']]);row['Id']=selected
        row['State'].update(StartedAt='selected-start',Status='exited',Running=False,Pid=0)
        self.rows[selected]=row;self.runtime.selected=selected
        self.runtime.selected_static=self.runtime.static(row);self.runtime.selected_started='selected-start'
        self.runtime.process=SimpleNamespace(poll=lambda:0)
        parent._TERMINALS[self.runtime]=(selected,'selected-start',self.runtime.selected_static,self.runtime.process)

    def test_quiesce_and_resume_keep_explicit_original_phase(self):
        self.terminal();answer=self.runtime.resume_reader();self.runtime.close()
        self.assertEqual(answer['container'],self.ids['reader']);self.assertTrue(self.runtime.quiescent)
        self.assertTrue(self.runtime.native_open)
        self.assertEqual([c[0] for c in self.commands if c[0] not in ('inspect','events')],['pause','stop','unpause','start'])
        with self.assertRaisesRegex(ValueError,'resume-once'):self.runtime.resume_reader()

    def test_resume_without_selected_natural_exit_refuses_before_start(self):
        self.lifecycle_transport();self.runtime.quiesce();self.runtime.open_native();self.commands.clear()
        with self.assertRaisesRegex(ValueError,'resume-once'):self.runtime.resume_reader()
        self.assertNotIn('start',[c[0] for c in self.commands])

    def test_unknown_start_ACK_cannot_be_replayed_or_rebased(self):
        self.terminal();command=parent.ConfiguredRuntime.command
        def unknown(runtime,args):
            answer=command(runtime,args);return b'unknown\n' if args[0]=='start' else answer
        with patch.object(parent.ConfiguredRuntime,'command',unknown):
            with self.assertRaisesRegex(ValueError,'exact-start-ACK'):self.runtime.resume_reader()
        with self.assertRaisesRegex(ValueError,'original-ACK'):self.runtime.resume_reader()
        self.assertEqual(sum(c[0]=='start' for c in self.commands),1)

    def test_resumed_foreign_incarnation_or_profile_refuses(self):
        self.terminal();self.runtime.resume_reader()
        row=self.rows[self.ids['reader']];row['State']['Pid']+=1
        with self.assertRaisesRegex(ValueError,'resumed-incarnation'):self.runtime.close()
        row['State']['Pid']-=1;row['Config']['foreign']=True
        with self.assertRaisesRegex(ValueError,'original-profile'):self.runtime.close()

    def test_unknown_native_unpause_ACK_is_not_retried(self):
        self.lifecycle_transport(unknown='unpause');self.runtime.quiesce()
        with self.assertRaisesRegex(ValueError,'exact-unpause-ACK'):self.runtime.open_native()
        with self.assertRaisesRegex(ValueError,'original-release-ACK'):self.runtime.open_native()
        self.assertEqual(sum(c[0]=='unpause' for c in self.commands),1)

    def test_unknown_pause_ACK_is_not_retried(self):
        self.lifecycle_transport(unknown='pause')
        with self.assertRaisesRegex(ValueError,'exact-pause-ACK'):self.runtime.quiesce()
        with self.assertRaises(ValueError):self.runtime.quiesce()
        self.assertEqual(sum(c[0]=='pause' for c in self.commands),1)


    def cleanup_transport(self, *, unknown=False, foreign=False):
        calls=[]
        def transport(runtime,args,pending):
            calls.append(args)
            if args[0]=='inspect':return json.dumps([self.rows[self.ids['native']]]).encode()
            if args[0]=='events':
                actions=['pause']+(['unpause'] if foreign else [])
                return b'\n'.join(json.dumps(dict(Type='container',Actor=dict(ID=self.ids['native']),Action=action)).encode() for action in actions)
            self.assertEqual(args,['unpause',self.ids['native']])
            self.rows[self.ids['native']]['State']['Paused']=False
            return b'unknown\n' if unknown else (self.ids['native']+'\n').encode()
        if foreign:parent._NATIVE_PAUSES[self.runtime][4].events+=(('unpause',0,b'foreign'),)
        guard=patch.object(parent.ConfiguredRuntime,'_cleanup_command',transport)
        guard.start();self.addCleanup(guard.stop)
        return calls

    def test_confirmed_pause_cleanup_survives_execution_expiry_without_reader_resume(self):
        self.lifecycle_transport();self.runtime.quiesce();calls=self.cleanup_transport()
        with patch.object(parent.time,'monotonic',return_value=self.runtime.deadline+1):
            self.assertTrue(self.runtime.release_owned_native_pause())
            self.assertTrue(self.runtime.release_owned_native_pause())
            with self.assertRaisesRegex(ValueError,'runtime-lifetime'):self.runtime.close()
        self.assertEqual(sum(args[0]=='unpause' for args in calls),1)
        self.assertFalse(self.rows[self.ids['reader']]['State']['Running'])
        self.assertNotIn('start',[args[0] for args in self.commands])

    def test_reader_stop_failure_releases_only_confirmed_native_pause(self):
        self.lifecycle_transport();calls=self.cleanup_transport();command=parent.ConfiguredRuntime.command
        def refused(runtime,args):
            if args[0]=='stop':raise ValueError('original-reader-stop-failure')
            return command(runtime,args)
        with patch.object(parent.ConfiguredRuntime,'command',refused):
            with self.assertRaisesRegex(ValueError,'original-reader-stop-failure'):self.runtime.quiesce()
        self.assertTrue(self.rows[self.ids['reader']]['State']['Running'])
        self.assertFalse(self.rows[self.ids['native']]['State']['Paused'])
        self.assertEqual(sum(args[0]=='unpause' for args in calls),1)

    def test_cleanup_unknown_unpause_ACK_never_replays(self):
        self.lifecycle_transport();self.runtime.quiesce();calls=self.cleanup_transport(unknown=True)
        with self.assertRaisesRegex(ValueError,'exact-unpause-ACK'):self.runtime.release_owned_native_pause()
        self.assertFalse(self.runtime.release_owned_native_pause())
        with self.assertRaisesRegex(ValueError,'original-release-ACK'):self.runtime.close()
        self.assertEqual(sum(args[0]=='unpause' for args in calls),1)

    def test_cleanup_refuses_foreign_native_lifecycle_before_unpause(self):
        self.lifecycle_transport();self.runtime.quiesce();calls=self.cleanup_transport(foreign=True)
        with self.assertRaisesRegex(ValueError,'native-event-foreign-transition'):self.runtime.release_owned_native_pause()
        self.assertNotIn('unpause',[args[0] for args in calls])

    def test_cleanup_refuses_replaced_native_process_before_unpause(self):
        self.lifecycle_transport();self.runtime.quiesce();calls=self.cleanup_transport()
        self.rows[self.ids['native']]['State']['Pid']+=1
        with self.assertRaisesRegex(ValueError,'original-process-profile'):self.runtime.release_owned_native_pause()
        self.assertNotIn('unpause',[args[0] for args in calls])

    def test_original_observer_cleanup_is_independent_of_runtime_registry_refusal(self):
        self.lifecycle_transport();observer=self.runtime.quiesce()
        parent._RUNTIMES[self.runtime]=b'foreign'
        primary=ValueError('original-backup-failure')
        with self.assertRaisesRegex(ValueError,'original-backup-failure') as result:
            parent.finish_owned_pause(self.runtime,observer,primary)
        self.assertIs(result.exception,primary)
        self.assertTrue(observer[0].closed)
        self.assertTrue(self.rows[self.ids['native']]['State']['Paused'])
        self.assertFalse(self.rows[self.ids['reader']]['State']['Running'])

    def test_unknown_pause_ACK_does_not_grant_cleanup(self):
        self.lifecycle_transport(unknown='pause');calls=self.cleanup_transport()
        with self.assertRaisesRegex(ValueError,'exact-pause-ACK'):self.runtime.quiesce()
        self.assertFalse(self.runtime.release_owned_native_pause())
        self.assertEqual(calls,[])

class NativeEventPipe(unittest.TestCase):
    def setUp(self):
        import subprocess
        self.subprocess=subprocess;self.real=subprocess.Popen
        def process(args,**kwargs):
            self.assertEqual(args[:2],['docker','events'])
            self.assertIn('container='+'1'*64,args)
            # One private echo process exercises actual pipes/EOF/FD custody;
            # no Docker daemon or service actions occur in this suite.
            child=self.real([sys.executable,'-u','-c',
                'import sys\nfor line in sys.stdin.buffer:\n sys.stdout.buffer.write(line);sys.stdout.buffer.flush()'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            self.child=child;return child
        self.transport=patch.object(subprocess,'Popen',process);self.transport.start();self.addCleanup(self.transport.stop)
        self.watcher=parent._NativePauseEvents(SimpleNamespace(ids={'native':'1'*64}))
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.watcher.finish()
        self.child.stdin.close()

    def send(self,action):
        import time
        stamp=time.time_ns()
        raw=json.dumps(dict(Type='container',Actor=dict(ID='1'*64),Action=action,timeNano=stamp)).encode()+b'\n'
        self.child.stdin.write(raw);self.child.stdin.flush()
        return stamp

    def test_live_pipe_binds_pause_and_unpause_without_daemon_history(self):
        import time
        first=self.send('pause');self.watcher.expect('pause',(first,first),time.monotonic()+3)
        self.watcher.paused()
        second=self.send('unpause');self.watcher.expect('unpause',(second,second),time.monotonic()+3)
        self.assertEqual([row[0] for row in self.watcher.events],['pause','unpause'])
        self.watcher.finish();self.assertIsNotNone(self.child.poll())

    def test_foreign_transition_cannot_be_replaced_by_later_pause(self):
        import time
        first=self.send('pause');self.watcher.expect('pause',(first,first),time.monotonic()+3)
        self.send('unpause');self.send('pause')
        with self.assertRaisesRegex(ValueError,'foreign-transition'):
            self.watcher.expect('unpause',(0,10**30),time.monotonic()+3)

    def test_record_outside_own_command_window_refuses(self):
        import time
        stamp=self.send('pause')
        with self.assertRaisesRegex(ValueError,'command-window'):
            self.watcher.expect('pause',(stamp+1,stamp+2),time.monotonic()+3)

    def test_observer_exit_refuses_even_with_retained_pause(self):
        import time
        stamp=self.send('pause');self.watcher.expect('pause',(stamp,stamp),time.monotonic()+3)
        self.child.stdin.close();self.child.wait(timeout=3)
        with self.assertRaisesRegex(ValueError,'original-stream'):self.watcher.paused()

    def test_substituted_process_is_never_a_cleanup_target(self):
        foreign=self.real([sys.executable,'-c','import sys;sys.stdin.read()'],stdin=self.subprocess.PIPE)
        origin=self.watcher.origin;owned=self.child
        try:
            self.watcher.process=foreign
            with self.assertRaisesRegex(ValueError,'original-stream'):self.watcher.check(origin)
            with self.assertRaisesRegex(ValueError,'field-drift'):self.watcher.finish(origin)
            self.assertIsNone(foreign.poll());self.assertIsNotNone(owned.poll())
        finally:
            self.watcher.process=owned
            foreign.terminate();foreign.wait(timeout=3);foreign.stdin.close()

    def test_initial_FD_fault_quarantines_stream_and_reaps_only_created_process(self):
        owned=self.child;original_fstat=parent.os.fstat;start=len(parent._NATIVE_EVENT_QUARANTINE)
        try:
            with patch.object(parent.os,'fstat',side_effect=OSError('initial-FD-fault')):
                with self.assertRaisesRegex(OSError,'initial-FD-fault'):
                    parent._NativePauseEvents(SimpleNamespace(ids={'native':'1'*64}))
            failed=self.child;self.assertIsNotNone(failed.poll())
            self.assertEqual(len(parent._NATIVE_EVENT_QUARANTINE),start+1)
            stream=parent._NATIVE_EVENT_QUARANTINE[-1]
            self.assertFalse(stream.closed);original_fstat(stream.fileno())
            stream.close();parent._NATIVE_EVENT_QUARANTINE.pop();failed.stdin.close()
        finally:self.child=owned

    def test_partial_record_deadline_refuses(self):
        import time
        self.child.stdin.write(b'{"Type":');self.child.stdin.flush()
        with self.assertRaisesRegex(ValueError,'original-deadline'):
            self.watcher.expect('pause',(0,10**30),time.monotonic()+0.05)




if __name__=='__main__':unittest.main()
