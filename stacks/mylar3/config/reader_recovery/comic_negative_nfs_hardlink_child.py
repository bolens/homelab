"""Finite checked hardlink canary child; no socket, media or library grants."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import types

KERNEL_SHA='393d398e1e08ce147d4f8efa60879b99a910af582fbb6ae70e0f71cc0229d0bf'

def nine(z):
    return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)

def run(input_path,input_sha,source_sha,kernel_path):
    own=Path(__file__).absolute();kernel=Path(kernel_path);inp=Path(input_path)
    paths=(own,kernel,inp);files=tuple((str(p),nine(os.lstat(p))) for p in paths)
    nodes={}
    for p in paths:
        for q in p.parents:
            z=os.lstat(q)
            if not stat.S_ISDIR(z.st_mode):raise ValueError('child-ancestor')
            nodes[str(q)]=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
    def read(p,expected):
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            if nine(os.fstat(fd))!=expected or expected[8]!=1:raise ValueError('child-read-FD')
            raw=os.read(fd,1048577)
            if len(raw)>1048576 or nine(os.fstat(fd))!=expected:raise ValueError('child-read-bound')
            return raw
        finally:os.close(fd)
    ownraw,kraw,raw=(read(p,v) for p,(_,v) in zip(paths,files))
    if hashlib.sha256(ownraw).hexdigest()!=source_sha or hashlib.sha256(kraw).hexdigest()!=KERNEL_SHA or hashlib.sha256(raw).hexdigest()!=input_sha:raise ValueError('child-source')
    module=types.ModuleType('checked_hardlink_kernel');module.__file__=str(kernel)
    exec(compile(kraw,str(kernel),'exec'),module.__dict__)
    observation=module.run(dict(path=str(inp),sha256=input_sha,signature9=files[2][1]),dict(path=str(kernel),sha256=KERNEL_SHA,signature9=files[1][1]))
    value=observation.binding
    report=Path(json.loads(raw)['root'])/'result.json'
    report9=nine(os.lstat(report));report_raw=read(report,report9)
    root=report.parent
    names=('source/source.bin','source/collision.bin','target/foreign.bin','stage-intent.json','collision-intent.json','retire-intent.json','restore-intent.json','unstage-intent.json','result.json')
    facts={}
    for name in names:
        path=root/name;v=nine(os.lstat(path));content=read(path,v)
        facts[str(path)]=dict(signature9=v,sha256=hashlib.sha256(content).hexdigest())
    directories={name:nine(os.lstat(root/name)) for name in ('source','target')}
    root9=nine(os.lstat(root))
    ack=dict(version=1,kind='checked-hardlink-canary-child',source_sha256=source_sha,kernel_sha256=KERNEL_SHA,input_sha256=input_sha,
             report=dict(path=str(report),sha256=hashlib.sha256(report_raw).hexdigest(),signature9=report9),
             transitions=value['transitions'],facts=facts,directories=directories,root9=root9,actual_library_platform_verified=False,native_grant=False,publication_authority=False)
    encoded=json.dumps(ack,sort_keys=True,separators=(',',':')).encode()
    observation.close()
    for p,v in nodes.items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise ValueError('child-final-ancestor')
    for p,v in (*files,*((q,f['signature9']) for q,f in facts.items()),(str(root),root9),*((str(root/name),v) for name,v in directories.items())):
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise ValueError('child-final-source')
    return encoded

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--input-sha256',required=True);p.add_argument('--source-sha256',required=True);p.add_argument('--kernel',required=True)
    a=p.parse_args();print(run(a.input,a.input_sha256,a.source_sha256,a.kernel).decode())
