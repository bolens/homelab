"""Finite installer, original Config values, durable unresolved capture controls."""
import ast
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import cache_admission
import patch_cache_admission as installer
import patch_ddl_status_retention as status
from workflow_store import Store

HERE=Path(__file__).parent
FIXTURE=HERE/'test_fixtures/cache_admission'
INSTALLED=Path(sys.argv.pop(1)) if __name__=='__main__' and len(sys.argv)>1 and not sys.argv[1].startswith('-') else None


class Installation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if INSTALLED is not None:
            for name in ('config.py','getcomics.py','downloaders/mega.py','downloaders/mediafire.py','downloaders/pixeldrain.py','queues/ddl.py'):
                if installer.MARKER not in (INSTALLED/name).read_text():
                    raise AssertionError('Cache allocation guard is not installed: '+name)
            if installer.MARKER not in (INSTALLED.parent/'lib/mega/mega.py').read_text():
                raise AssertionError('Mega plaintext allocation guard is not installed')
            for name in ('cache_admission.py','cache_reservation.py','verified_transfer.py','pack_intake.py','queue_control.py'):
                if (INSTALLED/name).read_bytes() != (HERE/name).read_bytes():
                    raise AssertionError('Installed cache source differs: '+name)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'mylar';self.root.mkdir();(self.root/'queues').mkdir();(self.root/'downloaders').mkdir();(self.root.parent/'lib/mega').mkdir(parents=True)
        for name in ('config.py','getcomics.py','mega.py','mediafire.py','pixeldrain.py'):
            target = self.root/name if name in ('config.py','getcomics.py') else self.root/'downloaders'/name
            shutil.copyfile(FIXTURE/(name+'.txt'),target)
        (self.root/'queues/ddl.py').write_text(status.patched_source((HERE/'test_fixtures/ddl_status_retention/ddl.py').read_text()))
        shutil.copyfile(FIXTURE/'mega_library.py.txt',self.root.parent/'lib/mega/mega.py')

    def test_real_original_sources_install_idempotently_and_preserve_status_guards(self):
        installer.main(self.root);original={str(p.relative_to(self.root.parent)):p.read_bytes() for p in self.root.parent.rglob('*.py')}
        installer.main(self.root);self.assertEqual(original,{str(p.relative_to(self.root.parent)):p.read_bytes() for p in self.root.parent.rglob('*.py')})
        status.patched_source((self.root/'queues/ddl.py').read_text())
        self.assertIn("'DDL_CACHE_MAX_GIB': (int, 'DDL', 20)",(self.root/'config.py').read_text())
        self.assertIn("'DDL_CACHE_MIN_FREE_GIB': (int, 'DDL', 5)",(self.root/'config.py').read_text())
        for name in ('cache_admission.py','cache_reservation.py','verified_transfer.py','pack_intake.py','queue_control.py'):
            self.assertEqual((self.root/name).read_bytes(),(HERE/name).read_bytes())

    def test_actual_verifier_copies_owning_library_before_temporary_replay(self):
        tree = ast.parse((HERE / 'verify_image.py').read_text())
        stage = next(n for n in tree.body if isinstance(n, ast.With)
                     and any(isinstance(i.context_expr, ast.Call)
                             and ast.unparse(i.context_expr.func) == 'tempfile.TemporaryDirectory'
                             for i in n.items))
        index = next(i for i, n in enumerate(stage.body) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'library' for t in n.targets))
        install = next(i for i, n in enumerate(stage.body)
                       if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                       and ast.unparse(n.value.func) == 'subprocess.run')
        self.assertLess(index + 2, install)
        original = FIXTURE / 'mega_library.py.txt'
        class PublicLibraryProjection(ast.NodeTransformer):
            def visit_Constant(self, node):
                if node.value == '/app/mylar3/lib/mega/mega.py':
                    return ast.copy_location(ast.Constant(str(original)), node)
                return node
        copied = ast.Module(body=stage.body[index:index + 3], type_ignores=[])
        copied = ast.fix_missing_locations(PublicLibraryProjection().visit(copied))
        (self.root.parent / 'lib/mega/mega.py').unlink()
        (self.root.parent / 'lib/mega').rmdir()
        exec(compile(copied, '<actual-verifier-library-copy>', 'exec'),
             dict(Path=Path, shutil=shutil, directory=str(self.root.parent)))
        self.assertEqual((self.root.parent / 'lib/mega/mega.py').read_bytes(), original.read_bytes())
        installer.main(self.root)
        self.assertIn(installer.MARKER, (self.root.parent / 'lib/mega/mega.py').read_text())

    def test_actual_verifier_preserves_self_contained_cache_suite_arguments(self):
        tree = ast.parse((HERE / 'verify_image.py').read_text())
        loop = next(n for n in ast.walk(tree) if isinstance(n, ast.For)
                    and isinstance(n.iter, ast.Tuple)
                    and any(isinstance(v, ast.Constant) and v.value == 'test_cache_admission.py'
                            for v in n.iter.elts))
        calls = []
        runner = SimpleNamespace(run=lambda argv, **options: calls.append((argv, options)))
        exec(compile(ast.Module(body=[loop], type_ignores=[]), '<actual-verifier-suite-routing>', 'exec'),
             dict(sys=sys, FIXES=HERE, source=self.root, subprocess=runner))
        independent = {'test_cache_admission.py', 'test_cache_policy.py', 'test_cache_transfer.py',
                       'test_cache_providers.py', 'test_cache_ddl.py'}
        self.assertTrue(independent <= {Path(argv[1]).name for argv, _ in calls})
        for argv, options in calls:
            self.assertEqual(argv[0], sys.executable)
            self.assertEqual(options, dict(check=True))
            self.assertEqual(argv[2:], [] if Path(argv[1]).name in independent else [str(self.root)])

    def test_unsupported_provider_preimage_fails_before_any_target_write(self):
        (self.root/'downloaders/mediafire.py').write_text('def changed(): pass\n')
        before={str(p):p.read_bytes() for p in self.root.parent.rglob('*.py')}
        with self.assertRaises((ValueError,StopIteration)):installer.main(self.root)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.parent.rglob('*.py')})

    def test_actual_Config_rejects_unsafe_preferences_before_processing(self):
        source=installer.configuration((FIXTURE/'config.py.txt').read_text());tree=ast.parse(source)
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='process_kwargs')
        # Compile the actual validation prefix only; the unrelated Settings UI
        # processing below has its own upstream dependencies and is not mocked safe.
        idx=next(i for i,n in enumerate(node.body) if isinstance(n,ast.For) and ast.unparse(n.target)=='(name, value)')
        prefix=ast.FunctionDef(name='preflight',args=node.args,body=[n for n in node.body[:idx] if (isinstance(n,ast.ImportFrom) and any(x.name=='cache_admission' for x in n.names)) or (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id=='cache_admission')],decorator_list=[])
        ns={};exec(compile(ast.fix_missing_locations(ast.Module(body=[prefix],type_ignores=[])),'<original-config>','exec'),ns)
        app=SimpleNamespace(cache_admission=cache_admission)
        with patch.dict(sys.modules,{'mylar':app}):
            ns['preflight'](None,{'ddl_cache_max_gib':'20','ddl_cache_min_free_gib':'5'})
            for value in (True,0,-1,4097,'unlimited','1.5'):
                with self.subTest(value=value),self.assertRaises(ValueError):ns['preflight'](None,{'ddl_cache_max_gib':value})

    def test_unresolved_durable_capture_prevents_same_DDL_redownload_without_merging_paths(self):
        state=Store(Path(self.temp.name));app=SimpleNamespace(workflow=SimpleNamespace(store=lambda:state))
        module=SimpleNamespace(ddl_identifier=lambda value:str(value),identifier=lambda v:v,label=lambda v:v)
        with patch.dict(sys.modules,{'mylar':app,'mylar.workflow_store':module}):
            spec=importlib.util.spec_from_file_location('cache_pack_fixture',HERE/'pack_intake.py');packs=importlib.util.module_from_spec(spec);spec.loader.exec_module(packs)
            self.assertFalse(packs.unresolved_capture('1'))
            state.set('pack','a'*64,dict(id='a'*64,ddl_id='1',source='/first/original.zip',name='Fixture',phase='discovered',members=[],inventory_complete=False))
            before=state.get('pack','a'*64);self.assertTrue(packs.unresolved_capture('1'));self.assertFalse(packs.unresolved_capture('2'));self.assertEqual(state.get('pack','a'*64),before)
            state.set('pack','b'*64,dict(id='b'*64,ddl_id='1',source='/second/original.zip',name='Other physical source',phase='confirmed',inventory_complete=True,cleanup_complete=True,members=[dict(kind='sidecar',sha256='invalid',sidecar='')]))
            reloaded=Store(Path(self.temp.name));app.workflow.store=lambda:reloaded
            self.assertTrue(packs.unresolved_capture('1'));self.assertEqual(len(reloaded.active('pack',{'discovered','confirmed'})),2)

if __name__=='__main__':unittest.main()
