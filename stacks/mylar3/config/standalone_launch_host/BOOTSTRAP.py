"""Exact stdlib-only -I/-B/-c payload; no Mylar import before original map closure."""
import hashlib
import importlib
import json
import os
import re
import sys
from pathlib import Path

ROOT=Path('/app/mylar3/mylar')
LIMIT=4*1024**2

def need(x,why):
    if not x:raise ValueError(why)

def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
def decode(raw):
    def unique(rows):
        answer={}
        for k,v in rows:
            need(k not in answer,'bootstrap-duplicate-key');answer[k]=v
        return answer
    return json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('bootstrap-number')))

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def capture(path,files,nodes):
    need(type(path) is str and path==str(Path(path)) and Path(path).is_absolute() and '..' not in Path(path).parts,'bootstrap-path')
    stamp=nine(os.lstat(path));need(stamp[5]&0o170000==0o100000 and stamp[8]==1,'bootstrap-regular')
    need(path not in files or files[path]==stamp,'bootstrap-leaf-conflict');files.setdefault(path,stamp)
    for parent in Path(path).parents:
        key=str(parent);v=five(os.lstat(parent));need(v[2]&0o170000==0o040000,'bootstrap-ancestor-type')
        need(key not in nodes or nodes[key]==v,'bootstrap-node-conflict');nodes.setdefault(key,v)

def read(path,stamp,maximum):
    need(0<stamp[2]<=maximum,'bootstrap-size');fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        need(nine(os.fstat(fd))==stamp,'bootstrap-original-FD');out=bytearray()
        while block:=os.read(fd,1024**2):out.extend(block);need(len(out)<=maximum,'bootstrap-read-bound')
        need(nine(os.fstat(fd))==stamp and len(out)==stamp[2],'bootstrap-FD-final')
    finally:os.close(fd)
    return bytes(out)

def close(files,nodes):
    for p,v in nodes.items():need(five(os.lstat(p))==v,'bootstrap-node-final')
    for p,v in files.items():need(nine(os.lstat(p))==v,'bootstrap-file-final')

need(sys.argv[1:]==['--input',sys.argv[2] if len(sys.argv)>2 else '', '--input-sha256',sys.argv[4] if len(sys.argv)>4 else ''] and len(sys.argv)==5,'bootstrap-exact-argv')
input_path=sys.argv[2];input_sha=sys.argv[4]
need(re.fullmatch('[0-9a-f]{64}',input_sha),'bootstrap-input-digest')
files={};nodes={};capture(input_path,files,nodes)
need(files[input_path][5]&0o7777==0o600 and files[input_path][6:8]==(os.geteuid(),os.getegid()),'bootstrap-private-input')
raw=read(input_path,files[input_path],LIMIT);need(hashlib.sha256(raw).hexdigest()==input_sha,'bootstrap-input-SHA')
boot=decode(raw);need(canonical(boot)==raw and type(boot) is dict,'bootstrap-canonical-input')
keys={'version','kind','nonce','challenge','parent_sha256','request','config_ref','data_root','source_map_ref','review_ref'}
need(set(boot)==keys and type(boot['version']) is int and boot['version']==1 and boot['kind']=='standalone-retained-bootstrap-v1','bootstrap-schema')
# Every original control leaf precedes the first map/config/review read callback.
for key in ('config_ref','source_map_ref','review_ref'):
    ref=boot[key];need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and re.fullmatch('[0-9a-f]{64}',ref['sha256']) and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(x) is int for x in ref['signature9']),'bootstrap-ref')
    capture(ref['path'],files,nodes);need(tuple(ref['signature9'])==files[ref['path']],'bootstrap-original-control')
close(files,nodes)
map_ref=boot['source_map_ref'];map_raw=read(map_ref['path'],files[map_ref['path']],LIMIT)
need(hashlib.sha256(map_raw).hexdigest()==map_ref['sha256'],'bootstrap-map-SHA');mapping=decode(map_raw)
need(type(mapping) is dict and 1<=len(mapping)<=1024 and canonical(mapping)==map_raw and all(type(k) is str and re.fullmatch('[a-z_]+\.py',k) and type(v) is str and re.fullmatch('[0-9a-f]{64}',v) for k,v in mapping.items()),'bootstrap-map-schema')
required={'__init__.py','config.py','publication_api.py','media_writer.py','publication_guard.py','publication_archive_owned.py','publication_retained_delivery.py','publication_retained_standalone.py','comic_retained_standalone_action.py'}
need(required<=set(mapping),'bootstrap-complete-map')
for name in mapping:capture(str(ROOT/name),files,nodes)
close(files,nodes)
hashes={input_path:input_sha,map_ref['path']:map_ref['sha256']}
for key in ('config_ref','review_ref'):
    ref=boot[key];content=read(ref['path'],files[ref['path']],LIMIT);digest=hashlib.sha256(content).hexdigest();need(digest==ref['sha256'],'bootstrap-control-SHA');hashes[ref['path']]=digest
for name,digest in mapping.items():
    path=str(ROOT/name);content=read(path,files[path],4*1024**2);need(hashlib.sha256(content).hexdigest()==digest,'bootstrap-source-SHA');hashes[path]=digest
# The fixed public installation is measured before its first Python execution.
INSTALL=Path('/opt/mylar-publication-launch');AUTH=INSTALL/'auth'
AUTH_ABSENT=(AUTH/'__pycache__',AUTH/'private_crypto.pyc',AUTH/'v3_auth_core.pyc',AUTH/'standalone_launch_auth.pyc')
def auth_absence():
    for path in AUTH_ABSENT:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise ValueError('bootstrap-auth-bytecode-present')
auth_absence()
fixed=[INSTALL/'installation-v1.json',INSTALL/'inventory-v1.json',INSTALL/'public-ed25519.der',
       AUTH/'private_crypto.py',AUTH/'v3_auth_core.py',AUTH/'standalone_launch_auth.py']
for path in fixed:capture(str(path),files,nodes)
for path in fixed:
    v=files[str(path)];need(v[6]==0 and not v[5]&0o022,'bootstrap-install-root-file')
    for parent in path.parents:
        v=nodes[str(parent)];need(v[3]==0 and not v[2]&0o022,'bootstrap-install-root-node')
anchor_raw=read(str(fixed[0]),files[str(fixed[0])],65536)
inventory_raw=read(str(fixed[1]),files[str(fixed[1])],65536)
public_raw=read(str(fixed[2]),files[str(fixed[2])],44)
anchor=decode(anchor_raw);inventory=decode(inventory_raw)
need(canonical(anchor)==anchor_raw and canonical(inventory)==inventory_raw,'bootstrap-install-canonical')
need(set(anchor)=={'version','kind','deployment','profile','broker_sources','parent_sha256','bootstrap_sha256','inventory_sha256','key_sha256'} and type(anchor['version']) is int and anchor['version']==1 and anchor['kind']=='standalone-installation-anchor-v1','bootstrap-install-schema')
need(anchor['bootstrap_sha256']==hashlib.sha256(sys.orig_argv[4].encode()).hexdigest() and anchor['inventory_sha256']==hashlib.sha256(inventory_raw).hexdigest() and anchor['key_sha256']==hashlib.sha256(public_raw).hexdigest(),'bootstrap-install-pins')
need(set(inventory)=={'version','kind','sources'} and type(inventory['version']) is int and inventory['version']==1 and inventory['kind']=='standalone-leaf-inventory-v1' and type(inventory['sources']) is dict and 12<=len(inventory['sources'])<=512,'bootstrap-inventory-schema')
for path,digest in inventory['sources'].items():
    q=Path(path);need(str(q)==path and '..' not in q.parts and (q.is_relative_to(AUTH) or q.is_relative_to(ROOT)) and re.fullmatch('[0-9a-f]{64}',digest),'bootstrap-inventory-fixed-path')
    capture(path,files,nodes)
for path,digest in inventory['sources'].items():
    v=files[path];need(v[6]==0 and not v[5]&0o022,'bootstrap-inventory-root-file')
    for parent in Path(path).parents:
        v=nodes[str(parent)];need(v[3]==0 and not v[2]&0o022,'bootstrap-inventory-root-node')
    content=read(path,v,LIMIT);need(hashlib.sha256(content).hexdigest()==digest,'bootstrap-inventory-original-hash');hashes[path]=digest
for path,content in zip(fixed[:3],(anchor_raw,inventory_raw,public_raw)):hashes[str(path)]=hashlib.sha256(content).hexdigest()
need({str(AUTH/name) for name in ('private_crypto.py','v3_auth_core.py','standalone_launch_auth.py')}<=set(inventory['sources']),'bootstrap-required-auth')
close(files,nodes);auth_absence()
original={'files':files,'nodes':nodes,'hashes':hashes,'input_bytes':raw}
sys.path[:0]=[str(AUTH),'/app/mylar3','/app/mylar3/lib']
auth_absence()
auth=importlib.import_module('standalone_launch_auth')
need(auth.__file__==str(AUTH/'standalone_launch_auth.py'),'bootstrap-canonical-auth')
close(files,nodes)
boot_ref={'path':input_path,'sha256':input_sha,'signature9':list(files[input_path])}
admission=auth.authenticate_original(boot_ref,0,1,original)
close(files,nodes)
module=importlib.import_module('mylar.comic_retained_standalone_action')
need(module.__file__==str(ROOT/'comic_retained_standalone_action.py'),'bootstrap-canonical-action')
close(files,nodes)
auth_absence()
raise SystemExit(module.main(original_preimport=original,admission=admission))
