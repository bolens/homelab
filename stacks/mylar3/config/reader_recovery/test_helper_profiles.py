"""Qualified Docker lifecycle shapes with synthetic identities; no engine calls."""
import copy
import json
from pathlib import Path
import unittest
import subprocess
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_reader_backup_primitives as p


class HelperProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=json.loads(Path(__file__).with_name('helper_profile_vectors.json').read_bytes())['cases']

    def birth(self,case):
        return p.helper_started_profile(case['created'],case['running'],case['cid'],case['networks'])

    def test_actual_created_running_and_exited_shapes(self):
        for name,case in self.cases.items():
            with self.subTest(name=name):
                self.assertTrue(self.birth(case))
                self.assertTrue(p.helper_exited_profile(case['running'],case['exited'],case['cid']))
                self.assertNotEqual(p.helper_profile(case['created']),p.helper_profile(case['running']))

    def test_unrelated_profile_changes_refuse(self):
        for name,case in self.cases.items():
            for field,value in (('Privileged',True),('CapAdd',['SYS_ADMIN']),('ReadonlyRootfs',False),('Memory',1),('OomScoreAdj',False)):
                changed=copy.deepcopy(case);changed['running']['HostConfig'][field]=value
                with self.subTest(name=name,field=field):self.assertFalse(self.birth(changed))
            for field,value in (('Env',['A=foreign']),('User','0:0'),('Cmd',['foreign'])):
                changed=copy.deepcopy(case);changed['running']['Config'][field]=value
                with self.subTest(name=name,field=field):self.assertFalse(self.birth(changed))
            changed=copy.deepcopy(case);changed['running']['Mounts'].append({'Type':'bind','Source':'/foreign','Destination':'/foreign','RW':True})
            self.assertFalse(self.birth(changed))

    def test_foreign_identity_or_network_refuses(self):
        for name,case in self.cases.items():
            changed=copy.deepcopy(case);changed['running']['Id']='9'*64;self.assertFalse(self.birth(changed))
            network=next(iter(case['networks']))
            for field,value in (('NetworkID','9'*64),('Aliases',['foreign']),('DriverOpts',{'foreign':'true'})):
                changed=copy.deepcopy(case);changed['running']['NetworkSettings']['Networks'][network][field]=value
                with self.subTest(name=name,field=field):self.assertFalse(self.birth(changed))
            changed=copy.deepcopy(case);changed['running']['NetworkSettings']['Networks']['foreign']={};self.assertFalse(self.birth(changed))

    def test_address_and_dns_allocation_are_bounded(self):
        case=self.cases['configured'];network=next(iter(case['networks']))
        for field,value in (('IPAddress','203.0.113.50'),('IPPrefixLen',8),('Gateway','203.0.113.1'),('DNSNames',['foreign']),('MacAddress','ff:ff:ff:ff:ff:ff')):
            changed=copy.deepcopy(case);changed['running']['NetworkSettings']['Networks'][network][field]=value
            with self.subTest(field=field):self.assertFalse(self.birth(changed))
        case=self.cases['none']
        for field,value in (('IPAddress','192.0.2.50'),('Gateway','192.0.2.1'),('MacAddress','02:00:00:00:00:01'),('DNSNames',['foreign'])):
            changed=copy.deepcopy(case);changed['running']['NetworkSettings']['Networks']['none'][field]=value
            with self.subTest(field=field):self.assertFalse(self.birth(changed))

    def test_running_profile_cannot_be_reused_as_created(self):
        for case in self.cases.values():
            self.assertFalse(p.helper_started_profile(case['running'],case['running'],case['cid'],case['networks']))

    def test_exit_permits_only_endpoint_teardown(self):
        for case in self.cases.values():
            for mutate in (
                lambda row:row['HostConfig'].update(OomKillDisable=False),
                lambda row:row['Config'].update(Env=['foreign']),
                lambda row:row.update(Id='9'*64),
                lambda row:next(iter(row['NetworkSettings']['Networks'].values())).update(NetworkID='9'*64),
            ):
                changed=copy.deepcopy(case['exited']);mutate(changed)
                self.assertFalse(p.helper_exited_profile(case['running'],changed,case['cid']))

    def test_only_runtime_network_usage_is_excluded(self):
        for case in self.cases.values():
            for original in case['networks'].values():
                changed=copy.deepcopy(original);changed['Containers']={'public':{}};changed['Status']={'IPAM':{'public':{'IPsInUse':99}}}
                self.assertEqual(p.helper_network_configuration(original),p.helper_network_configuration(changed))
                changed['IPAM']['Driver']='foreign'
                self.assertNotEqual(p.helper_network_configuration(original),p.helper_network_configuration(changed))

    def test_unpublished_exposed_port_metadata_may_materialize(self):
        for ports in ({},{'8090/tcp':None}):
            changed=copy.deepcopy(self.cases['none'])
            for phase in ('created','running','exited'):changed[phase]['Config']['ExposedPorts']={'8090/tcp':{}}
            changed['running']['NetworkSettings']['Ports']=ports
            self.assertTrue(self.birth(changed))
            self.assertTrue(p.helper_exited_profile(changed['running'],changed['exited'],changed['cid']))
        changed['running']['NetworkSettings']['Ports']={'8090/tcp':[{'HostIp':'0.0.0.0','HostPort':'8090'}]}
        self.assertFalse(self.birth(changed))

    def test_failed_witness_acquisition_consumes_birth(self):
        class Runtime:pass
        for failure in ('fstat','poll'):
            with self.subTest(failure=failure):
                runtime=Runtime();registry={runtime:object()};records=p.HelperBirths(registry)
                case=self.cases['none'];records.remember(runtime,case['created'],case['networks'])
                process=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.read()'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                try:
                    target=patch.object(p.os,'fstat',side_effect=OSError('synthetic')) if failure=='fstat'else patch.object(process,'poll',side_effect=OSError('synthetic'))
                    with target,self.assertRaises(OSError):records.begin(runtime,process)
                    with self.assertRaisesRegex(ValueError,'bind-once'):records.begin(runtime,process)
                finally:
                    process.stdin.close();process.wait(timeout=5);process.stdout.close();process.stderr.close()

    def test_record_methods_cannot_be_shadowed_on_instance(self):
        records=p.HelperBirths({});guard=p.helper_profile_implementation()
        for name in ('begin','commit','check','close_pending','remember'):
            with self.subTest(name=name),self.assertRaises(AttributeError):setattr(records,name,lambda *a:None)
        guard()

    def test_primary_network_does_not_depend_on_dictionary_order(self):
        case=copy.deepcopy(self.cases['configured']);created=case['created']
        expected=p.helper_network_order(created,case['networks'])
        created['NetworkSettings']['Networks']=dict(reversed(list(created['NetworkSettings']['Networks'].items())))
        self.assertEqual(p.helper_network_order(created,dict(reversed(list(case['networks'].items())))),expected)

    def test_installed_shared_implementation_is_identical(self):
        host=Path(__file__).parent.parent/'standalone_launch_host/comic_reader_backup_primitives.py'
        self.assertEqual(Path(p.__file__).read_bytes(),host.read_bytes())


if __name__=='__main__':unittest.main()
