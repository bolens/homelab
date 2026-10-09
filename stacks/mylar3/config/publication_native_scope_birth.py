"""Selected-child original metadata birth. No SDK/Writer or publication grant."""
import copy
import hashlib
import os
from pathlib import Path
import secrets
import select
import sys
import threading
import time
import weakref
from . import publication_reader_lifecycle as life
from . import publication_native_configured_scope as scope

SOURCE = Path('/app/mylar3/mylar/publication_native_scope_birth.py')
_KEY = object()
_SEALS = weakref.WeakKeyDictionary()


def check(value, reason):
    if not value:
        raise life.Held(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def installed_source(expected):
    path = Path(__file__)
    check(path == SOURCE and path.resolve() == path, 'birth-installed-source')
    signature = scope.nine(path.lstat())
    nodes = scope.ancestors([path])
    scope.bounded_read(path, expected, signature, nodes)
    return dict(path=str(path), sha256=expected, signature9=signature), nodes


def normalized(value):
    check(all(k in value for k in ('reader', 'native', 'worker', 'child_mounts',
                                   'child_source_sha256', 'child_image')), 'birth-extended-parent-required')
    life.require(value['reader']['State']['Running'] is False
                 and value['reader']['State']['Pid'] == 0, 'birth-reader-not-stopped')
    return dict(reader=copy.deepcopy(value['reader']), native=scope.observed_native(value['native']),
                worker=scope.observed_worker(value['worker']), child_mounts=copy.deepcopy(value['child_mounts']),
                child_source_sha256=value['child_source_sha256'], child_image=value['child_image'])


def merge_nodes(target, incoming):
    for path, vector in incoming.items():
        check(path not in target or target[path] == vector, 'birth-original-ancestor-conflict')
        target[path] = copy.deepcopy(vector)


def commit(channel, binding, birth):
    """One source-bound commit on the SAME original inherited pipe sequence."""
    original = channel.binding()
    channel.seq += 1
    token = secrets.token_hex(32)
    request = dict(protocol='reader-lifecycle-pipe-v1', type='birth-commit',
        nonce=binding['nonce'], input_sha256=binding['input_sha256'],
        parent_sha256=binding['parent_sha256'], sequence=channel.seq, challenge=token,
        birth=copy.deepcopy(birth))
    raw = life.encoded(request) + b'\n'
    check(os.write(channel.output, raw) == len(raw), 'birth-pipe-short-write')
    end = time.monotonic() + 5
    buffer = bytearray()
    while not buffer.endswith(b'\n'):
        check(time.monotonic() < end and len(buffer) < life.FRAME_MAX, 'birth-pipe-bound')
        ready = select.select([channel.input], [], [], max(0, end - time.monotonic()))[0]
        check(ready, 'birth-pipe-timeout')
        block = os.read(channel.input, 1)
        check(block, 'birth-parent-EOF')
        buffer.extend(block)
    reply = life.decoded(buffer)
    expected_keys = set(request) | {'lifecycle', 'execution_authority', 'publication_acceptance',
        'reader', 'native', 'worker', 'child_mounts', 'child_source_sha256', 'child_image'}
    check(set(reply) == expected_keys, 'birth-response-schema')
    check(all(reply[k] == v for k, v in request.items() if k != 'type')
          and reply['type'] == 'birth-accepted', 'birth-response-binding')
    check(reply['execution_authority'] is False and reply['publication_acceptance'] is False,
          'birth-response-no-rights')
    check(channel.binding() == original, 'birth-original-pipe-CAS')
    return reply


class BirthMetadata:
    """One-use original vectors; never serialized into a custody capability."""
    def __init__(self, key, channel, binding, files, nodes, lifecycle_ref, source_sha):
        check(key is _KEY, 'birth-owning-factory')
        self.channel = channel
        self.channel_seal = channel.binding()
        self.binding = copy.deepcopy(binding)
        self.files = copy.deepcopy(files)
        self.nodes = copy.deepcopy(nodes)
        self.lifecycle_ref = copy.deepcopy(lifecycle_ref)
        self.source_sha = source_sha
        self.thread = threading.get_ident()
        self.used = False
        self.seal = self.core()
        _SEALS[self] = self.seal

    def core(self):
        return digest(life.encoded(dict(channel=id(self.channel), channel_seal=self.channel_seal,
            binding=self.binding, files={str(p):v for p,v in self.files.items()},
            nodes={str(p):v for p,v in self.nodes.items()}, lifecycle_ref=self.lifecycle_ref,
            source_sha=self.source_sha, thread=self.thread, used=self.used)))

    def original(self):
        expected = _SEALS.get(self)
        check(expected is not None and self.core() == self.seal == expected
              and self.thread == threading.get_ident() and not self.used, 'birth-original-token')
        check(type(self.channel) is life.ParentPipe and self.channel.binding() == self.channel_seal,
              'birth-original-channel')
        files, nodes = copy.deepcopy(self.files), copy.deepcopy(self.nodes)
        life.passive(files, nodes)
        check(self.core() == self.seal == _SEALS.get(self), 'birth-token-after-closure')
        return copy.deepcopy(self.binding), files, nodes, copy.deepcopy(self.lifecycle_ref), self.channel

    def consume(self):
        result = self.original()
        self.used = True
        self.seal = self.core()
        _SEALS[self] = self.seal
        return result


def from_checked_parent(input_path, input_sha, nonce, *, parent_sha, argv):
    """Run before lifecycle construction, in the actual direct provider process."""
    check(all(scope.digest(v) for v in (input_sha, nonce, parent_sha)), 'birth-invocation-digests')
    check(list(argv) == list(sys.orig_argv), 'birth-actual-provider-argv')
    channel = life.ParentPipe()
    original_channel = channel.binding()
    binding = dict(input_path=str(life.canonical(input_path)), input_sha256=input_sha,
        parent_sha256=parent_sha, command=list(argv), nonce=nonce)
    raw, input_fact = life.read(binding['input_path'], input_sha)
    life.decoded(raw)
    seed_path = Path(input_path).with_suffix('.birth.json')
    raw, seed_fact = life.read(seed_path)
    seed_sha = digest(raw)
    seed = life.decoded(raw)
    check(set(seed) == {'version', 'kind', 'invocation', 'parent_source', 'birth_source',
        'config', 'worker_library', 'selected_image'} and type(seed['version']) is int
        and seed['version'] == 1 and seed['kind'] == 'selected-child-native-scope-birth', 'birth-seed-schema')
    invocation = seed['invocation']
    check(set(invocation) == set(binding) | {'provider_sha256'}
          and all(invocation[k] == v for k,v in binding.items()), 'birth-original-invocation')
    check(set(seed['birth_source']) == {'path','sha256'} and seed['birth_source']['path'] == str(SOURCE),
          'birth-fixed-source')
    source_sha = seed['birth_source']['sha256']
    check(scope.digest(source_sha), 'birth-source-digest')
    source_ref, source_nodes = installed_source(source_sha)
    files = {Path(input_path):input_fact, seed_path:seed_fact, Path(source_ref['path']):source_ref['signature9']}
    nodes = scope.ancestors([input_path, seed_path])
    merge_nodes(nodes, source_nodes)
    parent = seed['parent_source']
    check(set(parent) == {'path','sha256','signature9'} and parent['sha256'] == parent_sha, 'birth-parent-source')
    _, parent_fact = life.read(parent['path'], parent_sha)
    check(parent_fact == parent['signature9'], 'birth-parent-incarnation')
    files[Path(parent['path'])] = parent_fact
    merge_nodes(nodes, scope.ancestors([parent['path']]))
    observed = copy.deepcopy(channel.challenge(nonce, input_sha, parent_sha))
    captured = normalized(observed)
    check(captured['child_source_sha256'] == invocation['provider_sha256']
          and captured['child_image'] == seed['selected_image'], 'birth-selected-provider-image')
    native, worker, mounts = copy.deepcopy(observed['native']), copy.deepcopy(observed['worker']), copy.deepcopy(observed['child_mounts'])
    check(native['inspect']['Id'] != worker['Id'], 'birth-distinct-native-worker')
    data = scope.data_from_argv(native['process']['argv'])
    check(set(seed['config']) == {'path','sha256'}
          and seed['config']['path'] == str(Path(data) / 'config.ini')
          and scope.digest(seed['config']['sha256']), 'birth-derived-config')
    paths = [seed['config']['path'], scope.CONFIG_PATH, scope.MAIN_PATH]
    expected = [seed['config']['sha256'], scope.CONFIG_SHA, scope.MAIN_SHA]
    merge_nodes(nodes, scope.ancestors(paths))
    contents, refs = [], []
    for path, sha in zip(paths, expected):
        fact = scope.nine(os.lstat(path))
        contents.append(scope.bounded_read(path, sha, fact, nodes))
        refs.append(dict(path=str(path), sha256=sha, signature9=fact))
        files[Path(path)] = fact
    scope.source_contract(contents[1], contents[2])
    root = scope.destination(contents[0])
    host_data = scope.projection(native['inspect']['Mounts'], data)
    host_root = scope.projection(native['inspect']['Mounts'], root)
    check(host_root == scope.projection(worker['Mounts'], seed['worker_library'])
          and host_root == scope.projection(mounts, root)
          and host_data == scope.projection(mounts, data), 'birth-fresh-mount-geometry')
    dp,rp,dh,rh = map(scope.absolute,(data,root,host_data,host_root))
    check(dp != rp and dp not in rp.parents and rp not in dp.parents and dh != rh
          and dh not in rh.parents and rh not in dh.parents, 'birth-disjoint-derived-roots')
    proof_path = Path(input_path).with_suffix('.native-scope.json')
    final_path = Path(input_path).with_suffix('.lifecycle.json')
    check(not os.path.lexists(proof_path) and not os.path.lexists(final_path), 'birth-exclusive-output')
    merge_nodes(nodes, scope.ancestors([proof_path, Path(data)/'.scope-placeholder', Path(root)/'.scope-placeholder']))
    document = dict(version=1, kind='existing-native-configured-scope', invocation=invocation,
        native=native, worker=worker, child_mounts=mounts, config=refs[0], config_module=refs[1],
        main_module=refs[2], worker_library=seed['worker_library'], tool_root='/opt/archiving-utils',
        ancestors={str(p):v for p,v in nodes.items()})
    encoded = life.encoded(document)
    life.passive(files, nodes)
    fd = os.open(proof_path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(encoded); stream.flush(); os.fsync(fd)
        proof_fact = scope.nine(os.fstat(fd))
        files[proof_path] = proof_fact
        proof_ref = dict(path=str(proof_path), sha256=digest(encoded), signature9=proof_fact)
        reply = commit(channel, binding, dict(source_sha256=source_sha, seed_sha256=seed_sha, native_scope=proof_ref))
        check(normalized(reply) == captured, 'birth-original-observation-CAS')
        lifecycle_ref = reply['lifecycle']
        check(set(lifecycle_ref) == {'path','sha256'} and lifecycle_ref['path'] == str(final_path)
              and scope.digest(lifecycle_ref['sha256']), 'birth-fixed-lifecycle-ACK')
        raw, final_fact = life.read(final_path, lifecycle_ref['sha256'])
        final = life.decoded(raw)
        check(final['proofs']['native_scope'] == proof_ref and final['nonce'] == nonce
              and final['input_sha256'] == input_sha and final['command'] == list(argv)
              and final['parent_source'] == parent, 'birth-final-sidecar-binding')
        files[final_path] = final_fact
        life.passive(files, nodes)
        check(scope.nine(os.fstat(fd)) == proof_fact, 'birth-original-proof-FD')
        check(channel.binding() == original_channel, 'birth-channel-terminal')
        return BirthMetadata(_KEY, channel, invocation, files, nodes, lifecycle_ref, source_sha)
    finally:
        os.close(fd)
