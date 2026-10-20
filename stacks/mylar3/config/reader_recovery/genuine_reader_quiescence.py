"""Bounded pinned-Komga task-empty observations; never quiescence authority.

Komga 1.28.1 interfaces/sse/SseController.kt emits TaskQueueStatus every 10s.
TasksDao counts every TASK row; TaskProcessor deletes after handler completion
and its downstream submissions. Two empty samples cannot exclude future work.
"""
import http.client
import json
import os
from pathlib import Path
import re
import signal
import sys
import time
import urllib.parse

LIMIT = 1024 * 1024
LINE_LIMIT = 65536
FRAME_LIMIT = 131072
FRAME_COUNT = 256
LINE_COUNT = 4096
JAR = '/app/application.jar'
JAR_SHA = 'f76aff7d31f2735ed902e3a004540e869568be42dc099a5560d72fd3d8f2c0fe'
MUTATIONS = frozenset({
    'LibraryAdded','LibraryChanged','LibraryDeleted','SeriesAdded','SeriesChanged','SeriesDeleted',
    'BookAdded','BookChanged','BookDeleted','BookImported','ReadListAdded','ReadListChanged','ReadListDeleted',
    'CollectionAdded','CollectionChanged','CollectionDeleted','ReadProgressChanged','ReadProgressDeleted',
    'ReadProgressSeriesChanged','ReadProgressSeriesDeleted','ThumbnailBookAdded','ThumbnailBookDeleted',
    'ThumbnailSeriesAdded','ThumbnailSeriesDeleted','ThumbnailSeriesCollectionAdded','ThumbnailSeriesCollectionDeleted',
    'ThumbnailReadListAdded','ThumbnailReadListDeleted'})


class Held(ValueError):
    pass


def need(value, reason):
    if not value:raise Held(reason)


def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def decode(raw):
    def pairs(items):
        value={}
        for key,item in items:
            need(key not in value,'duplicate-json-field');value[key]=item
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(Held('json-number')))


class Deadline:
    def __init__(self, seconds, clock=time.monotonic):
        need(type(seconds) is int and 1 <= seconds <= 30,'finite-queue-deadline')
        self.clock=clock;self.start=clock();self.end=self.start+seconds
    def now(self):
        value=self.clock();need(self.start <= value < self.end,'queue-total-deadline');return value
    def left(self):
        return self.end-self.now()


def request(value):
    need(type(value) is dict and set(value)=={'version','nonce','native_cid','base','key','seconds'},'queue-request-schema')
    need(type(value['version']) is int and value['version']==1
         and all(type(value[k]) is str and re.fullmatch('[a-f0-9]{64}',value[k]) for k in ('nonce','native_cid')),'queue-original-selector')
    parsed=urllib.parse.urlsplit(value['base'])
    need(parsed.scheme=='http' and parsed.hostname and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',parsed.hostname)
         and parsed.port and 1 <= parsed.port <= 65535 and not parsed.username and not parsed.password
         and parsed.path=='' and not parsed.query and not parsed.fragment
         and value['base']=='http://'+parsed.hostname+':'+str(parsed.port),'queue-original-origin')
    need(type(value['key']) is str and 1 <= len(value['key']) <= 256 and value['key'].isascii()
         and all(32 < ord(c) < 127 for c in value['key']),'queue-private-key')
    need(type(value['seconds']) is int and 1 <= value['seconds'] <= 30,'finite-queue-deadline')
    return parsed.hostname,parsed.port


def stream(response, deadline):
    event=None;data=[];frame_bytes=0;frames=0;lines=0;total=0;first=None
    while True:
        deadline.now()
        raw=response.readline(LINE_LIMIT+1)
        stamp=deadline.now();need(type(raw) is bytes and raw,'queue-eof-or-silence')
        total+=len(raw);lines+=1;frame_bytes+=len(raw)
        need(len(raw)<=LINE_LIMIT and total<=LIMIT and lines<=LINE_COUNT and frame_bytes<=FRAME_LIMIT,'queue-stream-bound')
        need(raw.endswith(b'\n') and b'\0' not in raw,'queue-partial-line')
        text=raw[:-1]
        if text.endswith(b'\r'):text=text[:-1]
        line=text.decode('utf-8',errors='strict')
        need('\r' not in line,'queue-line-ending')
        if not line:
            frames+=1;need(frames<=FRAME_COUNT,'queue-frame-count')
            if event is None and not data:
                frame_bytes=0;continue  # Comment heartbeats are never empty evidence.
            need(event is not None and data,'queue-incomplete-event')
            if event=='TaskQueueStatus':
                value=decode('\n'.join(data))
                need(type(value) is dict and set(value)=={'count','countByType'},'queue-status-schema')
                count=value['count'];types=value['countByType']
                need(type(count) is int and 0 <= count <= 1000000 and type(types) is dict and len(types)<=128
                     and all(type(k) is str and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,63}',k)
                             and type(v) is int and 0 < v <= 1000000 for k,v in types.items())
                     and sum(types.values())==count,'queue-count-contract')
                if count:
                    first=None
                elif first is None:
                    first=stamp
                elif stamp-first>=8:
                    return dict(queue_empty_observed=True,zero_events=2,separation_ms=int((stamp-first)*1000),
                                elapsed_ms=int((stamp-deadline.start)*1000),frames=frames,lines=lines,bytes=total)
            else:
                need(event in MUTATIONS and type(decode('\n'.join(data))) is dict,'queue-unsupported-event');first=None
            event=None;data=[];frame_bytes=0
        elif line.startswith(':'):
            continue
        else:
            field,separator,value=line.partition(':');need(separator and field in ('event','data'),'queue-unsupported-field')
            if value.startswith(' '):value=value[1:]
            if field=='event':
                need(event is None and re.fullmatch('[A-Za-z][A-Za-z0-9]{0,63}',value),'queue-event-name');event=value
            else:data.append(value)


def perform(value):
    host,port=request(value);deadline=Deadline(value['seconds'])
    # Per-socket timeouts alone allow endless trickles and do not bound DNS.
    # This helper owns one process/main thread and one total real-time alarm.
    need(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'queue-ambient-timer')
    previous=signal.getsignal(signal.SIGALRM)
    def expired(*_):raise Held('queue-total-deadline')
    signal.signal(signal.SIGALRM,expired)
    connection=None
    try:
        signal.setitimer(signal.ITIMER_REAL,deadline.left())
        connection=http.client.HTTPConnection(host,port,timeout=deadline.left())
        connection.request('GET','/sse/v1/events',headers={'X-API-Key':value['key'],'Accept':'text/event-stream'})
        response=connection.getresponse();deadline.now()
        need(response.status==200 and response.getheader('Content-Type','').split(';',1)[0].strip().lower()=='text/event-stream',
             'queue-stream-response')
        return stream(response,deadline)
    finally:
        try:
            if connection is not None:connection.close()
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
            signal.signal(signal.SIGALRM,previous)


def observe(session, helper_ref, reader):
    import genuine_application_bootstrap as b
    need(type(session) is b.Bootstrap,'original-bootstrap-session')
    session.queue_originals();session.roles()
    need(Path(helper_ref['path'])==Path(__file__).resolve(),'fixed-queue-helper')
    program=b.p.read(helper_ref,private=False).decode()
    need(type(reader) is dict and set(reader)=={'library','books'} and reader['library']['root']==str(session.library),'original-reader-library')
    before=encode(dict(profiles=session.profiles,epochs=session.epochs,network=session.network_profile,reader=reader))
    session.installed_sources()
    principal=session.http('reader','principal');b.active.checked_library_user(principal)
    libraries=session.http('reader','libraries')
    need(type(libraries) is list and len(libraries)==1 and libraries[0]['id']==reader['library']['id']
         and libraries[0]['root']==reader['library']['root'],'original-reader-library-settings')
    b.active.checked_library_documents(dict(user=principal,libraries=libraries,repeated_libraries=session.http('reader','libraries')))
    native=session.plan['roles']['native']['id'];cid=session.plan['roles']['reader']['id']
    jar_args=['exec','--user','1000:1000',cid,'sha256sum',JAR]
    need(session.engine.run(jar_args,session.seconds()).decode().split()==[JAR_SHA,JAR],'queue-original-1-28-1-jar')
    request_value=dict(version=1,nonce=session.plan['nonce'],native_cid=native,base=session.reader_base,key=session.reader_key,seconds=session.seconds())
    request(request_value)
    raw=session.engine.run(['exec','--interactive','--user','1000:1000',native,'/lsiopy/bin/python3','-I','-B','-c',program,
                            '--disposable-reader-queue-v1',session.plan['nonce'],native],request_value['seconds'],encode(request_value))
    value=decode(raw)
    need(type(value) is dict and set(value)=={'queue_empty_observed','zero_events','separation_ms','elapsed_ms','frames','lines','bytes'}
         and value['queue_empty_observed'] is True and type(value['zero_events']) is int and value['zero_events']==2
         and all(type(value[k]) is int and value[k]>=0 for k in ('separation_ms','elapsed_ms','frames','lines','bytes'))
         and 8000<=value['separation_ms']<=value['elapsed_ms']<request_value['seconds']*1000
         and 2<=value['frames']<=FRAME_COUNT and value['frames']<=value['lines']<=LINE_COUNT
         and 0<value['bytes']<=LIMIT,'queue-observation-only')
    session.roles();session.queue_originals();b.p.read(helper_ref,private=False)
    need(session.engine.run(jar_args,session.seconds()).decode().split()==[JAR_SHA,JAR],'queue-original-1-28-1-jar')
    need(session.http('reader','principal')==principal and session.http('reader','libraries')==libraries,'queue-original-reader-documents')
    need(encode(dict(profiles=session.profiles,epochs=session.epochs,network=session.network_profile,reader=reader))==before,'queue-original-session-bracket')
    session.installed_sources();session.roles();session.queue_originals();b.p.read(helper_ref,private=False)
    return dict(version=1,kind='original-reader-task-empty-bracket',nonce=session.plan['nonce'],
                roles=decode(before),helper=helper_ref,observation=value,reader_image=session.plan['images']['reader'],
                application_quiescence_verified=False,future_exclusion_verified=False,stop_authority=False,
                reader_resume_authority=False,publication_acceptance=False,mutation_authority=False,
                ordinary_import_verified=False,ordinary_ack_verified=False)


def main():
    try:
        need(sys.flags.isolated and sys.dont_write_bytecode and os.geteuid()==1000 and len(sys.argv)==4
             and sys.argv[:2]==['-c','--disposable-reader-queue-v1'],'owning-queue-invocation')
        raw=sys.stdin.buffer.read(LIMIT+1);need(0<len(raw)<=LIMIT,'queue-input-bound');value=decode(raw)
        request(value);need(sys.argv[2:]==[value['nonce'],value['native_cid']],'queue-original-argv')
        result=perform(value);sys.stdout.buffer.write(encode(result)+b'\n');return 0
    except Exception:
        # Never emit credentials, URLs, event payloads or exception details.
        sys.stdout.buffer.write(b'{"held":"reader-task-empty"}\n');return 2


if __name__=='__main__':raise SystemExit(main())
