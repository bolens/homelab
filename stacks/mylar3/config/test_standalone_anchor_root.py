"""Disposable image-build fixed-root fixture; never an operational provisioning CLI.

Root-only, explicit invocation, initially absent fixed roots. Public RFC8032
fixture key is read from the unchanged authenticated test fixture. No Docker,
application state, signing, authentication grant or retained acceptance occurs.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

ROOT=Path(__file__).parent
HOST=ROOT/'standalone_launch_host'


def main():
    if sys.argv[1:]!=['--disposable-build-fixture'] or os.geteuid()!=0:
        raise ValueError('explicit-root-disposable-build-fixture-required')
    roots=(Path('/etc/mylar-publication-launch'),Path('/usr/local/lib/mylar-publication-launch'),Path('/var/lib/mylar-publication-launch'))
    if any(os.path.lexists(p) for p in roots):raise ValueError('fixed-fixture-root-already-present')
    files={};dirs={}
    def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
    def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    def directory(p):
        os.mkdir(p,0o700);dirs[p]=five(os.lstat(p))
    def write(p,raw,mode):
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            view=memoryview(raw)
            while view:
                n=os.write(fd,view)
                if n<=0:raise ValueError('fixture-short-write')
                view=view[n:]
            os.fchmod(fd,mode);os.fsync(fd);files[p]=nine(os.fstat(fd))
        finally:os.close(fd)
    def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    try:
        for p in roots:directory(p)
        etc,package,keyroot=roots
        for name in ('reviewed-child',):directory(etc/name)
        for path in HOST.iterdir():
            if path.name in ('private_crypto.py','comic_reader_backup_primitives.py','comic_retained_standalone_backup.py','comic_retained_standalone_parent.py','comic_retained_standalone_broker.py','comic_native_process_probe.py','publication_native_configured_scope.py','BOOTSTRAP.py'):
                write(package/path.name,path.read_bytes(),0o444)
        spec=importlib.util.spec_from_file_location('fixed_installed_broker',package/'comic_retained_standalone_broker.py')
        broker=importlib.util.module_from_spec(spec);spec.loader.exec_module(broker)
        fixture=ast.parse((ROOT/'test_fixtures/authenticated_standalone/tests/test_fixed_broker.py').read_bytes())
        keys={node.targets[0].id:bytes.fromhex(ast.literal_eval(node.value.args[0])) for node in fixture.body if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('PUBLIC','DER')}
        write(keyroot/'root-signing-ed25519.der',keys['DER'],0o600)
        inventory=dict(version=1,kind='standalone-leaf-inventory-v1',sources={**{'/opt/mylar-publication-launch/auth/'+n:'1'*64 for n in ('standalone_launch_auth.py','v3_auth_core.py','private_crypto.py')},**{'/app/mylar3/mylar/public_fixture_'+str(i)+'.py':'2'*64 for i in range(9)}})
        inventory_raw=canonical(inventory)
        host_sources={n:sha((package/n).read_bytes()) for n in broker.NAMES}
        document=dict(version=1,kind='standalone-root-deployment-v1',deployment='a'*64,image='b'*64,profile=broker.LOGICAL_PROFILE_SHA,runtime_profile_sha256='c'*64,broker_sources=sha(canonical(host_sources)),parent_sha256=host_sources['comic_retained_standalone_parent.py'],bootstrap_sha256=host_sources['BOOTSTRAP.py'],inventory_sha256=sha(inventory_raw),key_sha256=sha(keys['PUBLIC']),public_der=keys['PUBLIC'].hex(),host_sources=host_sources,daemon_sources={'/app/mylar3/mylar/worker_health.py':'d'*64,'/app/mylar3/mylar/native_writers.py':'e'*64},ids=dict(native='1'*64,reader='2'*64,worker='3'*64))
        anchor=dict(version=1,kind='standalone-installation-anchor-v1',**{k:document[k] for k in ('deployment','profile','broker_sources','parent_sha256','bootstrap_sha256','inventory_sha256','key_sha256')})
        anchor_raw=canonical(anchor);document['anchor_sha256']=sha(anchor_raw);doc_raw=canonical(document)
        write(etc/'deployment-v1.json',doc_raw,0o600)
        write(etc/'enrollment-v1.json',canonical(dict(version=1,kind='standalone-root-enrollment-v1',deployment_sha256=sha(doc_raw))),0o600)
        for name,raw in zip(broker.ANCHOR_NAMES,(anchor_raw,inventory_raw,keys['PUBLIC'])):write(etc/'reviewed-child'/name,raw,0o444)
        result=broker.provision_original_anchors()
        dirs[etc/'child']=five(os.lstat(etc/'child'))
        for name in broker.ANCHOR_NAMES:files[etc/'child'/name]=nine(os.lstat(etc/'child'/name))
        assert result==dict(provisioned_public_anchors=True,activation=False)
        installation=broker.load_original_installation();installation.close()
        assert Path(broker.__file__)==package/'comic_retained_standalone_broker.py'
        for name in broker.ANCHOR_NAMES:
            assert (etc/'child'/name).read_bytes()==(etc/'reviewed-child'/name).read_bytes()
            assert os.lstat(etc/'child'/name).st_uid==0 and stat.S_IMODE(os.lstat(etc/'child'/name).st_mode)==0o444
        broker.provision_original_anchors();installation.close()
        layout_spec=importlib.util.spec_from_file_location('original_auth_layout',ROOT/'patch_publication_launch_auth.py')
        layout=importlib.util.module_from_spec(layout_spec);layout_spec.loader.exec_module(layout)
        auth=Path('/opt/mylar-publication-launch/auth')
        layout.verify_installed(auth)
        for name in broker.ANCHOR_NAMES:write(auth.parent/name,b'',0o444)
        layout.verify_required_targets(auth)

    finally:
        # Unknown children or identity drift leave disposable fixture for review.
        for path,original in files.items():
            if nine(os.lstat(path))!=original:raise ValueError('fixture-original-file-drift')
        for path,original in dirs.items():
            if five(os.lstat(path))!=original:raise ValueError('fixture-original-directory-drift')
            expected={p.name for p in (*files,*dirs) if p.parent==path}
            if set(os.listdir(path))!=expected:raise ValueError('fixture-foreign-child')
        for path in files:os.unlink(path)
        for path in sorted(dirs,key=lambda p:len(p.parts),reverse=True):os.rmdir(path)
    print(json.dumps(dict(actual_root_anchors=True,actual_installed_broker_load=True,fixture_enrollment_only=True,docker_mounts_executed=False,authentication_acceptance=False,retained_ack=False,cleanup=True),sort_keys=True))


if __name__=='__main__':main()
