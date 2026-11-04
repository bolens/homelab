"""Fixed UID1000 loopback control; the native API key never leaves its container."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import time
import configparser
import urllib.error
import urllib.parse
import urllib.request

LIMIT=4096
CONFIG_LIMIT=2*1024**2
RIGHTS=('mutation_authority','reader_resume_grant','ordinary_import_grant','cleanup_grant')
CONFIG_SECTIONS={'api_enabled':'API','api_key':'API','http_port':'Interface',
                 'http_root':'Interface','enable_https':'Interface','https_cert':'Interface'}


def need(value,reason):
    if not value:raise ValueError(reason)


def compact(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def decode(raw):
    def pairs(rows):
        result={}
        for key,value in rows:
            need(key not in result,'duplicate-control-key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('control-number')))


def nine(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)
def five(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def invoke(packet,*,publish=None):
    need(os.geteuid()==os.getegid()==1000,'native-owner-actor-required')
    need(type(packet) is dict and set(packet)=={'version','kind','nonce','config_ref','session','deadline'},'native-control-schema')
    need(type(packet['version']) is int and packet['version']==1 and packet['kind']=='root-retained-native-control-v1','native-control-kind')
    nonce=packet['nonce'];deadline=packet['deadline']
    need(type(nonce) is str and re.fullmatch('[0-9a-f]{64}',nonce),'native-control-nonce')
    need(type(deadline) in (int,float) and math.isfinite(deadline) and time.monotonic()<deadline,'native-control-original-deadline')
    reference=packet['config_ref'];session=packet['session']
    need(type(reference) is dict and set(reference)=={'path','signature9','sha256'},'native-control-config-ref')
    path=Path(reference['path']);stamp=reference['signature9']
    need(type(reference['path']) is str and path.is_absolute() and str(path)==reference['path'] and '..' not in path.parts,'native-control-config-path')
    need(type(stamp) is list and len(stamp)==9 and all(type(v) is int for v in stamp)
         and type(reference['sha256']) is str and re.fullmatch('[0-9a-f]{64}',reference['sha256']),'native-control-config-vector')
    stamp=tuple(stamp);nodes=tuple((p,five(os.lstat(p))) for p in path.parents)
    need(all(stat.S_ISDIR(v[2]) for p,v in nodes),'native-control-config-ancestry')
    need(type(session) is dict and set(session)=={'version','kind','action','nonce','request','proof'}
         and session['nonce']==nonce and session['action'] in ('open','observe','close')
         and session['kind']=='retained-native-session-v1' and type(session['version']) is int and session['version']==1,'native-control-session')
    session_raw=compact(session);need(len(session_raw)<LIMIT,'native-control-request-bound')
    session=decode(session_raw)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        need(nine(os.fstat(fd))==stamp and stat.S_ISREG(stamp[5]) and stamp[8]==1 and 0<stamp[2]<=CONFIG_LIMIT,'native-control-original-config')
        data=bytearray()
        while block:=os.read(fd,65536):
            data.extend(block);need(len(data)<=CONFIG_LIMIT,'native-control-config-bound')
        need(nine(os.fstat(fd))==stamp and len(data)==stamp[2] and hashlib.sha256(data).hexdigest()==reference['sha256'],'native-control-config-bytes')
        try:
            parser=configparser.ConfigParser(interpolation=None,strict=True);parser.read_string(data.decode())
            need(not parser.defaults() and parser.getboolean(CONFIG_SECTIONS['api_enabled'],'api_enabled'),'native-control-api-enabled')
            key=parser.get(CONFIG_SECTIONS['api_key'],'api_key',raw=True);need(len(key)==32 and key==key.strip(),'native-control-primary-key')
            port=parser.get(CONFIG_SECTIONS['http_port'],'http_port',raw=True)
            need(re.fullmatch('[0-9]{1,5}',port) and 1<=int(port)<=65535,'native-control-port')
            prefix=parser.get(CONFIG_SECTIONS['http_root'],'http_root',raw=True)
            normalized=prefix[:-1] if prefix.endswith('/') else prefix
            need(prefix in ('','/') or prefix.startswith('/') and str(Path(normalized))==normalized
                 and '..' not in Path(prefix).parts and not prefix.startswith('//') and '?' not in prefix and '#' not in prefix,'native-control-http-root')
            secure=parser.getboolean(CONFIG_SECTIONS['enable_https'],'enable_https')
            handlers=[urllib.request.ProxyHandler({}),NoRedirect()]
            if secure:
                context=ssl.create_default_context(cafile=parser.get(CONFIG_SECTIONS['https_cert'],'https_cert',raw=True))
                handlers.append(urllib.request.HTTPSHandler(context=context))
            url=('https' if secure else 'http')+'://127.0.0.1:'+port+prefix.rstrip('/')+'/api'
        except (ValueError,UnicodeError,configparser.Error,OSError):
            raise ValueError('native-control-config-held') from None
        wire=urllib.parse.urlencode({'apikey':key,'cmd':'retainedDeliverySession','request':session_raw.decode()}).encode()
        request=urllib.request.Request(url,data=wire,method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
        need(nine(os.lstat(path))==stamp and all(five(os.lstat(p))==v for p,v in nodes),'native-control-before-request')
        timeout=min(60,deadline-time.monotonic());need(timeout>0,'native-control-deadline')
        try:
            with urllib.request.build_opener(*handlers).open(request,timeout=timeout) as response:
                need(response.status==200,'native-control-http-status');raw=response.read(LIMIT+1)
        except (urllib.error.URLError,OSError):raise ValueError('native-control-transport-held') from None
        need(0<len(raw)<=LIMIT,'native-control-response-bound');answer=decode(raw)
        need(type(answer) is dict and set(answer)=={'success','data'} and answer['success'] is True,'native-control-api-held')
        result=answer['data'];action=session['action']
        common={'version','kind','nonce',*RIGHTS}
        fields=common|({'state'} if action=='observe' else {'request_sha256','pid','marker_sha256','marker_signature9'} if action=='open' else {'request_sha256','pid','proof'})
        need(type(result) is dict and set(result)==fields and type(result['version']) is int and result['version']==1
             and result['nonce']==nonce and all(result[k] is False for k in RIGHTS),'native-control-response-schema')
        need(result['kind']=={'open':'retained-native-session-opened','observe':'retained-native-session-observation','close':'retained-native-session-closed'}[action],'native-control-response-kind')
        if action!='observe':
            need(result['request_sha256']==hashlib.sha256(compact(session['request'])).hexdigest()
                 and type(result['pid']) is int and result['pid']>0,'native-control-owning-request')
        if action=='open':
            vector=result['marker_signature9']
            need(type(vector) is list and len(vector)==9 and all(type(v) is int for v in vector)
                 and type(result['marker_sha256']) is str and re.fullmatch('[0-9a-f]{64}',result['marker_sha256']),
                 'native-control-marker-vector')
        if action=='close':need(compact(result['proof'])==compact(session['proof']),'native-control-owning-release')
        if action=='observe':need(result['state'] in ('active-original-process','factual-held','factual-unreserved'),'native-control-observation')
        encoded=compact(dict(version=1,kind='root-retained-native-control-result-v1',nonce=nonce,
                    config_signature9=list(stamp),response_sha256=hashlib.sha256(raw).hexdigest(),response=answer))
        def close_originals():
            need(nine(os.fstat(fd))==stamp and nine(os.lstat(path))==stamp
                 and all(five(os.lstat(p))==v for p,v in nodes) and time.monotonic()<deadline,
                 'native-control-final-originals')
        close_originals()
        if publish is None:return encoded
        view=memoryview(encoded)
        while view:
            close_originals();count=publish(view)
            need(type(count) is int and 0<count<=len(view),'native-control-short-write');view=view[count:]
        close_originals();need(publish(b'\n')==1,'native-control-delimiter-write');close_originals()
        return None
    finally:os.close(fd)


def main():
    write=os.write
    try:
        raw=sys.stdin.buffer.read(LIMIT+1);need(0<len(raw)<=LIMIT,'native-control-input-bound')
        invoke(decode(raw),publish=lambda data:write(1,data))
    except Exception:
        # No parser, transport or private configuration exception text escapes.
        write(2,b'native-control-held\n');raise SystemExit(2) from None


if __name__=='__main__':main()
