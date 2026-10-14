"""Finite host engine reply boundary for the maintained retained NFS child.

Used only inside an original registered ScopedDocker dialogue. Facts returned by
that child are not an ActiveNFSCanaryObservation and grant no terminal authority.
"""
import base64
import copy
import json
import hashlib
import threading

MAX=16*1024**2
class Held(ValueError):pass

def need(ok,reason):
    if not ok:raise Held(reason)

def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

class ExactCalls:
    """Host-original intents; never learn argv, inputs, IDs, or limits from child."""
    def __init__(self,document,nonce,docker,role_ids):
        need(type(document) is dict and set(document)=={'version','kind','nonce','calls'}
             and type(document['version']) is int and document['version']==1
             and document['kind']=='host-original-nfs-engine-intents-v1'
             and document['nonce']==nonce,'nfs-host-intent-schema')
        need(type(document['calls']) is list and 1<=len(document['calls'])<=512,'nfs-host-intent-bound')
        self.docker=tuple(docker);self.roles=frozenset(role_ids);rows=[]
        for row in document['calls']:
            need(type(row) is dict and set(row)=={'argv','input_sha256','timeout_max','uses'}
                 and type(row['argv']) is list and all(type(v) is str for v in row['argv'])
                 and type(row['timeout_max']) is int and 1<=row['timeout_max']<=900
                 and type(row['uses']) is int and 1<=row['uses']<=1024,'nfs-host-exact-intent')
            need(row['input_sha256'] is None or type(row['input_sha256']) is str
                 and len(row['input_sha256'])==64 and all(c in '0123456789abcdef' for c in row['input_sha256']),'nfs-host-intent-input')
            argv=tuple(row['argv']);self._geometry(argv)
            rows.append((argv,row['input_sha256'],row['timeout_max'],row['uses']))
        need(len({(r[0],r[1]) for r in rows})==len(rows),'nfs-host-intent-duplicate')
        self.rows=tuple(rows);self.original=(self.docker,self.roles,self.rows);self.counts=[0]*len(rows)
    def _geometry(self,argv):
        if argv[:2]==('findmnt','--json'):
            need(len(argv) in (4,6) and argv[2]=='--target' and argv[3].startswith('/')
                 and (len(argv)==4 or argv[4:]==('--output','SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN')),'nfs-host-findmnt-intent');return
        need(argv[:len(self.docker)]==self.docker and len(argv)>len(self.docker),'nfs-host-intent-prefix')
        args=argv[len(self.docker):];verb=args[0]
        # Unowned creation/interactive starts remain refused until the separate
        # host birth/spec/CID + nested lease session producer is implemented.
        need(verb in ('inspect','exec'),'nfs-host-birth-session-unbound')
        if verb=='inspect':
            need(len(args)>1 and len(set(args[1:]))==len(args[1:]) and set(args[1:])<=self.roles,'nfs-host-original-role-CID')
        else:
            index=1
            seen=set()
            while index<len(args) and args[index] in ('-i','--user'):
                flag=args[index];need(flag not in seen,'nfs-host-repeated-exec-option');seen.add(flag);index+=1
                if flag=='--user':
                    need(index<len(args) and args[index] in ('1000','1000:1000'),'nfs-host-fixed-exec-user');index+=1
            need(len(args)>index+1 and args[index] in self.roles,'nfs-host-original-role-exec')
    def close(self):
        need((self.docker,self.roles,self.rows)==self.original,'nfs-host-intent-original')
    def approve(self,argv,data,timeout):
        self.close()
        target=tuple(argv);digest=None if data is None else hashlib.sha256(data).hexdigest()
        matches=[i for i,r in enumerate(self.rows) if r[0]==target and r[1]==digest]
        need(len(matches)==1,'nfs-host-undeclared-child-call');i=matches[0];row=self.rows[i]
        need(type(timeout) in (int,float) and 0<timeout<=row[2] and self.counts[i]<row[3],'nfs-host-intent-limit')
        self._geometry(target);self.counts[i]+=1

class EngineReplies:
    def __init__(self,owner,cid,nonce,intents_ref=None):
        g=owner.left.__func__.__globals__
        need(type(owner) is g.get('LifecycleParent') and g.get('_CORES',{}).get(owner)==owner.core
             and type(owner.engine) is g.get('ScopedDocker'),'nfs-host-original-parent-engine')
        need(g['digest'](cid) and g['digest'](nonce) and nonce==owner.plan['nonce'],'nfs-host-child-binding')
        need(intents_ref is not None and type(intents_ref) is dict and intents_ref.get('path') in owner.files
             and tuple(intents_ref.get('signature9',()))==tuple(owner.files[intents_ref['path']]),'nfs-host-original-intents-default-unbound')
        document=g['decode'](g['read'](intents_ref))
        self.calls=ExactCalls(document,nonce,g['DOCKER'],[owner.baselines[k]['Id'] for k in ('held_native','held_worker','reader')])
        self.intent_ref=copy.deepcopy(intents_ref)
        self.owner,self.cid,self.nonce,self.sequence=owner,cid,nonce,0
        self.g,self.source=g,copy.deepcopy(owner.source_ref)
        self.seal=encode(dict(owner=id(owner),engine=id(owner.engine),cid=cid,nonce=nonce,source=self.source,thread=threading.get_ident()))
        self.close()
    def close(self):
        owner=self.owner;g=self.g
        need(type(owner) is g.get('LifecycleParent') and g.get('_CORES',{}).get(owner)==owner.core
             and type(owner.engine) is g.get('ScopedDocker') and threading.get_ident()==owner.thread,'nfs-host-parent-lifetime')
        need(self.seal==encode(dict(owner=id(owner),engine=id(owner.engine),cid=self.cid,nonce=self.nonce,source=owner.source_ref,thread=threading.get_ident())),'nfs-host-original-binding')
        self.calls.close();owner.left();g['read'](self.source);g['read'](self.intent_ref)
        # Requires the actual existing engine-created Popen/CID/pipe registration.
        g['dialogue_close'](owner.engine,self.cid)
    def fact(self,frame,kind):
        """Advance the same dialogue; returning facts is not capability admission."""
        self.close()
        need(kind in ('nfs-ready','nfs-result','nfs-done') and type(frame) is dict
             and set(frame)=={'type','nonce','sequence','payload'} and frame['type']==kind
             and frame['nonce']==self.nonce and type(frame['sequence']) is int
             and frame['sequence']==self.sequence+1 and len(encode(frame))<=MAX,'nfs-host-fact-frame')
        result=copy.deepcopy(frame['payload']);self.close();self.sequence=frame['sequence'];return result
    def accept(self,frame):
        self.close()
        need(type(frame) is dict and set(frame)=={'type','nonce','sequence','payload'}
             and frame['nonce']==self.nonce and type(frame['sequence']) is int
             and frame['sequence']==self.sequence+1 and len(encode(frame))<=MAX,'nfs-host-frame')
        need(frame['type']=='nfs-engine','nfs-host-engine-frame-only')
        payload=frame['payload'];need(type(payload) is dict and set(payload)=={'argv','input','timeout'},'nfs-host-call')
        need(type(payload['argv']) is list and all(type(v) is str for v in payload['argv'])
             and type(payload['timeout']) in (int,float) and 0<payload['timeout']<=900,'nfs-host-call-shape')
        data=None if payload['input'] is None else base64.b64decode(payload['input'],validate=True)
        need(data is None or len(data)<=8*1024**2,'nfs-host-input-bound')
        self.calls.approve(payload['argv'],data,payload['timeout'])
        result=self.owner.engine.canary(payload['argv'],input=data,capture_output=True,check=False,timeout=min(payload['timeout'],self.owner.left()))
        need(type(result.returncode) is int and type(result.stdout) is bytes and type(result.stderr) is bytes
             and len(result.stdout)<=8*1024**2 and len(result.stderr)<=4*1024**2,'nfs-host-result-bound')
        self.close();self.sequence=frame['sequence']
        return encode(dict(type='nfs-host',nonce=self.nonce,sequence=self.sequence,payload=dict(returncode=result.returncode,stdout=base64.b64encode(result.stdout).decode(),stderr=base64.b64encode(result.stderr).decode())))+b'\n'
