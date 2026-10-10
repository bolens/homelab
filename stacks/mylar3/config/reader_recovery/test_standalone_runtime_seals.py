"""Logical seal controls with explicit synthetic inspect/events; no runtime grant."""
import copy
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_retained_standalone_parent as p

class RuntimeSealTests(unittest.TestCase):
    def fixture(self):
        value=object.__new__(p.ConfiguredRuntime)
        value.pid=p.os.getpid();value.thread=p.threading.get_ident();value.deadline=p.time.monotonic()+30
        value.started=p.time.time();value.ids=dict(native='a'*64,reader='b'*64,worker='c'*64)
        def row(cid,state):
            return dict(Id=cid,Image='d'*64,Config={},HostConfig={},Mounts=[],NetworkSettings={'Networks':{}},State=state)
        native=dict(Running=True,Paused=False,Pid=123,StartedAt='original',Restarting=False,Dead=False)
        reader=dict(Running=True,Paused=False,Pid=124,StartedAt='reader')
        worker=dict(Running=False,Paused=False,Pid=0,Status='created',StartedAt='')
        value.baseline={role:row(cid,copy.deepcopy(state)) for role,cid,state in (
            ('native',value.ids['native'],native),('reader',value.ids['reader'],reader),('worker',value.ids['worker'],worker))}
        p._RUNTIMES[value]=p.encode(dict(ids=value.ids,baseline=value.baseline,pid=value.pid,thread=value.thread,
                                       deadline=value.deadline,started=value.started))
        value.quiescent=True;value.selected=None;value.process=None
        value.reader_state=dict(Running=False,Paused=False,Pid=0,Status='exited',StartedAt='reader',ExitCode=0)
        current=copy.deepcopy(value.baseline);current['native']['State']['Paused']=True
        current['reader']['State']=copy.deepcopy(value.reader_state)
        return value,current
    def test_original_frame_closes_synthetic_inspect_without_authority(self):
        runtime,rows=self.fixture()
        with patch.object(p.ConfiguredRuntime,'inspect',lambda _,cid:copy.deepcopy(next(v for v in rows.values() if v['Id']==cid))),patch.object(p.ConfiguredRuntime,'command',lambda *_:b''):
            runtime.close()
    def test_original_baseline_cannot_change_in_last_event_callback(self):
        runtime,rows=self.fixture();fired=[]
        def event(*_):
            runtime.baseline['native']['Config']['foreign']=True;fired.append(True);return b''
        with patch.object(p.ConfiguredRuntime,'inspect',lambda _,cid:copy.deepcopy(next(v for v in rows.values() if v['Id']==cid))),patch.object(p.ConfiguredRuntime,'command',event),self.assertRaises(ValueError):runtime.close()
        self.assertTrue(fired)
    def test_runtime_registry_cannot_be_replaced_after_last_event(self):
        runtime,rows=self.fixture()
        def event(*_):p._RUNTIMES[runtime]=b'foreign';return b''
        with patch.object(p.ConfiguredRuntime,'inspect',lambda _,cid:copy.deepcopy(next(v for v in rows.values() if v['Id']==cid))),patch.object(p.ConfiguredRuntime,'command',event),self.assertRaises(ValueError):runtime.close()
    def test_original_terminal_absence_refuses_present_None(self):
        runtime,rows=self.fixture()
        def event(*_):p._TERMINALS[runtime]=None;return b''
        with patch.object(p.ConfiguredRuntime,'inspect',lambda _,cid:copy.deepcopy(next(v for v in rows.values() if v['Id']==cid))),patch.object(p.ConfiguredRuntime,'command',event),self.assertRaises(ValueError):runtime.close()
    def test_foreign_native_unpause_event_refuses(self):
        runtime,rows=self.fixture();event=json.dumps({'Type':'container','Action':'unpause','Actor':{'ID':runtime.ids['native']}}).encode()
        with patch.object(p.ConfiguredRuntime,'inspect',lambda _,cid:copy.deepcopy(next(v for v in rows.values() if v['Id']==cid))),patch.object(p.ConfiguredRuntime,'command',lambda *_:event),self.assertRaises(ValueError):runtime.close()
    def test_late_quiescence_or_reader_terminal_state_change_refuses(self):
        for field in ('quiescent','reader_state'):
            runtime,rows=self.fixture()
            def event(*_):
                if field=='quiescent':runtime.quiescent=False
                else:runtime.reader_state['ExitCode']=9
                return b''
            with patch.object(p.ConfiguredRuntime,'inspect',lambda _,cid:copy.deepcopy(next(v for v in rows.values() if v['Id']==cid))),patch.object(p.ConfiguredRuntime,'command',event),self.assertRaises(ValueError):runtime.close()

if __name__=='__main__':unittest.main()
