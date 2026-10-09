"""Exact private invocation producer. No lifecycle or child execution is installed.

Root owns continuous stopped-reader lifecycle. This producer binds its explicit
proofs and command; serialized proof never grants SQL or filesystem mutation.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import time

ROLES={'stopped_runtime','backup_ack','backup_manifest','backup_acceptance','rows',
       'schema','reviewed_plan','timestamp_evidence','custody','native_scope'}
MISSING=('checked-owning-reader-invocation-source-pin',
         'NativeNegativePreparation.consume owning filesystem consumer',
         'operational stopped-reader disk consumer')
class Held(ValueError):pass

def check(v,s):
    if not v:raise Held(s)
def compact(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def signature(p):
    s=os.lstat(p);return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)
def canonical(p):
    p=Path(p);check(p.is_absolute() and '..' not in p.parts and p.resolve()==p
        and not any(q.is_symlink() for q in (p,*p.parents)),'canonical');return p
def ancestors(paths):
    return {p:signature(p)[:2]+signature(p)[5:8] for x in paths for p in canonical(x).parents}
def read(p):
    p=canonical(p);s=signature(p)
    check(stat.S_ISREG(s[5]) and stat.S_IMODE(s[5])==0o600 and s[6]==os.geteuid()
          and s[8]==1 and 0<s[2]<=64*1024**2,'private-input')
    raw=p.read_bytes();check(signature(p)==s,'read-incarnation');return raw,s

def decode(raw):
    def pairs(items):
        result={}
        for k,v in items:check(k not in result,'duplicate-json');result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:check(False,'json-number'))
def hex64(v):return type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v)
def references(refs):
    check(type(refs) is dict and set(refs)==ROLES,'exact-control-roles')
    for ref in refs.values():
        check(type(ref) is dict and set(ref)=={'path','sha256','signature9'}
              and hex64(ref['sha256']) and type(ref['signature9']) is list
              and len(ref['signature9'])==9 and all(type(v) is int for v in ref['signature9']),
              'control-reference')
        canonical(ref['path'])

def close(files,nodes):
    # Complete passive closure follows all semantic reads/writes/hash callbacks.
    for p,v in files.items():
        s=os.lstat(p)
        check((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,
               s.st_uid,s.st_gid,s.st_nlink)==v,'terminal-file')
    for p,v in nodes.items():
        s=os.lstat(p);check((s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)==v,'terminal-ancestor')

def validate(doc):
    check(type(doc) is dict and set(doc)=={'version','kind','nonce','consumer','controls',
          'reader_root','restore_root','scratch','operation','native','corrections'},'plan-schema')
    check(type(doc['version']) is int and doc['version']==1
          and doc['kind']=='reviewed-negative-reader-prepare-input' and hex64(doc['nonce']),'plan-kind')
    references(doc['controls'])
    consumer=doc['consumer']
    check(type(consumer) is dict and set(consumer)=={'path','sha256','signature9'}
          and hex64(consumer['sha256']),'consumer-pin')
    canonical(consumer['path'])
    roots=[canonical(doc[k]) for k in ('reader_root','restore_root','scratch','operation')]
    check(all(not a.is_relative_to(b) and not b.is_relative_to(a)
          for i,a in enumerate(roots) for b in roots[i+1:]),'scope-overlap')
    native=doc['native']
    check(type(native) is dict and set(native)=={'data','roots','tool_root','census','writer_identity'}
          and type(native['roots']) is list and 1<=len(native['roots'])<=8,'native-scope')
    canonical(native['data']);canonical(native['tool_root'])
    for p in native['roots']:canonical(p)
    check(type(doc['corrections']) is list and len(doc['corrections'])==5,'exact-five-corrections')
    allpaths=[]
    for row in doc['corrections']:
        check(type(row) is dict and set(row)=={'source','owner','counterpart','retained','restore'},'correction-schema')
        check(type(row['owner']) is dict and set(row['owner'])=={'table','issueid','parentcomicid','releasecomicid'},'owner-schema')
        for key in ('source','counterpart','retained','restore'):allpaths.append(canonical(row[key]))
    check(len(set(allpaths))==20,'correction-alias')
    return doc

def build(input_path,input_sha,output,own_sha):
    inp=canonical(input_path);own=canonical(Path(__file__).absolute());out=canonical(output)
    check(not os.path.lexists(out),'output-collision')
    names=set(os.listdir(out.parent))
    nodes=ancestors([inp,own,out]);raw,inf=read(inp)
    check(hashlib.sha256(raw).hexdigest()==input_sha,'input-pin')
    doc=validate(decode(raw))
    # Declared parents captured immediately after decode, before source/proof reads.
    declared=[Path(r['path']) for r in doc['controls'].values()]+[Path(doc['consumer']['path'])]
    more=ancestors(declared+[Path(doc[k]) for k in ('reader_root','restore_root','scratch','operation')])
    check(all(more.get(p,v)==v for p,v in nodes.items()),'admission-ancestor')
    nodes.update(more);files={inp:inf};ownraw,files[own]=read(own)
    check(hashlib.sha256(ownraw).hexdigest()==own_sha,'source-pin')
    for ref in list(doc['controls'].values())+[doc['consumer']]:
        p=Path(ref['path']);r,s=read(p)
        check(hashlib.sha256(r).hexdigest()==ref['sha256'] and list(s)==ref['signature9'],'declared-proof')
        files[p]=s
    runtime=decode(read(doc['controls']['stopped_runtime']['path'])[0])
    check(runtime.get('kind')=='root-owned-reader-stopped-observation'
          and runtime.get('nonce')==doc['nonce'] and type(runtime.get('observed')) is int
          and 0<=time.time()-runtime['observed']<=120,'stopped-parent-binding')
    state=runtime.get('container',{}).get('State',{})
    check(state.get('Running') is False and type(state.get('Pid')) is int and state['Pid']==0
          and state.get('Status')=='exited','stopped-proof-required')
    result=dict(version=1,kind='negative-reader-prepare-invocation',input_sha256=input_sha,
        parent_source_sha256=own_sha,nonce=doc['nonce'],document=doc,
        command=['python3',doc['consumer']['path'],'--prepare','--input',str(out)],
        executable=False,sql_authority=False,filesystem_authority=False,
        publication_acceptance=False,operation_verified=False,final_ack_required=True,
        missing_consumers=list(MISSING))
    data=compact(result);digest=hashlib.sha256(data).hexdigest()
    ps=signature(out.parent);check(stat.S_ISDIR(ps[5]) and stat.S_IMODE(ps[5])==0o700
                                  and ps[6]==os.geteuid(),'private-output-parent')
    check(not any(out.is_relative_to(Path(doc[k])) for k in ('reader_root','restore_root','scratch')),'output-live-overlap')
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    expected=signature(out);parent_after=signature(out.parent);actual,ofs=read(out)
    check(hashlib.sha256(actual).hexdigest()==digest and ofs==expected,'emitted-output-digest')
    check(set(os.listdir(out.parent))==names|{out.name},'output-census')
    files[out]=expected;files[out.parent]=parent_after;close(files,nodes)
    return dict(invocation_verified=True,invocation_sha256=digest,executable=False,
                sql_authority=False,filesystem_authority=False,operation_verified=False)

if __name__=='__main__':
    print(json.dumps({'executable':False,'missing_consumers':MISSING,'sql_authority':False}))
