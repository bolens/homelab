"""Backend choice across native config persistence, request validation and dispatch."""
import ast
import configparser
from io import StringIO
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from patch_tagger_backend import configuration, web, caller, template
import tagger_backend
import tagger_handoff

SOURCE = Path(sys.argv.pop(1))


def method(source, name):
    node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    return node


def function(node, namespace):
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), '<native>', 'exec'), namespace)
    return namespace[node.name]


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.config = SimpleNamespace(TAGGER_BACKEND='legacy')
        self.mylar = SimpleNamespace(CONFIG=self.config, tagger_backend=tagger_backend,
                                     tagger_handoff=tagger_handoff, logger=Mock())
        context=patch.dict(sys.modules, {'mylar':self.mylar})
        context.start();self.addCleanup(context.stop)

    def test_legacy_selected_once_and_argument_contract_preserved(self):
        def legacy(*args, **kwargs):
            self.config.TAGGER_BACKEND='modern'
            return args,kwargs
        self.assertEqual(tagger_backend.dispatch(legacy,'folder',issueid='1',manualmeta=True),
                         (('folder',),{'issueid':'1','manualmeta':True}))
        self.config.TAGGER_BACKEND='legacy'
        with self.assertRaisesRegex(RuntimeError,'fixture'):
            tagger_backend.dispatch(Mock(side_effect=RuntimeError('fixture')))

    def test_unavailable_and_invalid_never_fall_back_or_expose_raw_value(self):
        legacy=Mock()
        for selected in ('modern','secret-invalid',None,[],True):
            self.config.TAGGER_BACKEND=selected
            result=tagger_backend.dispatch(legacy,filename='source.cbz')
            self.assertEqual(result,'fail');self.assertEqual(result.state,'unsupported')
        legacy.assert_not_called()
        self.assertNotIn('secret-invalid',str(self.mylar.logger.mock_calls))
        for value in ('modern', 'unknown', None, ['legacy']):
            with self.assertRaises(ValueError):tagger_backend.validate_update(value)
        self.assertEqual(tagger_backend.validate_update('legacy'),'legacy')

    def test_native_configuration_roundtrip_and_prevalidation(self):
        source=configuration((SOURCE/'config.py').read_text())
        tree=ast.parse(source)
        assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_CONFIG_DEFINITIONS' for t in n.targets))
        # Execute only the actual backend definition and actual native methods.
        definitions=assignment.value.args[0]
        definition=next((k,v) for k,v in zip(definitions.keys,definitions.values) if isinstance(k,ast.Constant) and k.value=='TAGGER_BACKEND')
        defs={'TAGGER_BACKEND':eval(compile(ast.Expression(definition[1]),'<definition>','eval')),
              'OTHER':(str,'General','unchanged')}
        parser=configparser.ConfigParser()
        namespace={'_CONFIG_DEFINITIONS':defs,'config':parser,'configparser':configparser}
        define=function(method(source,'_define'),namespace)
        process=function(method(source,'process_kwargs'),namespace)
        target=SimpleNamespace(MINIMAL_INI=False,ENCRYPT_PASSWORDS=False,OTHER='unchanged')
        target._define=lambda key:define(target,key)
        self.assertEqual(defs['TAGGER_BACKEND'],(str,'Metatagging','legacy'))
        process(target,{'tagger_backend':'legacy'})
        output=StringIO();parser.write(output)
        restored=configparser.ConfigParser();restored.read_string(output.getvalue())
        self.assertEqual(restored.get('Metatagging','tagger_backend'),'legacy')
        for values in ({'other':'changed','TAGGER_BACKEND':'bad'}, {'other':'changed','tagger_backend':'modern'},
                       {'other':'changed','tagger_backend':'legacy','TAGGER_BACKEND':'legacy'}):
            with self.assertRaises(ValueError):process(target,values)
            self.assertEqual(target.OTHER,'unchanged')
        process(target,{'other':'changed'})
        self.assertEqual(target.TAGGER_BACKEND,'legacy')

    def test_native_web_rejects_before_any_configuration_mutation(self):
        source=web((SOURCE/'webserve.py').read_text())
        class HTTPError(Exception):pass
        update=function(method(source,'configUpdate'),{'mylar':self.mylar,'cherrypy':SimpleNamespace(HTTPError=HTTPError)})
        for values in ({'tagger_backend':'invalid'},{'TAGGER_BACKEND':'modern'},
                       {'tagger_backend':'legacy','TAGGER_BACKEND':'legacy'}):
            with self.assertRaises(HTTPError) as caught:update(None,**values)
            self.assertEqual(caught.exception.args[0],400)
        self.assertFalse(hasattr(self.config,'EXTRA_NEWZNABS'))

    def test_native_wrapper_preserves_signature_and_single_observation(self):
        source=caller((SOURCE/'cmtagmylar.py').read_text())
        legacy=Mock(return_value='temporary.cbz')
        run=function(method(source,'run'),{'_legacy_run':legacy})
        self.assertEqual(run('folder',filename='file.cbz',readingorder=[('Arc',1)]),'temporary.cbz')
        self.assertEqual(legacy.call_args.kwargs['readingorder'],[('Arc',1)])
        self.assertEqual(legacy.call_args.kwargs['manualmeta'],False)
        tree=ast.parse(source)
        self.assertEqual(sum(bool(n.decorator_list) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('run','_legacy_run')),1)

    def test_native_template_renders_availability_and_escapes_help(self):
        from mako.template import Template
        source=template((SOURCE.parent/'data/interfaces/default/config.html').read_text())
        block=source.split('<!-- homelab-tagger-backend-v1 -->',1)[1].split('<div class="row checkbox',1)[0]
        for selected in ('legacy','modern'):
            html=Template(block).render(config={'tagger_backend':selected,'tagger_backend_status':dict(tagger_backend.status(),message='<unsafe>')})
            self.assertIn('&lt;unsafe&gt;',html)
            self.assertIn('aria-describedby="tagger_backend_help"',html)
            modern=html.split('<option value="modern"',1)[1].split('</option>',1)[0]
            self.assertIn('disabled="disabled"',modern)
            self.assertEqual('selected="selected"' in modern,selected=='modern')

    def test_patches_are_idempotent(self):
        for name,patcher in [('config.py',configuration),('webserve.py',web),('cmtagmylar.py',caller)]:
            value=patcher((SOURCE/name).read_text());self.assertEqual(patcher(value),value)
        path=SOURCE.parent/'data/interfaces/default/config.html'
        value=template(path.read_text());self.assertEqual(template(value),value)


if __name__ == '__main__':unittest.main()
