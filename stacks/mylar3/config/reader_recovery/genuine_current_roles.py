"""Explicit bounded post-bootstrap observation for the plan13 composer.

No application bootstrap, restart, Writer, stop, ACK or SourceCohort is produced.
The existing native probe calls primary getHealth: passive behavior depends on
its original installed image/source pins, never an assumption about all images.
The output is private observation data, not a connected-factory grant.
"""
import configparser
import copy
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import time
import weakref

import genuine_application_bootstrap as b
import genuine_plan13_producer as composer
import publication_native_configured_scope as scope_parser

p = b.p
need = p.need
HERE = Path(__file__).absolute().parent
SOURCE_PINS = {
    'genuine_application_bootstrap.py': '76c7812eb30af609b063b214840a586a6289f1ce4fe7e1a8f48727b9b60ade71',
    'genuine_plan13_producer.py': '9094219b99b1c157294bb778c15b6c0250be681c8bca0050f68158180dd0998a',
    'comic_reader_lifecycle_parent.py': '231dffa6a6dc5473877a9ee42d9a4088a219a5ea0961d73e4fce0729718ff7a7',
    'publication_native_configured_scope.py': '43dfd29de92f2dd963b876b261add29f1d251b11d612f18f56e43b72ed9516ed',
}
PROBE_SHA = 'c8db0286911ad3cdd0ddc9cd17cdb5b88a206b06a49f9b28c79ce00275a57bce'
SCOPE_SHA = '43dfd29de92f2dd963b876b261add29f1d251b11d612f18f56e43b72ed9516ed'
QUEUE_SHA = '1a364068a61d9093d55228eed7596cad4e4aae923cb864b263306190f593c7fd'
HTTP_SHA = '502d08654d71ecded3f6d2ec78c7a6dcd0702bda149ffece4afebd190ecd6df1'


class ReadOnlyDocker:
    """Finite original CID, code, input and mount selectors; no fallback client."""
    def __init__(self, owner):
        self.owner = owner
        self.ids = frozenset(row['id'] for row in owner.plan['roles'].values())
        self.network = owner.plan['network']['id']
        self.mounts = frozenset(owner.geometry_originals[name]['path'] for name in ('common_root', 'library', 'retention'))

    def approve(self, args, data):
        o = self.owner
        if type(args) is list and len(args) == 2 and args[0] == 'inspect':
            need(args[1] in self.ids and data is None, 'capture-original-inspect-only'); return
        if args == ['network', 'inspect', self.network]:
            need(data is None, 'capture-network-no-input'); return
        prefix = ['exec', '--interactive', '--user', '1000:1000', o.plan['roles']['native']['id'],
                  '/lsiopy/bin/python3', '-I', '-B', '-c']
        need(type(args) is list and len(args) == 10 and args[:9] == prefix, 'capture-readonly-exec-only')
        if args[-1] == b.IMAGE_PROGRAM:
            need(data == p.encode(sorted(o.sdk)), 'capture-original-sdk-input'); return
        need(args[-1] == o.probe_program and type(data) is bytes, 'capture-original-probe-only')
        value = p.decode(data)
        need(value == o.probe_request(value.get('seconds')) and type(value['seconds']) is int
             and 1 <= value['seconds'] <= 30, 'capture-original-probe-input')

    def run(self, args, seconds, data=None):
        p.owner_root_guard()
        self.approve(args, data)
        return b.Docker().run(args, self.timeout(seconds), data)

    def timeout(self, seconds):
        need(type(seconds) in (int, float) and 0 < seconds <= 30, 'capture-transport-deadline')
        remaining = self.owner.end - time.monotonic(); need(remaining > 0, 'capture-transport-expired')
        return min(seconds, remaining)

    def mount(self, path, seconds):
        need(str(path) in self.mounts, 'capture-original-mount-only')
        return b.Docker().mount(path, self.timeout(seconds))


class Capture:
    """Source-mode tests may double transport; actual run uses ReadOnlyDocker."""
    # Reuse the owning checks verbatim; no synthetic Bootstrap/session identity.
    roles = b.Bootstrap.roles
    installed_sources = b.Bootstrap.installed_sources

    def __init__(self, plan_ref, result_ref, catalog_ref, source_refs, output, *, seconds=30, engine=None):
        need(type(seconds) is int and 1 <= seconds <= 120, 'capture-deadline-bound')
        self.end = time.monotonic() + seconds
        self.originals = composer.Originals(); self.geometry = None; self.finished = False
        self.parent_fd = None; self.output_fd = None; self.output_ref = None
        self.parent_finalizer = None; self.output_finalizer = None
        self.output = p.absolute(str(output))
        need(not os.path.lexists(self.output), 'capture-output-no-adoption')
        z = os.lstat(self.output.parent)
        need(stat.S_ISDIR(z.st_mode) and stat.S_IMODE(z.st_mode) == 0o700 and z.st_uid == os.geteuid(), 'capture-private-output-parent')
        self.parent5 = p.five(z)
        self.originals.nodes.update(p.parents(self.output))
        need(type(source_refs) is dict and set(source_refs) == {*SOURCE_PINS, 'genuine_current_roles.py'}, 'capture-original-source-roles')
        # Each finite role retains its actual loaded generation. A new host
        # observer must not relabel unchanged installed E sources as local F copies.
        modules = {'genuine_application_bootstrap.py': b, 'genuine_plan13_producer.py': composer,
                   'comic_reader_lifecycle_parent.py': p, 'publication_native_configured_scope.py': scope_parser}
        paths = {name: Path(module.__file__).absolute() for name, module in modules.items()}
        paths['genuine_current_roles.py'] = Path(__file__).absolute()
        for name, ref in source_refs.items():
            need(paths[name].name == name and ref['path'] == str(paths[name])
                 and (name not in SOURCE_PINS or ref['sha256'] == SOURCE_PINS[name]), 'capture-original-source-pin')
            self.originals.read(ref, private=False)
        self.sources = copy.deepcopy(source_refs)
        self.plan = self.originals.json(plan_ref, private=False)
        result = self.originals.json(result_ref, private=False)
        self.catalog = self.originals.json(catalog_ref, private=False)
        need(self.plan.get('kind') == 'approved-disposable-application-bootstrap' and p.digest(self.plan.get('nonce'))
             and result.get('kind') == 'disposable-application-bootstrap-observation'
             and result.get('nonce') == self.catalog.get('nonce') == self.plan['nonce']
             and self.catalog.get('kind') == 'disposable-native-catalog-processing-observation'
             and result.get('native_catalog_processing') == catalog_ref
             and result.get('native_catalog_processing_observed') is True
             and self.catalog.get('native_catalog_processing_observed') is True
             and all(result.get(k) is False and self.catalog.get(k) is False for k in composer.RIGHTS)
             and result.get('ordinary_ack_verified') is False and self.catalog.get('ordinary_ack_verified') is False
             and self.catalog.get('birth_verified') is False and self.catalog.get('daemon_operation_identity') is False,
             'capture-original-bootstrap-catalog')
        bracket = result.get('reader_task_empty_observation')
        need(type(bracket) is dict and bracket.get('kind') == 'original-reader-task-empty-bracket'
             and bracket.get('nonce') == self.plan['nonce'] and bracket.get('observation', {}).get('queue_empty_observed') is True
             and bracket.get('reader_image') == self.plan['images']['reader']
             and all(bracket.get(k) is False for k in ('application_quiescence_verified', 'future_exclusion_verified',
                 'stop_authority', 'reader_resume_authority', 'publication_acceptance', 'mutation_authority', 'ordinary_ack_verified')),
             'capture-original-sse-required')
        # Bootstrap's original HTTP helper fixes its source context. Retain the
        # actual queue helper incarnation; a co-located current alias is not it.
        http = self.plan['helper']
        need(Path(http['path']).name == 'genuine_bootstrap_http.py'
             and http['sha256'] == HTTP_SHA, 'capture-original-bootstrap-source')
        self.originals.read(http, private=False)
        bootstrap_sources = Path(http['path']).parent
        need(bracket['helper']['path'] == str(bootstrap_sources / 'genuine_reader_quiescence.py')
             and bracket['helper']['sha256'] == QUEUE_SHA, 'capture-original-queue-source')
        self.originals.read(bracket['helper'], private=False)
        row = bracket['roles']; need(set(row) == {'profiles', 'epochs', 'network', 'reader'} and row['reader'] == result['reader'], 'capture-original-sse-bracket')
        need(set(self.plan['roles']) == set(self.plan['images']) == set(row['profiles']) == set(row['epochs']) == {'native', 'reader', 'worker'}, 'capture-three-original-roles')
        self.profiles = copy.deepcopy(row['profiles']); self.epochs = copy.deepcopy(row['epochs']); self.network_profile = copy.deepcopy(row['network'])
        need(len({r['id'] for r in self.plan['roles'].values()}) == 3, 'capture-distinct-original-roles')
        for role, original in self.plan['roles'].items():
            profile = self.profiles[role]
            need(p.digest(original['id']) and re.fullmatch('sha256:[a-f0-9]{64}', original['image'])
                 and original['image'] == self.plan['images'][role] and profile['Id'] == original['id']
                 and profile['Image'] == original['image'] and set(profile) == set(p.static(profile))
                 and profile['Name'] == '/archive-bootstrap-' + self.plan['nonce'][:16] + '-' + role
                 and profile.get('Config', {}).get('Labels', {}).get(b.LABEL) == self.plan['nonce']
                 and profile['Config']['Labels'].get(b.PURPOSE) == 'genuine-archive-fixture', 'capture-original-role-purpose-image')
        need(self.catalog['native_CID'] == self.plan['roles']['native']['id']
             and self.catalog['native_image'] == self.plan['images']['native'], 'capture-catalog-original-native')
        self.root = p.absolute(self.plan['state_root']['path']); self.native_mount = self.root / 'native'
        self.data = p.absolute(self.plan['native_ini']['path']).parent
        self.reader = self.root / 'reader'; self.worker = self.root / 'worker'
        need(self.root.name == 'archive-bootstrap-' + self.plan['nonce']
             and (self.data == self.native_mount or self.native_mount in self.data.parents), 'capture-disposable-state')
        self._identity(self.plan['state_root'])
        geometry = self.plan['geometry']; need(set(geometry) == {'version', 'kind', 'common_root', 'library', 'retention'}, 'capture-geometry-schema')
        self.owner_reads = p.bind_owner_reads(geometry)
        try:
            self.geometry_originals = copy.deepcopy(geometry)
            for name in ('common_root', 'library', 'retention'):
                # Original producer observation of CURRENT full9 after bootstrap,
                # not a replacement for its pre-seed directory identity.
                self.geometry_originals[name]['signature9'] = self._identity(geometry[name])
            common = Path(geometry['common_root']['path']); self.library = Path(geometry['library']['path']); self.retention = Path(geometry['retention']['path'])
            need(common.name == 'archive-publication-' + self.plan['nonce'] and result['reader']['library']['root'] == str(self.library), 'capture-original-disposable-library')
            self.sdk = self.originals.json(self.plan['native_sdk'], private=False)
            need(type(self.sdk) is dict and b.REQUIRED_SDK <= set(self.sdk)
                 and {'worker_health.py', 'native_writers.py'} <= set(self.sdk) and len(self.sdk) <= 512
                 and all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*[.]py', name) and p.digest(pin) for name, pin in self.sdk.items()), 'capture-original-sdk-map')
            for name, pin, ref in (('comic_native_process_probe.py', PROBE_SHA, self.plan['native_probe']),
                                   ('publication_native_configured_scope.py', SCOPE_SHA, self.plan['scope_source'])):
                need(ref['path'] == str(bootstrap_sources / name) and ref['sha256'] == pin, 'capture-original-native-source')
            self.probe_program = self.originals.read(self.plan['native_probe'], private=False).decode()
            self.scope_source = self.originals.read(self.plan['scope_source'], private=False).decode()
            need(self.sdk['publication_native_configured_scope.py'] == SCOPE_SHA, 'capture-installed-scope-pin')
            # Catalog.original_process owns this post-startup config original. The
            # virgin plan INI may legitimately have been saved before that capture.
            # Its fixed DATA spelling remains the mapping selector, not its old9.
            self.native_process = copy.deepcopy(self.catalog['process'])
            need(type(self.native_process) is dict and set(self.native_process) == {'process', 'config'}, 'capture-original-native-config')
            fresh = self.native_process['config']
            expected_path = '/config/' + str((self.data / 'config.ini').relative_to(self.native_mount))
            need(type(fresh) is dict and set(fresh) == {'path', 'sha256', 'signature9'}
                 and fresh['path'] == expected_path, 'capture-original-native-config')
            self.original_config = dict(fresh, path=str(self.data / 'config.ini'))
            raw = self.originals.read(self.original_config, private=False)
            need(self.original_config['signature9'][6:8] == [1000, 1000] and stat.S_IMODE(self.original_config['signature9'][5]) == 0o600, 'capture-original-config-owner')
            self._config(raw)
            process = self.native_process['process']
            need(type(process) is dict and set(process) == {'pid', 'start_ticks', 'argv'}
                 and type(process['pid']) is int and process['pid'] > 0 and type(process['start_ticks']) is int and process['start_ticks'] > 0
                 and type(process['argv']) is list and 4 <= len(process['argv']) <= 64
                 and all(type(v) is str and len(v.encode()) <= 8192 for v in process['argv']), 'capture-original-process-shape')
            need(Path(scope_parser.__file__).absolute() == Path(b.__file__).absolute().parent.parent / 'publication_native_configured_scope.py', 'capture-owning-parser-origin')
            need(scope_parser.data_from_argv(process['argv']) == str(Path(expected_path).parent)
                 and '--port' not in process['argv'] and '-p' not in process['argv']
                 and scope_parser.destination(raw) == str(self.library), 'capture-owning-config-process-policy')
            self.tape = p.encode(dict(plan=self.plan, profiles=self.profiles, epochs=self.epochs, network=self.network_profile,
                                      native_process=self.native_process, sdk=self.sdk, geometry=self.geometry_originals, sources=self.sources))
            self.engine = ReadOnlyDocker(self) if engine is None else engine
            self.parent_fd = os.open(self.output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            self.parent_finalizer = weakref.finalize(self, os.close, self.parent_fd)
            try:self.originals.close(); self.output_close()
            except BaseException:
                try:self.release()
                except BaseException:pass  # Cleanup cannot replace the original refusal.
                raise
        except BaseException:
            try:self.release()
            except BaseException:pass
            raise

    def _identity(self, ref):
        path = p.absolute(ref['path']); now = p.nfs_lstat(path); old = ref['signature9']
        need(type(old) is list and len(old) == 9 and all(type(x) is int for x in old)
             and stat.S_ISDIR(now.st_mode) and stat.S_IMODE(now.st_mode) == (0o711 if self.plan['geometry']['version'] == 2 and str(path) == self.plan['geometry']['common_root']['path'] else 0o700)
             and (now.st_uid, now.st_gid) == (1000, 1000)
             and tuple(p.five(now)) == tuple(old[i] for i in (0, 1, 5, 6, 7)), 'capture-original-directory-identity')
        for name, value in p.parents(path).items():
            need(name not in self.originals.nodes or self.originals.nodes[name] == value, 'capture-original-directory-ancestor')
            self.originals.nodes[name] = value
        value = p.five(now); name = str(path)
        need(name not in self.originals.nodes or self.originals.nodes[name] == value, 'capture-original-directory-node')
        self.originals.nodes[name] = value
        return p.nine(now)

    @staticmethod
    def _config(raw):
        cfg = configparser.ConfigParser(interpolation=None, strict=True); cfg.read_string(raw.decode())
        need(not cfg.defaults(), 'capture-config-defaults')
        def one(section, name):
            values = [(s, cfg.get(s, name, raw=True)) for s in cfg.sections() if cfg.has_option(s, name)]
            need(len(values) == 1 and values[0][0] == section, 'capture-config-unique-key'); return values[0][1]
        need(one('API', 'api_enabled').casefold() in ('1', 'true') and len(one('API', 'api_key')) == 32, 'capture-primary-key-policy')
        need(one('Interface', 'enable_https').casefold() in ('0', 'false') and one('Interface', 'http_port').isdecimal()
             and 1 <= int(one('Interface', 'http_port')) <= 65535, 'capture-primary-port-policy')

    def seconds(self):
        remaining = self.end - time.monotonic(); need(remaining > 0, 'capture-deadline')
        return min(30, max(1, int(remaining)))

    def probe_request(self, seconds):
        return dict(version=1, nonce=self.plan['nonce'], source_sha256=PROBE_SHA, seconds=seconds,
            module_pins={'/app/mylar3/mylar/' + name: self.sdk[name] for name in ('worker_health.py', 'native_writers.py')}, scope_source=self.scope_source)

    def close(self):
        self.originals.close(); self.seconds()
        need(p.encode(dict(plan=self.plan, profiles=self.profiles, epochs=self.epochs, network=self.network_profile,
             native_process=self.native_process, sdk=self.sdk, geometry=self.geometry_originals, sources=self.sources)) == self.tape, 'capture-original-inputs-changed')
        if self.geometry is not None:
            p.check_common_root(self.geometry)
            # The reused common-root helper intentionally holds child identity5;
            # this read-only capture additionally retains each CURRENT full9.
            handles = (self.geometry[0], *self.geometry[2])
            for name, fd in zip(('common_root', 'library', 'retention'), handles):
                expected = self.geometry_originals[name]
                need(p.nine(os.fstat(fd)) == expected['signature9']
                     and p.nine(p.nfs_lstat(expected['path'])) == expected['signature9'], 'capture-current-directory-full9')
        self.output_close()

    def output_close(self):
        if p.five(os.lstat(self.output.parent)) != self.parent5:raise p.Held('capture-original-output-parent')
        if self.parent_fd is not None and p.five(os.fstat(self.parent_fd)) != self.parent5:raise p.Held('capture-output-parent-FD')
        if self.output_ref is not None:
            expected = self.output_ref['signature9']
            if p.nine(os.lstat(self.output)) != expected:raise p.Held('capture-output-original9')
            if self.output_fd is not None and p.nine(os.fstat(self.output_fd)) != expected:raise p.Held('capture-output-original-FD9')
            if self.parent_fd is not None and p.nine(os.stat(self.output.name, dir_fd=self.parent_fd, follow_symlinks=False)) != expected:raise p.Held('capture-output-original-at9')

    def write(self, value):
        raw = p.encode(value) + b'\n'; need(0 < len(raw) <= p.MAX, 'capture-output-bound')
        self.close()
        self.output_fd = os.open(self.output.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.parent_fd)
        self.output_finalizer = weakref.finalize(self, os.close, self.output_fd)
        born = p.nine(os.fstat(self.output_fd))
        need(stat.S_ISREG(born[5]) and stat.S_IMODE(born[5]) == 0o600 and born[6:] == [os.geteuid(), os.getegid(), 1], 'capture-output-birth')
        pending = memoryview(raw)
        while pending:
            count = os.write(self.output_fd, pending); need(count > 0, 'capture-output-short-write'); pending = pending[count:]
        os.fsync(self.output_fd); current = p.nine(os.fstat(self.output_fd))
        need(current[:2] == born[:2] and current[2] == len(raw) and current[5:] == born[5:], 'capture-output-own-transition')
        os.lseek(self.output_fd, 0, os.SEEK_SET)
        need(os.read(self.output_fd, len(raw) + 1) == raw and p.nine(os.fstat(self.output_fd)) == current, 'capture-output-readback')
        self.output_ref = dict(path=str(self.output), sha256=hashlib.sha256(raw).hexdigest(), signature9=current)
        os.fsync(self.parent_fd); self.output_close()
        return self.output_ref

    def release(self):
        error = None
        if self.geometry is not None:
            try:p.close_common_root(self.geometry)
            except BaseException as exc:error = exc
            self.geometry = None
        for finalizer in (self.output_finalizer, self.parent_finalizer):
            try:
                if finalizer is not None:finalizer()
            except BaseException as exc:
                if error is None:error = exc
        self.output_fd = self.parent_fd = None
        try:p.release_owner_reads(getattr(self, 'owner_reads', None))
        except BaseException as exc:
            if error is None:error = exc
        self.owner_reads = None
        if error is not None:raise error

    def execute(self):
        need(not self.finished and not os.path.lexists(self.output), 'capture-no-replay')
        self.finished = True
        try:
            self.geometry = p.admit_common_root(self.geometry_originals,
                [dict(host=self.geometry_originals['common_root']['path'], child=self.geometry_originals['common_root']['path'], write=True)],
                str(self.library), str(self.retention), [str(self.root)])
            self.close(); self.roles(); self.installed_sources(); self.close()
            request = self.probe_request(self.seconds())
            value = p.decode(self.engine.run(['exec', '--interactive', '--user', '1000:1000', self.plan['roles']['native']['id'],
                '/lsiopy/bin/python3', '-I', '-B', '-c', self.probe_program], self.seconds(), p.encode(request)))
            need(type(value) is dict and set(value) == {'version', 'nonce', 'source_sha256', 'process', 'publication', 'config'}
                 and type(value['version']) is int and value['version'] == 1 and value['nonce'] == self.plan['nonce']
                 and value['source_sha256'] == PROBE_SHA and dict(process=value['process'], config=value['config']) == self.native_process
                 and value['publication'].get('state') == 'ready', 'capture-fresh-native-original-ready')
            self.roles(); self.installed_sources(); self.close()
            current = dict(nonce=self.plan['nonce'], observed=int(time.time()),
                roles={name: dict(id=old['id'], image=old['image'], profile=copy.deepcopy(self.profiles[name]), epoch=copy.deepcopy(self.epochs[name]))
                       for name, old in self.plan['roles'].items()}, native_process=copy.deepcopy(self.native_process))
            ref = self.write(current); self.close()
            return ref
        finally:
            primary = sys.exc_info()[1]
            try:
                self.release(); self.originals.close(); self.output_close()
            except BaseException:
                if primary is None:raise


def run(plan_ref, result_ref, catalog_ref, source_refs, output, *, activate=False, seconds=30):
    need(activate is True and os.geteuid() == 0, 'capture-explicit-root-activation')
    return Capture(plan_ref, result_ref, catalog_ref, source_refs, output, seconds=seconds).execute()
