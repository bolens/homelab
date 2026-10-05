"""Native tagging producer requiring a coordinated writer owner.

Manual jobs publish in place and return canonical native receipts. Automatic jobs
return a verified disposable path, leaving placement to native post-processing.
"""
import os
from pathlib import Path
import stat
import sys
import tempfile
import uuid
import zipfile
import zlib

if __package__:
    from .tagger_archive import identity, regular, snapshot
    from .tagger_adapter import fingerprint
    from .tagger_metadata import overrides
    from .tagger_enrichment import supplements
else:
    from tagger_archive import identity, regular, snapshot
    from tagger_adapter import fingerprint
    from tagger_metadata import overrides
    from tagger_enrichment import supplements

# Only provider-owned fields explicitly present may replace existing values.
# Notes, page bookmarks, unknown extensions and unselected fields remain intact.
PROVIDER_FIELDS = {'series':'Series','issue':'Number','issue_count':'Count','title':'Title',
                   'description':'Summary','publisher':'Publisher','year':'Year','month':'Month',
                   'day':'Day','characters':'Characters','teams':'Teams','locations':'Locations',
                   'web_links':'Web'}
CREDIT_FIELDS = {'Writer':'Writer','Penciller':'Penciller','Inker':'Inker','Colorist':'Colorist',
                 'Letterer':'Letterer','Cover':'CoverArtist','Editor':'Editor','Translator':'Translator'}


def select(backend, legacy, modern, *args, **kwargs):
    """Dispatch exactly once; never silently fall back after a modern operation."""
    if backend == 'legacy':
        return legacy(*args, **kwargs)
    if backend == 'modern':
        return modern(*args, **kwargs)
    raise ValueError('Unsupported tagging backend')


class Service:
    def __init__(self, publisher, cache, lookup, handoff, coordinate, *, staging=None, publication=None):
        self.publisher, self.lookup, self.handoff = publisher, lookup, handoff
        if not callable(coordinate):
            raise ValueError('Global media writer exclusion is required')
        self.staging = staging
        self.publication = publication  # Exact private in-process job; never an API flag.
        self.coordinate = coordinate  # Must exclude writers for every journaled path.
        self.cache = Path(cache).absolute()
        if self.cache.anchor != '/' or '..' in self.cache.parts or any(p.is_symlink() for p in (self.cache, *self.cache.parents)):
            raise ValueError('Invalid staging root')
        info = self.cache.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Expected private owned staging root')

    def failure(self, state, manual):
        return self.handoff.Published(state) if manual else self.handoff.Failure(state)

    def check_publication(self, source, issueid, *, target=None):
        runtime = sys.modules.get('mylar')
        if runtime is None or not runtime.native_writers.publication_mode():
            return False
        if __package__:
            from . import publication_native as native, publication_transaction as transaction
        else:
            import publication_native as native, publication_transaction as transaction
        job = self.publication
        if not isinstance(job, transaction.Tagging):
            # Direct Service users must not recover old receipts or silently
            # publish through an unbound job after only an entry check.
            native.require(source, issueid=issueid)
            raise native.Review('tagging-producer-unbound')
        if __package__:
            from .tagger_pack import Publisher
            from .tagger_staging import Staging
        else:
            from tagger_pack import Publisher
            from tagger_staging import Staging
        recovery = job.value['recovery']
        if (recovery is None or type(self.publisher) is not Publisher
                or type(self.staging) is not Staging
                or str(self.publisher.root) != recovery['directories'][1][0]
                or str(self.cache) != recovery['directories'][2][0]
                or str(self.staging.root) != recovery['directories'][2][0]
                or str(self.staging.receipts) != recovery['directories'][3][0]
                or Path(self.publisher.config_root).absolute() != job.writer.root.parent):
            raise native.Review('tagging-producer-state-changed')
        if (str(source) != job.value['source']
                or (job.value['owner'] is not None and issueid != job.value['owner']['issueid'])):
            raise native.Review('tagging-producer-changed')
        job.proof(source, original=True)
        if target is not None:
            job.proof(target)
        return True

    def tag(self, filename, *, issueid, volumeid=None, manualmeta=False, enabled=True,
            comicrack=True, comicbooklover=False, conversion_only=False, overwrite=False,
            volume=None, reading_order=None, age_rating=None, publication_token=None, expected_digest=None):
        if any(type(v) is not bool for v in (manualmeta, enabled, comicrack, comicbooklover, conversion_only, overwrite)):
            raise ValueError('Expected explicit tagging policy')
        if not enabled or not comicrack or comicbooklover or conversion_only:
            return self.failure('unsupported', manualmeta)
        source = Path(filename).absolute()
        if source.anchor != '/' or source.suffix.lower() != '.cbz' or '..' in source.parts or any(p.is_symlink() for p in (source, *source.parents)):
            return self.failure('unsupported', manualmeta)
        try:
            updates = overrides(volume=volume, reading_order=reading_order, age_rating=age_rating)
            with self.coordinate():
                guarded = self.check_publication(source, issueid)
                if guarded:
                    if __package__:
                        from . import publication_guard as guard, publication_native as native
                    else:
                        import publication_guard as guard, publication_native as native
                    policy = dict(manualmeta=manualmeta, enabled=enabled, comicrack=comicrack,
                                  comicbooklover=comicbooklover, conversion_only=conversion_only,
                                  overwrite=overwrite, volume=volume, reading_order=reading_order,
                                  age_rating=age_rating, volumeid=volumeid, expected_digest=expected_digest)
                    if not guard.same_json(policy, self.publication.value['policy']):
                        raise native.Review('tagging-policy-changed')
                    # Only exact owned terminal witnesses allow historical reads.
                    # Unbound history is not upgraded and no receipt is replayed.
                    with os.scandir(self.publisher.root) as entries:
                        for entry in entries:
                            if entry.name.endswith('.json'):
                                try:self.publisher.read(entry.name[:-5])
                                except (guard.Unavailable,OSError,ValueError,TypeError,KeyError):
                                    raise native.Review('tagging-replay-unbound') from None
                for recovered in (() if guarded else self.publisher.recover_pending()):
                    if recovered.state not in ('committed', 'unchanged', 'failed', 'timed_out', 'unsupported'):
                        return self.failure('conflict', manualmeta)
                if publication_token is not None:
                    if not manualmeta:
                        return self.failure('unsupported', manualmeta)
                    receipt = self.publisher.receipt(publication_token)
                    if receipt.exists() or receipt.is_symlink():
                        if guarded:
                            raise native.Review('tagging-replay-unbound')
                        record = self.publisher.read(publication_token)
                        if record['source'] != str(source):
                            return self.failure('conflict', manualmeta)
                        return self.handoff.capture(self.publisher, publication_token)
                self.check_publication(source, issueid)
                original = snapshot(source)
                security = self.publisher.security(source)
                before = fingerprint(source)
                if expected_digest is not None and before != expected_digest:
                    return self.failure('conflict', manualmeta)
                if identity(source.lstat()) != original.identity:
                    return self.failure('conflict', manualmeta)
                # No-overwrite means an existing ComicInfo is not modified at all.
                if original.xml is not None and not overwrite:
                    metadata = {'series':'Preserve existing metadata'}
                    updates = {}
                    skip = True
                else:
                    self.check_publication(source, issueid)
                    with tempfile.TemporaryDirectory(prefix='.metadata-', dir=self.cache) as work:
                        fetched = self.lookup(issueid=issueid, volumeid=volumeid, workdir=work)
                    self.check_publication(source, issueid)
                    if fetched.state != 'ok':
                        return self.failure('timed_out' if fetched.state == 'timed_out' else 'failed', manualmeta)
                    metadata, skip = fetched.metadata, False
                    updates = {**supplements(original.xml, metadata=metadata), **updates}
                replacements = []
                if overwrite and not skip:
                    replacements = [field for key, field in PROVIDER_FIELDS.items() if metadata.get(key) is not None]
                    replacements += [CREDIT_FIELDS[c['role']] for c in metadata.get('credits', []) if c.get('role') in CREDIT_FIELDS]
                self.check_publication(source, issueid)
                token = publication_token or (self.publication.value['token'] if guarded else uuid.uuid4().hex)
                if guarded and token != self.publication.value['token']:
                    if __package__:
                        from .publication_native import Review
                    else:
                        from publication_native import Review
                    raise Review('tagging-token-changed')
                target = source
                if not manualmeta:
                    if self.staging is not None:
                        target = self.staging.allocate(token, source, before, original.identity)
                    else:
                        folder = Path(tempfile.mkdtemp(prefix='mylar_modern_', dir=self.cache))
                        target = folder/source.name
                    self.check_publication(source, issueid)
                    with regular(source) as reader, target.open('xb') as writer:
                        remaining = original.identity[2]
                        while remaining:
                            block = reader.read(min(1024*1024, remaining))
                            if not block:
                                raise ValueError('Source shrank')
                            writer.write(block); remaining -= len(block)
                        if reader.read(1):
                            raise ValueError('Source grew')
                        writer.flush(); os.fsync(writer.fileno())
                    target.chmod(original.mode)
                    if fingerprint(target) != before or identity(source.lstat()) != original.identity:
                        return self.failure('conflict', manualmeta)
                self.check_publication(source, issueid, target=target)
                result = self.publisher.tag(target, metadata, token=token, updates=updates,
                                            replace_fields=replacements, preserve_existing=skip,
                                            expected_digest=expected_digest)
                self.check_publication(source, issueid, target=target)
                if result.state not in ('committed', 'unchanged'):
                    return self.failure(result.state, manualmeta)
                if manualmeta:
                    self.check_publication(source, issueid)
                    return self.handoff.capture(self.publisher, token)
                if (fingerprint(source) != before or identity(source.lstat()) != original.identity
                        or self.publisher.security(source) != security):
                    return self.failure('conflict', False)
                self.check_publication(source, issueid, target=target)
                if self.staging is not None:
                    self.staging.ready(token, target)
                self.check_publication(source, issueid, target=target)
                return str(target)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, zipfile.BadZipFile, zlib.error, EOFError):
            # Keep uncertain staging for recovery; never remove publisher copies.
            return self.failure('failed', manualmeta)
