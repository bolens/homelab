"""Explicit rename/link publisher for NFS; never an exchange fallback.

The original inode is retained before a no-clobber link publishes the candidate.
The source name can be absent until recovery. All library writers must be excluded
until recovery completes. Version 2 receipts require this recovery implementation.
"""
import os
from pathlib import Path
import stat

if __package__:
    from . import tagger_adapter as base, tagger_attributes as attributes
    from .tagger_archive import identity, regular
else:
    import tagger_adapter as base
    import tagger_attributes as attributes
    from tagger_archive import identity, regular


class Publisher(base.Publisher):
    version = 2

    def read(self, token):
        record = super().read(token)
        if record.get('publication') != 'rename-link-v1':
            raise ValueError('Unknown publication strategy')
        attributes.validate(record.get('attributes'))
        return record

    def security(self, source):
        if source.stat().st_nlink != 1:
            raise ValueError('Hardlinked source')
        return {'publication':'rename-link-v1', 'attributes':attributes.capture(source)}

    def matches(self, path, record, candidate=False, links=(1,)):
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            return False
        info = path.lstat()
        return (stat.S_ISREG(info.st_mode) and info.st_nlink in links
                and list(identity(info)[:4]) == record['candidate_identity' if candidate else 'source_identity'][:4]
                and [stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid] == record['permissions']
                and attributes.capture(path) == record['attributes']
                and base.fingerprint(path) == record['after' if candidate else 'before'])

    def original_intact(self, record):
        return self.matches(Path(record['source']), record)

    def prepare_output(self, output, record):
        attributes.apply(output, record['attributes'])
        with regular(output) as stream:
            info = os.fstat(stream.fileno())
            if [stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid] != record['permissions']:
                raise ValueError('ACL changed file permissions')
            os.fsync(stream.fileno())
        if not self.original_intact(record):
            raise ValueError('Source changed before publication')

    def publish(self, source, output, record):
        folder = self.workspace(record)
        displaced = folder/'displaced.cbz'
        if displaced.exists() or displaced.is_symlink() or not self.original_intact(record):
            raise ValueError('Publication ownership changed')
        # The private workspace belongs to this operation. Even a raced source is
        # retained; no existing library filename is replaced with the candidate.
        os.rename(source, displaced)
        base.sync(source.parent); base.sync(folder)
        base._checkpoint('after_displace')
        if not self.matches(displaced, record):
            self.restore_name(displaced, source)
            raise ValueError('Displaced source changed')
        os.link(output, source, follow_symlinks=False)
        base.sync(source.parent)
        base._checkpoint('after_link')
        if not self.matches(source, record, True, (2,)) or not self.matches(displaced, record):
            raise ValueError('Published ownership changed')
        output.unlink()
        base.sync(folder)
        base._checkpoint('after_unlink')

    @staticmethod
    def restore_name(displaced, source):
        # Link is no-clobber even if another writer races the missing-name check.
        try:
            os.link(displaced, source, follow_symlinks=False)
            base.sync(source.parent)
        except FileExistsError:
            pass

    def committed_intact(self, record):
        source = Path(record['source'])
        if not self.matches(source, record, True):
            return False
        folder = source.parent/('.mylar-tag-'+record['token'])
        if folder.exists() or folder.is_symlink():
            folder = self.workspace(record)
            displaced = folder/'displaced.cbz'
            if displaced.exists() or displaced.is_symlink():
                return self.matches(displaced, record)
        return True  # A committed cleanup may have removed its workspace already.

    def _recover(self, record):
        if record['cleaned'] and record['state'] in ('committed', 'unchanged'):
            try:
                intact = self.matches(Path(record['source']), record, record['state'] == 'committed')
            except (OSError, ValueError):
                intact = False
            if not intact:
                return base.Result('conflict')
        if record['state'] != 'publishing':
            return super()._recover(record)
        source = Path(record['source'])
        try:
            folder = self.workspace(record)
            displaced, output = folder/'displaced.cbz', folder/'verified.cbz'
            if displaced.exists() or displaced.is_symlink():
                if not self.matches(displaced, record, links=(1, 2)):
                    self.restore_name(displaced, source)
                    return self.finish(record, 'conflict', cleanup=False)
                if not source.exists() and not source.is_symlink():
                    self.restore_name(displaced, source)
                if self.matches(source, record, links=(2,)):
                    # Crash before publication (or during rollback): restore the
                    # original inode, then finish without replaying a tagger write.
                    displaced.unlink(); base.sync(folder); base.sync(source.parent)
                    return self.finish(record, 'failed')
                if self.matches(source, record, True, (1, 2)):
                    if output.exists() or output.is_symlink():
                        if not self.matches(output, record, True, (2,)):
                            return self.finish(record, 'conflict', cleanup=False)
                        output.unlink(); base.sync(folder)
                    base.sync(source.parent)
                    return self.finish(record, 'committed')
                return self.finish(record, 'conflict', cleanup=False)
            # Rename did not happen, or recovery already restored the original.
            if self.original_intact(record):
                return self.finish(record, 'failed')
            return self.finish(record, 'conflict', cleanup=False)
        except (OSError, ValueError, KeyError, TypeError):
            return self.finish(record, 'conflict', cleanup=False)
