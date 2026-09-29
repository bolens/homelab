"""Real local HTTP/TLS fixtures for discovery; no production providers or data."""
import ast
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import select
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import requests
import ddl_transport as transport
from patch_ddl_transport import caller, configuration, template, web

COUNTS = Counter()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_GET(self):
        COUNTS[self.path] += 1
        if self.path == '/reset':
            self.connection.shutdown(socket.SHUT_RDWR); self.connection.close(); return
        if self.path == '/slow': time.sleep(1)
        status = int(self.path[1:]) if self.path in ('/429', '/503') else 200
        if self.path == '/cross-origin':
            self.send_response(302)
            self.send_header('Location', 'http://localhost:' + str(self.server.server_port) + '/identity')
            self.end_headers(); return
        if self.path in ('/redirect', '/loop'):
            self.send_response(302)
            self.send_header('Location', '/cookies' if self.path == '/redirect' else '/loop')
            self.send_header('Set-Cookie', 'scoped=fixture; Path=/cookies; HttpOnly')
            self.end_headers(); return
        body = (self.headers.get('Cookie', '') if self.path == '/cookies' else self.path).encode()
        if self.path == '/identity': body = (self.headers.get('Authorization', '') + self.headers.get('Cookie', '')).encode()
        if self.path == '/large': body = b'x' * (transport.MAX_BODY + 1)
        self.send_response(status)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        if self.path == '/delete': self.send_header('Set-Cookie', 'initial=; Max-Age=0; Path=/')
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError): pass

    def do_CONNECT(self):
        host, port = self.path.rsplit(':', 1)
        if host != '127.0.0.1':
            self.send_error(403); return
        COUNTS['CONNECT'] += 1
        with socket.create_connection((host, int(port)), timeout=3) as upstream:
            self.send_response(200); self.end_headers()
            for _ in range(100):
                ready, _, _ = select.select([self.connection, upstream], [], [], 3)
                if not ready: break
                for source in ready:
                    data = source.recv(65536)
                    if not data: return
                    (upstream if source is self.connection else self.connection).sendall(data)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        COUNTS[self.path] += 1
        self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers()
        self.wfile.write(body)


class TransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def test_both_backends_redirect_cookie_post_status_and_no_retry(self):
        self.assertTrue(transport.status()['curl_available'], 'Final-image curl runtime required')
        for backend in transport.CHOICES:
            with self.subTest(backend=backend), transport.session(backend) as session:
                response = session.get(self.url+'/redirect')
                self.assertEqual(response.url, self.url+'/cookies')
                self.assertIn('scoped=fixture', response.text)
                self.assertNotIn('scoped=fixture', session.get(self.url+'/other').text)
                session.cookies.set('initial', 'fixture', domain='127.0.0.1', path='/')
                session.get(self.url+'/delete')
                self.assertNotIn('initial=fixture', session.get(self.url+'/cookies').text)
                self.assertEqual(session.post(self.url+'/post', json={'fixture':True}).json(), {'fixture':True})
                for status in (429,503):
                    path='/'+str(status); before=COUNTS[path]
                    self.assertEqual(session.get(self.url+path).status_code,status)
                    self.assertEqual(COUNTS[path]-before,1)
                response=session.get(self.url+'/stream',stream=True)
                self.assertEqual(b''.join(response.iter_content(2)), b'/stream')

    def test_cross_origin_redirect_does_not_leak_auth_or_scoped_cookie(self):
        for backend in transport.CHOICES:
            with self.subTest(backend=backend), transport.session(backend) as session:
                session.trust_env = False
                session.cookies.set('private', 'fixture', domain='127.0.0.1', path='/')
                self.assertEqual(session.get(self.url + '/cross-origin', auth=('fixture', 'secret')).text, '')

    def test_malformed_worker_results_are_normalized(self):
        for payload in ({}, [], {'state':'secret'}, {'state':'ok', 'body':'!'}):
            result = SimpleNamespace(returncode=0, stdout=json.dumps(payload).encode())
            with transport.session('curl') as session, patch.object(transport.subprocess, 'run', return_value=result):
                with self.assertRaises(requests.ConnectionError) as caught:
                    session.get(self.url + '/secret')
                self.assertNotIn('secret', str(caught.exception))

    def test_normalized_timeout_reset_and_redirect_failures(self):
        for backend in transport.CHOICES:
            with self.subTest(backend=backend), transport.session(backend) as session:
                for path,error in [('/slow',requests.Timeout),('/reset',requests.ConnectionError),('/loop',requests.TooManyRedirects)]:
                    before=time.monotonic()
                    with self.assertRaises(error): session.get(self.url+path,timeout=(.2,.2))
                    self.assertLess(time.monotonic()-before,6)

    def test_curl_body_and_parent_deadline_are_bounded_and_redacted(self):
        with transport.session('curl') as session:
            with self.assertRaises(requests.RequestException) as caught: session.get(self.url+'/large')
            self.assertNotIn(self.url,str(caught.exception))
            with patch.object(transport.subprocess,'run',side_effect=subprocess.TimeoutExpired(['private-token'],1)):
                with self.assertRaises(requests.Timeout) as caught: session.get(self.url+'/private-token')
            self.assertNotIn('private-token',str(caught.exception))
            with patch.object(transport.subprocess,'run',side_effect=FileNotFoundError('private-token')):
                with self.assertRaises(requests.ConnectionError) as caught: session.get(self.url+'/private-token')
            self.assertNotIn('private-token',str(caught.exception))

    def test_explicit_http_proxy_and_tls_verification(self):
        # The local HTTP fixture doubles as an HTTP proxy: absolute target proves routing.
        for backend in transport.CHOICES:
            with transport.session(backend) as session:
                session.trust_env=False
                response=session.get('http://fixture.invalid/proxy',proxies={'http':self.url})
                self.assertEqual(response.text,'http://fixture.invalid/proxy')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); key=root/'key.pem'; cert=root/'cert.pem'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1',
                '-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
            server.socket=context.wrap_socket(server.socket,server_side=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                url='https://127.0.0.1:'+str(server.server_port)+'/tls'
                for backend in transport.CHOICES:
                    with transport.session(backend) as session:
                        session.trust_env=False
                        with self.assertRaises(requests.exceptions.SSLError):session.get(url)
                        self.assertEqual(session.get(url,verify=str(cert)).text,'/tls')
                        before = COUNTS['CONNECT']
                        self.assertEqual(session.get(url,verify=str(cert),proxies={'https':self.url}).text,'/tls')
                        self.assertEqual(COUNTS['CONNECT'], before + 1)
            finally:server.shutdown();server.server_close();thread.join()

    def test_next_operation_switch_nested_ownership_and_missing_runtime(self):
        config=SimpleNamespace(DDL_DISCOVERY_BACKEND='requests')
        obj=SimpleNamespace(session=requests.Session())
        seen=[]
        @transport.discovery
        def nested(self):seen.append(type(self._discovery_session))
        @transport.discovery
        def operation(self):
            seen.append(type(self._discovery_session));config.DDL_DISCOVERY_BACKEND='curl';nested(self)
        with patch.dict(sys.modules,{'mylar':SimpleNamespace(CONFIG=config)}):
            operation(obj);nested(obj)
        self.assertEqual(seen,[transport.DiscoveryRequests,transport.DiscoveryRequests,transport.CurlSession])
        obj.session.close()
        with patch.object(transport,'PYTHON',Path('/missing')):
            self.assertIsInstance(transport.session('requests'),requests.Session)
            with self.assertRaises(ValueError):transport.validate_update('curl')
        for value in ('invalid','Curl','curl-stream',None,[]):
            with self.assertRaises(ValueError):transport.validate_update(value)

    def test_native_settings_roundtrip_validation_and_availability(self):
        import configparser
        from io import StringIO
        from mako.template import Template
        import tagger_backend
        def method(source, name):
            node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name==name)
            node.decorator_list=[]
            return node
        def function(node, namespace):
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'<native>', 'exec'),namespace)
            return namespace[node.name]
        source = Path(os.environ['MYLAR_WORKFLOW_SOURCE'])
        text = configuration((source/'config.py').read_text())
        parser = configparser.ConfigParser()
        definitions = {'DDL_DISCOVERY_BACKEND':(str,'DDL','requests'), 'OTHER':(str,'General','unchanged')}
        namespace = {'_CONFIG_DEFINITIONS':definitions,'config':parser,'configparser':configparser}
        define = function(method(text,'_define'),namespace)
        process = function(method(text,'process_kwargs'),namespace)
        target = SimpleNamespace(MINIMAL_INI=False,ENCRYPT_PASSWORDS=False,OTHER='unchanged')
        target._define = lambda key:define(target,key)
        mylar = SimpleNamespace(CONFIG=target,ddl_transport=transport,tagger_backend=tagger_backend)
        with patch.dict(sys.modules,{'mylar':mylar}):
            for selected in ('requests','curl','requests'):
                process(target,{'ddl_discovery_backend':selected})
                output=StringIO();parser.write(output)
                restored=configparser.ConfigParser();restored.read_string(output.getvalue())
                self.assertEqual(restored.get('DDL','ddl_discovery_backend'),selected)
            class HTTPError(Exception):pass
            update=function(method(web((source/'webserve.py').read_text()),'configUpdate'),
                {'mylar':mylar,'cherrypy':SimpleNamespace(HTTPError=HTTPError)})
            for values in ({'ddl_discovery_backend':'bad'},
                           {'ddl_discovery_backend':'requests','DDL_DISCOVERY_BACKEND':'curl'}):
                with self.assertRaises(HTTPError) as caught:update(None,**values)
                self.assertEqual(caught.exception.args[0],400)
                with self.assertRaises(ValueError):process(target,dict(values,other='changed'))
                self.assertEqual(target.OTHER,'unchanged')
        text=template((source.parent/'data/interfaces/default/config.html').read_text())
        block=text.split('<!-- homelab-ddl-transport-v1 -->',1)[1].split('<div class="row checkbox',1)[0]
        for available in (True,False):
            rendered=Template(block).render(config={'ddl_discovery_backend':'curl',
                'ddl_transport_status':{'curl_available':available,'message':'<unsafe>'}})
            self.assertIn('&lt;unsafe&gt;',rendered)
            self.assertEqual('disabled="disabled"' in rendered,not available)

    def test_source_patches_preserve_archive_owner_and_are_idempotent(self):
        source=Path(os.environ['MYLAR_WORKFLOW_SOURCE'])
        for name,patcher in [('config.py',configuration),('webserve.py',web),('getcomics.py',caller)]:
            text=patcher((source/name).read_text());self.assertEqual(text,patcher(text));ast.parse(text)
        tree=ast.parse((source/'getcomics.py').read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='downloadit')
        text=ast.unparse(method)
        self.assertIn('self.session.get',text);self.assertNotIn('_discovery_session',text)
        constructor=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='__init__')
        self.assertIn('self.session = requests.Session()',ast.unparse(constructor))
        path=source.parent/'data/interfaces/default/config.html'
        value=template(path.read_text());self.assertEqual(template(value),value)


if __name__=='__main__':unittest.main()
