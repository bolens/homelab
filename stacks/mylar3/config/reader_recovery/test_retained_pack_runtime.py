"""Real runtime closure against a declared Docker transport double; no lifecycle calls."""
import copy
import json
from pathlib import Path
import sys
import unittest
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
            self.rows[cid]=dict(Id=cid,Image='sha256:'+'a'*64,Config={},HostConfig={},Mounts=[],
                NetworkSettings=dict(Networks={}),State=state)
        def command(runtime,args):
            if args[0]=='inspect':return json.dumps([self.rows[args[1]]]).encode()
            self.assertEqual(args[0],'events');return b''
        self.transport=patch.object(parent.ConfiguredRuntime,'command',command)
        self.transport.start();self.addCleanup(self.transport.stop)
        self.runtime=parent.ConfiguredRuntime.observe(self.ids)
        self.addCleanup(parent._RUNTIMES.pop,self.runtime,None)
        self.addCleanup(parent._RUNTIME_ANCHORS.pop,self.runtime,None)
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


if __name__=='__main__':unittest.main()
