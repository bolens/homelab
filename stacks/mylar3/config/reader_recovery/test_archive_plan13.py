"""Exact prospective schemas and missing-prerequisite refusal, no fake admission."""
import ast
import copy
import hashlib
import os
import threading
import time
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).parent))
import comic_archive_repair_action as action
import comic_reader_lifecycle_parent as parent
import comic_child_control_projection as controls
import comic_nfs_child_input_projection as projection


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


class EntrypointTests(unittest.TestCase):
    def test_configured_original_inputs_reach_constructor_unchanged_before_execute(self):
        plan=object();source=object();engine=object();configured=object();nfs=object();intents=object();calls=[]
        class OwningConstructorBoundary:
            def __init__(self,*args,**kwargs):calls.append(('constructor',args,kwargs))
            def execute(self):calls.append(('execute',));return 'original-result'
        with patch.object(parent,'LifecycleParent',OwningConstructorBoundary):
            self.assertEqual(parent.run_operation(plan,source,engine=engine,configured=configured,nfs_sources=nfs,nfs_intents=intents),'original-result')
        self.assertEqual(calls,[('constructor',(plan,source,engine),dict(configured=configured,nfs_sources=nfs,nfs_intents=intents)),('execute',)])
    def test_legacy_entry_keeps_original_constructor_call(self):
        plan=object();source=object();engine=object()
        with patch.object(parent,'LifecycleParent') as boundary:
            parent.run_operation(plan,source,engine=engine)
        boundary.assert_called_once_with(plan,source,engine);boundary.return_value.execute.assert_called_once_with()
    def test_constructor_refusal_never_executes(self):
        with patch.object(parent,'LifecycleParent',side_effect=parent.Held('original-admission-refused')) as boundary:
            with self.assertRaisesRegex(parent.Held,'original-admission-refused'):parent.run_operation({}, {},engine=object(),configured={})
        self.assertEqual(boundary.call_args.kwargs,dict(configured={},nfs_sources=None,nfs_intents=None))


class ProjectionTests(unittest.TestCase):
    """Real Paths/Tree/files; explicit source-mode Parent state, no factory grant."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.op=self.root/'operation';self.op.mkdir(mode=0o700)
        self.data=self.root/'native';self.data.mkdir(mode=0o700)
        self.geometry=self.root/'G';self.geometry.mkdir(mode=0o700)
        self.library=self.geometry/'L';self.library.mkdir(mode=0o700)
        self.retention=self.geometry/'R';self.retention.mkdir(mode=0o700)
        self.scope=self.root/'scope.json';self.scope.write_bytes(parent.encode(dict(forbidden_roots=[str(self.data),str(self.library)])));self.scope.chmod(0o600)
        self.ref=dict(path=str(self.scope),sha256=hashlib.sha256(self.scope.read_bytes()).hexdigest(),signature9=parent.nine(self.scope.stat()))
        self.owner=object.__new__(parent.LifecycleParent);owner=self.owner
        owner.plan=dict(version=13,kind='reviewed-archive-one-lifecycle-protocol',operation=str(self.op));owner.op=self.op
        owner.mapping=parent.Paths([dict(host=str(self.data),child='/config',write=True),dict(host=str(self.geometry),child=str(self.geometry),write=True),dict(host=str(self.op),child='/_operation',write=True)])
        owner.mapping.owner=owner;owner.files={self.ref['path']:tuple(self.ref['signature9'])};owner.nodes={};owner.generated={};owner.source_ref=self.ref;owner.plan_ref=self.ref;owner.engine=object();owner.thread=threading.get_ident();owner.deadline=time.monotonic()+60
        self.tree=controls.Tree(self.root/'child','/_operation',self.op,parent.read,uid=os.geteuid(),gid=os.getegid())
        active=dict(active_scope={k:self.ref[k] for k in ('path','sha256')},parent_admission=dict(path=str(self.retention/'canary')),operation_output=str(self.root/'original-output'))
        parent._CHILD_TREES[owner]=self.tree
        for registry in (parent._CONFIGURED_OVERLAYS,parent._CONFIGURED_OVERLAY_SEALS,parent._CONFIGURED_IMAGE_LABELS,parent._CONFIGURED_IMAGE_SEALS):registry[owner]=()
        parent._NFS_DATA_ROOTS[owner]=(str(self.data),str(self.library),str(self.retention))
        parent._NFS_SOURCE_CONTEXTS[owner]=({}, {},parent.encode(active),parent.encode({}),active['operation_output'])
        parent._NFS_EFFECTIVE_ABSENCES[owner]=parent.encode([])
        parent._NFS_SOURCE_SEALS[owner]=parent.encode(dict(refs={},raw_sha={},active=active,probe={},output=active['operation_output'],effective_absences=[]))
        self.reseal()
        for registry in (parent._CORES,parent._GENERATED,parent._CHILD_TREES,parent._CONFIGURED_OVERLAYS,parent._CONFIGURED_OVERLAY_SEALS,parent._CONFIGURED_IMAGE_LABELS,parent._CONFIGURED_IMAGE_SEALS,parent._NFS_DATA_ROOTS,parent._NFS_SOURCE_CONTEXTS,parent._NFS_EFFECTIVE_ABSENCES,parent._NFS_SOURCE_SEALS):self.addCleanup(registry.pop,owner,None)
    def reseal(self):
        owner=self.owner;owner.core=parent.encode(dict(plan=owner.plan,files=owner.files,nodes=owner.nodes,source=owner.source_ref,input=owner.plan_ref,engine=id(owner.engine),thread=owner.thread,deadline=owner.deadline));parent._CORES[owner]=owner.core;parent._GENERATED[owner]=parent.encode(owner.generated)
    def test_v13_nfs_projection_then_native_phase_mapping_remain_distinct(self):
        mapping=self.owner.mapping;projector=projection.Inputs(self.owner);calls=[]
        nfs=mapping.nfs_child;ordinary=mapping.child
        with patch.object(mapping,'nfs_child',side_effect=lambda value:(calls.append('nfs'),nfs(value))[1]),patch.object(mapping,'child',side_effect=lambda value:(calls.append('native'),ordinary(value))[1]):
            self.assertEqual(projector.child(str(self.data/'media-writer')),str(self.data/'media-writer'))
            self.assertEqual(mapping.child(str(self.data/'config.ini')),'/config/config.ini')
        self.assertEqual(calls,['nfs','native'])
        self.assertEqual(mapping.host('/config/config.ini'),str(self.data/'config.ini'))
        self.assertEqual(projector.host(str(self.data/'config.ini')),str(self.data/'config.ini'))
        with self.assertRaisesRegex(parent.Held,'unmapped-child'):mapping.host(str(self.data/'config.ini'))
        self.assertEqual(mapping.child(str(self.library/'book.cbz')),str(self.library/'book.cbz'))
    def test_v12_projection_retains_original_canonical_mapping(self):
        self.owner.plan['version']=12;self.reseal();mapping=self.owner.mapping;projector=projection.Inputs(self.owner)
        with patch.object(mapping,'nfs_child',side_effect=AssertionError('v13 view selected')),patch.object(mapping,'nfs_host',side_effect=AssertionError('v13 view selected')):
            self.assertEqual(projector.child(str(self.data/'media-writer')),str(self.data/'media-writer'))
            self.assertEqual(projector.host(str(self.data/'media-writer')),str(self.data/'media-writer'))
            self.assertEqual(mapping.child(str(self.data/'config.ini')),str(self.data/'config.ini'))
    def test_explicit_observer_view_refuses_default_wrong_version_and_unbound_roots(self):
        mapping=self.owner.mapping
        for version in (9,10,11,12,True,'13'):
            self.owner.plan['version']=version;self.reseal()
            with self.subTest(version=version),self.assertRaisesRegex(parent.Held,'plan13-owning-mapping'):mapping.nfs_child(str(self.data))
        self.owner.plan['version']=13;self.reseal();parent._NFS_DATA_ROOTS[self.owner]=(str(self.data),)
        with self.assertRaisesRegex(parent.Held,'original-protected-roots'):mapping.nfs_host(str(self.data))
    def test_original_scope_or_parent_drift_refuses_projection(self):
        self.scope.chmod(0o640)
        with self.assertRaises(parent.Held):self.owner.mapping.nfs_child(str(self.data))
    def test_late_scope_drift_after_last_lifetime_callback_is_not_adopted(self):
        real=self.owner.left;calls=[]
        def changed():
            result=real();calls.append(True)
            if len(calls)==2:self.scope.chmod(0o640)
            return result
        with patch.object(self.owner,'left',side_effect=changed),self.assertRaisesRegex(parent.Held,'file-final'):self.owner.mapping.nfs_child(str(self.data))
        self.assertEqual(len(calls),2)
    def test_v13_output_projection_is_observer_only_and_original_pair_bound(self):
        phase=self.tree.phase('nfs');physical=phase/'active-output';virtual='/_operation/nfs/active-output';original=str(self.root/'original-output')
        parent._NFS_OUTPUT_PAIRS[self.owner]=(original,str(physical),virtual,tuple(parent.five(phase.lstat())))
        self.addCleanup(parent._NFS_OUTPUT_PAIRS.pop,self.owner,None)
        mapping=self.owner.mapping;projector=projection.Inputs(self.owner)
        self.assertEqual(projector.child(original+'/probe'),virtual+'/probe')
        self.assertEqual(projector.host(virtual+'/probe'),str(physical/'probe'))
        with self.assertRaisesRegex(parent.Held,'unmapped-host'):mapping.child(original+'/probe')
        parent._NFS_OUTPUT_PAIRS[self.owner]=(original+'-foreign',str(physical),virtual,tuple(parent.five(phase.lstat())))
        with self.assertRaisesRegex(parent.Held,'original-pair'):projector.child(original+'/probe')

    def test_missing_declared_native_mapping_is_never_filled_by_nfs_root(self):
        self.owner.mapping.mounts=[row for row in self.owner.mapping.mounts if row['host']!=str(self.data)]
        self.assertEqual(self.owner.mapping.nfs_child(str(self.data)),str(self.data))
        with self.assertRaisesRegex(parent.Held,'unmapped-host'):self.owner.mapping.child(str(self.data/'config.ini'))


if __name__=='__main__':unittest.main()
