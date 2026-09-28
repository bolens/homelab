#!/usr/bin/env python3
"""Verify two already-built images share writer admission, using disposable state only."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


def main(mylar_image, worker_image):
    docker=shutil.which('docker')
    if not docker:raise RuntimeError('Docker CLI required')
    for image in (mylar_image,worker_image):
        subprocess.run([docker,'image','inspect',image],check=True,stdout=subprocess.DEVNULL)
    root=Path(tempfile.mkdtemp(prefix='mylar-writer-proof-'))
    uid,gid=(1000,1000) if os.geteuid()==0 else (os.geteuid(),os.getegid())
    os.chown(root,uid,gid)
    name='mylar-writer-proof-'+uuid.uuid4().hex
    running=False
    try:
        def command(image,mount,code,extra=()):
            return [docker,'run','--rm','--pull=never','--network=none','--read-only',
                '--user',f'{uid}:{gid}','--cap-drop=ALL','--security-opt=no-new-privileges',
                '--pids-limit=64','--memory=256m','--tmpfs','/tmp:rw,size=32m,mode=1777',
                '--mount',f'type=bind,src={root},dst={mount}',*extra,
                '--entrypoint','python3',image,'-c',code]
        native="import sys;sys.path.insert(0,'/app/mylar3/mylar');from media_writer import Writer,Busy\n"
        subprocess.run(command(mylar_image,'/native',native+"Writer('/native/protocol',create=True)"),check=True,timeout=30)
        worker="import sys;sys.path.insert(0,'/app');from media_writer import Writer\n"
        hold=worker+"import time\nw=Writer('/worker/protocol')\nwith w.hold(allow_pending=True):\n w.mark_pending();print('owned',flush=True);time.sleep(60)"
        running=True
        subprocess.run(command(worker_image,'/worker',hold,('-d','--name',name)),check=True,capture_output=True,timeout=30)
        deadline=time.monotonic()+20
        while True:
            logs=subprocess.run([docker,'logs',name],check=True,capture_output=True,text=True,timeout=10).stdout
            if 'owned' in logs:break
            if time.monotonic()>deadline:raise RuntimeError('Worker fixture did not acquire its lock')
            time.sleep(.1)
        blocked=native+"try:\n with Writer('/native/protocol').hold(timeout=.1):pass\nexcept Busy:sys.exit(23)\nraise RuntimeError('Concurrent writer admitted')"
        if subprocess.run(command(mylar_image,'/native',blocked),timeout=30).returncode!=23:
            raise RuntimeError('Expected writer admission to be blocked')
        subprocess.run([docker,'kill',name],check=True,capture_output=True,timeout=15)
        running=False
        # The operating-system lock is gone, but the durable marker must survive.
        if subprocess.run(command(mylar_image,'/native',blocked),timeout=30).returncode!=23:
            raise RuntimeError('Expected writer admission to be blocked')
        recover=worker+"w=Writer('/recovery/protocol')\nwith w.hold(allow_pending=True):w.clear_pending()"
        subprocess.run(command(worker_image,'/recovery',recover),check=True,timeout=30)
        subprocess.run(command(mylar_image,'/native',native+"with Writer('/native/protocol').hold(timeout=.1):pass"),check=True,timeout=30)
        print('PASS: cross-image exclusion, killed-worker fence, verified recovery admission')
    finally:
        if running:subprocess.run([docker,'rm','-f',name],check=False,capture_output=True,timeout=15)
        shutil.rmtree(root)


if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Usage: verify-coordination.py MYLAR_IMAGE NORMALIZER_IMAGE')
    main(*sys.argv[1:])
