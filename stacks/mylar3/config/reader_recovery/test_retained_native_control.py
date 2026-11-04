"""Actual private config reads with explicit actor/HTTP doubles; no service calls."""
import ast
import hashlib
from pathlib import Path
import sys
import tempfile
import time
import unittest
import urllib.parse
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_retained_native_control as control


class Loopback(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'config.ini'
        self.path.write_text('[API]\napi_enabled=True\napi_key='+('x'*32)+'\n[Interface]\nhttp_port=8090\nhttp_root=/mylar/\nenable_https=False\n')
        self.path.chmod(0o640)
        reference=dict(path=str(self.path),signature9=list(control.nine(self.path.lstat())),
            sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.session=dict(version=1,kind='retained-native-session-v1',action='observe',nonce='a'*64,request={},proof=None)
        self.packet=dict(version=1,kind='root-retained-native-control-v1',nonce='a'*64,
            config_ref=reference,session=self.session,deadline=time.monotonic()+30)
        self.answer=dict(success=True,data=dict(version=1,kind='retained-native-session-observation',
            nonce='a'*64,state='active-original-process',**{key:False for key in control.RIGHTS}))
        self.requests=[];self.handlers=[]
        owner=self
        class Response:
            status=200
            def __enter__(inner):return inner
            def __exit__(inner,*args):pass
            def read(inner,maximum):return control.compact(owner.answer)[:maximum]
        class Opener:
            def open(inner,request,timeout):owner.requests.append(request);return Response()
        def build(*handlers):self.handlers.extend(handlers);return Opener()
        for name,value in (('geteuid',1000),('getegid',1000)):
            context=patch.object(control.os,name,return_value=value);context.start();self.addCleanup(context.stop)
        context=patch.object(control.urllib.request,'build_opener',build);context.start();self.addCleanup(context.stop)
    def test_sections_match_the_pinned_native_config_definitions(self):
        source=Path(__file__).parent.parent/'test_fixtures/cache_admission/config.py.txt'
        definition=next(n.value for n in ast.parse(source.read_text()).body
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_CONFIG_DEFINITIONS' for t in n.targets))
        self.assertIsInstance(definition,ast.Call);self.assertEqual(definition.func.id,'OrderedDict')
        rows=definition.args[0];self.assertIsInstance(rows,ast.Dict)
        sections={key.value.lower():value.elts[1].value for key,value in zip(rows.keys,rows.values)
                  if key.value.lower() in control.CONFIG_SECTIONS}
        self.assertEqual(sections,control.CONFIG_SECTIONS)

    def test_key_stays_in_fixed_loopback_POST_and_proxy_is_disabled(self):
        result=control.decode(control.invoke(self.packet));self.assertEqual(result['response'],self.answer)
        self.assertEqual(len(self.requests),1);request=self.requests[0]
        self.assertEqual(request.full_url,'http://127.0.0.1:8090/mylar/api');self.assertEqual(request.get_method(),'POST')
        form=urllib.parse.parse_qs(request.data.decode())
        self.assertEqual(form['cmd'],['retainedDeliverySession']);self.assertEqual(form['apikey'],['x'*32])
        self.assertNotIn('x'*32,control.compact(result).decode())
        self.assertTrue(any(isinstance(h,control.urllib.request.ProxyHandler) and h.proxies=={} for h in self.handlers))
    def test_changed_original_config_after_HTTP_refuses(self):
        build=control.urllib.request.build_opener
        def changed(*handlers):
            self.path.chmod(0o600);return build(*handlers)
        with patch.object(control.urllib.request,'build_opener',changed),self.assertRaisesRegex(ValueError,'final-originals'):
            control.invoke(self.packet)
    def test_foreign_response_grant_or_field_refuses(self):
        self.answer['data']['mutation_authority']=True
        with self.assertRaisesRegex(ValueError,'response-schema'):control.invoke(self.packet)
        self.answer['data']['mutation_authority']=False;self.answer['data']['foreign']='unadmitted'
        with self.assertRaisesRegex(ValueError,'response-schema'):control.invoke(self.packet)
    def test_private_parser_line_is_sanitized(self):
        self.path.write_text('api_key_private_line_'+('x'*32)+'\n')
        self.packet['config_ref'].update(signature9=list(control.nine(self.path.lstat())),
            sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError,'native-control-config-held') as caught:control.invoke(self.packet)
        self.assertNotIn('x'*32,str(caught.exception));self.assertEqual(self.requests,[])
    def test_output_serialization_precedes_final_original_closure(self):
        compact=control.compact
        def changed(value):
            encoded=compact(value)
            if type(value) is dict and value.get('kind')=='root-retained-native-control-result-v1':self.path.chmod(0o600)
            return encoded
        with patch.object(control,'compact',changed),self.assertRaisesRegex(ValueError,'final-originals'):
            control.invoke(self.packet)
    def test_config_drift_after_body_suppresses_output_delimiter(self):
        chunks=[]
        def write(data):
            chunks.append(bytes(data));self.path.chmod(0o600);return len(data)
        with self.assertRaisesRegex(ValueError,'final-originals'):control.invoke(self.packet,publish=write)
        self.assertEqual(len(chunks),1);self.assertNotIn(b'\n',chunks[0])

    def test_wrong_actor_refuses_before_config_or_HTTP(self):
        with patch.object(control.os,'geteuid',return_value=0),self.assertRaisesRegex(ValueError,'owner-actor'):
            control.invoke(self.packet)
        self.assertEqual(self.requests,[])
    def test_original_expired_deadline_refuses_before_HTTP(self):
        self.packet['deadline']=time.monotonic()-1
        with self.assertRaisesRegex(ValueError,'original-deadline'):control.invoke(self.packet)
        self.assertEqual(self.requests,[])
    def test_redirects_are_not_followed(self):
        self.assertIsNone(control.NoRedirect().redirect_request(None,None,None,None,None,None))


if __name__=='__main__':unittest.main()
