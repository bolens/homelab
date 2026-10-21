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
        # Birth/start belong to HostProbeReplies and HostWriterLease, never
        # this generic exact-call channel, including declared child requests.
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

# A finite budget for the maintained preflight and retained current/check rounds.
# Exhaustion holds; this is not permission to poll until an operation succeeds.
MAX_REOBSERVATIONS = 128


def build_intents(active_ref, roles_ref, original_refs):
    """Derive read-only intents from original assembler/current-role references.

    No argv, command text, use count or new CID is accepted from a child. This
    prepares a v1 document for the existing producer's nfs_intents reference;
    callers persist it with their existing exclusive private writer. The owning
    plan13 composer/Parent still validates the complete cohort, geometry and
    freshness. This builder neither admits those facts nor executes transport.
    Source/readiness bytes remain original; only their exact argv/stdin hashes
    become intents. The retained canonical NFS paths are not stat'ed here.
    """
    import comic_reader_lifecycle_parent as p
    from pathlib import PurePosixPath

    need(type(original_refs) is dict and 1 <= len(original_refs) <= 6
         and all(type(k) is str and type(v) is dict and v.get('path') == k
                 for k,v in original_refs.items()), 'nfs-intent-original-table')
    refs=copy.deepcopy(original_refs);used={};nodes={}

    def read(ref, private=False):
        need(type(ref) is dict and set(ref)=={'path','sha256','signature9'}
             and refs.get(ref['path'])==ref, 'nfs-intent-full-original')
        for path,stamp in p.parents(p.absolute(ref['path'])).items():
            need(path not in nodes or nodes[path]==stamp,'nfs-intent-original-ancestor')
            nodes[path]=stamp
        raw=p.read(ref,private=private);used[ref['path']]=copy.deepcopy(ref)
        return raw

    def follow(ref):
        need(type(ref) is dict and set(ref)=={'path','sha256'}
             and ref['path'] in refs and refs[ref['path']]['sha256']==ref['sha256'],
             'nfs-intent-source-original')
        return read(refs[ref['path']])

    def close():
        for ref in used.values():p.read(ref,private=False)
        p.final({path:tuple(ref['signature9'])for path,ref in used.items()},nodes,())

    def path(value):
        need(type(value) is str and value.startswith('/') and str(PurePosixPath(value))==value
             and '..' not in PurePosixPath(value).parts,'nfs-intent-lexical-target')
        return value

    try:
        active=p.decode(read(active_ref,True));roles=p.decode(read(roles_ref,True))
        need(type(active) is dict and type(active.get('version')) is int and active['version']==1
             and active.get('kind')=='approved-active-nfs-owned-lifecycle','nfs-intent-active-input')
        need(type(roles) is dict and set(roles)=={'nonce','observed','roles','native_process'}
             and p.digest(roles['nonce']) and type(roles['observed']) is int
             and type(roles['native_process']) is dict and type(roles['roles']) is dict
             and set(roles['roles'])=={'native','worker','reader'},'nfs-intent-current-roles')
        ids=[];images={}
        for name in ('native','worker','reader'):
            row=roles['roles'][name]
            need(type(row) is dict and set(row)=={'id','image','profile','epoch'}
                 and p.digest(row['id']) and type(row['image']) is str
                 and row['image'].startswith('sha256:') and p.digest(row['image'][7:])
                 and type(row['profile']) is dict and row['profile'].get('Id')==row['id']
                 and row['profile'].get('Image')==row['image'] and type(row['epoch']) is dict,
                 'nfs-intent-original-role')
            ids.append(row['id']);images[name]=row['image']
        need(len(set(ids))==3,'nfs-intent-distinct-roles')
        cohort=p.decode(follow(active['source_cohort']))
        need(type(cohort) is dict and type(cohort.get('version')) is int and cohort['version']==1
             and cohort.get('kind')=='approved-disposable-nfs-current-source-cohort'
             and cohort.get('images')==dict(images,selected=images['native'])
             and type(cohort.get('sources')) is dict,'nfs-intent-original-cohort')
        ready=follow(cohort['sources']['readiness'])
        request=follow(cohort['sources']['readiness_input'])
        parity=follow(cohort['sources']['parity'])
        need(0<len(ready)<=4*1024**2 and 0<len(parity)<=4*1024**2 and 0<len(request)<=65536,
             'nfs-intent-source-bound')
        request_value=p.decode(request)
        need(type(request_value) is dict and type(request_value.get('nonce')) is str
             and bool(request_value['nonce']), 'nfs-intent-readiness-nonce')
        admission=active['parent_admission'];core=active['probe_plan']
        parent=path(admission['path']);library=path(core['library_root'])
        need(core['fixture_parent']==parent,'nfs-intent-parent-join')
        grandparent=str(PurePosixPath(parent).parent)
        calls=[]
        def add(argv,data,uses):
            sha=None if data is None else hashlib.sha256(data).hexdigest()
            for row in calls:
                if row['argv']==argv and row['input_sha256']==sha:
                    row['uses']+=uses;return
            calls.append(dict(argv=argv,input_sha256=sha,timeout_max=900,uses=uses))
        prefix=list(p.DOCKER)
        # Four outer observations, four inner observations and the initial
        # retained native observation; later current/check rounds are bounded.
        observations=9+MAX_REOBSERVATIONS
        add(prefix+['inspect',*ids],None,observations)
        add(prefix+['exec','-i','--user','1000:1000',ids[0],'/lsiopy/bin/python3','-I','-B','-c',ready.decode('utf-8')],request,observations)
        add(prefix+['exec','-i','--user','1000',ids[0],'/lsiopy/bin/python3','-'],parity,5)
        for target,uses in ((library,3+MAX_REOBSERVATIONS),(grandparent,1),(parent,1)):
            add(['findmnt','--json','--target',target,'--output','SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN'],None,uses)
        need(set(used)==set(refs),'nfs-intent-no-extra-originals')
        document=dict(version=1,kind='host-original-nfs-engine-intents-v1',nonce=roles['nonce'],calls=calls)
        ExactCalls(document,roles['nonce'],p.DOCKER,ids)
        close();return document
    except BaseException as primary:
        try:close()
        except BaseException as secondary:raise primary from secondary
        raise


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
