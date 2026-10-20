"""Exact prospective schemas and missing-prerequisite refusal, no fake admission."""
import ast
import copy
import hashlib
from pathlib import Path
import tempfile
import types
import unittest
import sys
sys.path.insert(0,str(Path(__file__).parent))
import comic_archive_repair_action as action
import comic_reader_lifecycle_parent as parent


class Tests(unittest.TestCase):
    def setUp(self):
        self.owner=dict(table='issues',issueid='123',parentcomicid='456',releasecomicid='456')
        self.args=types.SimpleNamespace(phase='execute',input='/fixture/input.json',input_sha256='a'*64,source_sha256='b'*64)
        self.argv=['/lsiopy/bin/python3','-I','-B',str(Path(action.__file__).absolute()),'--phase','execute','--input',self.args.input,'--input-sha256',self.args.input_sha256,'--source-sha256',self.args.source_sha256]
        command=list(self.argv);command[-3]='<INPUT_SHA256>'
        self.plan=dict(version=3,action='archive-one',command_template=command,operation='/fixture/execute',sdk_map={},nonce='c'*64,parent_sha256='d'*64,selected_image='sha256:'+'e'*64,controls={name:{} for name in action.ROLES},archive_scopes={},owner=self.owner,operation_id='f'*64,terminal_mode='same-child-v1',terminal='forward',publication_protocol='rename-link-v1')

    def test_exact_v3_forward_and_explicit_rollback(self):
        for terminal in ('forward','rollback'):
            value=dict(self.plan,terminal=terminal)
            self.assertEqual(action.validate_plan(value,self.args,self.argv),value)

    def test_missing_unknown_or_legacy_protocol_fields_refuse(self):
        for mutation in ({'version':2},{'publication_protocol':'exchange-fallback'},{'terminal':'retry'}):
            with self.subTest(mutation=mutation),self.assertRaises(action.Held):
                action.validate_plan(dict(self.plan,**mutation),self.args,self.argv)
        value=copy.deepcopy(self.plan);del value['publication_protocol']
        with self.assertRaises(action.Held):action.validate_plan(value,self.args,self.argv)
        old={key:value for key,value in self.plan.items() if key not in ('terminal','publication_protocol')};old['version']=2
        self.assertEqual(action.validate_plan(old,self.args,self.argv),old)

    def test_original_private_request_v2_never_accepts_paths_or_unknown_terminal(self):
        request=dict(version=2,owner=self.owner,operation_id='f'*64,terminal='rollback')
        self.assertEqual(action.owner_request(request),request)
        for mutation in ({'terminal':'retry'},{'path':'/foreign'}):
            with self.subTest(mutation=mutation),self.assertRaises(action.Held):action.owner_request(dict(request,**mutation))

    def test_original_terminal_request_is_admitted_only_by_exact_plan13(self):
        # Execute the actual constructor's finite request predicates in isolation;
        # this is a schema unit control, not a connected Parent factory claim.
        tree=ast.parse(Path(parent.__file__).read_text())
        constructor=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='__init__' and any(isinstance(value,ast.Constant) and value.value=='archive-explicit-terminal-plan13-only' for value in ast.walk(node)))
        predicates=[node for node in ast.walk(constructor) if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and any(isinstance(value,ast.Constant) and value.value in ('archive-owner-request','archive-explicit-terminal-plan13-only') for value in node.value.args)]
        self.assertEqual(len(predicates),2)
        code=compile(ast.Module(body=predicates,type_ignores=[]),parent.__file__,'exec')
        for version in (10,11,12,13):
            request=dict(version=2,owner=self.owner,operation_id='f'*64,terminal='rollback')
            scope=dict(need=parent.need,digest=parent.digest,request=request,plan=dict(version=version))
            with self.subTest(version=version):
                if version==13:exec(code,scope)
                else:
                    with self.assertRaisesRegex(parent.Held,'plan13-only'):exec(code,scope)
            scope['request']=dict(version=1,owner=self.owner,operation_id='f'*64)
            exec(code,scope)

    def test_default_plan13_refuses_before_engine_or_operation_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def ref(path,raw):
                path.write_bytes(raw);path.chmod(0o600)
                return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),signature9=parent.nine(path.stat()))
            source=ref(root/'parent.py',Path(parent.__file__).read_bytes())
            plan={key:{} for key in ('reader','held_native','held_worker','provider','producer','observer','sdk_map','native','producer_inputs','scope_projection','bounds','nfs','backup_provider','worker_observation','publication_geometry')}
            plan.update(version=13,kind='reviewed-archive-one-lifecycle-protocol',nonce='a'*64,seconds=60,operation=str(root/'operation'),selected_image='sha256:'+'b'*64,mounts=[],birth_source_sha256='c'*64,action='archive-one',terminal_mode='same-child-v1')
            original=ref(root/'plan.json',parent.encode(plan))
            class NoEngine:
                def run(self,*args):raise AssertionError('No engine access before genuine prerequisites')
            self.assertFalse(parent.WORKER_OBSERVATION_ENABLED)
            with self.assertRaisesRegex(parent.Held,'worker-observation-default-disabled'):
                parent.LifecycleParent(original,source,NoEngine())
            self.assertFalse((root/'operation').exists())


if __name__=='__main__':unittest.main()
