"""Real bounded stream/parser/signal controls; transports doubled, no runtime grant."""
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
import genuine_reader_quiescence as q


class Clock:
    value=0
    def __call__(self):return self.value


def event(value=None,name='TaskQueueStatus',ending='\n'):
    value={'count':0,'countByType':{}} if value is None else value
    return ('event:'+name+ending+'data:'+json.dumps(value,separators=(',',':'))+ending+ending).encode()


class Response:
    status=200
    content_type='text/event-stream;charset=UTF-8'
    def __init__(self,clock,frames):
        self.clock=clock
        self.lines=[(stamp,line)for stamp,raw in frames for line in raw.splitlines(keepends=True)]
    def readline(self,limit):
        if not self.lines:return b''
        stamp,line=self.lines.pop(0);self.clock.value=stamp;return line[:limit]
    def getheader(self,name,default):return self.content_type


class Parser(unittest.TestCase):
    def parse(self,frames,seconds=30):
        clock=Clock();return q.stream(Response(clock,frames),q.Deadline(seconds,clock))
    def test_two_complete_lf_or_crlf_empty_events_are_only_factual(self):
        for ending in ('\n','\r\n'):
            value=self.parse([(1,event(ending=ending)),(11,event(ending=ending))])
            self.assertEqual(value['zero_events'],2);self.assertEqual(value['separation_ms'],10000)
            self.assertTrue(value['queue_empty_observed']);self.assertEqual(value['frames'],2)
            self.assertNotIn('publication_acceptance',value)
    def test_minimum_eight_seconds_and_early_duplicate_do_not_finish(self):
        with self.assertRaises(q.Held):self.parse([(1,event()),(8.99,event())])
        value=self.parse([(1,event()),(2,event()),(9,event())]);self.assertEqual(value['frames'],3)
    def test_nonzero_and_mutation_each_reset_empty_window(self):
        for middle in (event(dict(count=1,countByType={'AnalyzeBook':1})),event({'bookId':'private'},'BookChanged')):
            with self.assertRaises(q.Held):self.parse([(1,event()),(5,middle),(11,event())])
            self.assertEqual(self.parse([(1,event()),(5,middle),(11,event()),(21,event())])['separation_ms'],10000)
    def test_all_pinned_mutation_names_reset_without_returning_payloads(self):
        for name in q.MUTATIONS:
            with self.subTest(name=name),self.assertRaises(q.Held):self.parse([(1,event()),(5,event({'id':'private'},name)),(11,event())])
    def test_comments_empty_frames_or_silence_never_count_as_empty(self):
        for raw in (b':heartbeat\n\n',b'\n',b''):
            with self.assertRaises(q.Held):self.parse([(1,raw),(11,raw)])
        self.assertEqual(self.parse([(1,event()),(5,b':heartbeat\n\n'),(11,event())])['frames'],3)
    def test_timeout_including_partial_or_trickled_input_refuses(self):
        for frames in ([(30,event())],[(1,event()),(30,event())],[(1,b'event:TaskQueueStatus\n'),(30,b'data:')]):
            with self.assertRaises(q.Held):self.parse(frames)
    def test_eof_partial_lines_missing_event_and_missing_data_refuse(self):
        for raw in (b'event:TaskQueueStatus\n',b'event:TaskQueueStatus',b'event:TaskQueueStatus\n\n',b'data:{}\n\n'):
            with self.subTest(raw=raw),self.assertRaises(q.Held):self.parse([(1,raw)])
    def test_invalid_utf8_nul_bare_cr_and_unknown_fields_refuse(self):
        for raw in (b'event:\xff\n\n',b'event:X\0\n\n',b'event:X\rY\n\n',b'id:old\n\n',b'retry:100\n\n',b'event:TaskQueueStatus\nevent:TaskQueueStatus\n\n'):
            with self.subTest(raw=raw),self.assertRaises((q.Held,UnicodeError)):self.parse([(1,raw)])
    def test_counts_reject_bool_noninteger_negative_sum_and_zero_groups(self):
        for count,types in ((False,{}),(1.0,{'AnalyzeBook':1}),(-1,{}),(1,{}),(0,{'AnalyzeBook':0}),(1,{'AnalyzeBook':True}),(1,{'AnalyzeBook':-1}),(1,{'/private':1})):
            with self.subTest(count=count,types=types),self.assertRaises(q.Held):self.parse([(1,event(dict(count=count,countByType=types)))])
    def test_duplicate_fields_nonfinite_json_and_unsupported_events_refuse(self):
        for raw in (b'event:TaskQueueStatus\ndata:{"count":0,"count":0,"countByType":{}}\n\n',
                    b'event:TaskQueueStatus\ndata:{"count":NaN,"countByType":{}}\n\n',
                    event({},'SessionExpired'),event({},'UnknownEvent'),b'event:BookChanged\ndata:not-json\n\n'):
            with self.assertRaises((q.Held,ValueError)):self.parse([(1,raw)])
    def test_byte_line_frame_and_frame_count_bounds(self):
        cases=[(patch.object(q,'LINE_LIMIT',8),[(1,event())]),(patch.object(q,'LIMIT',16),[(1,event())]),
               (patch.object(q,'FRAME_LIMIT',16),[(1,event())]),(patch.object(q,'FRAME_COUNT',1),[(1,b':heartbeat\n\n'),(2,event())]),
               (patch.object(q,'LINE_COUNT',1),[(1,event())])]
        for control,frames in cases:
            with control,self.assertRaises(q.Held):self.parse(frames)
    def test_seconds_are_exact_positive_integers_bounded_at_thirty(self):
        for value in (False,True,0,31,1.0):
            with self.assertRaises(q.Held):q.Deadline(value)


class Connection:
    def __init__(self,response):self.response=response;self.calls=[];self.closed=False;self.fail=None
    def request(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        if self.fail:raise self.fail
    def getresponse(self):return self.response
    def close(self):self.closed=True


class Transport(unittest.TestCase):
    def value(self):return dict(version=1,nonce='a'*64,native_cid='1'*64,base='http://reader-fixture:25600',key='PRIVATE-FIXTURE',seconds=30)
    def test_exact_readonly_route_headers_and_one_connection(self):
        clock=Clock();connection=Connection(Response(clock,[(1,event()),(11,event())]));deadline=q.Deadline(30,clock)
        with patch.object(q,'Deadline',return_value=deadline),patch.object(q.http.client,'HTTPConnection',return_value=connection)as factory:
            self.assertTrue(q.perform(self.value())['queue_empty_observed'])
        factory.assert_called_once_with('reader-fixture',25600,timeout=30)
        self.assertEqual(connection.calls,[(('GET','/sse/v1/events'),dict(headers={'X-API-Key':'PRIVATE-FIXTURE','Accept':'text/event-stream'}))])
        self.assertTrue(connection.closed);self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
    def test_redirect_http_error_wrong_type_and_connection_fault_do_not_reconnect(self):
        for status,ctype in ((302,'text/event-stream'),(401,'text/event-stream'),(200,'application/json')):
            clock=Clock();response=Response(clock,[]);response.status=status;response.content_type=ctype;connection=Connection(response)
            with patch.object(q.http.client,'HTTPConnection',return_value=connection)as factory,self.assertRaises(q.Held):q.perform(self.value())
            self.assertEqual(factory.call_count,1);self.assertTrue(connection.closed)
        connection=Connection(None);connection.fail=OSError('private endpoint')
        with patch.object(q.http.client,'HTTPConnection',return_value=connection)as factory,self.assertRaises(OSError):q.perform(self.value())
        self.assertEqual(factory.call_count,1);self.assertTrue(connection.closed)
    def test_actual_total_alarm_interrupts_blocking_connect_without_network(self):
        connection=Connection(None)
        def stalled(*args,**kwargs):time.sleep(5)
        connection.request=stalled;value=self.value();value['seconds']=1;before=time.monotonic();handler=signal.getsignal(signal.SIGALRM)
        with patch.object(q.http.client,'HTTPConnection',return_value=connection),self.assertRaisesRegex(q.Held,'total-deadline'):q.perform(value)
        self.assertLess(time.monotonic()-before,3);self.assertTrue(connection.closed)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0));self.assertEqual(signal.getsignal(signal.SIGALRM),handler)
    def test_actual_total_alarm_interrupts_real_local_byte_stream_read(self):
        left,right=socket.socketpair();self.addCleanup(left.close);self.addCleanup(right.close)
        file=left.makefile('rb');self.addCleanup(file.close)
        response=Response(Clock(),[]);response.readline=file.readline;connection=Connection(response)
        value=self.value();value['seconds']=1
        with patch.object(q.http.client,'HTTPConnection',return_value=connection),self.assertRaisesRegex(q.Held,'total-deadline'):q.perform(value)
        self.assertTrue(connection.closed);self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
    def test_origin_credentials_and_schema_refuse_before_transport(self):
        original=self.value()
        for change in ({'base':'https://reader-fixture:25600'},{'base':'http://user@reader-fixture:25600'},{'base':'http://reader-fixture:25600/api/v1/tasks'},
                       {'base':'http://reader-fixture:25600?x=1'},{'key':'private\r\ninjected'},{'seconds':31},{'native_cid':'foreign'},{'operation':'delete'}):
            with patch.object(q.http.client,'HTTPConnection',side_effect=AssertionError('transport reached')),self.assertRaises(q.Held):q.perform(dict(original,**change))
    def test_cli_is_disabled_without_original_actor_and_never_echoes_input(self):
        result=subprocess.run([sys.executable,'-I','-B',str(HERE/'genuine_reader_quiescence.py')],input=b'PRIVATE-API-KEY',capture_output=True,timeout=5)
        self.assertEqual(result.returncode,2);self.assertNotIn(b'PRIVATE',result.stdout+result.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
