"""Offline lookup identity, bounded HTTP and private child-process contract."""
import json
import http.server
import threading
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import Mock, patch

import tagger_lookup as lookup
from tagger_runtime import ProcessResult

ISSUE = {'id':123,'issue_number':'1','name':'Étoile','volume':{'id':456},
         'cover_date':'2020-02-29','description':'<p>Story &amp; art</p><script>ignore</script>',
         'person_credits':[{'name':'Creator','role':'writer, penciler'}],
         'character_credits':[{'name':'Hero'}], 'site_detail_url':'https://example.com/issue/123'}
VOLUME = {'id':456,'name':'Fixture Annual','count_of_issues':2,'publisher':{'name':'Publisher'}}


class Response:
    def __init__(self, data, code=200):
        self.data = data if isinstance(data, bytes) else json.dumps({'status_code':1,'results':data}).encode()
        self.status_code = code
        self.closed = False
    def __enter__(self):return self
    def __exit__(self,*args):self.closed=True
    def iter_content(self,chunk_size):
        for i in range(0,len(self.data),chunk_size):yield self.data[i:i+chunk_size]


class LookupTest(unittest.TestCase):
    def setUp(self):
        self.cache = patch.object(lookup, 'VOLUMES', lookup.VolumeCache())
        self.cache.start()
        self.addCleanup(self.cache.stop)

    def fetch(self, responses, **changes):
        settings = dict(issueid='123',volumeid='456',base_url='https://example.com/api',api_key='private-fixture-key')
        settings.update(changes)
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        session.get.side_effect = responses
        with patch.object(lookup.time,'sleep'):
            result = lookup.fetch(settings, session_factory=lambda:session)
        return result,session

    def test_mapping_identity_credits_unicode_and_real_date(self):
        value = lookup.mapping(ISSUE,VOLUME,'123','456')
        self.assertEqual(value['series'],'Fixture Annual')
        self.assertEqual(value['issue'],'1')
        self.assertEqual(value['description'],'Story & art')
        self.assertEqual(value['credits'],[{'person':'Creator','role':'Writer'},{'person':'Creator','role':'Penciller'}])
        self.assertEqual((value['year'],value['month'],value['day']),(2020,2,29))
        self.assertNotIn('volume',value)  # Catalog series ID is not the volume label.

    def test_wrong_issue_or_volume_never_maps(self):
        for issue,volume,expected in [(dict(ISSUE,id=999),VOLUME,'456'),(ISSUE,dict(VOLUME,id=999),'456'),(ISSUE,VOLUME,'999')]:
            with self.assertRaises(ValueError):lookup.mapping(issue,volume,'123',expected)
        result,session=self.fetch([Response(dict(ISSUE,id=999))])
        self.assertEqual(result.state,'failed');self.assertEqual(session.get.call_count,1)

    def test_http_disallows_redirects_and_bounds_responses(self):
        first,second=Response(ISSUE),Response(VOLUME)
        result,session=self.fetch([first,second])
        self.assertEqual(result.state,'ok')
        self.assertTrue(first.closed and second.closed)
        options=session.get.call_args.kwargs
        self.assertEqual(options['timeout'],(5,15));self.assertFalse(options['allow_redirects'])
        self.assertTrue(options['stream']);self.assertTrue(options['verify'])
        self.assertNotIn('private-fixture-key',repr(result))
        for response in [Response({},302),Response({},429),Response(b'x'*(lookup.MAX_RESPONSE+1)),Response(b'['*10000+b']'*10000)]:
            result,_=self.fetch([response]);self.assertEqual(result.state,'failed');self.assertTrue(response.closed)

    def test_missing_dates_optional_fields_and_bad_types(self):
        minimal={'id':123,'issue_number':'½','volume':{'id':456}}
        self.assertEqual(lookup.mapping(minimal,{'id':456,'name':'Fixture'},123),{'series':'Fixture','issue':'½'})
        for changes in ({'cover_date':'2020-02-30'},{'person_credits':[None]},{'character_credits':'bad'},{'issue_number':True}):
            with self.assertRaises((ValueError,TypeError)):lookup.mapping(dict(ISSUE,**changes),VOLUME,'123')

    def test_real_worker_queries_only_requested_issue_and_volume(self):
        paths=[]
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                paths.append(self.path.split('?')[0])
                value=(dict(ISSUE, id=int(self.path.split('4000-')[1].split('/')[0]))
                       if '/issue/' in self.path else VOLUME)
                body=json.dumps({'status_code':1,'results':value}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                result=lookup.lookup(workdir=directory,issueid='123',volumeid='456',api_key='private-fixture-key',
                                     base_url='http://127.0.0.1:'+str(server.server_port)+'/api')
                self.assertEqual(result.state,'ok')
                self.assertEqual(result.metadata['series'],'Fixture Annual')
                result=lookup.lookup(workdir=directory,issueid='124',volumeid='456',api_key='private-fixture-key',
                                     base_url='http://127.0.0.1:'+str(server.server_port)+'/api')
                self.assertEqual(result.state,'ok')
                self.assertEqual(result.metadata, lookup.mapping(dict(ISSUE,id=124),VOLUME,'124','456'))
                self.assertEqual(list(Path(directory).iterdir()),[])
        finally:
            server.shutdown();server.server_close();thread.join(5)
        self.assertEqual(paths,['/api/issue/4000-123/','/api/volume/4050-456/','/api/issue/4000-124/'])

    def test_cache_hit_still_fetches_issue_and_does_not_return_renewable_volume(self):
        with patch.object(lookup.time,'monotonic',return_value=1000):
            result,session=self.fetch([Response(ISSUE)], cached_volume={'volume':VOLUME,'expires':1100})
        self.assertEqual(result.metadata,lookup.mapping(ISSUE,VOLUME,'123','456'))
        self.assertEqual(session.get.call_count,1)
        self.assertEqual(result.volume,{})
        self.assertEqual(result.expires,0)

    def test_expired_malformed_and_wrong_volume_cache_fall_back(self):
        for cached in [{'volume':VOLUME,'expires':1000}, {'volume':VOLUME,'expires':float('nan')},
                       {'volume':dict(VOLUME,id=999),'expires':1100},
                       {'volume':dict(VOLUME,name=None),'expires':1100},
                       {'volume':VOLUME,'expires':1400}, {'expires':1100}]:
            with self.subTest(cached=cached), patch.object(lookup.time,'monotonic',return_value=1000):
                result,session=self.fetch([Response(ISSUE),Response(VOLUME)],cached_volume=cached)
                self.assertEqual(result.state,'ok');self.assertEqual(session.get.call_count,2)
                self.assertEqual(result.volume,VOLUME);self.assertEqual(result.expires,1300)

    def test_wrong_fresh_issue_or_volume_never_uses_cache(self):
        for issue in [dict(ISSUE,id=999),dict(ISSUE,volume={'id':999})]:
            with patch.object(lookup.time,'monotonic',return_value=1000):
                result,session=self.fetch([Response(issue)],cached_volume={'volume':VOLUME,'expires':1100})
            self.assertEqual(result.state,'failed');self.assertEqual(session.get.call_count,1)
            self.assertEqual(result.volume,{})

    def test_expiry_is_checked_after_issue_request_and_every_request_is_paced(self):
        clock=[1000]
        class SlowIssue(Response):
            def iter_content(self,chunk_size):
                clock[0]=1101
                yield from super().iter_content(chunk_size)
        settings=dict(issueid='123',volumeid='456',base_url='https://example.com/api',api_key='fixture',
                      interval=7,cached_volume={'volume':VOLUME,'expires':1100})
        session=Mock();session.__enter__=Mock(return_value=session);session.__exit__=Mock(return_value=False)
        session.get.side_effect=[SlowIssue(ISSUE),Response(VOLUME)]
        with patch.object(lookup.time,'monotonic',side_effect=lambda:clock[0]), patch.object(lookup.time,'sleep') as sleep:
            result=lookup.fetch(settings,session_factory=lambda:session)
        self.assertEqual(result.state,'ok');self.assertEqual(session.get.call_count,2)
        self.assertEqual([c.args for c in sleep.call_args_list],[(7,),(7,)])

    def test_parent_context_isolation_failure_and_no_renewal(self):
        now=[1000]
        lookup.VOLUMES=lookup.VolumeCache(clock=lambda:now[0])
        seen=[]
        def worker(argv,**kwargs):
            settings=json.loads(Path(argv[-1]).read_text());seen.append(settings.get('cached_volume'))
            if settings['api_key']=='failed':
                return ProcessResult('ok',0,b'{"state":"failed"}')
            payload={'state':'ok','metadata':{'series':'Fixture','issue':'1'}}
            if not settings.get('cached_volume'):
                payload.update(volume=VOLUME,expires=now[0]+300)
            return ProcessResult('ok',0,json.dumps(payload).encode())
        with tempfile.TemporaryDirectory() as directory, patch.object(lookup,'run',side_effect=worker):
            args=dict(workdir=directory,issueid='123',volumeid='456',api_key='fixture',base_url='https://example.com/api')
            lookup.lookup(**args);now[0]+=200;lookup.lookup(**args)
            self.assertIsNone(seen[0]);self.assertEqual(seen[1]['expires'],1300)
            for changes in [{'api_key':'other'},{'base_url':'https://other.example/api'},{'verify':False},{'api_key':'failed'}]:
                lookup.lookup(**dict(args,**changes));self.assertIsNone(seen[-1])
            lookup.lookup(**dict(args,api_key='failed'));self.assertIsNone(seen[-1])
            now[0]=1300;lookup.lookup(**args);self.assertIsNone(seen[-1])

    def test_private_settings_never_enter_argv_and_are_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            def run(argv,**kwargs):
                self.assertNotIn('private-fixture-key',' '.join(argv))
                path=Path(argv[-1]);self.assertEqual(path.stat().st_mode&0o777,0o600)
                self.assertEqual(path.parent.stat().st_mode&0o777,0o700)
                self.assertEqual(json.loads(path.read_text())['api_key'],'private-fixture-key')
                self.assertEqual(kwargs['timeout'],45)
                return ProcessResult('ok',0,json.dumps({'state':'ok','metadata':{'series':'Fixture','issue':'1'}}).encode())
            with patch.object(lookup,'run',side_effect=run):
                result=lookup.lookup(workdir=directory,issueid='123',api_key='private-fixture-key',base_url='https://example.com/api')
            self.assertEqual(result.state,'ok');self.assertEqual(list(Path(directory).iterdir()),[])
            with patch.object(lookup,'run',return_value=ProcessResult('timed_out',-9)):
                self.assertEqual(lookup.lookup(workdir=directory,issueid='123',api_key='fixture',base_url='https://example.com/api').state,'timed_out')
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_optional_cache_payload_does_not_overflow_worker_output_budget(self):
        volume=dict(VOLUME,name='S'*4000)
        metadata=lookup.mapping(dict(ISSUE,description='D'*60000),volume,'123','456')
        encoded=lookup.encode_result(lookup.LookupResult('ok',metadata,volume,12345))
        self.assertLessEqual(len(encoded.encode())+1,lookup.MAX_OUTPUT)
        self.assertNotIn('volume',json.loads(encoded))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'response.json';path.write_text(encoded)
            result=lookup.run([sys.executable,'-c','import pathlib,sys;print(pathlib.Path(sys.argv[1]).read_text())',str(path)],
                              cwd=directory,timeout=5)
        self.assertEqual(result.state,'ok')
        self.assertEqual(json.loads(result.stdout)['metadata'],metadata)


if __name__=='__main__':unittest.main()
