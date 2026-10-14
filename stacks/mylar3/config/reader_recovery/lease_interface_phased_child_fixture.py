"""Disposable actual UID1000 child interface, no NFS/factory/Parent grant."""
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
from comic_nfs_uid_child import Channel
from comic_nfs_lease_session import ChildLeaseInterface

if __name__=='__main__':
    output=Path(sys.argv[1]);output.mkdir(mode=0o700)
    channel=Channel(0,1,'b'*64,20)
    lease=ChildLeaseInterface(channel);lease.factory(output,channel.engine);lease.prepare();lease.acquire();lease.pulse()
    lease.release_after_absence((output/'owned-parent'/'owned-fixture',output/'owned-parent'))
    channel.send('nfs-done',dict(uid=os.geteuid(),released=lease.released))
