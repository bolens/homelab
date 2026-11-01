"""Production-original plan13 composition, separate from disposable bootstrap.

No receipt constructs a Writer, stopped-reader lease or publication capability.
The installed Parent observes every original role again and owns execution.
"""
import copy
import os
from pathlib import Path
import stat
import time

import genuine_plan13_producer as shared

p = shared.p
need = p.need


class Originals(shared.Originals):
    """Retain selected metadata; the owning Writer verifies archive bytes.

    Control/source reads keep their existing bounded content checks. Archives
    are not treated as control files or read into a Root-side 64 MiB buffer.
    The inherited executor retires this metadata closure exactly once at entry;
    the immutable Parent plan then requires catalog/preparation/hash equality.
    """
    def __init__(self):
        super().__init__(); self.selected=None

    def select(self, ref):
        need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and p.digest(ref['sha256']),
             'configured-original-ref')
        stamp=ref['signature9'];path=p.absolute(ref['path'])
        need(type(stamp) is list and len(stamp)==9 and all(type(v) is int for v in stamp)
             and stat.S_ISREG(stamp[5]) and stamp[8]==1 and stamp[6]==1000
             and 0<stamp[2]<=512*1024**2 and p.nfs_canonical(path)
             and p.nine(p.nfs_lstat(path))==stamp, 'configured-original-selected9')
        need(self.selected is None or self.selected==ref, 'configured-original-no-reselection')
        for name,value in p.parents(path).items():
            need(name not in self.nodes or self.nodes[name]==value,'configured-original-ancestor5')
            self.nodes[name]=value
        self.selected=copy.deepcopy(ref);self.refs[str(path)]=copy.deepcopy(ref)

    def close(self):
        selected=self.selected
        current=None if selected is None else self.refs.pop(selected['path'],None)
        try:
            super().close()
            if current is not None:
                need(current==selected and p.nfs_canonical(p.absolute(current['path']))
                     and p.nine(p.nfs_lstat(current['path']))==current['signature9'],
                     'configured-original-preentry9')
        finally:
            if current is not None:self.refs[current['path']]=current


def compose(document, originals, installation):
    keys = {'version', 'kind', 'nonce', 'observed', 'seconds', 'installation',
            'base_manifest', 'current_roles', 'publication_geometry', 'native',
            'native_config', 'mounts', 'bounds', 'operation', 'archive_request',
            'archive_scopes', 'archive_original', 'nfs_active_input', 'nfs_intents',
            'originals', 'selected_image_metadata', 'observer', 'base_admission'}
    need(type(document) is dict and set(document) == keys
         and type(document['version']) is int and document['version'] == 1
         and document['kind'] == 'configured-original-plan13-input'
         and p.digest(document['nonce']) and type(document['observed']) is int
         and 0 <= time.time() - document['observed'] <= 120
         and type(document['seconds']) is int and 1 <= document['seconds'] <= 900,
         'configured-producer-original-schema')
    current = originals.json(document['current_roles'])
    need(type(current) is dict and set(current) == {'nonce', 'observed', 'roles', 'native_process'}
         and current['nonce'] == document['nonce'] and current['observed'] == document['observed'],
         'configured-producer-current-role-bracket')
    roles = current['roles']
    need(type(roles) is dict and set(roles) == {'native', 'reader', 'worker'}, 'configured-producer-three-roles')
    for role, row in roles.items():
        need(type(row) is dict and set(row) == {'id', 'image', 'profile', 'epoch'}
             and p.digest(row['id']) and type(row['profile']) is dict
             and set(row['profile']) == {'Id', 'Name', 'Image', 'Path', 'Args',
                 'Config', 'HostConfig', 'Mounts', 'NetworkSettings'}
             and row['profile']['Id'] == row['id'] and row['profile']['Image'] == row['image']
             and type(row['epoch']) is dict and 'Health' not in row['epoch'],
             'configured-producer-original-role')
        # CurrentRoles and Assembly share a static profile with a separate
        # complete lifecycle epoch. Neither field can supply the other's facts.
        state = row['epoch']; p.lifecycle_state({'State': state})
        running = role != 'worker'
        need(state['Status'] == ('running' if running else 'created')
             and state['Running'] is running and (state['Pid'] > 0 if running else state['Pid'] == 0)
             and not any(state[key] for key in ('Paused', 'Restarting', 'Dead', 'OOMKilled')),
             'configured-producer-role-phase')
    need(len({row['id'] for row in roles.values()}) == 3, 'configured-producer-distinct-roles')
    native = document['native']; geometry = document['publication_geometry']
    need(type(native) is dict and set(native) == {'data', 'roots'}
         and type(native['roots']) is list and len(native['roots']) == 1, 'configured-producer-native-root')
    scope=p.pinned_module(installation['refs']['publication_native_configured_scope.py'])
    config = originals.read(document['native_config'], private=False)
    need(scope.destination(config) == native['roots'][0]
         and scope.projection(roles['native']['profile']['Mounts'], native['data'] + '/config.ini')
             == document['native_config']['path'], 'configured-producer-original-configured-destination')
    library = scope.projection(roles['native']['profile']['Mounts'], native['roots'][0])
    scopes = originals.json(document['archive_scopes'])
    need(type(scopes) is dict and set(scopes) == {'version', 'scratch', 'retention_root'}
         and type(scopes['version']) is int and scopes['version'] == 1, 'configured-producer-private-scopes')
    p.configured_common_root(geometry, document['mounts'], roles['native']['profile'], library, scopes['retention_root'])
    mapping = p.Paths(document['mounts']); operation = p.absolute(document['operation'])
    need(mapping.host(native['roots'][0]) == library
         and mapping.host(native['data'] + '/config.ini') == document['native_config']['path']
         and mapping.child(str(operation)) == str(shared.installer.CHILD_OPERATION),
         'configured-producer-child-projection')
    need(not os.path.lexists(operation), 'configured-producer-exclusive-operation')
    for role in ('common_root', 'library', 'retention'):
        ref = geometry[role]; path = p.absolute(ref['path'])
        need(p.nfs_canonical(path) and p.nine(p.nfs_lstat(path)) == ref['signature9'],
             'configured-producer-original-directory9')
    need(set(p.nfs_names(geometry['common_root']['path'])) == set(geometry['namespace']),
         'configured-producer-original-namespace')
    for name, fact in geometry['namespace'].items():
        need(p.five(p.nfs_lstat(Path(geometry['common_root']['path']) / name)) == fact,
             'configured-producer-original-child5')
    original = document['archive_original']; originals.select(original)
    need(Path(original['path']).is_relative_to(Path(library))
         and Path(original['path']) != Path(library), 'configured-producer-selected-original')
    request = originals.json(document['archive_request'])
    need(type(request) is dict and set(request) == {'version', 'owner', 'operation_id', 'terminal'}
         and type(request['version']) is int and request['version'] == 2
         and request['terminal'] in ('forward', 'rollback') and p.digest(request['operation_id']),
         'configured-producer-request-without-fixture-authority')
    action = p.pinned_module(installation['refs']['comic_archive_repair_action.py'])
    action.owner_request(request)
    _, docs = shared.nested_originals(originals, document['nfs_active_input'], document['originals'])
    images = dict(native=roles['native']['image'], selected=roles['native']['image'],
                  reader=roles['reader']['image'], worker=roles['worker']['image'])
    need(docs['source_cohort']['images'] == images and installation['worker_image'] == roles['worker']['image'],
         'configured-producer-original-image-cohort')
    refs = installation['refs']
    parent_original = installation['receipt']['original_source_refs']['comic_negative_nfs_active_parent.py']
    need(docs['source_cohort']['parent'] == {key: parent_original[key] for key in ('path', 'sha256')}
         and refs['comic_negative_nfs_active_parent.py']['sha256'] == parent_original['sha256'],
         'configured-producer-original-nfs-parent')
    for ref in (document['nfs_intents'], document['selected_image_metadata'], document['observer'], document['base_admission']):
        originals.read(ref)
    need(document['observer']['sha256'] == shared.OBSERVER_SHA
         and Path(document['observer']['path']).name == 'comic_archive_terminal_vectors.py'
         and document['base_admission']['sha256'] == shared.installer.EXPECTED['admission'],
         'configured-producer-reviewed-sources')
    plan = dict(version=13, kind='reviewed-archive-one-lifecycle-protocol', nonce=document['nonce'],
        seconds=document['seconds'], operation=str(operation), selected_image=roles['native']['image'],
        action='archive-one', terminal_mode='same-child-v1',
        **{key: dict(id=roles[role]['id'], profile=p.static(roles[role]['profile']))
           for key, role in (('reader', 'reader'), ('held_native', 'native'), ('held_worker', 'worker'))},
        provider=refs['comic_archive_repair_action.py'], producer=refs['comic_archive_evidence_adapter.py'],
        observer=copy.deepcopy(document['observer']), backup_provider=refs['comic_archive_backup_action.py'],
        sdk_map=refs['configured-sdk-map.json'], mounts=copy.deepcopy(document['mounts']), native=copy.deepcopy(native),
        producer_inputs={key: copy.deepcopy(document[key]) for key in ('archive_request', 'archive_scopes')},
        birth_source_sha256=installation['sdk']['publication_native_scope_birth.py'],
        scope_projection=refs['publication_native_configured_scope.py'], bounds=copy.deepcopy(document['bounds']),
        nfs=dict(adapter=refs['comic_nfs_factual_successor.py'], active_parent=refs['comic_negative_nfs_active_parent.py'],
                 active_input=copy.deepcopy(document['nfs_active_input'])),
        worker_observation={key: copy.deepcopy(installation['worker'][key]) for key in ('mode', 'source', 'image_sources')},
        publication_geometry=copy.deepcopy(geometry), configured_original=copy.deepcopy(original))
    configured = dict(base_admission=copy.deepcopy(document['base_admission']),
        admission=refs['publication_reader_admission.py'], cohort=refs['configured-cohort.json'],
        image_metadata=copy.deepcopy(document['selected_image_metadata']))
    need(set(p.NFS_HOST_SOURCE_PINS) < set(shared.installer.EXPECTED_NFS)
         and all(shared.installer.EXPECTED_NFS[name] == pin for name, pin in p.NFS_HOST_SOURCE_PINS.items()),
         'configured-producer-nfs-host-selection')
    originals.close()
    return plan, refs['comic_reader_lifecycle_parent.py'], configured, {name: refs[name] for name in p.NFS_HOST_SOURCE_PINS}


class Producer(shared.Producer):
    """Reuse the owning one-attempt executor, never the bootstrap constructor."""
    def __init__(self, request_ref, output):
        self.originals = Originals(); self.request_ref = copy.deepcopy(request_ref)
        self.document = self.originals.json(request_ref); self.output = p.absolute(str(output)); self.entered = False
        need(not os.path.lexists(self.output), 'configured-producer-output-no-adoption')
        parent = os.lstat(self.output.parent)
        need(stat.S_ISDIR(parent.st_mode) and stat.S_IMODE(parent.st_mode) == 0o700
             and parent.st_uid == os.geteuid(), 'configured-producer-private-output-parent')
        installation = shared.checked_installation(self.originals, self.document['installation'], self.document['base_manifest'])
        geometry = self.document['publication_geometry']
        current = self.originals.json(self.document['current_roles'])
        p.configured_common_root(geometry, self.document['mounts'], current['roles']['native']['profile'],
                                 geometry['library']['path'], geometry['retention']['path'])
        self.owner_reads = p.bind_owner_reads(geometry)
        try:
            self.plan, self.source, self.configured, self.nfs_sources = compose(self.document, self.originals, installation)
            self.tape = p.encode(self.document); self.deadline = time.monotonic() + self.document['seconds']
            self.bound = p.encode(dict(plan=self.plan, source=self.source, configured=self.configured, nfs_sources=self.nfs_sources))
            self.target = self.document['archive_original']['path']
        except BaseException:
            try:p.release_owner_reads(self.owner_reads)
            except BaseException:pass
            raise
