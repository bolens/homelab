"""Serial, source-preserving pack inventory and member recovery."""
from contextlib import closing
import hashlib
import base64
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time
import xml.etree.ElementTree as ET
import zipfile

from import_match import catalog, match, metadata, number, title
from import_recovery import submit, issue_state
from maintenance import preserves, scoped_file
from pdf_conversion import Pending as PDFPending
from normalize import archive_suffix, digest, identity, save, sync_directory, api_path


# A named cover is supplemental only when it contains cover-sized content.
COVER = re.compile(r'\b(covers?|cover collection|cover gallery)\b', re.I)
EXTRA = re.compile(r'\b(ashcan|sketchbook|extras?|director[\W_]*s cut|preview|artbook)\b', re.I)
FILENAME = re.compile(r'(.+?)\s+#?(\d+(?:\.\d+)?)\s+\(((?:19|20)\d{2})\)(?:\s*\([^)]*\)|\s*\[[^]]*\])*')


def evidence(path):
    meta = metadata(path)
    clean = re.sub(r'\[__\d+__\]', '', path.stem).strip()
    parsed = FILENAME.fullmatch(clean)
    ids = set(re.findall(r'\[__(\d+)__\]', path.name) + re.findall(r'4000-(\d+)(?:/|\b)', meta.get('Web', '')))
    if len(ids) > 1:
        raise ValueError('Conflicting issue identities')
    name = meta.get('Series') or (parsed[1] if parsed else '')
    num = meta.get('Number') or (parsed[2] if parsed else '')
    year = meta.get('Volume') if re.fullmatch(r'(19|20)\d{2}', meta.get('Volume', '')) else (parsed[3] if parsed else meta.get('Year', ''))
    if parsed and ((meta.get('Series') and title(meta['Series']) != title(parsed[1]))
                   or (meta.get('Number') and number(meta['Number']) != number(parsed[2]))
                   or (re.fullmatch(r'(19|20)\d{2}', meta.get('Volume', '')) and meta['Volume'] != parsed[3]
                       and meta.get('Year') != parsed[3])):
        raise ValueError('Filename and metadata disagree')
    edition = 'Digital' if re.search(r'\b(digital first|digital exclusive)\b|\[digital\]', clean, re.I) or meta.get('Format', '').lower() == 'digital' else ''
    return {'series': name, 'number': num, 'year': str(year or ''), 'issueid': next(iter(ids), ''), 'edition': edition}


def kind(path, info):
    # A cover-count annotation describes variants inside a full issue.
    name = re.sub(r'\(\s*\d+\s+covers?\s*\)', '', path.stem, flags=re.I) if info['page_count'] > 3 else path.stem
    if (COVER.search(name) and (info['page_count'] <= 3 or re.search(r'\bcovers\b|collection|gallery', name, re.I))) or EXTRA.search(name):
        return 'supplement'
    return 'annual' if re.search(r'\bannual\b', name, re.I) else 'issue'


def source_state(source, content=False):
    """Bounded source version, including an extracted companion when present."""
    source = Path(source)
    roots = [("source", source)]
    companion = source.with_suffix('') if source.suffix.lower() == '.zip' else None
    if source.is_file() and companion is not None and companion.exists():
        roots.append(("companion", companion))
    entries = []; total = 0
    for prefix, root in roots:
        if any(p.is_symlink() for p in (root, *root.parents)):
            raise ValueError('Linked pack source')
        paths = [root]
        if root.is_dir():
            for folder, dirs, files in os.walk(root, followlinks=False):
                paths.extend(Path(folder) / name for name in dirs + files)
                if len(paths) > 4001:
                    raise ValueError('Pack source exceeds limits')
        for path in sorted(paths):
            if path.is_symlink():
                raise ValueError('Linked pack source')
            info = path.stat()
            name = prefix + '/' + str(path.relative_to(root))
            if not path.is_file() and not path.is_dir():
                raise ValueError('Unsupported pack source')
            signature = [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
            checksum = None
            if path.is_file():
                total += info.st_size
                if total > 32 * 1024**3:
                    raise ValueError('Pack source exceeds limits')
                if content:
                    digest = hashlib.sha256()
                    with path.open('rb') as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                            digest.update(chunk)
                    after = path.stat()
                    if signature != [after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns]:
                        raise ValueError('Pack source changed')
                    checksum = digest.hexdigest()
            entries.append([name, 'file' if path.is_file() else 'directory', checksum if content else signature])
    if not any(entry[1] == 'file' for entry in entries):
        raise ValueError('Pack source has no files')
    return hashlib.sha256(json.dumps(entries, separators=(',', ':')).encode()).hexdigest()


class Packs:
    def __init__(self, maintenance):
        self.m = maintenance
        self.worker = maintenance.worker
        self.root = maintenance.state / 'packs'
        self.root.mkdir(exist_ok=True, mode=0o700)
        self.cache = Path(maintenance.settings.get('ddl_cache', ''))
        self.remote = Path(maintenance.settings.get('mylar_ddl_cache', ''))
        if self.cache not in self.m.roots or not self.remote.is_absolute() or not self.cache.is_dir():
            raise ValueError('Explicit shared cache mapping required')
        self.db = Path(self.worker.config['mylar'].get('config_dir', '/mylar')) / 'mylar.db'
        self.changed = False

    def report(self, value):
        from native_handoff import report
        return report(self.m, value)

    def local(self, remote):
        source = Path(remote)
        if not self.remote.is_absolute() or not source.is_relative_to(self.remote) or '..' in source.parts:
            raise ValueError('Pack is outside the shared cache')
        path = self.cache / source.relative_to(self.remote)
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Linked pack path')
        return path

    def inventory(self, record):
        directory = self.root / record['id']
        directory.mkdir(exist_ok=True, mode=0o700)
        receipt = directory / 'receipt.json'
        source = self.local(record['source'])
        previous = json.loads(receipt.read_text()) if receipt.exists() else None
        # Partial cleanup is tied to the retained receipt. Remaining originals
        # are checked by cleanup before it resumes; missing originals are expected.
        cleaning = previous is not None and previous.get('cleanup_verified_at')
        generation = None
        if (previous and record.get('source_generation') and previous.get('source_generation')
                and record['source_generation'] != previous['source_generation']):
            raise ValueError('Pack receipt generation differs from capture')
        if source.exists() and not cleaning:
            generation = source_state(source, content=True)
            expected = record.get('source_generation') or (previous or {}).get('source_generation')
            if expected and generation != expected:
                raise ValueError('Pack source generation changed')
            if previous and not expected:
                # Legacy receipts have no manifest. Their exact original hashes
                # and member set still have to match before receipt reuse.
                outer = previous.get('outer')
                if outer and (identity(source) != outer['identity'] or digest(source) != outer['sha256']):
                    raise ValueError('Legacy pack source changed')
                roots = [source] if source.is_dir() else []
                companion = source.with_suffix('') if source.suffix.lower() == '.zip' else None
                if companion is not None and companion.is_dir():
                    roots.append(companion)
                expected_files = {Path(m['source']): m for m in previous['members']
                                  if any(Path(m['source']).is_relative_to(root) for root in roots)}
                actual_files = {p for root in roots for p in root.rglob('*') if p.is_file()}
                if actual_files != set(expected_files) or any(
                        identity(path) != member['identity'] or digest(path) != member['sha256']
                        for path, member in expected_files.items()):
                    raise ValueError('Legacy pack inventory changed')
                if not outer and not roots:
                    original = next((m for m in previous['members'] if m['source'] == str(source)), None)
                    if not original or identity(source) != original['identity'] or digest(source) != original['sha256']:
                        raise ValueError('Legacy single pack source changed')
        if previous is not None:
            return receipt, previous
        outer = None
        companion = source.with_suffix('') if source.suffix.lower() == '.zip' else None
        if companion is not None and (not companion.is_dir() or companion.is_symlink()):
            companion = None
        single = None
        if source.is_file():
            try:
                info = self.m.info(source)
                nested = any(archive_suffix(Path(row['name'])) and
                             (Path(row['name']).suffix.lower() != '.pdf' or self.worker.pdf_policy['enabled'])
                             for row in info['other_files'])
                if info['page_count'] > 0 and not nested:
                    single = source
            except ValueError:
                pass
        if source.is_file() and single is None:
            # Reuse the pinned bounded extractor, never ZIP extractall on untrusted paths.
            outer = {'source': str(source), 'identity': identity(source), 'sha256': digest(source)}
            target = directory / 'extracted'
            intent = directory / 'extraction.json'
            if intent.exists():
                old = json.loads(intent.read_text())
                if old != outer:
                    raise ValueError('Extraction source changed')
                if target.exists():
                    # No inventory receipt means no members could have been imported.
                    # This owned intermediate is reproducible from the unchanged source.
                    if target.is_symlink() or not target.is_dir():
                        raise ValueError('Extraction destination is unsafe')
                    shutil.rmtree(target)
            elif target.exists():
                raise ValueError('Unowned extraction output retained for review')
            save(intent, outer)
            self.worker.convert_tool('archive-extract', '--apply', '--output', target, source)
            if identity(source) != outer['identity'] or digest(source) != outer['sha256']:
                raise ValueError('Pack changed during extraction')
            source = target
        if single is not None:
            source = single.parent
        if not source.is_dir():
            raise ValueError('Pack source is missing')
        paths = [single] if single is not None else []
        total = 0
        import itertools
        roots = [source] + ([companion] if companion is not None and outer else [])
        for folder, dirs, files in ([] if single is not None else itertools.chain.from_iterable(os.walk(root, followlinks=False) for root in roots)):
            if any((Path(folder) / name).is_symlink() for name in dirs + files):
                raise ValueError('Linked pack member')
            for name in sorted(files):
                path = Path(folder) / name
                total += path.stat().st_size
                paths.append(path)
                if len(paths) > 2000 or total > 32 * 1024**3:
                    raise ValueError('Pack inventory exceeds limits')
        members = []
        for path in sorted(paths):
            before = identity(path)
            checksum = digest(path)
            if identity(path) != before:
                raise ValueError('Pack member changed')
            relative = Path('extracted') / path.relative_to(source) if path.is_relative_to(source) else Path('companion') / path.relative_to(companion)
            token = hashlib.sha256(os.fsencode(relative) + b'\0' + checksum.encode()).hexdigest()
            members.append({'id': token, 'name': path.name, 'source': str(path), 'identity': before,
                            'sha256': checksum, 'format': archive_suffix(path) or path.suffix,
                            'kind': 'review', 'phase': 'discovered'})
        if source_state(self.local(record['source']), content=True) != generation:
            raise ValueError('Pack source changed during inventory')
        value = {'id': record['id'], 'capture_source': str(self.local(record['source'])),
                 'source_generation': generation, 'source': str(source), 'outer': outer, 'inventory_complete': True,
                 'members': members, 'created_at': time.time()}
        save(receipt, value)
        return receipt, value

    def prepared(self, member, directory):
        source = Path(member['source'])
        if identity(source) != member['identity'] or digest(source) != member['sha256']:
            raise ValueError('Source version changed')
        info = self.m.info(source)
        if not info['page_count']:
            raise ValueError('Not a comic archive; retained for review')
        stage = self.cache / ('.mylar-pack-' + member['id'])
        stage.mkdir(exist_ok=True, mode=0o700)
        output = stage / (source.name[:-len(archive_suffix(source))] + '.cbz')
        if not output.exists():
            required = source.stat().st_size * 3
            if source.suffix.lower() == '.pdf':
                from pdf_conversion import derivative
                required = derivative(self.worker, source).stat().st_size * 2
            if shutil.disk_usage(stage).free < required + 128 * 1024**2:
                raise ValueError('Insufficient conversion space')
            if source.suffix.lower() == '.cbz' and zipfile.is_zipfile(source):
                shutil.copyfile(source, output)
                with output.open('rb') as stream:
                    os.fsync(stream.fileno())
            else:
                self.worker.convert_tool('comic-to-cbz', '--apply', '--output', output, source)
        if not preserves(info, self.m.info(output)):
            raise ValueError('Converted content differs')
        member['kind'] = kind(source, info)
        member['prepared'] = str(output)
        if 'original_metadata' not in member:
            with zipfile.ZipFile(output) as archive:
                entries = [r for r in archive.infolist() if Path(r.filename).name.lower() == 'comicinfo.xml']
                if len(entries) > 1 or any(r.file_size > 262144 for r in entries):
                    raise ValueError('Ambiguous or oversized original metadata')
                member['original_metadata'] = {r.filename: base64.b64encode(archive.read(r)).decode('ascii') for r in entries}
        return output, info

    def parent(self, points):
        names = {title(points['series']), title(re.sub(r'\bannual\b', '', points['series'], flags=re.I))}
        with closing(sqlite3.connect('file:' + str(self.db) + '?mode=ro', uri=True)) as database:
            rows = database.execute('SELECT ComicID,ComicName,ComicYear,ComicLocation FROM comics').fetchall()
        rows = [r for r in rows if title(r[1]) in names and str(r[2]) == points['year']]
        if len(rows) != 1:
            return None
        from publication_guard import catalog_path
        folder = catalog_path(self.worker,rows[0][3] or '')
        if not folder.is_absolute() or not any(folder.is_relative_to(root) for root in self.worker.roots):
            return None
        return rows[0]

    def destination(self, matched):
        with closing(sqlite3.connect('file:' + str(self.db) + '?mode=ro', uri=True)) as database:
            current = issue_state(database, matched)
            parent = database.execute('SELECT ComicLocation FROM comics WHERE ComicID=?', [matched['comicid']]).fetchone()
            if current and current[0] in ('Downloaded', 'Archived') and current[1] and parent and parent[0]:
                from publication_guard import catalog_path
                path = catalog_path(self.worker,Path(parent[0]) / current[1])
                return path if scoped_file(path, self.worker.roots) else None
        return None

    def preserve_extra(self, source, member, points, info, comicid=None):
        authority=None
        if self.worker.config.get('writer_state') is not None:
            from publication_guard import current
            authority=current(self.worker)
            source_proof=authority.unowned_check(source)
        if comicid is None:
            parent = self.parent(points)
        else:
            # An alternate scan already has a verified issue owner. Its release
            # year need not be the parent series start year.
            with closing(sqlite3.connect('file:' + str(self.db) + '?mode=ro', uri=True)) as database:
                rows = database.execute('SELECT ComicID,ComicName,ComicYear,ComicLocation FROM comics WHERE ComicID=?', [comicid]).fetchall()
            parent = rows[0] if len(rows) == 1 else None
        if not parent:
            raise ValueError('Related series is not uniquely established')
        from publication_guard import catalog_path
        parent_path=catalog_path(self.worker,parent[3])
        folder = parent_path.with_name(parent_path.name + ' - Extras')
        if folder.is_symlink() or any(p.is_symlink() for p in folder.parents):
            raise ValueError('Linked supplement destination')
        # The configured library must still be mounted; never make a replacement root.
        if not any(r.is_dir() and folder.is_relative_to(r) for r in self.worker.roots):
            raise ValueError('Library mount unavailable')
        folder.mkdir(exist_ok=True)
        target = folder / (source.stem + ' [' + member['sha256'][:12] + '].cbz')
        temporary = folder / ('.' + member['id'] + '.tmp.cbz')
        if not target.exists():
            meta = metadata(source)
            for field in ('Web', 'Number', 'Count', 'Volume'):
                meta.pop(field, None)
            meta.update(Series=str(parent[1]) + ' (' + str(parent[2]) + ') - Extras', Title=member['name'],
                        Notes='Related pack supplement or alternate copy; does not satisfy a full issue.')
            root = ET.Element('ComicInfo')
            for key, value in meta.items():
                ET.SubElement(root, key).text = value
            with zipfile.ZipFile(source) as original, zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED) as output:
                for entry in original.infolist():
                    if Path(entry.filename).name.lower() != 'comicinfo.xml':
                        with original.open(entry) as reader, output.open(entry, 'w') as writer:
                            shutil.copyfileobj(reader, writer, 1024 * 1024)
                output.writestr('ComicInfo.xml', ET.tostring(root, encoding='utf-8', xml_declaration=True))
            if not preserves(info, self.m.info(temporary), metadata_changed=True):
                raise ValueError('Supplement preservation failed')
            with temporary.open('rb') as stream:
                os.fsync(stream.fileno())
            if authority is not None:
                from publication_guard import evidence,Unavailable
                if not evidence.same_json(source_proof,authority.unowned_check(source)):
                    raise Unavailable('Supplement source or authority changed')
                candidate=authority.unowned_check(temporary)
                if candidate['inventory']['payload']!=source_proof['inventory']['payload']:
                    raise Unavailable('Supplement member bytes changed')
            os.link(temporary, target)
            temporary.unlink()
            sync_directory(folder)
            self.changed = True
        if not preserves(info, self.m.info(target), metadata_changed=True):
            raise ValueError('Existing supplement differs')
        if authority is not None:
            from publication_guard import evidence,Unavailable
            target_proof=authority.unowned_check(target)
            if (not evidence.same_json(source_proof,authority.unowned_check(source))
                    or target_proof['inventory']['payload']!=source_proof['inventory']['payload']):
                raise Unavailable('Supplement publication no longer matches source')
        member.update(kind='supplement', phase='preserved', comicid=str(parent[0]), destination=str(target),
                      destination_sha256=digest(target), destination_identity=identity(target), reason='Related supplement preserved')

    def member(self, member, directory):
        if member['phase'] in ('confirmed', 'preserved'):
            if member['kind'] == 'sidecar':
                if digest(directory / ('sidecar-' + member['id'])) != member['sha256']:
                    raise ValueError('Retained sidecar changed')
                return
            target = Path(member['destination'])
            if scoped_file(target, self.worker.roots):
                if member.get('destination_identity') == identity(target):
                    return
                if digest(target) == member['destination_sha256']:
                    member['destination_identity'] = identity(target)
                    return
            raise ValueError('Previously verified library file changed')
        original = Path(member['source'])
        if not archive_suffix(original):
            if original.suffix.lower() in ('.txt', '.nfo', '.diz', '.url') and original.stat().st_size <= 262144:
                raw = original.read_bytes()
                if hashlib.sha256(raw).hexdigest() != member['sha256']:
                    raise ValueError('Pack sidecar changed')
                saved = directory / ('sidecar-' + member['id'])
                if not saved.exists():
                    saved.write_bytes(raw)
                    with saved.open('rb') as stream:
                        os.fsync(stream.fileno())
                if digest(saved) != member['sha256']:
                    raise ValueError('Retained sidecar changed')
                member.update(kind='sidecar', phase='preserved', sidecar=base64.b64encode(raw).decode('ascii'),
                              reason='Non-comic sidecar retained in private receipt')
            else:
                member.update(kind='sidecar', phase='review', reason='Non-comic pack member retained for review')
            return
        prepared, info = self.prepared(member, directory)
        points = evidence(prepared)
        if member['kind'] == 'supplement':
            self.preserve_extra(prepared, member, points, info)
            return
        rows = catalog(self.db)
        # Include downloaded identities for comparison before considering another import.
        eligible = [tuple(list(r[:2]) + ['Wanted'] + list(r[3:])) for r in rows]
        matched = match(prepared, self.db, eligible)
        if not matched and not member.get('catalog_attempted') and points['series'] and number(points['number']) is not None:
            member['catalog_attempted'] = True
            return  # Persist intent before the next cycle makes an external request.
        previous = member.get('catalog_result') or {}
        retry_due = previous.get('phase') == 'retry' and time.time() >= previous.get('retry_at', 0)
        if not matched and member.get('catalog_attempted') and (not previous or retry_due):
            # Server stores the idempotent request before catalog mutations.
            parent = self.parent(points)
            if parent:
                points['parentid'] = str(parent[0])
            from native_handoff import request, guard
            result = request(self.m,'packCatalog',{'evidence':json.dumps(points),
                'catalog_attempt':str(previous.get('attempts',0)+1)},[guard(prepared)])
            if result is None:
                member.update(phase='discovered',reason='Catalog handoff prepared; original retained')
                return
            member['catalog_result'] = result
            if result.get('phase') == 'ready':
                matched = {k: result[k] for k in ('issueid', 'comicid')}
        if not matched and member.get('catalog_result', {}).get('phase') == 'ready':
            matched = {k: member['catalog_result'][k] for k in ('issueid', 'comicid')}
        if not matched:
            member.update(phase='review', reason='Catalog lookup unavailable; waiting for scheduled retry'
                          if member.get('catalog_result', {}).get('phase') == 'retry' else
                          'No unique catalog identity; original retained')
            return
        from edition_evidence import landscape
        with closing(sqlite3.connect('file:' + str(self.db) + '?mode=ro', uri=True)) as database:
            if not issue_state(database, matched):
                member.update(phase='review', reason='Catalog identity changed; original retained')
                return
            columns = {r[1] for r in database.execute('PRAGMA table_info(comics)')}
            row = database.execute('SELECT Type FROM comics WHERE ComicID=?', [matched['comicid']]).fetchone() if 'Type' in columns else None
        actual_edition = row[0] if row else ''
        if ((points['edition'] and actual_edition != points['edition'])
                or (actual_edition != 'Digital' and landscape(prepared))):
            member.update(phase='review', reason='Edition evidence conflicts; verify digital versus print identity')
            return
        from publication_guard import import_check
        import_check(self.worker, prepared, matched)
        member.update(**matched)
        target = self.destination(matched)
        if target:
            from publication_guard import confirmation_check
            confirmation_check(self.worker, prepared, target, matched)
            if preserves(info, self.m.info(target), metadata_changed=True):
                member.update(phase='confirmed', destination=str(target), destination_sha256=digest(target), destination_identity=identity(target), reason='Library content verified')
            else:
                # A different scan is worth retaining, without replacing an existing issue.
                self.preserve_extra(prepared, member, points, info, comicid=matched['comicid'])
            return
        result = submit(self.m, prepared, matched)
        member.update(phase='submitted' if result == 'import_queued' else 'ready' if result == 'ready' else 'review',
                      reason='Import submitted; awaiting content verification' if result == 'import_queued' else 'Import retained for verification')

    def cleanup(self, receipt, value):
        if not value['members'] or any(m['phase'] not in ('confirmed', 'preserved') for m in value['members']):
            return
        if not self.m.idle():
            return
        # Historical verification is not permission to delete a current repeat.
        # Recheck all members before writing intent or removing any source.
        if self.worker.config.get('writer_state') is not None:
            from publication_guard import confirmation_check, Unavailable
            for member in value['members']:
                if member['kind'] == 'sidecar':
                    continue
                if member['phase'] != 'confirmed':
                    raise Unavailable('Supplement cleanup requires reviewed derivative ownership')
                match = {key:member.get(key) for key in ('issueid','comicid')}
                source = Path(member['source'])
                target = Path(member['destination'])
                confirmation_check(self.worker, source if source.exists() else target, target, match)
        # Verify every destination and every source before removing any source.
        for member in value['members']:
            source = Path(member['source'])
            if member.get('prepared'):
                prepared = Path(member['prepared'])
                if prepared.exists() and (prepared.parent != self.cache / ('.mylar-pack-' + member['id'])
                        or not scoped_file(prepared, [self.cache])
                        or not preserves(self.m.info(prepared), self.m.info(Path(member['destination'])), metadata_changed=True)):
                    raise ValueError('Preparation copy changed before cleanup')
            if source.exists() and (identity(source) != member['identity'] or digest(source) != member['sha256']):
                raise ValueError('Pack source changed before cleanup')
            if member['kind'] == 'sidecar':
                if digest(receipt.parent / ('sidecar-' + member['id'])) != member['sha256']:
                    raise ValueError('Sidecar retention failed')
            elif (not scoped_file(Path(member['destination']), self.worker.roots)
                  or digest(Path(member['destination'])) != member['destination_sha256']):
                raise ValueError('Pack destination changed before cleanup')
        outer = value.get('outer')
        if outer and Path(outer['source']).exists():
            source = Path(outer['source'])
            if not scoped_file(source, self.m.roots) or identity(source) != outer['identity'] or digest(source) != outer['sha256']:
                raise ValueError('Outer pack changed before cleanup')
        # Resumed cleanup may have fewer original files, but must never remove
        # a shared source after a new, uninventoried file has arrived there.
        original = Path(value.get('capture_source') or
                        (value['outer']['source'] if value.get('outer') else value['source']))
        roots = [original] if original.is_dir() else []
        companion = original.with_suffix('') if original.suffix.lower() == '.zip' else None
        if companion is not None and companion.is_dir():
            roots.append(companion)
        owned = {Path(m['source']) for m in value['members']}
        for root in roots:
            if any(path.is_symlink() for path in (root, *root.parents)):
                raise ValueError('Linked cleanup source')
            for count, path in enumerate(root.rglob('*'), 1):
                if count > 4000:
                    raise ValueError('Cleanup source exceeds limits')
                if path.is_symlink() or (path.is_file() and path not in owned):
                    raise ValueError('Pack contains uninventoried sources before cleanup')
        value.setdefault('cleanup_verified_at', time.time())
        save(receipt, value)
        # Publish the cleanup intent before removing any source, so native
        # discovery cannot interpret interrupted cleanup as a new delivery.
        result=self.report(dict(value, members=[
            {k: v for k, v in m.items() if k != 'original_metadata'} for m in value['members']]))
        if self.worker.config.get('writer_state') is not None and (
                not isinstance(result,dict) or result.get('phase')!='confirmed'
                or type(result.get('recorded')) is not int or result['recorded']!=len(value['members'])):
            return  # Native cleanup intent must be durably acknowledged first.
        for member in value['members']:
            source = Path(member['source'])
            if source.exists() and (scoped_file(source, self.m.roots) or scoped_file(source, [receipt.parent / 'extracted'])):
                source.unlink()
                sync_directory(source.parent)
        for member in value['members']:
            if member.get('prepared'):
                prepared = Path(member['prepared'])
                if prepared.exists():
                    prepared.unlink()
                    sync_directory(prepared.parent)
                try:
                    prepared.parent.rmdir()
                except OSError:
                    pass
        if outer and Path(outer['source']).exists():
            Path(outer['source']).unlink()
            sync_directory(Path(outer['source']).parent)
        value['cleaned_at'] = time.time()
        save(receipt, value)

    def cycle(self):
        if not self.m.settings.get('pack_import', False):
            return set()
        from maintenance import native_work
        work = native_work(self.m,'packWork')
        if not work.get('enabled'):
            return set()
        protected = set()
        for source in work.get('protected', [r['source'] for r in work['packs']]):
            try:
                protected.add(self.local(source))
            except ValueError:
                pass
        for record in work['packs']:
            if record.get('phase') == 'confirmed' and record.get('cleanup_complete'):
                # Cleaned sources and worker receipts are no longer required.
                # Mylar rechecks the stored destination hashes before refreshing
                # stale signatures. Rejected proofs retain the original history.
                try:
                    self.report(dict(record, cleaned_at=time.time()))
                except Exception:
                    pass
                continue
            try:
                protected.add(self.local(record['source']))
                receipt, value = self.inventory(record)
                for member in value['members']:
                    try:
                        self.member(member, receipt.parent)
                    except PDFPending:
                        member.update(phase='discovered', reason='PDF saved; waiting for page rendering')
                    except Exception:
                        member.update(phase='review', reason='Member validation or import needs review; source retained')
                    save(receipt, value)
                    if self.m.import_submitted:
                        break
                self.report(dict(value, members=[{k: v for k, v in m.items() if k != 'original_metadata'} for m in value['members']]))
                if not value.get('cleaned_at'):
                    self.cleanup(receipt, value)
                    if value.get('cleaned_at'):
                        self.report(dict(value, members=[{k: v for k, v in m.items() if k != 'original_metadata'} for m in value['members']]))
            except PDFPending:
                continue
            except Exception:
                # Surface a failure through worker health; leave all originals in place.
                if record.get('members'):
                    # A failed refresh must not replace earlier member proofs.
                    continue
                failure = {'id': record['id'], 'inventory_complete': False,
                           'members': [{'id': hashlib.sha256((record['id'] + ':failure').encode()).hexdigest(),
                                        'name': record['name'], 'kind': 'review', 'phase': 'review',
                                        'reason': 'Pack inventory or report failed; source retained'}]}
                self.report(failure)
                continue
            if self.m.import_submitted:
                break
        if self.changed:
            for library in self.worker.reader.call('/api/v1/libraries'):
                root = api_path(library.get('root', ''))
                if root in self.worker.roots:
                    self.worker.reader.call('/api/v1/libraries/' + library['id'] + '/scan', {})
        return protected
