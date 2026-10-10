"""Explicit build-only standalone controls; original public tree remains read-only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT=Path(__file__).absolute().parent
HOST=(('test_standalone_backup.py',24),('test_standalone_parent.py',28),
      ('test_standalone_runtime_seals.py',6),('test_standalone_bodies.py',11),
      ('test_standalone_publication.py',11),('test_standalone_directory_joins.py',31))


def full(s):
    return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--family',choices=('all','mechanical'),default='all');args=parser.parse_args()
    manifest=ROOT/'standalone_control_sources.json';stamp=manifest.lstat();original=full(stamp)
    if not stat.S_ISREG(stamp.st_mode) or stamp.st_nlink!=1 or not 0<stamp.st_size<=1024**2:raise ValueError('Standalone fixture manifest type/bound')
    nodes={}
    # Original manifest ancestors precede the first read/decode/helper callback.
    for ancestor in (manifest.parent,*manifest.parent.parents):
        z=os.lstat(ancestor);primitive=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
        if not stat.S_ISDIR(z.st_mode):raise ValueError('Standalone manifest ancestor type')
        nodes[ancestor]=primitive
    fd=os.open(manifest,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        if full(os.fstat(fd))!=original:raise ValueError('Standalone manifest original FD')
        chunks=[]
        while True:
            chunk=os.read(fd,65536)
            if not chunk:break
            chunks.append(chunk)
        raw=b''.join(chunks)
        if full(os.fstat(fd))!=original:raise ValueError('Standalone manifest read drift')
    finally:os.close(fd)
    rows=json.loads(raw)
    if full(manifest.lstat())!=original or not isinstance(rows,list) or not 1<=len(rows)<=512:raise ValueError('Standalone fixture manifest changed')
    leaves={manifest:original};seen=set();targets=set();total=0
    for row in rows:
        if set(row)!= {'path','target','sha256'}:raise ValueError('Standalone fixture schema')
        source=Path(row['path']);target=Path(row['target'])
        if source.is_absolute() or target.is_absolute() or '..' in source.parts or '..' in target.parts or str(target) in targets:raise ValueError('Standalone fixture aliases')
        if str(source) in seen and not (str(source)=='reader_recovery/comic_retained_standalone_action.py' and str(target)=='comic_retained_standalone_action.py'):
            raise ValueError('Standalone fixture duplicate source')
        seen.add(str(source));targets.add(str(target));path=ROOT/source;s=path.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:raise ValueError('Standalone fixture type')
        if path in leaves and leaves[path]!=full(s):raise ValueError('Standalone duplicate original conflict')
        leaves[path]=full(s);total+=s.st_size
        for ancestor in (path.parent,*path.parent.parents):
            fact=ancestor.lstat();primitive=(fact.st_dev,fact.st_ino,fact.st_mode,fact.st_uid,fact.st_gid)
            if not stat.S_ISDIR(fact.st_mode) or (ancestor in nodes and nodes[ancestor]!=primitive):raise ValueError('Standalone fixture ancestor conflict')
            nodes[ancestor]=primitive
    if total>64*1024**2:raise ValueError('Standalone public fixture size ceiling')
    with tempfile.TemporaryDirectory(prefix='mylar-standalone-controls-') as directory:
        private=Path(directory)
        for row in rows:
            source=ROOT/row['path'];fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
            try:
                if full(os.fstat(fd))!=leaves[source]:raise ValueError('Standalone fixture original FD')
                chunks=[]
                while True:
                    chunk=os.read(fd,65536)
                    if not chunk:break
                    chunks.append(chunk)
                data=b''.join(chunks)
                if full(os.fstat(fd))!=leaves[source]:raise ValueError('Standalone fixture read drift')
            finally:os.close(fd)
            if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Standalone fixture source pin: '+row['path'])
            destination=private/row['target'];destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data);os.chmod(destination,0o600)
        def run(argv,count):
            result=subprocess.run(argv,cwd=private,capture_output=True,text=True)
            sys.stdout.write(result.stdout);sys.stderr.write(result.stderr)
            found=re.search(r'Ran (\d+) tests? in',result.stderr)
            if result.returncode or found is None or int(found.group(1))!=count or 'skipped=' in result.stderr:raise ValueError('Standalone owning suite count/failure/skip')
        run([sys.executable,'-I','-B','-c',"import sys,unittest;sys.path.insert(0,'.');r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_publication_standalone_installation'));raise SystemExit(not r.wasSuccessful())"],7)
        run([sys.executable,'-I','-B',str(private/'test_standalone_gate.py')],2)
        for name,count in HOST:run([sys.executable,'-I','-B',str(private/'reader_recovery'/name)],count)
        if args.family=='all':
            run([sys.executable,'-I','-B','-c',"import sys,unittest;sys.path.insert(0,'.');r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(['test_publication_retained_standalone','test_standalone_pack_report_deny','test_standalone_resources']));raise SystemExit(not r.wasSuccessful())"],56)
        else:print('Native standalone 56 controls unproved: optional archive backend absent.',flush=True)
    # Last subprocess/output/temp cleanup helpers precede complete original public closure.
    for path,expected in nodes.items():
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)!=expected:raise ValueError('Standalone public ancestor final drift')
    for path,expected in leaves.items():
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)!=expected:raise ValueError('Standalone public leaf final drift')


if __name__=='__main__':main()
