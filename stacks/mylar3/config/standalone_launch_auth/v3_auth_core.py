"""Private V3 verifier evidence. No operational admission or signing API."""
import hashlib
import json
import os
import threading
import time
import weakref
from pathlib import Path
from private_crypto import Held, _TargetExperiment, _OriginalSources, _SOURCE_FRAMES

_LIMIT=65536
_TOTAL_SECONDS=3600
_WAIT_SECONDS=1800
_TERMINAL_SECONDS=180
_DOMAIN='standalone-fixed-launch-admission-v1'
_STAGES={2:'backup-ready',4:'observed-release',6:'observed-exit'}
_MEASURED=('installation','key','broker_sources','child_sources','bootstrap','input','review','deployment','profile')
_FRAMES=weakref.WeakKeyDictionary()
_STATE_SEALS=weakref.WeakKeyDictionary()
_CONTEXT_SEALS=weakref.WeakKeyDictionary()

def _canonical(value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
    if not 0<len(raw)<=_LIMIT:raise Held('frame-bound')
    return raw

def _parse(raw):
    if type(raw) is not bytes or not 0<len(raw)<=_LIMIT or b'\n' in raw:raise Held('frame-bound')
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise Held('duplicate-field')
            out[key]=value
        return out
    try:value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(Held('nonfinite')))
    except (ValueError,UnicodeError) as e:raise Held('frame-json') from e
    if type(value) is not dict or _canonical(value)!=raw:raise Held('frame-canonical')
    return value

def _hash(raw):return hashlib.sha256(raw).hexdigest()
def _hex(value):return type(value) is str and len(value)==64 and all(x in '0123456789abcdef' for x in value)
def _fact(fd):
    z=os.fstat(fd)
    return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)

def _start():
    # /proc stat comm can contain spaces; fields after final ')' start at field3.
    with open('/proc/self/stat','rb') as stream:
        return stream.read(65536).rsplit(b')',1)[1].split()[19].decode('ascii')

class _TranscriptVerifier:
    """Private mechanics only; fixed installation loader owns typed admission.

    Direct construction never grants current standalone or SDK activation.
    Deployment and the privileged original host factory remain separate gates.
    """
    def __init__(self, measured, public_der, input_fd, output_fd):
        if type(measured) is not dict or set(measured)!=set(_MEASURED) or not all(_hex(v) for v in measured.values()) or measured['key']!=_hash(public_der):raise Held('measured-shape')
        self._runtime=_TargetExperiment()
        self._code=_OriginalSources([Path(__file__).resolve()])
        self._public=public_der
        challenge=os.urandom(32).hex()
        original=(tuple(sorted(measured.items())),public_der,input_fd,output_fd,_fact(input_fd),_fact(output_fd),os.getpid(),threading.get_ident(),_start(),time.monotonic()+5,challenge,self._runtime,self._code,_SOURCE_FRAMES[self._code])
        _FRAMES[self]=[original,None,0,b'',False,original[9]]
        self._challenge=_canonical({'domain':'standalone-launch-challenge-v3','challenge':challenge,'child_pid':original[6],'child_start':original[8],'measured':dict(original[0])})
        _FRAMES[self].append(self._challenge)
        _FRAMES[self].append(original[9])
        _FRAMES[self].append(False)
        _CONTEXT_SEALS[self]=(original,self._challenge)
        row=_FRAMES[self];_STATE_SEALS[self]=(row[1],row[2],row[3],row[4],row[5],row[7],row[8])
    def _close(self):
        row=_FRAMES.get(self)
        if row is None:raise Held('original-registry')
        context=_CONTEXT_SEALS.get(self)
        if context is None or row[0] is not context[0]:raise Held('original-context-custody')
        original=context[0];state=_STATE_SEALS.get(self)
        original[12].close()
        if self._runtime is not original[11] or self._public!=original[1] or os.getpid()!=original[6] or threading.get_ident()!=original[7] or _start()!=original[8] or time.monotonic()>=min(row[5],row[7]):raise Held('original-context')
        if _fact(original[2])!=original[4] or _fact(original[3])!=original[5]:raise Held('original-pipes')
        if state is None or (row[1],row[2],row[3],row[4],row[5],row[7],row[8])!=state or _STATE_SEALS.get(self) is not state:raise Held('original-transcript-state')
        if _CONTEXT_SEALS.get(self) is not context or _FRAMES.get(self) is not row or row[0] is not original or row[6]!=context[1]:raise Held('original-context-custody')
        if self._challenge!=context[1] or self._code is not original[12] or _SOURCE_FRAMES.get(original[12]) is not original[13]:raise Held('original-code-frame')
        leaves,nodes,aliases,absent=original[13]
        if (tuple(original[12].leaves.items()),tuple(original[12].nodes.items()),tuple(original[12].links.items()),original[12].absent)!=original[13]:raise Held('original-code-logical')
        for path,v in nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('original-code-node')
        for path,(v,digest) in leaves:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('original-code-leaf')
        return row
    def challenge_frame(self):self._close();return _CONTEXT_SEALS[self][1]
    def verify_admission(self,raw,signature):
        row=self._close();context=_CONTEXT_SEALS[self];original=context[0]
        if row[1] is not None:raise Held('admission-once')
        value=_parse(raw)
        fields={'domain','measured','challenge','child_pid','child_start','challenge_frame','session','broker_nonce','purpose','lifetime_ms','host_observation'}
        if set(value)!=fields or value['domain']!=_DOMAIN or value['measured']!=dict(original[0]) or value['challenge']!=original[10] or type(value['child_pid']) is not int or value['child_pid']!=original[6] or value['child_start']!=original[8] or value['challenge_frame']!=_hash(context[1]) or not _hex(value['session']) or not _hex(value['broker_nonce']) or value['purpose']!='retained-standalone' or type(value['lifetime_ms']) is not int or not 1<=value['lifetime_ms']<=5000:raise Held('admission-claims')
        host=value['host_observation']
        if type(host) is not dict or set(host)!={'container','start','host_pid','image'} or not _hex(host['container']) or not _hex(host['start']) or not _hex(host['image']) or type(host['host_pid']) is not int or host['host_pid']<=0:raise Held('host-observation-shape')
        deadline=min(original[9],original[9]-5+value['lifetime_ms']/1000)
        if time.monotonic()>=deadline:raise Held('admission-expired')
        self._runtime._verify(raw,signature,original[1]);final_now=time.monotonic();self._close()
        if final_now>=deadline:raise Held('admission-expired')
        if _CONTEXT_SEALS.get(self) is not context or row[0] is not original:raise Held('original-context-custody')
        row[5]=deadline
        row[1]=(_hash(raw+signature),value['session'],value['broker_nonce']);row[3]=hashlib.sha256(context[1]+raw+signature).digest()
        _STATE_SEALS[self]=(row[1],row[2],row[3],row[4],row[5],row[7],row[8])
        return _hash(raw+signature)
    def _begin_action(self):
        # Called by the typed consume-once preinit boundary, before Config.
        row=self._close();context=_CONTEXT_SEALS[self];original=context[0]
        if row[1] is None or row[2]!=0 or row[8]:raise Held('preinit-once')
        row[5]=original[9]-5+_TOTAL_SECONDS
        row[7]=min(row[5],original[9]-5+_WAIT_SECONDS)
        row[8]=True
        _STATE_SEALS[self]=(row[1],row[2],row[3],row[4],row[5],row[7],row[8])
    def child_frame(self,raw):
        row=self._close();context=_CONTEXT_SEALS[self];original=context[0]
        if row[1] is None or row[4] or row[2] not in (0,2,4):raise Held('child-order')
        value=_parse(raw);sequence=row[2]+1
        if set(value)!={'sequence','kind','payload'} or type(value['sequence']) is not int or value['sequence']!=sequence or value['kind']!={1:'initialized',3:'observed',5:'final-ACK'}[sequence] or type(value['payload']) is not dict:raise Held('child-frame')
        self._close()
        if _CONTEXT_SEALS.get(self) is not context or row[0] is not original:raise Held('original-context-custody')
        row[3]=hashlib.sha256(row[3]+raw).digest();row[2]=sequence
        if sequence==1 and not row[8]:
            # Preauth expiry gates admission and preinit only. Total lifetime
            # retains original challenge time; caller cannot supply/refresh it.
            row[5]=original[9]-5+_TOTAL_SECONDS
            row[7]=min(row[5],original[9]-5+_WAIT_SECONDS)
            row[8]=True
        _STATE_SEALS[self]=(row[1],row[2],row[3],row[4],row[5],row[7],row[8])
    def host_frame(self,raw,signature):
        row=self._close();context=_CONTEXT_SEALS[self];original=context[0]
        if row[1] is None or row[4] or row[2] not in (1,3,5):raise Held('host-order')
        value=_parse(raw);sequence=row[2]+1
        if set(value)!={'domain','session','admission','challenge','sequence','kind','previous','payload','payload_digest'} or value['domain']!='standalone-fixed-stage-v3' or value['session']!=row[1][1] or value['admission']!=row[1][0] or value['challenge']!=original[10] or type(value['sequence']) is not int or value['sequence']!=sequence or value['kind']!=_STAGES[sequence] or value['previous']!=row[3].hex() or type(value['payload']) is not dict or value['payload_digest']!=_hash(_canonical(value['payload'])):raise Held('host-claims')
        next_deadline=min(row[5],time.monotonic()+_TERMINAL_SECONDS) if sequence==2 else row[7]
        self._runtime._verify(raw,signature,original[1]);self._close()
        if _CONTEXT_SEALS.get(self) is not context or row[0] is not original:raise Held('original-context-custody')
        row[3]=hashlib.sha256(row[3]+raw+signature).digest();row[2]=sequence
        if sequence==2:row[7]=next_deadline
        _STATE_SEALS[self]=(row[1],row[2],row[3],row[4],row[5],row[7],row[8])
        return value['payload']
    def natural_exit(self,returncode):
        row=self._close();_CONTEXT_SEALS[self][0]
        if row[2]!=6 or row[4] or type(returncode) is not int or returncode!=0:raise Held('natural-exit')
        row[4]=True
        _STATE_SEALS[self]=(row[1],row[2],row[3],row[4],row[5],row[7],row[8])
    def activation_admission(self):
        raise Held('fixed-root-installation-and-launch-factory-unimplemented')
