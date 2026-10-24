"""Finite original-fact assembly for disposable plan13; no admission or transport.

Reviewed scope/query/ACKs and host probe choices must already exist. This writes
only an input graph for the existing composer. Source controls are not proof of
an installed factory, actual NFS, stopped reader, backup or terminal outcome.
"""
import copy
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

import genuine_plan13_producer as composer
import comic_negative_nfs_active_parent as active
import genuine_source_cohort as cohort_source

p = composer.p
need = p.need
HERE = Path(__file__).absolute().parent
PINS = {
    'genuine_plan13_producer.py': '9094219b99b1c157294bb778c15b6c0250be681c8bca0050f68158180dd0998a',
    'comic_negative_nfs_active_parent.py': 'e93fc18095854eeec31beb49dc282db3ffdf6028e495d10b25b479060530d5fc',
    'genuine_source_cohort.py': '9e9d4ec487d243025f8d46cc487f3333c8a5b4a37b003c48eb83d242b4636d6d',
}
RIGHTS = ('backup_verified', 'publication_acceptance', 'mutation_authority')


def pair(ref):
    return {key: ref[key] for key in ('path', 'sha256')}


def fresh(value):
    need(type(value) is int and 0 <= time.time() - value <= 120, 'active-input-expired')


class Assembly:
    def __init__(self, request_ref, output, *, owner_reads=None):
        need(owner_reads is None or type(owner_reads) is p.GeometryOwnerReads and p._OWNER_READS is owner_reads, 'active-owning-read-scope')
        self.owner_reads = owner_reads
        self.originals = composer.Originals(); self.parent_fd = self.fd = None
        self.output = p.absolute(str(output)); self.files = {}; self.names = set()
        need(not os.path.lexists(self.output), 'active-output-no-adoption')
        z = p.nfs_lstat(self.output.parent)
        need(stat.S_ISDIR(z.st_mode) and stat.S_IMODE(z.st_mode) == 0o700
             and z.st_uid == os.geteuid(), 'active-private-parent')
        self.parent5 = p.five(z); self.originals.nodes.update(p.parents(self.output))
        self.parent_fd = os.open(self.output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            need(p.five(os.fstat(self.parent_fd)) == self.parent5, 'active-parent-open')
            self.document = self.originals.json(request_ref)
            self.validate()
            self.tape = p.encode(self.document); self.close()
        except BaseException:
            self.release(); raise

    def validate(self):
        q = self.document
        need(type(q) is dict and set(q) == {'version', 'kind', 'nonce', 'observed', 'current_roles',
             'active_scope', 'query', 'native_controls', 'effective_observer_review', 'source_cohort',
             'parent_admission', 'probe_plan', 'operation_output', 'originals', 'sources'}
             and type(q['version']) is int and q['version'] == 1
             and q['kind'] == 'disposable-original-active-input-assembly' and p.digest(q['nonce']), 'active-input-schema')
        fresh(q['observed'])
        need(type(q['sources']) is dict and set(q['sources']) == {*PINS, 'genuine_active_inputs.py'}, 'active-source-set')
        modules = {'genuine_plan13_producer.py': composer, 'comic_negative_nfs_active_parent.py': active,
                   'genuine_source_cohort.py': cohort_source}
        for name, module in modules.items():
            need(type(module) is types.ModuleType and module.__name__ == name[:-3] and sys.modules.get(name[:-3]) is module
                 and Path(module.__file__).name == name, 'active-source-origin')
        for name, ref in q['sources'].items():
            origin = Path(__file__).absolute() if name == 'genuine_active_inputs.py' else Path(modules[name].__file__).absolute()
            need(ref['path'] == str(origin) and (name not in PINS or ref['sha256'] == PINS[name]), 'active-source-pin')
            self.originals.read(ref, private=False)
        current = self.originals.json(q['current_roles']); self.current = current
        need(type(current) is dict and set(current) == {'nonce', 'observed', 'roles', 'native_process'}
             and current['nonce'] == q['nonce'] and current['observed'] == q['observed']
             and type(current['native_process']) is dict, 'active-current-original')
        roles = current['roles']; need(type(roles) is dict and set(roles) == {'native', 'reader', 'worker'}, 'active-role-set')
        ids = set()
        for name, row in roles.items():
            need(type(row) is dict and set(row) == {'id', 'image', 'profile', 'epoch'}
                 and type(row['id']) is str and re.fullmatch('[a-f0-9]{64}', row['id'])
                 and row['id'] not in ids and type(row['image']) is str
                 and re.fullmatch('sha256:[a-f0-9]{64}', row['image']), 'active-role-identity')
            ids.add(row['id']); profile = row['profile']
            need(profile['Id'] == row['id'] and profile['Image'] == row['image']
                 and profile['Name'] == '/archive-bootstrap-' + q['nonce'][:16] + '-' + name
                 and profile['Config']['Labels'].get(composer.bootstrap.LABEL) == q['nonce']
                 and profile['Config']['Labels'].get(composer.bootstrap.PURPOSE) == 'genuine-archive-fixture', 'active-disposable-role')
        refs = q['originals']; need(type(refs) is dict and 1 <= len(refs) <= 128, 'active-finite-originals')
        self.used = set()
        def follow(ref, *, private=True):
            need(type(ref) is dict and set(ref) == {'path', 'sha256'} and ref['path'] in refs, 'active-missing-original')
            full = refs[ref['path']]
            need(full.get('path') == ref['path'] and full.get('sha256') == ref['sha256'], 'active-original-conflict')
            self.used.add(ref['path']); raw = self.originals.read(full, private=private); fresh(q['observed']); return raw
        self.follow = follow
        docs = {name: p.decode(follow(pair(q[name]))) for name in composer.NESTED}
        for name in composer.NESTED:
            need(refs[q[name]['path']] == q[name], 'active-original-reference')
        scope = docs['active_scope']; query = p.decode(follow(pair(q['query'])))
        need(refs[q['query']['path']] == q['query'] and scope['sources']['current_komga_libraries'] == pair(q['query']), 'active-query-join')
        need(type(query) is dict and set(query) == {'version', 'kind', 'configuration', 'expected_base_url'}
             and type(query['version']) is int and query['version'] == 1
             and query['kind'] == 'approved-active-komga-library-query', 'active-query-schema')
        cfg = p.decode(follow(query['configuration']))
        need(type(cfg.get('komga')) is dict and cfg['komga'].get('url') == query['expected_base_url']
             and type(cfg['komga'].get('api_key')) is str and cfg['komga']['api_key'] not in ('', 'REPLACE_ME'), 'active-query-private-config')
        need(type(q['parent_admission']) is dict and type(q['probe_plan']) is dict
             and q['probe_plan'].get('scope') == pair(q['active_scope'])
             and q['parent_admission'].get('expected_device') == q['probe_plan'].get('expected_device')
             and q['parent_admission'].get('mount_identity') == q['probe_plan'].get('mount_identity'), 'active-probe-parent-join')
        self.host_scope(scope, q['probe_plan'])
        operation = p.absolute(q['operation_output'])
        need(not os.path.lexists(operation) and operation != self.output
             and self.output not in operation.parents and operation not in self.output.parents, 'active-operation-output')
        self.originals.absent.update((str(operation), str(Path(q['probe_plan']['fixture_parent']) / q['probe_plan']['fixture_name']), q['probe_plan']['output_root']))
        for name in self.originals.absent:
            path = Path(name)
            # Only these two known owned parents are intentionally absent.
            # Their child absences retain the original existing grandparent.
            anchor = path.parent if path.parent in (operation, self.neutral_parent) else path
            self.remember(p.parents(anchor))
        for value in scope['sources'].values():follow(value)
        review = docs['effective_observer_review']
        need(type(review) is dict and set(review) == set(composer.EFFECTIVE), 'active-effective-seven')
        effective = {name: follow(ref, private=name not in ('producer', 'parent_source')) for name, ref in review.items()}
        report, runtime, ack, acceptance, parent_ack = (p.decode(effective[k]) for k in ('report', 'runtime', 'ack', 'acceptance', 'parent_ack'))
        reader = roles['reader']; fresh(runtime['observed'])
        need(runtime.get('kind') == 'reviewed-komga-effective-scope-runtime'
             and runtime['container']['Id'] == reader['id'] and runtime['container']['Image'] == reader['image']
             and p.static(runtime['container']) == reader['profile']
             and {k: v for k, v in runtime['container']['State'].items() if k != 'Health'} == reader['epoch'], 'active-effective-role-epoch')
        need(report.get('kind') == 'komga-effective-persistent-scope-observation'
             and report.get('image') == reader['image'] and report.get('container_id') == reader['id']
             and report.get('pid') == runtime['pid'] and report.get('start_time') == runtime['start_time']
             and report.get('runtime_sha256') == review['runtime']['sha256']
             and report.get('source_sha256') == review['producer']['sha256']
             and report.get('jar_sha256') == runtime['jar_sha256'] and report.get('source_commit') == runtime['source_commit']
             and report.get('scope_observation_verified') is False and report.get('final_ack_required') is True, 'active-effective-report')
        need(acceptance.get('kind') == 'accepted-komga-effective-scope'
             and acceptance.get('scope_observation_verified') is False and acceptance.get('final_ack_required') is True
             and acceptance.get('same_process_verified') is True
             and acceptance.get('report_sha256') == review['report']['sha256']
             and acceptance.get('source_sha256') == review['parent_source']['sha256']
             and acceptance.get('helper_sha256') == review['producer']['sha256'], 'active-effective-acceptance')
        need(ack.get('scope_observation_verified') is True and ack.get('report_sha256') == review['report']['sha256']
             and parent_ack.get('scope_observation_verified') is True and parent_ack.get('same_process_verified') is True
             and parent_ack.get('report_sha256') == review['report']['sha256']
             and parent_ack.get('acceptance_sha256') == review['acceptance']['sha256']
             and all(doc.get(k) is False for doc in (ack, acceptance, parent_ack) for k in RIGHTS), 'active-existing-final-acks')
        need(scope['sources']['current_komga_effective_scope'] == review['report'], 'active-effective-scope-join')
        active.validate_effective_nodes(report, [Path(x) for x in scope['forbidden_roots']])
        for path, ref in report['config_files'].items():
            full = dict(path=path, **ref); need(refs.get(path) == full, 'active-effective-config-original'); follow(pair(full), private=False)
        for path in (*report['absent_config_files'], *report['optional_absent_scopes']):
            path = p.absolute(path); need(p.nfs_absent(path), 'active-effective-absence')
            self.originals.absent.add(str(path)); self.remember(p.parents(path))
        cohort = docs['source_cohort']; images = dict(native=roles['native']['image'], selected=roles['native']['image'], reader=reader['image'], worker=roles['worker']['image'])
        need(cohort.get('kind') == 'approved-disposable-nfs-current-source-cohort' and cohort.get('images') == images
             and set(cohort.get('sources', {})) == set(cohort_source.ROLES)
             and set(cohort.get('logs', {})) == {'stdout', 'stderr'}, 'active-source-cohort')
        for value in (*cohort['sources'].values(), cohort['parent']):follow(value, private=False)
        for role,value in cohort['logs'].items():
            full = refs[value['path']]
            if role == 'stderr' and full['signature9'][2] == 0:
                need(full['sha256'] == value['sha256'], 'active-original-conflict')
                self.used.add(full['path']); self.originals.read_cohort_stderr(q['source_cohort'], full); fresh(q['observed'])
            else:follow(value)
        receipt = p.decode(follow(cohort['receipt']))
        need(receipt.get('kind') == 'owned-nfs-current-source-fixture-readiness' and receipt.get('images') == images
             and receipt.get('parent_sha256') == cohort['parent']['sha256']
             and receipt.get('source_pins') == {k: v['sha256'] for k, v in cohort['sources'].items()}
             and receipt.get('exit_code') == 0 and receipt.get('zero_skips') is True
             and all(receipt.get(k) is False for k in cohort_source.RIGHTS), 'active-existing-cohort-receipt')
        need(scope['sources']['current_runtime_bracket'] == pair(q['current_roles']), 'active-current-scope-join')
        need(q['native_controls'] == refs[cohort['receipt']['path']]
             and cohort['sources']['effective_helper'] == review['producer']
             and cohort['sources']['effective_parent'] == review['parent_source'], 'active-cohort-control-join')
        need(self.used == set(refs), 'active-no-unknown-originals')
        self.active = dict(version=1, kind='approved-active-nfs-owned-lifecycle',
            **{name: pair(q[name]) for name in composer.NESTED}, parent_admission=copy.deepcopy(q['parent_admission']),
            probe_plan=copy.deepcopy(q['probe_plan']), operation_output=str(operation))

    def remember(self, values):
        for name, value in values.items():
            need(name not in self.originals.nodes or self.originals.nodes[name] == value, 'active-original-ancestor-conflict')
            self.originals.nodes[name] = value

    def host_scope(self, scope, probe):
        # Host originals retain their actual owner. The genuine UID1000 child
        # validate() runs later under Parent's existing checked projection.
        active.exact(scope, ('version', 'kind', 'approved_disposable_diagnostic', 'observed',
            'current_active_scanner_publication_paths_reviewed', 'future_mylar_destination_verified',
            'future_mylar_destination', 'writer_lifecycle_resume_authorized', 'forbidden_roots', 'sources'))
        need(type(scope['version']) is int and scope['version'] == 2
             and scope['kind'] == 'root-reviewed-nfs-active-disposable-scope'
             and scope['approved_disposable_diagnostic'] is True
             and scope['current_active_scanner_publication_paths_reviewed'] is True
             and scope['future_mylar_destination_verified'] is False
             and scope['future_mylar_destination'] is None
             and scope['writer_lifecycle_resume_authorized'] is False, 'active-existing-reviewed-scope')
        fresh(scope['observed'])
        need(type(scope['forbidden_roots']) is list and 1 <= len(scope['forbidden_roots']) <= 32
             and len(set(scope['forbidden_roots'])) == len(scope['forbidden_roots']), 'active-scope-roots')
        roots = [p.absolute(x) for x in scope['forbidden_roots']]
        if getattr(self, 'owner_reads', None) is not None:
            self.owner_reads.check()
            geometry = self.owner_reads.geometry
            need(self.owner_reads.root.name == 'archive-publication-' + self.document['nonce'], 'active-owner-read-bootstrap-nonce')
            need(probe['library_root'] == geometry['library']['path']
                 and str(Path(probe['fixture_parent']).parent) == geometry['retention']['path']
                 and p.nine(self.owner_reads.stat(geometry['retention']['path'])) == self.document['parent_admission']['grandparent_signature'], 'active-owner-read-exact-probe-geometry')
        need(all(stat.S_ISDIR(p.nfs_lstat(x).st_mode) for x in roots), 'active-scope-root-kind')
        for path in roots:self.remember(p.parents(path)); self.remember({str(path): p.five(p.nfs_lstat(path))})
        active.exact(probe, ('version', 'kind', 'scope', 'fixture_parent', 'fixture_name',
            'fixture_parent_signature', 'library_root', 'expected_device', 'mount_identity', 'output_root'))
        need(type(probe['version']) is int and probe['version'] == 2
             and probe['kind'] == 'approved-negative-nfs-active-probe-parent'
             and p.absolute(probe['library_root']) in roots
             and type(probe['expected_device']) is int and probe['expected_device'] > 0
             and type(probe['fixture_name']) is str and re.fullmatch('[.]comic-nfs-probe-[0-9a-f]{32}', probe['fixture_name']), 'active-original-probe-choice')
        # The owning Parent alone births this node and derives its full9.
        # Host preparation binds absence and the existing grandparent instead.
        parent = p.absolute(probe['fixture_parent']); admission = self.document['parent_admission']
        active.exact(admission, ('path', 'grandparent_signature', 'expected_device', 'mount_identity'))
        grandparent = parent.parent; stamp = p.nine(p.nfs_lstat(grandparent))
        need(admission['path'] == str(parent) and re.fullmatch(r'[.]comic-nfs-private-[0-9a-f]{32}', parent.name)
             and probe['fixture_parent_signature'] is None and p.nfs_absent(parent)
             and stamp == admission['grandparent_signature'] and stat.S_ISDIR(stamp[5])
             and stamp[0] == probe['expected_device'] == p.nfs_lstat(probe['library_root']).st_dev,
             'active-original-precreation-parent')
        need(probe['output_root'] == str(p.absolute(self.document['operation_output']) / 'probe'),
             'active-probe-operation-output')
        self.neutral_parent = parent; self.grandparent9 = stamp
        self.originals.absent.add(str(parent)); self.remember(p.parents(parent))
        fixture = parent / probe['fixture_name']; out = p.absolute(probe['output_root'])
        need(p.nfs_absent(fixture) and not os.path.lexists(out)
             and active.outside(fixture, roots) and active.outside(out, roots)
             and fixture not in out.parents and out not in fixture.parents, 'active-original-probe-geometry')
        mount = probe['mount_identity']; active.exact(mount, ('source', 'target', 'fstype', 'fsroot', 'options', 'maj:min'))
        need(mount['fstype'] == 'nfs4' and all(type(x) is str and x for x in mount.values()), 'active-original-mount-choice')
        need(type(scope['sources']) is dict and set(scope['sources']) == {'current_runtime_bracket', 'current_mylar_hold',
            'current_worker_created', 'current_komga_libraries', 'current_komga_effective_scope',
            'protected_catalog_cache_recovery_scope', 'continuous_raw_writer_lease'}, 'active-scope-source-set')

    def output_names(self):
        # A persistent directory description can retain a stale Btrfs census
        # after our own writes. Open a fresh description of the HELD inode.
        fd = os.open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.fd)
        try:
            need(p.five(os.fstat(fd)) == self.output5 == p.five(os.fstat(self.fd))
                 == p.five(p.nfs_lstat(self.output)), 'active-output-census-open')
            names = set(os.listdir(fd))
            need(p.five(os.fstat(fd)) == self.output5 == p.five(os.fstat(self.fd))
                 == p.five(p.nfs_lstat(self.output)), 'active-output-census-close')
            return names
        finally:os.close(fd)

    def close(self):
        self.originals.close()
        if hasattr(self, 'neutral_parent'):
            need(not os.path.lexists(self.neutral_parent)
                 and p.nine(p.nfs_lstat(self.neutral_parent.parent)) == self.grandparent9,
                 'active-precreation-parent-closure')
        need(p.five(os.fstat(self.parent_fd)) == self.parent5 == p.five(p.nfs_lstat(self.output.parent)), 'active-output-parent')
        fresh(self.document['observed'])
        if hasattr(self, 'tape'):need(p.encode(self.document) == self.tape, 'active-request-changed')
        if self.fd is not None:
            need(p.five(os.fstat(self.fd)) == self.output5 == p.five(p.nfs_lstat(self.output))
                 and self.output_names() == self.names, 'active-output-custody')
            for ref in self.files.values():p.read(ref)

    def write(self, name, value):
        self.close(); raw = p.encode(value); need(0 < len(raw) <= p.MAX, 'active-output-bound')
        fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        try:
            born = p.nine(os.fstat(fd)); offset = 0
            while offset < len(raw):
                count = os.write(fd, raw[offset:]); need(count > 0, 'active-short-write'); offset += count
            os.fsync(fd); os.lseek(fd, 0, 0); z = os.fstat(fd)
            need(p.five(z) == [born[i] for i in (0, 1, 5, 6, 7)] and z.st_nlink == 1
                 and os.read(fd, len(raw) + 1) == raw, 'active-output-readback')
            ref = dict(path=str(self.output / name), sha256=hashlib.sha256(raw).hexdigest(), signature9=p.nine(z))
            self.names.add(name); self.files[name] = ref; self.close(); os.fsync(self.fd); return ref
        finally:os.close(fd)

    def execute(self):
        try:
            self.close(); os.mkdir(self.output.name, mode=0o700, dir_fd=self.parent_fd)
            self.fd = os.open(self.output.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.parent_fd)
            self.output5 = p.five(os.fstat(self.fd)); self.close()
            ref = self.write('active-input.json', self.active)
            # Invoke the genuine existing composer over actual freshly written
            # originals. No substitute Parent, JSON reader or source-mode grant.
            composer.nested_originals(self.originals, ref, self.document['originals']); self.close()
            result = dict(active_input=ref, originals=copy.deepcopy(self.document['originals']), current_roles=self.document['current_roles'],
                          publication_acceptance=False, actual_nfs_verified=False, installed_factories_verified=False,
                          mutation_authority=False, automatic_replay=False)
            self.write('composer-inputs.json', result); self.close(); os.fsync(self.parent_fd); return result
        finally:
            primary = sys.exc_info()[1]
            try:self.release()
            except BaseException as error:
                if primary is None:raise
                primary.active_input_release_failure = type(error).__name__

    def release(self):
        for name in ('fd', 'parent_fd'):
            fd = getattr(self, name, None)
            if fd is not None:os.close(fd); setattr(self, name, None)


def assemble(request_ref, output, *, owner_reads=None):
    """Only private input files are written; all operational rights stay absent."""
    return Assembly(request_ref, output, owner_reads=owner_reads).execute()
