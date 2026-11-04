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


class Epoch(unittest.TestCase):
    def setUp(self):
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
        with self.assertRaisesRegex(ValueError,'open-once'):self.runtime.open_native()
        self.assertEqual(sum(c[0]=='unpause' for c in self.commands),1)

    def test_unknown_pause_ACK_is_not_retried(self):
        self.lifecycle_transport(unknown='pause')
        with self.assertRaisesRegex(ValueError,'exact-pause-ACK'):self.runtime.quiesce()
        with self.assertRaises(ValueError):self.runtime.quiesce()
        self.assertEqual(sum(c[0]=='pause' for c in self.commands),1)


if __name__=='__main__':unittest.main()
