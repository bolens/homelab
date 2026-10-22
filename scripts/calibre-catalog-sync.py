#!/usr/bin/env python3
"""Catalog clear EPUB candidates only after an external verified recovery gate.

The host orchestrator owns quiescence, backups, restore proof and resuming
services. This program never changes service lifecycle or backup retention.
"""

import argparse
import base64
from collections import Counter
import hashlib
import importlib.machinery
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import time
import traceback


class Refused(Exception):
    pass


class NeedsRecovery(Exception):
    pass


def inventory(root):
    """Self-contained so the same reader can inspect the disposable container."""
    import base64
    import hashlib
    import os
    from pathlib import Path
    import stat
    root = Path(root)
    result = {}
    pending = [root]
    while pending:
        path = pending.pop()
        info = path.lstat()
        kind = 'link' if stat.S_ISLNK(info.st_mode) else 'dir' if stat.S_ISDIR(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else None
        if kind is None:
            raise ValueError('unsupported_file_kind')
        key = path.relative_to(root).as_posix()
        row = {'kind': kind, 'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid,
               'mtimeNs': info.st_mtime_ns,
               'attrs': {name: base64.b64encode(os.getxattr(path, name, follow_symlinks=False)).decode()
                         for name in os.listxattr(path, follow_symlinks=False)}}
        if kind == 'file':
            with path.open('rb') as stream:
                row['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
            row['bytes'] = info.st_size
        elif kind == 'dir':
            pending.extend(path.iterdir())
        else:
            row['target'] = os.readlink(path)
        result[key] = row
    return result


def snapshot_database(path):
    path = Path(path).resolve()
    wal = Path(str(path) + '-wal')
    if wal.exists() and wal.stat().st_size:
        raise Refused('active_wal_requires_checkpointed_backup')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise Refused('database_integrity_failed')
        result = {}
        for name, in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            quoted = '"' + name.replace('"', '""') + '"'
            cursor = connection.execute('SELECT * FROM ' + quoted)
            columns = [item[0] for item in cursor.description]
            rows = [[{'blob': base64.b64encode(value).decode()} if isinstance(value, bytes) else value for value in row]
                    for row in cursor.fetchall()]
            result[name] = {'columns': columns, 'rows': rows}
        return result
    finally:
        connection.close()


def rows(snapshot, table):
    value = snapshot.get(table)
    if not value:
        raise Refused('catalog_schema_missing')
    return [dict(zip(value['columns'], row)) for row in value['rows']]


def old_rows_preserved(before, after):
    for table, value in before.items():
        if table not in after or value['columns'] != after[table]['columns']:
            raise Refused('existing_catalog_schema_changed')
        original = Counter(json.dumps(row, sort_keys=True) for row in value['rows'])
        current = Counter(json.dumps(row, sort_keys=True) for row in after[table]['rows'])
        if original - current:
            raise Refused('existing_catalog_rows_changed')


def normalize_inventory(data):
    if not isinstance(data, dict):
        raise Refused('inventory_invalid')
    result = {}
    for relative, record in data.items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or not isinstance(record, dict):
            raise Refused('inventory_invalid')
        row = dict(record)
        row['kind'] = {'directory': 'dir', 'symlink': 'link'}.get(row.get('kind'), row.get('kind'))
        if row['kind'] not in ('file', 'dir', 'link'):
            raise Refused('inventory_invalid')
        for field in ('mode', 'uid', 'gid', 'mtimeNs'):
            if type(row.get(field)) is not int:
                raise Refused('inventory_invalid')
        row['mode'] = stat.S_IMODE(row['mode'])
        if not isinstance(row.get('attrs'), dict):
            raise Refused('inventory_invalid')
        for value in row['attrs'].values():
            base64.b64decode(value, validate=True)
        if row['kind'] == 'file' and not re.fullmatch('[0-9a-f]{64}', str(row.get('sha256'))):
            raise Refused('inventory_invalid')
        result[path.as_posix()] = row
    return result


DATABASE_FILES = {'metadata.db', 'metadata.db-wal', 'metadata.db-shm'}


def originals_preserved(original, current, *, catalog_changes=False, backup=False, nfs_verified=False):
    for name, expected in original.items():
        if catalog_changes and name in DATABASE_FILES:
            continue
        actual = current.get(name)
        if actual is None:
            raise Refused('original_library_file_missing')
        fields = ['kind', 'mode', 'uid', 'gid', 'attrs']
        if expected['kind'] == 'file':
            fields.extend(('sha256', 'mtimeNs'))
        elif expected['kind'] == 'link':
            fields.append('target')
        elif not catalog_changes:
            fields.append('mtimeNs')
        for field in fields:
            left, right = expected.get(field), actual.get(field)
            if field == 'attrs' and backup and nfs_verified:
                left = {k: v for k, v in left.items() if k != 'system.nfs4_acl'}
                right = {k: v for k, v in right.items() if k != 'system.nfs4_acl'}
            if left != right:
                raise Refused('original_library_metadata_or_content_changed')


def private_file(path, parent=None, private_leaf=True):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path or not path.is_file():
        raise Refused('private_receipt_path_invalid')
    info = path.stat()
    # Preserved library assets may retain permissive original modes beneath
    # the verified private ancestor; their exact attrs are checked by manifest.
    if private_leaf and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600):
        raise Refused('private_receipt_permissions_invalid')
    if parent is not None:
        path.relative_to(parent)
    return path


def load_receipt(path, library):
    path = private_file(path)
    parent = path.parent
    if parent.stat().st_uid != os.geteuid() or stat.S_IMODE(parent.stat().st_mode) != 0o700:
        raise Refused('private_receipt_parent_invalid')
    if any((ancestor / '.git').exists() for ancestor in (parent, *parent.parents)):
        raise Refused('private_receipt_inside_git')
    receipt = json.loads(path.read_text())
    age = time.time() - receipt.get('createdAtUnix', 0)
    if (receipt.get('version') != 1 or receipt.get('status') != 'verified' or receipt.get('quiesced') is not True
            or not -30 <= age <= 600 or receipt.get('libraryPath') != str(library)):
        raise Refused('verified_fresh_quiesced_receipt_required')
    backup = Path(receipt['backupPath'])
    if not backup.is_dir() or backup.resolve(strict=True) != backup:
        raise Refused('backup_path_invalid')
    backup.relative_to(parent)
    if backup == parent or backup == library or library.is_relative_to(parent) or parent.is_relative_to(library):
        raise Refused('backup_and_source_not_isolated')
    baseline = private_file(receipt['baselineDatabasePath'], parent, private_leaf=False)
    if baseline != backup / 'metadata.db':
        raise Refused('baseline_database_identity_mismatch')
    manifest = json.loads(private_file(receipt['inventoryPath'], parent).read_text())
    original = normalize_inventory(manifest.get('books', manifest))
    if any(row['kind'] == 'link' for row in original.values()):
        raise Refused('symlinked_library_requires_manual_review')
    source = inventory(library)
    if set(source) != set(original):
        raise Refused('source_inventory_changed')
    originals_preserved(original, source)
    copy = inventory(backup)
    if set(copy) != set(original):
        raise Refused('backup_inventory_incomplete')
    originals_preserved(original, copy, backup=True, nfs_verified=receipt.get('nfsAclVerified') is True)
    for name, row in original.items():
        if row['kind'] == 'file' and os.path.samestat((library / name).stat(), (backup / name).stat()):
            raise Refused('backup_shares_source_inodes')
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != original['metadata.db']['sha256']:
        raise Refused('baseline_database_mismatch')
    return receipt, parent, backup, baseline, original


def load_planner(path):
    loader = importlib.machinery.SourceFileLoader('calibre_catalog_import', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def verify_candidates(plan, expected, library):
    candidates = plan['candidates']
    hashes = [row['sha256'] for row in candidates]
    if not isinstance(expected, list) or len(hashes) != len(set(hashes)) or set(hashes) != set(expected):
        raise Refused('candidate_receipt_mismatch')
    for row in candidates:
        source = Path(row['path'])
        if (row.get('format') != 'EPUB' or source.resolve(strict=True) != source
                or not source.is_relative_to(library) or source.suffix.lower() != '.epub'
                or not re.fullmatch('[0-9a-f]{64}', row['sha256'])):
            raise Refused('candidate_path_invalid')
        with source.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                raise Refused('candidate_source_changed')
    return candidates


def verify_added(before, after, original, current, hashes, candidate_isbns=None, canonical_isbn=None):
    old_rows_preserved(before, after)
    originals_preserved(original, current, catalog_changes=True)
    original_ids = {row['id'] for row in rows(before, 'books')}
    added = {row['id']: row for row in rows(after, 'books') if row['id'] not in original_ids}
    if len(added) != len(hashes):
        raise Refused('added_book_count_mismatch')
    protected = {name.casefold() for name in original}
    namespaces = set()
    for row in added.values():
        name = row.get('path')
        if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
            raise Refused('added_book_path_invalid')
        folded = name.casefold()
        if any(item == folded or item.startswith(folded + '/') for item in protected):
            raise Refused('added_book_path_collision')
        namespaces.add(name)
    found = set()
    for row in rows(after, 'data'):
        if row['book'] in added and row['format'].upper() == 'EPUB':
            name = row['name']
            if not isinstance(name, str) or Path(name).name != name:
                raise Refused('added_format_path_invalid')
            relative = added[row['book']]['path'] + '/' + name + '.epub'
            record = current.get(relative, {})
            checksum = record.get('sha256')
            if checksum not in hashes or checksum in found:
                raise Refused('added_epub_content_mismatch')
            expected_isbns = (candidate_isbns or {}).get(checksum, [])
            if expected_isbns:
                if canonical_isbn is None:
                    raise Refused('isbn_canonicalizer_required')
                imported = {canonical_isbn(identifier['val']) for identifier in rows(after, 'identifiers')
                            if identifier['book'] == row['book'] and identifier['type'].lower() == 'isbn'}
                imported.discard(None)
                if imported != set(expected_isbns):
                    raise Refused('added_book_isbn_not_preserved')
            found.add(checksum)
    if found != set(hashes):
        raise Refused('added_epub_content_incomplete')
    return set(added), namespaces


WRAPPER = '''import sys
from calibre.constants import __version__
if __version__.split('.')[:2] != ['9', '16']:
    raise RuntimeError('Calibre version needs preservation verification')
from calibre.db.backend import DB
# Keep this process-local override through DB finalization. Zero retention
# otherwise deletes trash on close as well as during initialization.
DB.expire_old_trash = lambda *args, **kwargs: None
from calibre.db.cli.main import main
raise SystemExit(main(['calibredb', *sys.argv[1:]]))
'''


class ContainerRuntime:
    def __init__(self, container, library, log, user='1000:1000'):
        self.container, self.library, self.log, self.user = container, library, log, user
        self.remote = None
        self.candidate_isbns = {}

    def run(self, args, *, data=None, stream=None):
        if stream is None:
            result = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=self.log, check=False)
        else:
            result = subprocess.run(args, stdin=stream, stdout=subprocess.PIPE, stderr=self.log, check=False)
        if result.returncode:
            self.log.write(result.stdout)
            self.log.flush()
            raise Refused('native_catalog_command_failed')
        return result.stdout

    def execute(self, args, *, data=None, root=False):
        command = ['docker', 'exec', '--user', '0' if root else self.user]
        if data is not None:
            command.append('-i')
        return self.run([*command, self.container, *args], data=data)

    def transfer(self, source, destination, workspace, same_owner):
        archive = workspace / 'transfer.tar'
        with archive.open('wb') as stream:
            subprocess.run(['tar', '--format=pax', '--acls', '--xattrs', '-C', str(source), '-cf', '-', '.'],
                           stdout=stream, stderr=self.log, check=True)
        # Stream the archive; library-sized backups must not be loaded into RAM.
        with archive.open('rb') as stream:
            self.run(['docker', 'exec', '--user', '0' if same_owner else self.user, '-i', self.container,
                      'tar', '--acls', '--xattrs', '--same-owner' if same_owner else '--no-same-owner',
                      '-xpf', '-', '-C', destination], stream=stream)
        archive.unlink()

    def prepare(self, backup, incoming, workspace):
        actual = self.run(['docker', 'inspect', '--format', '{{range .Mounts}}{{if eq .Destination "/books"}}{{.Source}}{{end}}{{end}}', self.container]).decode().strip()
        if Path(actual).resolve() != self.library:
            raise Refused('container_library_identity_mismatch')
        self.remote = self.execute(['mktemp', '-d', '/tmp/calibre-catalog-sync.XXXXXX']).decode().strip()
        if not re.fullmatch(r'/tmp/calibre-catalog-sync\.[A-Za-z0-9]+', self.remote):
            self.remote = None
            raise Refused('container_staging_identity_invalid')
        self.execute(['mkdir', self.remote + '/rehearsal', self.remote + '/incoming'])
        self.transfer(backup, self.remote + '/rehearsal', workspace, True)
        self.transfer(incoming, self.remote + '/incoming', workspace, False)
        self.execute(['python3', '-c', 'import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())',
                      self.remote + '/calibredb-preserve-trash.py'], data=WRAPPER.encode())
        self.inputs = [self.remote + '/incoming/' + path.name for path in sorted(incoming.iterdir())]
        code = inspect.getsource(inventory) + '\nimport json,sys; print(json.dumps(inventory(sys.argv[1]),sort_keys=True))'
        self.remote_inventory_code = code
        baseline = json.loads(self.execute(['python3', '-c', code, self.remote + '/rehearsal']))
        originals_preserved(inventory(backup), baseline)
        return baseline

    def import_into(self, library):
        # Import each staged edition with its verified canonical ISBN. Calibre's
        # metadata reader does not always retain the EPUB identifier unaided.
        for source in self.inputs:
            known = self.candidate_isbns.get(Path(source).stem, [])
            isbn_args = ['--isbn', known[0]] if known else []
            self.execute(['calibre-debug', '-e', self.remote + '/calibredb-preserve-trash.py', '--',
                          'add', '--with-library', library, *isbn_args, '--', source])

    def rehearse(self, workspace):
        library = self.remote + '/rehearsal'
        self.import_into(library)
        database = workspace / 'rehearsal-after.db'
        database.write_bytes(self.execute(['cat', library + '/metadata.db']))
        return snapshot_database(database), json.loads(self.execute(['python3', '-c', self.remote_inventory_code, library]))

    def apply(self):
        self.import_into('/books')

    def close(self):
        if self.remote:
            self.execute(['rm', '-rf', '--', self.remote])


def _restore_owned(library, baseline_stream, original, current, trial_new):
    originals_preserved(original, current, catalog_changes=True)
    new = set(current) - set(original)
    if any(name not in trial_new and name not in DATABASE_FILES for name in new):
        raise NeedsRecovery('unexpected_new_namespace_requires_recovery')
    for name in sorted(new, key=lambda value: (len(Path(value).parts), value), reverse=True):
        path = library / name
        if current[name]['kind'] == 'dir':
            path.rmdir()
        else:
            path.unlink()
    for name in DATABASE_FILES - {'metadata.db'}:
        path = library / name
        if path.exists():
            path.unlink()
    descriptor, temporary = tempfile.mkstemp(prefix='.calibre-rollback.', dir=library)
    os.close(descriptor)
    temporary = Path(temporary)
    try:
        with temporary.open('wb') as outgoing:
            shutil.copyfileobj(baseline_stream, outgoing, length=1024 * 1024)
        expected = original['metadata.db']
        if (temporary.stat().st_uid, temporary.stat().st_gid) != (expected['uid'], expected['gid']):
            os.chown(temporary, expected['uid'], expected['gid'])
        os.chmod(temporary, expected['mode'])
        for name in os.listxattr(temporary):
            if name not in expected['attrs']:
                os.removexattr(temporary, name)
        for name, value in expected['attrs'].items():
            os.setxattr(temporary, name, base64.b64decode(value))
        os.utime(temporary, ns=(temporary.stat().st_atime_ns, expected['mtimeNs']))
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, library / 'metadata.db')
        directory = os.open(library, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)
    for name, expected in sorted(original.items(), key=lambda item: len(Path(item[0]).parts), reverse=True):
        if expected['kind'] == 'dir':
            path = library / name
            if path.stat().st_mtime_ns != expected['mtimeNs']:
                os.utime(path, ns=(path.stat().st_atime_ns, expected['mtimeNs']))


def restore_catalog(library, baseline, original, current, trial_new):
    # Open the private backup before dropping privileges. Root-squashed NFS
    # requires mutations as the original database owner, never a relaxed mode.
    with baseline.open('rb') as baseline_stream:
        expected = original['metadata.db']
        if os.geteuid() != expected['uid']:
            if os.geteuid() != 0:
                raise NeedsRecovery('rollback_owner_identity_unavailable')
            child = os.fork()
            if child == 0:
                try:
                    os.setgroups([expected['gid']])
                    os.setgid(expected['gid'])
                    os.setuid(expected['uid'])
                    _restore_owned(library, baseline_stream, original, current, trial_new)
                except BaseException:
                    os._exit(1)
                os._exit(0)
            _, status = os.waitpid(child, 0)
            if status != 0:
                raise NeedsRecovery('rollback_owner_operation_failed')
        else:
            _restore_owned(library, baseline_stream, original, current, trial_new)
    restored = inventory(library)
    if set(restored) != set(original):
        raise NeedsRecovery('rollback_inventory_not_verified')
    originals_preserved(original, restored)
    if snapshot_database(library / 'metadata.db') != snapshot_database(baseline):
        raise NeedsRecovery('rollback_catalog_not_verified')


def sync_catalog(library, planner, receipt_path, runtime_factory=ContainerRuntime, container='calibre-web'):
    library = Path(library).resolve(strict=True)
    receipt, parent, backup, baseline, original = load_receipt(receipt_path, library)
    plan = planner.plan(library)
    candidates = verify_candidates(plan, receipt.get('expectedCandidateHashes'), library)
    if not candidates:
        return {'status': 'unchanged', 'counts': {'addedBooks': 0}}
    workspace = Path(tempfile.mkdtemp(prefix='catalog-sync.', dir=parent))
    workspace.chmod(0o700)
    live_started = False
    retain = False
    runtime = None
    before = snapshot_database(baseline)
    candidate_isbns = {row['sha256']: row.get('isbns', []) for row in candidates}
    canonical_isbn = getattr(planner, 'isbn', None)
    for identifiers in candidate_isbns.values():
        if (not isinstance(identifiers, list) or len(identifiers) > 1
                or identifiers and (canonical_isbn is None or
                                    any(canonical_isbn(value) != value for value in identifiers))):
            raise Refused('candidate_canonical_isbn_invalid')
    try:
        incoming = workspace / 'incoming'
        incoming.mkdir(mode=0o700)
        for row in candidates:
            destination = incoming / (row['sha256'] + '.epub')
            shutil.copyfile(row['path'], destination)
            destination.chmod(0o600)
            if hashlib.sha256(destination.read_bytes()).hexdigest() != row['sha256']:
                raise Refused('staged_candidate_integrity_failed')
        with (workspace / 'native.log').open('wb') as log:
            runtime = runtime_factory(container, library, log)
            runtime.candidate_isbns = candidate_isbns
            trial_before = runtime.prepare(backup, incoming, workspace)
            trial_database, trial_after = runtime.rehearse(workspace)
            expected_ids, expected_paths = verify_added(before, trial_database, trial_before, trial_after,
                                                        receipt['expectedCandidateHashes'], candidate_isbns, canonical_isbn)
            trial_new = set(trial_after) - set(trial_before)
            # Recheck source and receipt age immediately before the first live write.
            load_receipt(receipt_path, library)
            verify_candidates(planner.plan(library), receipt['expectedCandidateHashes'], library)
            live_started = True
            runtime.apply()
            current, after = inventory(library), snapshot_database(library / 'metadata.db')
            actual_ids, actual_paths = verify_added(before, after, original, current, receipt['expectedCandidateHashes'],
                                                      candidate_isbns, canonical_isbn)
            if actual_ids != expected_ids or actual_paths != expected_paths:
                raise Refused('live_import_differs_from_rehearsal')
            if set(current) - set(original) - trial_new - DATABASE_FILES:
                raise Refused('unexpected_new_live_namespace')
            return {'status': 'applied', 'counts': {'addedBooks': len(actual_ids), 'preservedBooks': len(rows(before, 'books'))}}
    except Exception as error:
        retain = True
        if not live_started:
            raise Refused('rehearsal_or_recovery_gate_failed') from error
        try:
            restore_catalog(library, baseline, original, inventory(library), trial_new)
        except Exception as recovery_error:
            retain = True
            raise NeedsRecovery('live_catalog_requires_verified_backup_recovery') from recovery_error
        return {'status': 'rolled_back', 'counts': {'addedBooks': 0, 'preservedBooks': len(rows(before, 'books'))}}
    finally:
        if runtime:
            try:
                runtime.close()
            except Exception:
                retain = True
        if not retain:
            shutil.rmtree(workspace)


def record_private_failure(receipt_path, error):
    """Retain diagnostic chains only inside an already trusted private receipt area."""
    if receipt_path is None:
        return False
    try:
        receipt = private_file(receipt_path)
        parent = receipt.parent
        info = parent.stat()
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            return False
        if any((ancestor / '.git').exists() for ancestor in (parent, *parent.parents)):
            return False
        directory = Path(tempfile.mkdtemp(prefix='catalog-sync-failure.', dir=parent))
        directory.chmod(0o700)
        descriptor = os.open(directory / 'failure.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            traceback.print_exception(type(error), error, error.__traceback__, file=stream)
            stream.flush()
            os.fsync(stream.fileno())
        return True
    except Exception:
        # Diagnostic failure cannot authorize writes elsewhere or hide refusal.
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--container', default='calibre-web')
    parser.add_argument('--planner', type=Path, default=Path(os.environ.get('CALIBRE_IMPORT_PLANNER',
                                                                          '/usr/local/libexec/calibre-catalog-import')))
    args = parser.parse_args(argv)
    try:
        planner = load_planner(args.planner)
        if not args.apply:
            result = {'status': 'planned', 'counts': planner.plan(args.library)['counts']}
        elif args.receipt is None:
            raise Refused('verified_receipt_required')
        else:
            result = sync_catalog(args.library, planner, args.receipt, container=args.container)
        print(json.dumps(result, sort_keys=True))
        return 2 if result['status'] == 'rolled_back' else 0
    except NeedsRecovery as error:
        record_private_failure(args.receipt, error)
        print(json.dumps({'status': 'needs_recovery', 'error': 'verified_backup_recovery_required'}))
        return 3
    except Exception as error:
        record_private_failure(args.receipt, error)
        print(json.dumps({'status': 'refused', 'error': 'catalog_sync_not_completed'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
