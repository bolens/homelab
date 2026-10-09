"""Owned disposable staging and existing-only Writer lease; no media grant.

This source does not contact Docker or an application. The lease child is for a
separately profile-verified disposable container. Ordinary CLI execution is off.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

WRITER_SHA = None
NAMES = frozenset(('source.bin', 'retained.bin', 'collision-source.bin', 'collision-destination.bin'))


class Held(ValueError):
    pass


def require(value, reason):
    if not value:
        raise Held(reason)


def sig(st):
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns,
            st.st_mode, st.st_uid, st.st_gid, st.st_nlink]


def stamp(path):
    return sig(os.lstat(path))


def canonical(path):
    require(type(path) in (str, type(Path('/'))), 'path-type')
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and p.resolve(strict=False) == p
            and not any(q.is_symlink() for q in (p, *p.parents)), 'canonical')
    return p


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def direct_ancestors(paths):
    out = {}
    for p in paths:
        for q in canonical(p).parents:
            v = stamp(q)
            require(stat.S_ISDIR(v[5]), 'ancestor-directory')
            out[q] = [v[i] for i in (0, 1, 5, 6, 7)]
    return out


def close_vector(leaves, ancestors, censuses, absent=()):
    # Freeze originals before any filesystem operation; successful loops contain
    # no application helpers. OS namespace changes still require owning review.
    file_items = tuple((str(p), tuple(v)) for p, v in leaves.items())
    node_items = tuple((str(p), tuple(v)) for p, v in ancestors.items())
    name_items = tuple((str(p), frozenset(v)) for p, v in censuses.items())
    missing = tuple(str(p) for p in absent)
    for p, expected in name_items:
        if frozenset(os.listdir(p)) != expected:
            raise Held('terminal-census')
    for p, expected in node_items:
        x = os.lstat(p)
        if (x.st_dev, x.st_ino, x.st_mode, x.st_uid, x.st_gid) != expected:
            raise Held('terminal-ancestor')
    for p, expected in file_items:
        x = os.lstat(p)
        if (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns,
            x.st_mode, x.st_uid, x.st_gid, x.st_nlink) != expected:
            raise Held('terminal-leaf')
    for p in missing:
        try:
            os.lstat(p)
        except FileNotFoundError:
            continue
        raise Held('terminal-owned-absence')


def regular_fact_at(fd, name):
    require(name in NAMES, 'fixed-leaf-name')
    f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        before = sig(os.fstat(f))
        require(stat.S_ISREG(before[5]) and before[6] == os.geteuid()
                and stat.S_IMODE(before[5]) == 0o600 and before[8] == 1
                and 0 < before[2] <= 4096, 'own-tiny-regular-leaf')
        raw = os.read(f, 4097)
        require(len(raw) == before[2] and sig(os.fstat(f)) == before
                and sig(os.stat(name, dir_fd=fd, follow_symlinks=False)) == before,
                'leaf-drift')
        return {'signature': before, 'sha256': digest(raw)}
    finally:
        os.close(f)


def binding(fd, path, identity):
    require(sig(os.fstat(fd))[:2] == identity
            and sig(os.lstat(path))[:2] == identity, 'directory-replaced')
    canonical(path)


def admit_parent(plan, roots, lease, mount_observer):
    """Create exactly one already-admitted absent parent using a bound FD.

    mount_observer is the owning parent's frozen findmnt verifier; this helper
    has no default observer or alternate mount fallback.
    """
    require(type(plan) is dict and set(plan) == {
        'path', 'grandparent_signature', 'expected_device', 'mount_identity'}, 'parent-plan')
    p = canonical(plan['path'])
    require(re.fullmatch(r'\.comic-nfs-private-[0-9a-f]{32}', p.name), 'parent-nonce')
    require(not os.path.lexists(p), 'parent-already-exists')
    require(roots and all(not p.is_relative_to(r) and not r.is_relative_to(p) for r in roots),
            'parent-protected-overlap')
    require(stamp(p.parent) == plan['grandparent_signature']
            and plan['expected_device'] == stamp(p.parent)[0], 'grandparent-drift')
    require(plan['mount_identity']['fstype'] == 'nfs4'
            and mount_observer(p.parent) == plan['mount_identity'], 'actual-nfs-mount')
    ancestors = direct_ancestors([p, *roots])
    rootstates = {r: stamp(r) for r in roots}
    forbidden_ids = {tuple(v[:2]) for v in rootstates.values()}
    require(not any(tuple(stamp(q)[:2]) in forbidden_ids for q in (p.parent, *p.parent.parents)),
            'physical-protected-alias')
    lease.pulse()
    close_vector(rootstates | {p.parent: plan['grandparent_signature']}, ancestors, {})
    fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(sig(os.fstat(fd)) == plan['grandparent_signature'], 'grandparent-fd')
        os.mkdir(p.name, 0o700, dir_fd=fd)
        os.fsync(fd)
        created = sig(os.stat(p.name, dir_fd=fd, follow_symlinks=False))
        # Root squash is a HOLD. Never chown/chmod an unexpected result.
        require(stat.S_ISDIR(created[5]) and created[6] == os.geteuid() == 1000
                and stat.S_IMODE(created[5]) == 0o700
                and created[0] == plan['expected_device'] and not os.listdir(p),
                'created-parent-owner-device-mode')
        lease.pulse()
        close_vector(rootstates | {p: created}, ancestors, {p: set()})
        return {'path': str(p), 'signature': created, 'grandparent_identity': stamp(p.parent)[:2], 'grandparent_node5': list(ancestors[p.parent])}
    finally:
        os.close(fd)


def cleanup_owned(parent, child, facts, roots, lease, stopped_child_proof):
    """Delete only a verified completed canary's exact owned tiny namespace.

    All validation precedes the first unlink. Failure never releases the lease
    or recurses, and the caller retains its external lifecycle freeze.
    """
    require(stopped_child_proof is True, 'stopped-child-required')
    require(type(parent) is dict and set(parent) == {'path', 'signature', 'grandparent_identity'},
            'parent-record')
    require(type(child) is dict and set(child) == {'path', 'signature'}, 'child-record')
    p = canonical(parent['path'])
    c = canonical(child['path'])
    require(c.parent == p and re.fullmatch(r'\.comic-nfs-probe-[0-9a-f]{32}', c.name), 'child-nonce')
    require(type(facts) is dict and set(facts) in (
        {'source.bin', 'collision-source.bin', 'collision-destination.bin'},
        {'retained.bin', 'collision-source.bin', 'collision-destination.bin'}), 'completed-fixture-census')
    require(all(not p.is_relative_to(r) and not r.is_relative_to(p) for r in roots), 'cleanup-protected')
    require(stamp(p)[:2] == parent['signature'][:2] and stamp(p.parent)[:2] == parent['grandparent_identity']
            and stamp(c) == child['signature'], 'cleanup-root-binding')
    require(stamp(p)[6] == stamp(c)[6] == os.geteuid() == 1000
            and stat.S_IMODE(stamp(p)[5]) == stat.S_IMODE(stamp(c)[5]) == 0o700,
            'cleanup-private')
    ancestors = direct_ancestors([p, c, *roots])
    original_nodes = tuple((str(q),tuple(v)) for q,v in ancestors.items())
    original_facts = tuple((name,tuple(f['signature'])) for name,f in facts.items())
    rootstates = {r: stamp(r) for r in roots}
    pf = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    cf = os.open(c, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    gf = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        binding(pf, p, parent['signature'][:2])
        binding(cf, c, child['signature'][:2])
        binding(gf, p.parent, parent['grandparent_identity'])
        require(set(os.listdir(pf)) == {c.name} and set(os.listdir(cf)) == set(facts), 'cleanup-namespace')
        require(all(regular_fact_at(cf, name) == f for name, f in facts.items()), 'cleanup-leaf-proof')
        lease.pulse()
        leaves = rootstates | {p: stamp(p), c: child['signature']}
        leaves.update({c / name: f['signature'] for name, f in facts.items()})
        close_vector(leaves, ancestors, {p: {c.name}, c: set(facts)})
        remaining = set(facts)
        for name, f in sorted(facts.items()):
            binding(cf, c, child['signature'][:2])
            require(set(os.listdir(cf)) == remaining, 'cleanup-partial-foreign-namespace')
            require(regular_fact_at(cf, name) == f, 'cleanup-next-leaf-proof')
            x = os.stat(name, dir_fd=cf, follow_symlinks=False)
            if [x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink] != f['signature']:
                raise Held('cleanup-terminal-next-leaf')
            # Every semantic/hash/binding callback is complete. Re-close all
            # remaining original leaves, roots, ancestors and bound namespace.
            for q,v in original_nodes:
                x=os.lstat(q)
                if (x.st_dev,x.st_ino,x.st_mode,x.st_uid,x.st_gid)!=v:raise Held('cleanup-terminal-ancestor')
            for q,v in rootstates.items():
                x=os.lstat(q)
                if [x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink]!=v:raise Held('cleanup-terminal-root')
            if set(os.listdir(pf))!={c.name} or set(os.listdir(cf))!=remaining:raise Held('cleanup-terminal-namespace')
            for q,v in original_facts:
                if q not in remaining:continue
                x=os.stat(q,dir_fd=cf,follow_symlinks=False)
                if (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink)!=v:raise Held('cleanup-terminal-leaf')
            os.unlink(name, dir_fd=cf)
            os.fsync(cf)
            remaining.remove(name)
        require(not os.listdir(cf), 'cleanup-child-nonempty')
        binding(pf, p, parent['signature'][:2])
        binding(cf, c, child['signature'][:2])
        x=os.stat(c.name,dir_fd=pf,follow_symlinks=False)
        v=child['signature']
        if (x.st_dev,x.st_ino,x.st_mode,x.st_uid,x.st_gid)!=(v[0],v[1],v[5],v[6],v[7]):raise Held('cleanup-child-final-identity')
        if os.listdir(cf):raise Held('cleanup-child-final-nonempty')
        os.rmdir(c.name, dir_fd=pf)
        os.fsync(pf)
        require(not os.listdir(pf), 'cleanup-parent-nonempty')
        binding(pf, p, parent['signature'][:2])
        binding(gf, p.parent, parent['grandparent_identity'])
        x=os.stat(p.name,dir_fd=gf,follow_symlinks=False)
        v=parent['signature']
        if (x.st_dev,x.st_ino,x.st_mode,x.st_uid,x.st_gid)!=(v[0],v[1],v[5],v[6],v[7]):raise Held('cleanup-parent-final-identity')
        if os.listdir(pf):raise Held('cleanup-parent-final-nonempty')
        os.rmdir(p.name, dir_fd=gf)
        os.fsync(gf)
        lease.pulse()
        terminal_result = {'owned_fixture_absence_verified': True, 'native_grant': False,
                'publication_authority': False, 'writer_lifecycle_resume_authorized': False}
        os.close(gf);gf=None
        os.close(cf);cf=None
        os.close(pf);pf=None
        # Descriptor-close callbacks have completed before final direct proof.
        close_vector(rootstates, {q: v for q, v in ancestors.items() if q != p}, {})
        for removed in (c, p):
            try:
                os.lstat(removed)
            except FileNotFoundError:
                continue
            raise Held('terminal-owned-absence')
        return terminal_result
    finally:
        if gf is not None:os.close(gf)
        if cf is not None:os.close(cf)
        if pf is not None:os.close(pf)


def namespace(root):
    root = canonical(root)
    require(stamp(root)[6] == os.geteuid() and stat.S_IMODE(stamp(root)[5]) == 0o700,
            'writer-private')
    names = set(os.listdir(root))
    require('writer-v1.lock' in names and names <= {
        'writer-v1.lock', 'normalizer-v1.pending', 'tagger-v2.pending', 'release-v1.pending',
        'publication-v1.json'},
        'writer-namespace')
    return ({name: stamp(root / name) for name in names}, stamp(root)[:2])


def lease_child(writer_source, writer_root, token, input_stream=sys.stdin, output_stream=sys.stdout, *, writer_sha256):
    """Blocking lease only. EOF/unknown commands fail closed; no marker writes."""
    require(type(writer_sha256) is str and re.fullmatch('[a-f0-9]{64}', writer_sha256), 'explicit-writer-source-pin')
    require(os.geteuid() == 1000 and re.fullmatch('[a-f0-9]{64}', token), 'lease-caller-token')
    src = canonical(writer_source)
    source_sig = stamp(src)
    initial_nodes = direct_ancestors([src,canonical(writer_root)])
    source_fd = os.open(src,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        require(sig(os.fstat(source_fd))==source_sig,'writer-source-fd')
        raw=os.read(source_fd,32*1024**2+1)
        require(len(raw)==source_sig[2] and len(raw)<=32*1024**2
                and digest(raw)==writer_sha256 and sig(os.fstat(source_fd))==source_sig,'writer-source-pin')
    finally:os.close(source_fd)
    require(stamp(src)==source_sig,'writer-source-pin')
    spec = importlib.util.spec_from_file_location('disposable_raw_writer', src)
    module = importlib.util.module_from_spec(spec)
    # Avoid bytecode or a later source read: execute the exact admitted bytes.
    exec(compile(raw, str(src), 'exec'), module.__dict__)
    root = canonical(writer_root)
    before, identity = namespace(root)
    ancestors = direct_ancestors([src, root])
    require(ancestors==initial_nodes,'writer-original-ancestor')
    writer = module.Writer(root, create=False)
    with writer.hold(allow_pending=True, allow_tagger_pending=True, allow_release_pending=True, timeout=30):
        def emit(state):
            require(namespace(root) == (before, identity) and stamp(src) == source_sig, 'lease-source-namespace-drift')
            value = {'version': 1, 'kind': 'owned-nfs-existing-writer-lease', 'token': token,
                     'state': state, 'writer_identity': identity, 'source_sha256': writer_sha256,
                     'markers_unchanged': True, 'native_grant': False, 'publication_authority': False}
            raw_ack = (json.dumps(value, sort_keys=True) + '\n').encode()
            ack_fd = output_stream.fileno()
            output_stream.flush()
            close_vector({src: source_sig, **{root / n: s for n, s in before.items()}}, ancestors, {root: set(before)})
            require(os.write(ack_fd, raw_ack) == len(raw_ack), 'lease-ack-short-write')
        emit('held')
        while True:
            line = input_stream.readline(1025)
            require(line and len(line) <= 1024, 'lease-channel-lost')
            command = json.loads(line)
            require(type(command) is dict and set(command) == {'token', 'action', 'owned_absence_verified'}
                    and command['token'] == token, 'lease-message')
            if command['action'] == 'pulse' and command['owned_absence_verified'] is False:
                emit('held')
            elif command['action'] == 'release' and command['owned_absence_verified'] is True:
                emit('release-reviewed')
                return
            else:
                raise Held('lease-unknown-ack-no-release')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lease-child', action='store_true')
    parser.add_argument('--writer-source')
    parser.add_argument('--writer-sha256')
    parser.add_argument('--writer-root')
    parser.add_argument('--token')
    args = parser.parse_args()
    if not args.lease_child:
        print(json.dumps({'executable': False, 'native_grant': False,
                          'publication_authority': False, 'application_execution': False}))
        return
    require(all((args.writer_source, args.writer_sha256, args.writer_root, args.token)), 'explicit-child-contract')
    lease_child(args.writer_source, args.writer_root, args.token, writer_sha256=args.writer_sha256)


if __name__ == '__main__':
    main()


def cleanup_hardlink_owned(parent, child, facts, directories, roots, lease):
    """Exact stopped-child hardlink namespace only; all evidence is retained outside it."""
    p=canonical(parent['path']);c=canonical(child['path'])
    required={'source/source.bin','source/collision.bin','target/foreign.bin',
              'stage-intent.json','collision-intent.json','retire-intent.json','restore-intent.json','unstage-intent.json','result.json'}
    require(c.parent==p and re.fullmatch(r'\.comic-nfs-probe-[0-9a-f]{32}',c.name),'hardlink-child')
    require(set(facts)==required and set(directories)=={'source','target'},'hardlink-fixed-namespace')
    require(all(not p.is_relative_to(r) and not r.is_relative_to(p) for r in roots),'hardlink-protected')
    parent_node=tuple(parent['signature'][i] for i in (0,1,5,6,7));grandparent_node=tuple(parent['grandparent_node5'])
    for q,v in ((p,parent_node),(p.parent,grandparent_node)):
        z=os.lstat(q)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('hardlink-cleanup-original-parent-node')
    initial={p:stamp(p),c:child['signature'],c/'source':directories['source'],c/'target':directories['target']}
    require(initial[p][:2]==parent['signature'][:2] and stamp(p.parent)[:2]==parent['grandparent_identity'],'hardlink-parent')
    nodes=direct_ancestors([p,c,c/'source'/ 'leaf',c/'target'/'leaf',*roots])
    for q,v in ((p,parent_node),(p.parent,grandparent_node)):
        require(tuple(nodes[q])==v,'hardlink-original-ancestor-conflict');nodes[q]=v
    rootstates={q:stamp(q) for q in roots}
    fdpaths=(p.parent,p,c,c/'source',c/'target');fds=[]
    try:
        for q in fdpaths:
            expected=initial.get(q,stamp(q))
            fd=os.open(q,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fds.append(fd)
            require(sig(os.fstat(fd))==expected,'hardlink-cleanup-original-FD')
        gf,pf,cf,sf,tf=fds
        originals={str(c/name):tuple(f['signature']) for name,f in facts.items()}
        remaining=set(required);removed=[]
        def raw():
            censuses={p:{c.name},c:{'source','target'}|{n for n in remaining if '/' not in n},
                      c/'source':{n.split('/')[1] for n in remaining if n.startswith('source/')},
                      c/'target':{n.split('/')[1] for n in remaining if n.startswith('target/')}}
            for q,names in censuses.items():
                if set(os.listdir(q))!=names:raise Held('hardlink-cleanup-census')
            for q,v in nodes.items():
                if q in removed:continue
                z=os.lstat(q)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(v):raise Held('hardlink-cleanup-node')
            for q,v in {**rootstates,**initial,**{Path(q):v for q,v in originals.items() if Path(q).relative_to(c).as_posix() in remaining}}.items():
                if q in removed:continue
                z=os.lstat(q)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(v):raise Held('hardlink-cleanup-full9')
            for fd,q in zip(fds,fdpaths):
                if q in initial and q not in removed:
                    z=os.fstat(fd)
                    if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(initial[q]):raise Held('hardlink-cleanup-FD9')
            for q in removed:
                try:os.lstat(q)
                except FileNotFoundError:continue
                raise Held('hardlink-cleanup-removed-present')
        # Bytes/hash reads all precede the first unlink and original closure.
        for name,f in facts.items():
            path=c/name;fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            try:
                v=sig(os.fstat(fd));require(v==f['signature'] and stat.S_ISREG(v[5]) and v[8]==1 and 0<v[2]<=65536,'hardlink-cleanup-leaf')
                payload=os.read(fd,65537);require(len(payload)==v[2] and digest(payload)==f['sha256'] and sig(os.fstat(fd))==v,'hardlink-cleanup-hash')
            finally:os.close(fd)
        lease.pulse();raw()
        for name in sorted(required):
            lease.pulse();raw()
            parentfd,base=(sf,name.split('/')[1]) if name.startswith('source/') else ((tf,name.split('/')[1]) if name.startswith('target/') else (cf,name))
            os.unlink(base,dir_fd=parentfd)
            q=c/name;remaining.remove(name);removed.append(q)
            directory=q.parent;initial[directory]=sig(os.fstat(parentfd))
            os.fsync(parentfd)
        # Remove fixed empty dirs then the original fixture and admitted parent.
        for q,parentfd,fd in ((c/'source',cf,sf),(c/'target',cf,tf),(c,pf,cf),(p,gf,pf)):
            lease.pulse()
            if os.listdir(fd):raise Held('hardlink-rmdir-notempty')
            # Inline closure with dynamic namespace before each directory syscall.
            for node,v in nodes.items():
                if node in removed:continue
                z=os.lstat(node)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(v):raise Held('hardlink-rmdir-node')
            for item,v in {**rootstates,**initial}.items():
                if item in removed:continue
                z=os.lstat(item)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(v):raise Held('hardlink-rmdir-full9')
            os.rmdir(q.name,dir_fd=parentfd);removed.append(q)
            if q.parent in initial:initial[q.parent]=sig(os.fstat(parentfd))
            os.fsync(parentfd)
        lease.pulse()
        for fd in fds:os.close(fd)
        fds.clear()
        result={'owned_fixture_absence_verified':True,'native_grant':False,'publication_authority':False,'writer_lifecycle_resume_authorized':False}
        for q,v in nodes.items():
            if q in removed:continue
            z=os.lstat(q)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(v):raise Held('hardlink-final-node')
        for q,v in rootstates.items():
            z=os.lstat(q)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(v):raise Held('hardlink-final-root')
        for q in removed:
            try:os.lstat(q)
            except FileNotFoundError:continue
            raise Held('hardlink-final-removed-present')
        return result
    finally:
        for fd in fds:os.close(fd)
