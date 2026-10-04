"""Native ownership proofs and recoverable same-folder release name changes."""
import hashlib
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit


def regular(path, *, links=(1,)):
    path = Path(path)
    if (not path.is_absolute() or '..' in path.parts or str(path) != str(path.absolute())
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise ValueError('Unsafe release path')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink not in links:
        raise ValueError('Unsafe release file ownership')
    return info


def catalog(database, source):
    """Resolve exact existing location; include conflicting owners and deleted rows."""
    source = Path(source)
    found = []
    for parent in database.select('SELECT * FROM comics', []):
        if not parent['ComicLocation'] or Path(parent['ComicLocation']) != source.parent:
            continue
        for table in ('issues', 'annuals'):
            for row in database.select('SELECT * FROM '+table+' WHERE ComicID=?', [parent['ComicID']]):
                if row['Location'] and Path(row['Location']).name == row['Location'] and source.name == row['Location']:
                    found.append(dict(row=dict(row), parent=dict(parent), table=table))
    if len(found) != 1:
        raise ValueError('Release catalog ownership needs review')
    result = found[0]
    row = result['row']
    if row.get('Deleted') or row['Status'] not in ('Downloaded', 'Archived'):
        raise ValueError('Release is not an active existing library owner')
    from mylar import library_status
    owner = library_status.issue(database, row['IssueID'])
    if not owner or str(owner['ComicID']) != str(row['ComicID']):
        raise ValueError('Release catalog ownership is shadowed')
    return result


def parsed(database, parent, path):
    from mylar import filechecker, file_identity
    aliases = (parent.get('AlternateSearch') or '').split('##')
    for row in database.select('SELECT * FROM annuals WHERE ComicID=?', [parent['ComicID']]):
        if not row['Deleted']:
            aliases.append(row['ReleaseComicName']+'!!'+str(row['ReleaseComicID']))
    checker = filechecker.FileChecker(
        dir=str(path.parent), watchcomic=parent['ComicName'], Publisher=parent['ComicPublisher'],
        AlternateSearch='##'.join(x for x in aliases if x), comic_type=parent['Type'],
        single_issue_number=file_identity.single_issue_number(database, parent['ComicID'], parent['Total']))
    entries = [entry for entry in checker.listFiles().get('comiclist', [])
               if entry['ComicFilename'] == path.name and Path(entry['ComicLocation']) == path.parent]
    if len(entries) != 1:
        raise ValueError('Native release filename needs review')
    kind = parent.get('Corrected_Type') or parent['Type']
    if kind not in ('TPB', 'HC', 'GN', 'One-Shot'):
        kind = 'Print'
    file_identity.validate_rescan(database, parent, [dict(comiclist=entries)], booktype=kind)
    return entries[0], kind


def number_key(value):
    value = str(value).strip()
    for fraction, decimal in (('½', '.5'), ('¼', '.25'), ('¾', '.75')):
        if value == fraction:
            value = '0'+decimal
        elif re.fullmatch(r'[+-]?\d+'+fraction, value):
            value = value[:-1]+decimal
    match = re.fullmatch(r'([+-]?\d+(?:\.\d+)?)[\s.]*([A-Za-z]+)?', value)
    if not match:
        raise ValueError('Release issue numbering needs review')
    return Decimal(match[1]), (match[2] or '').casefold()


def release_volume(database, owner, root, path):
    record = owner['parent']
    if owner['table'] == 'annuals':
        rows = database.select('SELECT ComicVersion,ComicYear FROM comics WHERE ComicID=?', [owner['row']['ReleaseComicID']])
        if len(rows) > 1:
            raise ValueError('Annual release volume is ambiguous')
        record = dict(rows[0]) if rows else {}
    version = re.fullmatch(r'v?([1-9]\d{0,2})', str(record.get('ComicVersion') or ''), re.I)
    stem, _ = scanner(path.stem)
    stem = re.sub(r'\([^()]*\)|\[[^\[\]]*\]', '', stem)
    series = (owner['row'].get('ReleaseComicName') if owner['table'] == 'annuals'
              else owner['parent'].get('ComicName')) or root.findtext('Series')
    if series:
        words = re.findall(r'[^\W_]+', series)
        prefix = r'^[\W_]*'+r'[\W_]*'.join(re.escape(word) for word in words)+r'(?!\w)'
        stem = re.sub(prefix, '', stem, count=1, flags=re.I)
    explicit_tokens = re.findall(r'\b(?:v|vol\.?|volume)[.\s]*(\d+)\b', stem, re.I)
    kind = owner['parent'].get('Corrected_Type') or owner['parent'].get('Type')
    if kind in ('TPB', 'HC', 'GN') and explicit_tokens:
        # The last volume token numbers the collected issue, independently of its series run.
        number, suffix = number_key(owner['row']['Issue_Number'])
        if not suffix and number == int(explicit_tokens[-1]):
            explicit_tokens.pop()
    explicit = set(explicit_tokens)
    metadata = (root.findtext('Volume') or '').strip().lstrip('vV')
    volume = version[1] if version else None
    if owner['table'] == 'annuals' and volume is None and len(explicit) == 1:
        candidate = next(iter(explicit))
        if re.fullmatch(r'[1-9]\d{0,2}', candidate) and metadata.isdecimal() and int(metadata) == int(candidate):
            volume = str(int(candidate))
    metadata_matches_year = (re.fullmatch(r'(?:19|20)\d{2}', metadata)
                             and metadata == str(record.get('ComicYear') or ''))
    if volume and ((metadata and not metadata_matches_year and (not metadata.isdecimal() or int(metadata) != int(volume)))
                   or (explicit and {int(v) for v in explicit} != {int(volume)})):
        raise ValueError('Release volume evidence contradicts catalog')
    if owner['table'] == 'annuals' and explicit and volume is None:
        raise ValueError('Annual release volume needs review')
    return volume


def release_group(path, parsed_group):
    _, explicit = scanner(path.stem)
    if explicit:
        return explicit
    if not parsed_group:
        return None
    group = parsed_group.strip().lstrip('-')
    # Split only a legacy bracket block that explicitly combines source and group.
    blocks = re.findall(r'\(([^()]*)\)|\[([^\[\]]*)\]', path.stem)
    if any((left or right).strip().casefold() == group.casefold() for left,right in blocks):
        group = re.sub(r'^(?:digital|scan|webrip)-', '', group, flags=re.I)
    return group


def proposal(database, source):
    from mylar import tagger_archive, tagger_adapter, tagger_metadata
    path = Path(source)
    regular(path)
    if path.suffix.lower() != '.cbz':
        raise ValueError('Release naming requires a verified CBZ')
    owner = catalog(database, path)
    entry, kind = parsed(database, owner['parent'], path)
    archive = tagger_archive.snapshot(path)
    if archive.xml is None:
        raise ValueError('Release identity metadata is missing')
    root = tagger_metadata.parse(archive.xml)
    for field in ('Series', 'Number', 'Volume', 'Year', 'Web'):
        if len(root.findall(field)) > 1:
            raise ValueError('Repeated release identity metadata')
    if not root.findtext('Series') or not root.findtext('Number'):
        raise ValueError('Release identity metadata is incomplete')
    row, parent = owner['row'], owner['parent']
    year = str(row.get('IssueDate') or '')[:4]
    parsed_year = entry.get('IssueYear')
    if parsed_year is None and owner['table'] == 'issues' and root.findtext('Year') == year:
        web = root.findtext('Web') or ''
        ids = set(re.findall(r'4000-(\d+)(?:[/\s?#]|$)', web))
        linked = set()
        for link in re.findall(r'https?://[^\s;,]+', web, re.I):
            url = urlsplit(link)
            if (url.hostname in ('comicvine.gamespot.com', 'www.comicvine.gamespot.com',
                                 'comicvine.com', 'www.comicvine.com')
                    and url.username is None and url.password is None):
                linked.update(re.findall(r'(?:^|/)4000-(\d+)(?:/|$)', url.path))
        if ids == linked == {str(row['IssueID'])}:
            parsed_year = year
    if (not re.fullmatch(r'(?:19|20)\d{2}', year) or str(parsed_year) != year
            or (root.findtext('Year') and root.findtext('Year') != year)):

        raise ValueError('Publication or edition year needs review')
    if number_key(root.findtext('Number')) != number_key(row['Issue_Number']):
        raise ValueError('Release number contradicts catalog ownership')
    if any(p.is_file() or p.is_symlink() for p in path.parent.iterdir()
           if p.name.startswith(path.stem+'.') and p != path):
        raise ValueError('Release sidecars need a coordinated naming plan')
    volume = release_volume(database, owner, root, path)
    series = row['ReleaseComicName'] if owner['table'] == 'annuals' else parent['ComicName']
    checksum = tagger_adapter.fingerprint(path)
    if tagger_archive.identity(path.stat()) != archive.identity:
        raise ValueError('Release changed during naming proof')
    group = release_group(path, entry.get('scangroup'))
    return dict(version=1, source=str(path), sha256=checksum, issueid=str(row['IssueID']),
                comicid=str(row['ComicID']), table=owner['table'], status=row['Status'],
                series=series, number=row['Issue_Number'], year=year, type=kind,
                volume=volume,
                group=group)


def scanner(value):
    """Remove an explicit final release group from parser input only."""
    match = re.search(r'\)-([^()[\]]+)$', value)
    return (value[:match.start()+1], match[1]) if match else (value, None)



def collected(checker, value):
    """Read our explicit collected fields without conflating run and issue volume."""
    if getattr(checker, 'comic_type', None) not in ('GN', 'HC', 'TPB'):
        return None
    value, _ = scanner(value)
    match = re.fullmatch(r'(.+?)(?:\.v([1-9]\d{0,2}))?\.v([+-]?\d{3,}(?:\.\d+)?(?:\.[A-Za-z]+)?)'
                         r'\.\((GN|HC|TPB)\)\.\(((?:19|20)\d{2})\)(?:\.\([^()]*\))*', value)
    if not match or match[4] != checker.comic_type:
        return None
    import unicodedata
    def words(text):
        return re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', text).casefold())
    names = [checker.watchcomic or '']
    names.extend(name for name in (getattr(checker, 'AlternateSearch', None) or '').split('##')
                 if name and name != 'None' and '!!' not in name)
    for name in names:
        if words(match[1]) == words(name):
            return dict(series=name, number=match[3], year=match[5], kind=match[4])
    return None


def print_fields(checker, value):
    """Read explicit print fields only after an exact registered-title match."""
    if getattr(checker, 'comic_type', None) in ('GN', 'HC', 'TPB'):
        return None
    value, _ = scanner(value)
    if re.search(r'\(\s*#', value):
        return None
    names = [checker.watchcomic or '']
    names.extend(name for name in (getattr(checker, 'AlternateSearch', None) or '').split('##')
                 if name and name != 'None' and '!!' not in name)
    prefixes = []
    for name in names:
        words = re.findall(r'[^\W_]+', name)
        if not words:
            continue
        prefix = r'^[\W_]*'+r'[\W_]*'.join(re.escape(word) for word in words)+r'(?!\w)'
        matched = re.match(prefix, value, flags=re.I)
        if matched:
            prefixes.append((matched.end(), name))
    if not prefixes:
        return None
    end, name = max(prefixes, key=lambda item: item[0])
    match = re.fullmatch(r'(?:\.v([1-9]\d{0,2}))?\.([+-]?\d{3,}(?:\.\d+)?(?:\.[A-Za-z]+)?)'
                         r'\.\(((?:19|20)\d{2})\)(?:\.\([^()]*\))*', value[end:])
    if match:
        years = re.findall(r'\(\s*((?:19|20)\d{2})\s*\)', value)
        if any(year != match[3] for year in years):
            return None
        return dict(series=name, number=match[2], year=match[3], volume=match[1])
    return None


def release_number(value, checker=None):
    """Read a padded issue after excluding the verified catalog title."""
    names = [getattr(checker, 'watchcomic', None)]
    names.extend(name.split('!!', 1)[0] for name in
                 (getattr(checker, 'AlternateSearch', None) or '').split('##'))
    prefixes = []
    for name in names:
        words = re.findall(r'[^\W_]+', name or '')
        if not words:
            continue
        prefix = r'^[\W_]*'+r'[\W_]*'.join(re.escape(word) for word in words)+r'(?!\w)'
        matched = re.match(prefix, value, flags=re.I)
        if matched:
            prefixes.append(matched.end())
    if prefixes:
        value = value[max(prefixes):]
    match = re.search(r'\.([+-]?\d{3,}(?:\.\d+)?(?:\.[A-Za-z]+)?)\.\((?:19|20)\d{2}\)', value)
    return match[1] if match else None


def key(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def services():
    import mylar
    from mylar import db, workflow_store
    return db.DBConnection(), workflow_store.Store(mylar.DATA_DIR)


def stamp(path):
    from mylar import tagger_attributes
    info = regular(path, links=(1, 2))
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid], tagger_attributes.capture(path)


def verified(path, job):
    from mylar import tagger_adapter
    info, attributes = stamp(path)
    if info != job['stamp'] or attributes != job['attributes'] or tagger_adapter.fingerprint(path) != job['request']['sha256']:
        raise ValueError('Release publication ownership changed; recovery requires review')


def reject(database, store, job):
    """Recover rejection without recreating an already retired target link."""
    from mylar import pack_bindings
    from mylar.media_writer import sync
    request = job['request']; source = Path(request['source']); target = source.with_name(request['target'])
    verified(source, job)
    row = catalog(database, source)['row']
    if (str(row['IssueID']) != request['issueid'] or str(row['ComicID']) != request['comicid']
            or row['Status'] != job['status']):
        raise ValueError('Rejected release owner changed')
    if target.exists():
        verified(target, job); target.unlink(); sync(source.parent)
    verified(source, job)
    intent = job.get('pack_bindings')
    pack_bindings.finalize(store, dict(intent, destination=str(source)) if intent else None,
                           request['sha256'], catalog_owner={field: request[field] for field in ('issueid', 'comicid')})
    job['phase'] = 'rejected'; store.set('release_name', job['key'], job)
    return dict(version=1, key=job['key'], phase='rejected')


def finish(database, store, job):
    from mylar.media_writer import sync
    if job['phase'] == 'rejecting':
        return reject(database, store, job)
    request = job['request']; source = Path(request['source']); target = source.with_name(request['target'])
    if source.exists():
        verified(source, job)
    if target.exists():
        verified(target, job)
    else:
        if not source.exists():
            raise ValueError('Release publication paths missing; recovery requires review')
        os.link(source, target, follow_symlinks=False); sync(source.parent)
    try:
        owner = catalog(database, source)
    except ValueError:
        owner = catalog(database, target)
    row = owner['row']
    if (str(row['IssueID']) != request['issueid'] or str(row['ComicID']) != request['comicid']
            or owner['table'] != job['table'] or row['Status'] != job['status']):
        raise ValueError('Release catalog owner changed; recovery requires review')
    # Validate the final name with native matching before retiring its old path.
    try:
        entry, _ = parsed(database, owner['parent'], target)
        if str(entry.get('IssueYear')) != job['year']:
            raise ValueError('Renamed publication year contradicts ownership')
    except ValueError:
        if source.exists() and row['Location'] == source.name:
            verified(source, job); verified(target, job)
            job['phase'] = 'rejecting'; store.set('release_name', job['key'], job)
            reject(database, store, job)
        raise
    job['phase'] = 'linked'; store.set('release_name', job['key'], job)
    if source.exists():
        source.unlink(); sync(source.parent)
    job['phase'] = 'published'; store.set('release_name', job['key'], job)
    if row['Location'] != target.name:
        result = database.action('UPDATE '+job['table']+' SET Location=?,ComicSize=? WHERE IssueID=? AND ComicID=? AND Location=? AND Status=?',
                                 [target.name, target.stat().st_size, request['issueid'], request['comicid'], source.name, job['status']])
        if result is None or result.rowcount != 1:
            raise ValueError('Release catalog update failed; recovery remains fenced')
    verified(target, job)
    current = catalog(database, target)
    if str(current['row']['IssueID']) != request['issueid']:
        raise ValueError('Release catalog acknowledgement changed')
    from mylar import pack_bindings
    pack_bindings.finalize(store, job.get('pack_bindings'), request['sha256'],
                           catalog_owner={field: str(current['row'][native]) for field, native in
                                          (('issueid', 'IssueID'), ('comicid', 'ComicID'))})
    job['phase'] = 'committed'; store.set('release_name', job['key'], job)
    return dict(version=1, key=job['key'], phase='committed', source=str(source), destination=str(target), sha256=request['sha256'])


def bind_store(writer, store):
    """A missing/remounted journal must not look like an empty recovery queue."""
    from mylar.media_writer import sync
    path = store.path
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Linked release journal')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Invalid release journal')
    expected = (hashlib.sha256(json.dumps([info.st_dev, info.st_ino]).encode()).hexdigest()+'\n').encode()
    binding = writer.root/'release-state-v1.identity'
    if not binding.exists() and writer.fenced(release=True):
        raise ValueError('Pending release recovery has no journal binding')
    try:
        fd = os.open(binding, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    else:
        try:
            os.write(fd, expected); os.fsync(fd)
        finally:
            os.close(fd)
        sync(writer.root)
    fd = os.open(binding, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        bound = os.fstat(fd)
        if (not stat.S_ISREG(bound.st_mode) or bound.st_nlink != 1
                or bound.st_uid != os.geteuid() or stat.S_IMODE(bound.st_mode) != 0o600
                or os.read(fd, 66) != expected):
            raise ValueError('Release journal identity changed; review required')
    finally:
        os.close(fd)


def recover(writer):
    database, store = services()
    bind_store(writer, store)
    for job in store.active('release_name', {'prepared', 'linked', 'published', 'rejecting'}):
        finish(database, store, job)
    writer.clear_release_pending()


def get(source):
    from mylar import native_writers
    with native_writers.operation():
        database, _ = services()
        return proposal(database, source)


def rename(raw):
    from mylar import native_writers
    request = json.loads(raw) if isinstance(raw, str) else raw
    if (not isinstance(request, dict) or set(request) != {'version', 'source', 'target', 'sha256', 'issueid', 'comicid'}
            or type(request['version']) is not int or request['version'] != 1
            or any(not isinstance(request[f], str) for f in ('source', 'target', 'sha256', 'issueid', 'comicid'))
            or not re.fullmatch(r'[a-f0-9]{64}', request['sha256'])
            or not request['issueid'].isdecimal() or not request['comicid'].isdecimal()
            or Path(request['target']).name != request['target'] or request['target'] in ('.', '..')
            or not request['target'].endswith('.cbz') or len(request['target'].encode()) > 255):
        raise ValueError('Invalid release naming request')
    with native_writers.operation() as writer:
        database, store = services(); token = key(request)
        previous = store.get('release_name', token)
        if previous:
            if previous['request'] != request:
                raise ValueError('Release request changed')
            if previous['phase'] == 'committed':
                target = Path(request['source']).with_name(request['target'])
                verified(target, previous)
                row = catalog(database, target)['row']
                if str(row['IssueID']) != request['issueid'] or str(row['ComicID']) != request['comicid']:
                    raise ValueError('Release acknowledgement ownership changed')
                return dict(version=1, key=token, phase='committed', destination=str(target), sha256=request['sha256'])
            raise ValueError('Release recovery is incomplete')
        info = proposal(database, request['source'])
        if any(info[f] != request[f] for f in ('source', 'sha256', 'issueid', 'comicid')):
            raise ValueError('Release naming proposal is stale')
        source = Path(request['source']); target = source.with_name(request['target'])
        if any(p.name.casefold() == target.name.casefold() for p in source.parent.iterdir()):
            raise ValueError('Release destination already exists')
        identity, attributes = stamp(source)
        job = dict(key=token, request=request, stamp=identity, attributes=attributes,
                   table=info['table'], status=info['status'], year=info['year'], phase='prepared')
        from mylar import pack_bindings
        job['pack_bindings'] = pack_bindings.capture(store, source, target,
            catalog_owner={field: request[field] for field in ('issueid', 'comicid')})
        bind_store(writer, store)
        writer.mark_release_pending()
        if not store.create('release_name', token, job):
            raise ValueError('Release journal already exists')
        try:
            result = finish(database, store, job)
        except ValueError:
            if job['phase'] == 'rejected':
                writer.clear_release_pending()
            raise
        writer.clear_release_pending()
        return result


def status(token):
    if not isinstance(token, str) or not re.fullmatch(r'[a-f0-9]{64}', token):
        raise ValueError('Invalid release journal token')
    from mylar import native_writers
    with native_writers.operation():
        _, store = services()
        job = store.get('release_name', token)
        return dict(version=1, key=token, phase=job['phase'] if job else 'absent')
