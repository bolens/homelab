"""Disabled genuine Boot/typed-binder fixtures; disposable configuration only."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import resource
import secrets
import subprocess
import sys
import types
ACTIVATE = False
OUTPUT = None
SOURCE = Path(__file__).parent
PINS = {'KomgaEffectiveScope.class': '5097f1e28c15fc54fcbda0d8d09f7cfbf916b421d1327906c181cf337ce52555', 'KomgaEffectiveScope$Held.class': '1938cba2e7e14fd8d754dda90a0f45c0f532772031e0b0cf3204609877829d41', 'KomgaClasspathMetadata.class': '72c3422b8f6bd85d8a1e8cf26567a0080a20ed087020328dd2a0aeb1a4319fb9', 'TargetEffectiveScopeCase.class': '0ce53c0614c4c6180f3324403012b72cfbbb603627b56d74c2305daacedc59df', 'TargetEffectiveScopeCase$Observation.class': '6c3166e0b04b3cf65ae66f079ce659548a6b107d5c12cf154614952fbd69c559', 'owned.py': 'cef5caffab6a5ccabe4ba58b5ace158d3b81a332c104351255eb2e16993efa8c'}
IMAGE = None
CASES = ('defaults', 'precedence', 'profile', 'import', 'unsupported-tree', 'changed-config', 'uncaptured-default', 'explicit-default', 'inactive-default', 'heap-env')
CLASSES = ('KomgaEffectiveScope.class', 'KomgaEffectiveScope$Held.class', 'KomgaClasspathMetadata.class', 'TargetEffectiveScopeCase.class', 'TargetEffectiveScopeCase$Observation.class')
TMPFS = 'rw,nosuid,nodev,noexec,size=4194304,uid=1000,gid=1000,mode=0700'


def command(name, token, cid, code, case):
    assert case in CASES
    return ['/usr/bin/docker', 'run', '--name', name, '--label', 'com.homelab.isolated-verification=' + token,
            '--cidfile', str(cid), '--pull', 'never', '--read-only', '--network', 'none', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', '1000:1000', '--memory', '512m', '--memory-swap', '512m',
            '--pids-limit', '64', '--no-healthcheck', '--tmpfs', '/config:' + TMPFS,
            *[v for n in CLASSES for v in ('--volume', str(code / n) + ':/checks/' + n + ':ro')],
            '--entrypoint', 'java', IMAGE, '-XX:-UsePerfData', '-cp', '/checks:/app/application.jar',
            'TargetEffectiveScopeCase', case]


def profile(row, name, token, code, case, image_env):
    assert row['Image'] == IMAGE and row['Config']['Image'] == IMAGE and row['Name'] == '/' + name, 'owned-image'
    c, h, state = row['Config'], row['HostConfig'], row['State']
    assert c['User'] == '1000:1000' and c['WorkingDir'] == '/app' and c['Entrypoint'] == ['java'] and c['Cmd'] == ['-XX:-UsePerfData', '-cp', '/checks:/app/application.jar', 'TargetEffectiveScopeCase', case], 'owned-command'
    assert c['Env'] == image_env and c.get('Labels', {}).get('com.homelab.isolated-verification') == token and c['Healthcheck'] == {'Test': ['NONE']}, 'owned-environment'
    assert h['ReadonlyRootfs'] is True and h['NetworkMode'] == 'none' and h['CapDrop'] == ['ALL'] and h['SecurityOpt'] == ['no-new-privileges'] and h['Privileged'] is False, 'isolation'
    assert h['Memory'] == h['MemorySwap'] == 536870912 and h['PidsLimit'] == 64, 'bounded-resources'
    assert type(h.get('Binds')) is list and Counter(h['Binds']) == Counter(str(code / n) + ':/checks/' + n + ':ro' for n in CLASSES) and h.get('Tmpfs') == {'/config': TMPFS}, 'sole-public-code-and-disposable-config'
    assert not h.get('Mounts') and not h.get('Devices') and not h.get('DeviceRequests') and not h.get('PortBindings') and h.get('PublishAllPorts') is False, 'no-extra-access'
    binds = [m for m in row['Mounts'] if m['Type'] == 'bind']
    assert len(binds) == len(CLASSES) and {(m['Source'], m['Destination'], m['RW']) for m in binds} == {(str(code / n), '/checks/' + n, False) for n in CLASSES}, 'owned-bind-profile'
    others = [m for m in row['Mounts'] if m['Type'] != 'bind']
    # HostConfig.Tmpfs is authoritative; actual Docker may omit it from Mounts.
    assert not others or (len(others) == 1 and others[0]['Type'] == 'tmpfs' and others[0]['Destination'] == '/config' and others[0]['RW'] is True), 'owned-tmpfs-profile'
    assert state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0 and not state.get('OOMKilled'), 'owned-exited'


def case_output(observed, case):
    return observed == ('TARGET_CASE ' + case + ' PASS; CONFIGURED_ACCEPTANCE false\n').encode()


def _main():
    assert ACTIVATE is True and IMAGE is not None and OUTPUT is not None and PINS is not None and os.geteuid() == 0 and sys.flags.isolated and sys.dont_write_bytecode, 'disabled'
    assert set(PINS) == {*CLASSES, 'owned.py'}, 'supplier-set'
    # Use the already reviewed supplier/FD-original primitives, compiled from pinned bytes.
    source = SOURCE / 'owned.py'
    parent_frames = {}
    for q in (source.parent, *source.parent.parents):
        z = q.lstat(); assert __import__('stat').S_ISDIR(z.st_mode), 'source-parent'
        parent_frames[q] = (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid)
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        z = os.fstat(fd); source_frame = (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink)
        assert __import__('stat').S_ISREG(z.st_mode) and z.st_nlink == 1 and (z.st_uid, z.st_gid) == (1000, 1000) and __import__('stat').S_IMODE(z.st_mode) == 0o600 and z.st_size <= 131072, 'owned-source-header'
        raw = os.read(fd, 131073); after = os.fstat(fd); named = source.lstat()
        assert len(raw) == z.st_size and (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns,after.st_mode,after.st_uid,after.st_gid,after.st_nlink) == (named.st_dev,named.st_ino,named.st_size,named.st_mtime_ns,named.st_ctime_ns,named.st_mode,named.st_uid,named.st_gid,named.st_nlink) == source_frame and hashlib.sha256(raw).hexdigest() == PINS['owned.py'], 'owned-source-pin'
    finally: os.close(fd)
    owned = types.ModuleType('_effective_target_owned')
    owned.__file__ = str(SOURCE / 'owned.py')
    exec(compile(raw, owned.__file__, 'exec'), owned.__dict__)
    frames, parents, sources = {source: source_frame}, dict(parent_frames), {}
    for name, pin in PINS.items():
        p = SOURCE / name
        for q in (p.parent, *p.parent.parents):
            z = q.lstat(); assert __import__('stat').S_ISDIR(z.st_mode); assert parents.setdefault(q, owned.five(z)) == owned.five(z)
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            z = os.fstat(fd); data = os.read(fd, 131073)
            assert __import__('stat').S_ISREG(z.st_mode) and z.st_nlink == 1 and (z.st_uid, z.st_gid) == (1000, 1000) and __import__('stat').S_IMODE(z.st_mode) == 0o600 and len(data) == z.st_size <= 131072 and owned.nine(os.fstat(fd)) == owned.nine(p.lstat()) == owned.nine(z) and hashlib.sha256(data).hexdigest() == pin, 'public-supplier'
            assert frames.setdefault(p, owned.nine(z)) == owned.nine(z), 'original-source-frame'
            sources[name] = data
        finally: os.close(fd)
    def close():
        assert all(owned.five(p.lstat()) == v for p, v in parents.items()) and all(owned.nine(p.lstat()) == v for p, v in frames.items()), 'original-suppliers'
    close()
    image = json.loads(subprocess.run(['/usr/bin/docker', 'image', 'inspect', IMAGE], capture_output=True, check=True, timeout=30).stdout)
    assert len(image) == 1 and image[0]['Id'] == IMAGE and image[0]['Os'] == 'linux' and image[0]['Architecture'] == 'amd64' and image[0]['Config']['WorkingDir'] == '/app' and set(image[0]['Config'].get('Volumes') or {}) == {'/config'}, 'public-image'
    env = image[0]['Config']['Env']; assert not any(v.split('=', 1)[0] in ('JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS') for v in env), 'no-image-agents'
    class Output(owned.JarOutput):
        NAMES = {*CLASSES, 'export.cid', 'target.stdout', 'target.stderr', 'result.private.json'}
    root = Path(OUTPUT)
    assert root.is_absolute() and root.parent == SOURCE.parent and __import__('re').fullmatch('komga-effective-target-[a-f0-9]{32}', root.name), 'finite-output-prefix'
    assert not os.path.lexists(root) and not any(os.path.lexists(root.with_name(root.name + '-' + case)) for case in CASES), 'fresh-case-outputs'
    def outer_close():
        close()
    results = []
    try:
        for case in CASES:
            close(); outer_close(); out = Output(root.with_name(root.name + '-' + case))
            name = 'komga-effective-case-' + secrets.token_hex(16); token = name.removeprefix('komga-effective-case-')
            try:
                for leaf in CLASSES:
                    out.write(leaf, sources[leaf]); fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=out.fd)
                    try: os.fchmod(fd, 0o444); out.files[leaf] = owned.nine(os.fstat(fd))
                    finally: os.close(fd)
                assert owned.inspect(name) is None, 'fresh-test-name'; close(); out.close(); outer_close()
                stdout, stderr = out.create('target.stdout'), out.create('target.stderr')
                result = None
                def limit(): resource.setrlimit(resource.RLIMIT_FSIZE, (2097152, 2097152))
                try:
                    result = subprocess.run(command(name, token, Path('/proc/self/fd') / str(out.fd) / 'export.cid', out.path, case), stdout=stdout, stderr=stderr, timeout=120, preexec_fn=limit, umask=0o077, pass_fds=(out.fd,))
                finally:
                    out.close(allow_cid=True); out.seal('target.stdout', 2097152); out.seal('target.stderr', 2097152)
                out.cid(); close(); outer_close(); row = owned.inspect(name); profile(row, name, token, out.path, case, env); out.close()
                # Exact exited identity/profile precedes non-force cleanup, including refused cases.
                raw_cid = (Path('/proc/self/fd') / str(out.fd) / 'export.cid').read_bytes().rstrip(b'\n')
                assert raw_cid == row['Id'].encode(), 'owned-cid'
                subprocess.run(['/usr/bin/docker', 'container', 'rm', '--volumes', row['Id']], capture_output=True, check=True, timeout=30)
                assert owned.inspect(name) is None, 'owned-cleanup'; close(); out.close(); outer_close()
                observed = (Path('/proc/self/fd') / str(out.fd) / 'target.stdout').read_bytes()
                assert result.returncode == row['State']['ExitCode'] == 0 and case_output(observed, case), 'genuine-target-case-refused'
                value = dict(case=case, genuine_boot_case_passed=True, configured_acceptance=False, application_context_started=False, owned_exited_cleanup=True)
                out.write('result.private.json', (json.dumps(value, sort_keys=True) + '\n').encode()); close(); out.close(); outer_close(); results.append(value)
            finally:
                primary = sys.exc_info()[1]
                try: out.release()
                except BaseException:
                    if primary is None: raise
        assert len(results) == 10; close(); outer_close()
        print(json.dumps(dict(genuine_boot_cases_passed=10, configured_acceptance=False, application_context_started=False, live_mounts=False)), flush=True)
    finally:
        primary = sys.exc_info()[1]
        try: close()
        except BaseException:
            if primary is None: raise


def failure_summary(error):
    trusted={__file__:'target-runner',str(SOURCE/'owned.py'):'owned-output'}
    frames=[];trace=error.__traceback__
    while trace is not None:
        role=trusted.get(trace.tb_frame.f_code.co_filename)
        if role is not None:frames.append(dict(source=role,function=trace.tb_frame.f_code.co_name,line=trace.tb_lineno))
        trace=trace.tb_next
    codes={'disabled','supplier-set','public-supplier','original-source-frame','original-suppliers','public-image','no-image-agents','finite-output-prefix','fresh-case-outputs','fresh-test-name','owned-cid','owned-cleanup','genuine-target-case-refused','owned-image','owned-command','owned-environment','isolation','bounded-resources','sole-public-code-and-disposable-config','no-extra-access','owned-bind-profile','owned-tmpfs-profile','owned-exited','parent-original','parent-fd','output-original','output-namespace','output-leaf-original','output-open-original','output-leaf','output-file-owner','output-bounded','owned-cid-leaf'}
    code=error.args[0] if len(error.args)==1 and type(error.args[0]) is str and error.args[0] in codes else 'unclassified'
    kind=type(error).__name__ if type(error).__name__ in {'AssertionError','ValueError','OSError','RuntimeError','TimeoutExpired','CalledProcessError','FileNotFoundError','PermissionError'} else 'held'
    return dict(kind='komga-target-fixed-failure-v1',failure_type=kind,fixed_code=code,trusted_frames=frames,configured_acceptance=False)


def main():
    try:return _main()
    except BaseException as error:
        print(json.dumps(failure_summary(error),sort_keys=True),file=sys.stderr,flush=True)
        raise


if __name__ == '__main__': main()
