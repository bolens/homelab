"""Read-only, source-bound in-native-container process/config/daemon observation."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types
import time
import urllib.parse
import urllib.request

MAX = 1024 * 1024
SCOPE_SHA = 'ace628118bd21ac2f50bde93eacad7e0908a0d2e5b34bd5d83222da26a842d3d'
class Held(ValueError): pass

def need(value, reason):
    if not value: raise Held(reason)

def nine(z):
    return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)

def five(z): return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)

def decode(raw):
    def unique(items):
        result = {}
        for key,value in items:
            need(key not in result,'probe-duplicate'); result[key] = value
        return result
    return json.loads(raw,object_pairs_hook=unique)

class Reads:
    def __init__(self): self.files = {}; self.nodes = {}
    def read(self, value):
        path = Path(value); need(path.is_absolute() and '..' not in path.parts,'probe-path')
        for parent in reversed(path.parents):
            z = os.lstat(parent); need(stat.S_ISDIR(z.st_mode),'probe-parent')
            old = self.nodes.setdefault(str(parent),five(z)); need(old == five(z),'probe-parent-CAS')
        z = os.lstat(path); expected = nine(z)
        need(stat.S_ISREG(z.st_mode) and z.st_nlink == 1 and 0 < z.st_size <= MAX,'probe-file')
        fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            need(nine(os.fstat(fd)) == expected,'probe-FD')
            raw = bytearray()
            while len(raw) <= MAX:
                part = os.read(fd,min(65536,MAX + 1-len(raw)))
                if not part: break
                raw.extend(part)
            need(len(raw) == z.st_size and nine(os.fstat(fd)) == expected,'probe-read-CAS')
        finally: os.close(fd)
        old = self.files.setdefault(str(path),expected); need(old == expected,'probe-file-CAS')
        need(nine(os.lstat(path)) == expected,'probe-leaf-CAS')
        return bytes(raw)

# proc pseudo-files have no meaningful regular-file size. Read them bounded,
# then bind argv + start_ticks across the daemon request instead.
def proc_read(path):
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        raw = os.read(fd,MAX + 1); need(len(raw) <= MAX,'probe-proc-bound'); return raw
    finally: os.close(fd)

def process(proc):
    found = []
    names = list(proc.iterdir()); need(len(names) <= 65536,'probe-process-count')
    for directory in names:
        if not directory.name.isdecimal(): continue
        try: raw = proc_read(directory/'cmdline')
        except (FileNotFoundError,ProcessLookupError): continue
        argv = raw.rstrip(b'\0').split(b'\0')
        if len(argv) < 2 or argv[1] != b'/app/mylar3/Mylar.py': continue
        need(len(argv) <= 64 and all(len(x) <= 8192 for x in argv),'probe-argv-bound')
        text = proc_read(directory/'stat').decode(); pos = text.rfind(')')
        need(pos > 0 and text[:text.index('(')].strip() == directory.name,'probe-stat-pid')
        fields = text[pos+2:].split(); need(len(fields)>19,'probe-stat-fields')
        found.append(dict(pid=int(directory.name),start_ticks=int(fields[19]),argv=[x.decode('utf-8') for x in argv]))
    need(len(found) == 1 and found[0]['start_ticks'] > 0,'probe-unique-daemon')
    return found[0]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise Held('probe-redirect')

def health(url,body,seconds):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(urllib.request.Request(url,data=body,method='POST'),timeout=seconds) as response:
        need(response.status == 200,'probe-health-status')
        raw = response.read(MAX + 1); need(len(raw) <= MAX,'probe-health-bound')
    return decode(raw)

def capture(request,*,proc=Path('/proc'),transport=health,clock=time.monotonic):
    need(set(request) == {'version','nonce','source_sha256','seconds','module_pins','scope_source'},'probe-request')
    need(type(request['version']) is int and request['version'] == 1 and type(request['seconds']) is int and 1<=request['seconds']<=120,'probe-deadline')
    end = clock() + request['seconds']; reads = Reads(); current = process(proc)
    # Compile only the exact reviewed parser buffer. Reject unsupported argv
    # (including credential-shaped flags) BEFORE HTTP or output construction.
    scope_raw=request['scope_source'];need(type(scope_raw) is str and len(scope_raw.encode())<=MAX and hashlib.sha256(scope_raw.encode()).hexdigest()==SCOPE_SHA,'probe-scope-pin')
    scope=types.ModuleType('probe_checked_scope');exec(compile(scope_raw,'checked-native-scope','exec'),scope.__dict__)
    try:data=Path(scope.data_from_argv(current['argv']))
    except (ValueError,KeyError,TypeError):raise Held('probe-supported-launch') from None
    # Port overrides are conservatively held until their exact launch/config
    # precedence is included in an independently reviewed producer contract.
    need('--port' not in current['argv'] and '-p' not in current['argv'],'probe-port-override-held')
    original_cmdline=b'\0'.join(x.encode('utf-8') for x in current['argv'])+b'\0'
    original_pid=str(current['pid']);original_ticks=current['start_ticks']
    proc_directory=proc/original_pid
    config = data/'config.ini'; raw = reads.read(config)
    parser = configparser.ConfigParser(interpolation=None,strict=True); parser.read_string(raw.decode())
    need(not parser.defaults(),'probe-default-config')
    def one(key,default=None):
        values = [parser.get(s,key,raw=True) for s in parser.sections() if parser.has_option(s,key)]
        if not values and default is not None: return default
        need(len(values) == 1,'probe-config-unique'); return values[0]
    def boolean(key,default=None):
        value=one(key,default).casefold()
        need(value in ('0','1','false','true'),'probe-config-boolean')
        return value in ('1','true')
    key = one('api_key'); need(len(key)==32 and boolean('api_enabled'),'probe-primary-enabled')
    port = one('http_port'); need(port.isdecimal() and 1<=int(port)<=65535,'probe-port')
    prefix = one('http_root',''); need(not prefix or prefix.startswith('/') and all(x not in prefix for x in ('?','#','\\','://')) and '..' not in prefix.split('/'),'probe-prefix')
    need(not boolean('enable_https','0'),'probe-unsupported-https')
    pins = request['module_pins']; need(set(pins)=={'/app/mylar3/mylar/worker_health.py','/app/mylar3/mylar/native_writers.py'},'probe-daemon-origin-roles')
    for path,digest in pins.items(): need(hashlib.sha256(reads.read(path)).hexdigest()==digest,'probe-daemon-origin-pin')
    remaining = end-clock(); need(remaining > 0,'probe-expired')
    response = transport('http://127.0.0.1:'+port+prefix.rstrip('/')+'/api',urllib.parse.urlencode({'cmd':'getHealth','apikey':key}).encode(),min(10,remaining))
    need(type(response) is dict and response.get('success') is True and type(response.get('data')) is dict,'probe-daemon-response')
    publication = response['data'].get('publication'); need(type(publication) is dict,'probe-publication-missing')
    need(process(proc)==current and clock()<end,'probe-daemon-incarnation')
    # Prepare output before final raw file/ancestor loops. No key/config payload.
    output = dict(version=1,nonce=request['nonce'],source_sha256=request['source_sha256'],process=current,publication=publication,
                  config=dict(path=str(config),sha256=hashlib.sha256(raw).hexdigest(),signature9=list(reads.files[str(config)])))
    encoded = json.dumps(output,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    nodes = tuple(reads.nodes.items()); files = tuple(reads.files.items())
    need(process(proc)==current and clock()<end,'probe-final-process')
    # The last unique-process/parser/deadline/serialization callbacks finish
    # BEFORE a direct raw proc closure. No replaceable process/read/need helper
    # follows these kernel observations or the following raw file vectors.
    fd=os.open(proc_directory/'cmdline',os.O_RDONLY|os.O_NOFOLLOW)
    try:final_cmdline=os.read(fd,MAX+1)
    finally:os.close(fd)
    fd=os.open(proc_directory/'stat',os.O_RDONLY|os.O_NOFOLLOW)
    try:final_stat=os.read(fd,MAX+1)
    finally:os.close(fd)
    if final_cmdline!=original_cmdline or len(final_stat)>MAX:raise Held('probe-final-process-raw')
    text=final_stat.decode();end_name=text.rfind(')');fields=text[end_name+2:].split()
    if end_name<=0 or text[:text.index('(')].strip()!=original_pid or len(fields)<=19 or int(fields[19])!=original_ticks:raise Held('probe-final-process-raw')
    for path,value in nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value: raise Held('probe-final-parent')
    for path,value in files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value: raise Held('probe-final-file')
    return encoded

if __name__ == '__main__':
    try:
        raw = sys.stdin.buffer.read(MAX+1); need(len(raw)<=MAX,'probe-input-bound'); request=decode(raw)
        code = sys.orig_argv[sys.orig_argv.index('-c')+1]
        need(hashlib.sha256(code.encode()).hexdigest()==request['source_sha256'],'probe-executed-source')
        sys.stdout.buffer.write(capture(request)+b'\n')
    except Exception:
        sys.stdout.write('{"verified":false,"reason":"native-readonly-probe-held"}\n'); raise SystemExit(2)
