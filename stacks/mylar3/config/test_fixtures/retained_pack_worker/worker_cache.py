"""Worker consumption of the owning native Writer's finite cache snapshot."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import secrets
import stat

import cache_reservation as common

Held = common.Held


def path(value):
    if (type(value) is not str or '\\' in value or '\0' in value
            or not value.startswith('/') or '..' in Path(value).parts
            or str(Path(value)) != value or value == '/'):
        raise Held('Explicit canonical cache path required')
    return Path(value)


def checked_directory(value):
    value = path(str(value))
    fd, _ = common.open_directory(value)
    try:
        return tuple(common.directory_identity(os.fstat(fd)))
    finally:
        os.close(fd)


def signature(value, size):
    if type(value) is not list or len(value) != size or any(type(x) is not int for x in value):
        raise Held('Exact native cache identity required')
    return tuple(value)


class Policy:
    def __init__(self, maintenance):
        from maintenance import native_work
        from publication_guard import current
        self.m = maintenance
        self.authority = current(maintenance.worker)
        health = native_work(maintenance, 'getHealth')
        value = health.get('cache_policy') if type(health) is dict else None
        if (type(value) is not dict or set(value) != {'version', 'kind', 'data', 'roots', 'ddl', 'lock', 'config', 'maximum', 'reserve'}
                or type(value['version']) is not int or value['version'] != 1
                or value['kind'] != 'effective-ddl-cache-policy-v1'):
            raise Held('Owning native effective cache policy unavailable')
        for name in ('maximum', 'reserve'):
            if type(value[name]) is not int or not 0 < value[name] <= 4096 * common.GIB:
                raise Held('Finite native cache limits required')
        self.maximum, self.reserve = value['maximum'], value['reserve']
        data, lock, config = value['data'], value['lock'], value['config']
        if (type(data) is not dict or set(data) != {'path', 'identity5'}
                or type(lock) is not dict or set(lock) != {'path', 'signature9'}
                or type(config) is not dict or set(config) != {'path', 'signature9', 'sha256'}):
            raise Held('Exact native cache originals required')
        self.native_data = path(data['path'])
        self.data = path(str(self.authority.config))
        self.data5 = signature(data['identity5'], 5)
        if path(config['path']) != self.native_data / 'config.ini' or path(lock['path']) != self.native_data / 'cache-admission-v1.lock':
            raise Held('Native cache policy is outside its data root')
        self.config = self.data / 'config.ini'
        self.config9 = signature(config['signature9'], 9)
        self.sha256 = config['sha256']
        if type(self.sha256) is not str or re.fullmatch('[0-9a-f]{64}', self.sha256) is None:
            raise Held('Exact native cache configuration hash required')
        self.lock = self.data / 'cache-admission-v1.lock'
        self.lock9 = signature(lock['signature9'], 9)
        declared_native = path(maintenance.settings.get('mylar_ddl_cache'))
        declared_worker = path(maintenance.settings.get('ddl_cache'))
        self.mappings = ((self.native_data, self.data), (declared_native, declared_worker))
        roots = value['roots']
        if type(roots) is not list or not 1 <= len(roots) <= 2:
            raise Held('Bounded native cache roots required')
        self.roots = []
        self.root5 = []
        native_roots = []
        for root in roots:
            if type(root) is not dict or set(root) != {'path', 'identity5'}:
                raise Held('Exact native cache root required')
            native = path(root['path'])
            expected = signature(root['identity5'], 5)
            candidates = [worker / native.relative_to(source) for source, worker in self.mappings
                          if native.is_relative_to(source)]
            if not candidates or any(checked_directory(p) != expected for p in candidates):
                raise Held('Unmapped or shadowed native cache root')
            mapped = candidates[-1]
            if any(native.is_relative_to(old) or old.is_relative_to(native) for old in native_roots):
                raise Held('Overlapping native cache roots')
            if any(mapped.is_relative_to(old) or old.is_relative_to(mapped) for old in self.roots):
                raise Held('Conflicting worker cache roots')
            native_roots.append(native)
            self.roots.append(mapped)
            self.root5.append(expected)
        self.roots = tuple(self.roots)
        self.root5 = tuple(self.root5)
        ddl=value['ddl']
        if type(ddl) is not dict or set(ddl)!={'path','identity5'} or path(ddl['path'])!=declared_native:
            raise Held('Declared DDL alias differs from effective native policy')
        expected=signature(ddl['identity5'],5)
        originals=[root/declared_native.relative_to(original) for original,root in zip(native_roots,self.roots)
                   if declared_native.is_relative_to(original)]
        if len(originals)!=1:raise Held('Declared DDL subtree is outside aggregate policy')
        self.ddl=declared_worker;self.ddl_original=originals[0];self.ddl5=expected;self.alias_nodes={}
        for directory in (self.ddl_original,self.ddl):
            fd,nodes=common.open_directory(directory)
            try:
                if tuple(common.directory_identity(os.fstat(fd)))!=expected:
                    raise Held('Declared DDL subtree aliases a different directory')
                for name,row in nodes.items():
                    if name in self.alias_nodes and self.alias_nodes[name]!=row:raise Held('DDL alias ancestors conflict')
                    self.alias_nodes.setdefault(name,row)
            finally:os.close(fd)
        self.check()

    def destination_allowed(self,destination):
        self.check()
        return destination==self.ddl or self.ddl in destination.parents

    def check(self):
        from publication_guard import current
        if current(self.m.worker) is not self.authority:
            raise Held('Owning worker Writer changed')
        if checked_directory(self.data) != self.data5:
            raise Held('Native cache data alias changed')
        for root, expected in zip(self.roots, self.root5):
            if checked_directory(root) != expected:
                raise Held('Native cache root alias changed')
        for local, expected in ((self.config, self.config9), (self.lock, self.lock9)):
            fd = os.open(local, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                before = os.fstat(fd)
                if not stat.S_ISREG(before.st_mode) or common.identity(before) != expected or common.identity(os.lstat(local)) != expected:
                    raise Held('Native cache original changed')
                if local == self.config:
                    if before.st_size > 8 * 1024**2:
                        raise Held('Native cache configuration exceeds bounds')
                    with os.fdopen(os.dup(fd), 'rb') as stream:
                        raw = stream.read(8 * 1024**2 + 1)
                    if hashlib.sha256(raw).hexdigest() != self.sha256:
                        raise Held('Native cache configuration changed')
                if common.identity(os.fstat(fd)) != expected or common.identity(os.lstat(local)) != expected:
                    raise Held('Native cache original changed during check')
            finally:
                os.close(fd)
        # Close the original policy after all descriptor/read callbacks.
        if current(self.m.worker) is not self.authority:
            raise Held('Owning worker Writer changed')
        for name,row in self.alias_nodes.items():
            if common.directory_identity(os.lstat(name))!=row:raise Held('Original DDL alias ancestor changed')
        if (common.directory_identity(os.lstat(self.ddl))!=self.ddl5
                or common.directory_identity(os.lstat(self.ddl_original))!=self.ddl5
                or common.directory_identity(os.lstat(self.data)) != self.data5
                or any(common.directory_identity(os.lstat(root)) != expected for root,expected in zip(self.roots,self.root5))
                or common.identity(os.lstat(self.config)) != self.config9
                or common.identity(os.lstat(self.lock)) != self.lock9):
            raise Held('Original effective cache policy changed after read')

    def independent(self, directory):
        directory = path(str(directory))
        expected = checked_directory(directory)
        if any(directory.is_relative_to(root) or root.is_relative_to(directory) for root in self.roots):
            raise Held('Independent conversion must remain outside cache roots')
        # Detect bind aliases of cache descendants as well as lexical nesting.
        # The shared census first rejects unsafe or unstable cache namespaces.
        with self.allocation(self.ddl, 0, nodes=0):
            visited = 0
            for root in self.roots:
                for folder, dirs, files, fd in os.fwalk(root, follow_symlinks=False):
                    visited += 1 + len(dirs) + len(files)
                    if visited > common.MAX_ENTRIES or len(Path(folder).relative_to(root).parts) > 128:
                        raise Held('Independent path proof exceeds cache bounds')
                    if tuple(common.directory_identity(os.fstat(fd)))[:2] == expected[:2]:
                        raise Held('Independent conversion aliases a cache directory')
            if checked_directory(directory) != expected:
                raise Held('Independent conversion directory changed')
        return directory

    def allocation(self, destination, required=0, nodes=0):
        return Allocation(self, destination, required, nodes)


class Allocation(common.Allocation):
    readonly_lock = True

    def __init__(self, policy, destination, required=0, nodes=0):
        self.policy = policy
        super().__init__(destination, required, nodes)

    def destination_allowed(self):
        return self.policy.destination_allowed(self.destination)

    def configuration(self):
        self.policy.check()
        return self.policy.data, self.policy.roots, self.policy.maximum, self.policy.reserve

    def originals(self):
        super().originals()
        self.policy.check()

    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.policy.check()


def publish(policy, source, stage, output):
    """Reserve finalized bytes once; retain any failed partial for owning review."""
    source, stage, output = Path(source), Path(stage), Path(output)
    before = os.lstat(source)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise Held('Original finalized conversion required')
    if output.parent != stage or output.name in ('', '.', '..'):
        raise Held('Invalid pack cache output')
    exists = os.path.lexists(stage)
    destination = stage if exists else stage.parent
    with policy.allocation(destination, before.st_size, nodes=1 if exists else 2) as reservation:
        if not exists:
            os.mkdir(stage.name, 0o700, dir_fd=reservation.dirfd)
        stagefd, _ = common.open_directory(stage)
        leaf = '.partial-' + secrets.token_hex(16)
        try:
            if os.path.lexists(output):
                raise Held('Existing pack output retained')
            fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=stagefd)
            birth = os.fstat(fd)
            with os.fdopen(fd, 'wb') as target, source.open('rb') as original:
                if common.identity(os.fstat(original.fileno())) != common.identity(before):
                    raise Held('Finalized conversion changed')
                for chunk in iter(lambda: original.read(1024 * 1024), b''):
                    reservation.before_write(len(chunk))
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
                if (target.tell() != before.st_size
                        or common.identity(os.fstat(original.fileno())) != common.identity(before)
                        or common.identity(os.lstat(source)) != common.identity(before)):
                    raise Held('Finalized conversion changed during copy')
            reservation.originals()
            if common.directory_identity(os.fstat(stagefd)) != common.directory_identity(os.lstat(stage)):
                raise Held('Pack staging directory changed')
            current = os.stat(leaf, dir_fd=stagefd, follow_symlinks=False)
            if ((current.st_dev, current.st_ino) != (birth.st_dev, birth.st_ino)
                    or current.st_nlink != 1 or not stat.S_ISREG(current.st_mode)):
                raise Held('Original pack partial changed')
            os.link(leaf, output.name, src_dir_fd=stagefd, dst_dir_fd=stagefd, follow_symlinks=False)
            os.unlink(leaf, dir_fd=stagefd)
            os.fsync(stagefd)
        finally:
            os.close(stagefd)
    return output


def encoded(value):
    import json
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def read_original(path, expected=None, *, receipt=False, retained_source=False):
    """Hash one original nofollow file; small receipts additionally return bytes."""
    path=Path(path);parent,nodes=common.open_directory(path.parent);fd=None
    try:
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
        z=os.fstat(fd);row=common.identity(z)
        if (not stat.S_ISREG(z.st_mode) or z.st_nlink<1 or (not retained_source and z.st_nlink!=1) or (expected is not None and row!=expected)
                or (receipt and (z.st_uid!=os.geteuid() or stat.S_IMODE(z.st_mode)!=0o600 or not 0<z.st_size<=65536))):
            raise Held('Original conversion file unavailable')
        digest=hashlib.sha256();parts=[];remaining=z.st_size
        while remaining:
            chunk=os.read(fd,min(remaining,1024**2))
            if not chunk:raise Held('Original conversion file truncated')
            remaining-=len(chunk);digest.update(chunk)
            if receipt:parts.append(chunk)
        if common.identity(os.fstat(fd))!=row:raise Held('Original conversion file changed')
    finally:
        if fd is not None:os.close(fd)
        os.close(parent)
    for node,value in nodes.items():
        if common.directory_identity(os.lstat(node))!=value:raise Held('Original conversion ancestor changed')
    if common.identity(os.lstat(path))!=row:raise Held('Original conversion file changed')
    return row,digest.hexdigest(),b''.join(parts)


@contextmanager
def conversion(policy, directory, member, source9, filename, make, verify):
    """One exact finalized attempt per source; incomplete/unknown attempts hold."""
    import json
    source=Path(member['source'])
    request=dict(member=member['id'],source=str(source),source9=list(source9),sha256=member['sha256'],identity=list(member['identity']),output=filename)
    request_raw=encoded(request)
    if Path(filename).name!=filename or filename in ('','.', '..','finalized-v1.json'):
        raise Held('Invalid conversion output name')
    directory=policy.independent(directory)
    work=directory/('pack-conversion-'+hashlib.sha256(request_raw).hexdigest())
    prepared=work/filename;receipt=work/'finalized-v1.json'
    fresh=not os.path.lexists(work)
    if fresh:
        # Minimum positive admission prevents work birth at an already full cache.
        # Exact finalized-size admission is still independently required later.
        with policy.allocation(policy.ddl,1,nodes=2):pass
        try:work.mkdir(mode=0o700)
        except FileExistsError:raise Held('Concurrent conversion attempt retained for owning review') from None
    fd,nodes=common.open_directory(work)
    try:
        z=os.fstat(fd);work5=common.directory_identity(z)
        if z.st_uid!=os.geteuid() or stat.S_IMODE(z.st_mode)!=0o700:
            raise Held('Original conversion workspace unavailable')
    finally:os.close(fd)
    if fresh:
        parent,_=common.open_directory(directory)
        try:os.fsync(parent)
        finally:os.close(parent)
        make(prepared);verify(prepared)
        source_row,source_sha,_=read_original(source,tuple(source9),retained_source=True)
        if source_sha!=request['sha256']:raise Held('Original conversion source changed')
        output9,output_sha,_=read_original(prepared)
        outputfd=os.open(prepared,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            if common.identity(os.fstat(outputfd))!=output9:raise Held('Original finalized conversion changed')
            os.fsync(outputfd)
            if common.identity(os.fstat(outputfd))!=output9:raise Held('Original finalized conversion changed')
        finally:os.close(outputfd)
        if common.identity(os.lstat(prepared))!=output9:raise Held('Original finalized conversion changed')
        value=dict(version=1,kind='finalized-pack-conversion-v1',request=request,workspace5=list(work5),output9=list(output9),sha256=output_sha)
        raw=encoded(value);fd=os.open(receipt,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
            fresh_receipt9=common.identity(os.fstat(stream.fileno()))
        fd,_=common.open_directory(work)
        try:os.fsync(fd)
        finally:os.close(fd)
    names=tuple(sorted(os.listdir(work)))
    if names!=tuple(sorted((filename,receipt.name))):raise Held('Incomplete conversion attempt retained for owning review')
    receipt9,_,raw=read_original(receipt,fresh_receipt9 if fresh else None,receipt=True)
    if fresh and raw!=encoded(value):raise Held('Fresh conversion receipt changed')
    try:value=json.loads(raw)
    except (ValueError,UnicodeError):raise Held('Unknown conversion attempt retained for owning review') from None
    if (type(value) is not dict or set(value)!={'version','kind','request','workspace5','output9','sha256'}
            or type(value['version']) is not int or value['version']!=1 or value['kind']!='finalized-pack-conversion-v1'
            or encoded(value)!=raw or encoded(value['request'])!=request_raw or signature(value['workspace5'],5)!=work5):
        raise Held('Changed conversion receipt retained for owning review')
    output9=signature(value['output9'],9);output_sha=value['sha256']
    if type(output_sha) is not str or re.fullmatch('[0-9a-f]{64}',output_sha) is None:
        raise Held('Original finalized conversion hash required')
    if read_original(prepared,output9)[1]!=output_sha or read_original(source,tuple(source9),retained_source=True)[1]!=request['sha256']:
        raise Held('Original finalized conversion changed')
    verify(prepared)
    if encoded(dict(member=member['id'],source=member['source'],source9=list(source9),sha256=member['sha256'],identity=list(member['identity']),output=filename))!=request_raw:
        raise Held('Original conversion request changed')
    policy.check()
    if tuple(sorted(os.listdir(work)))!=names:raise Held('Original conversion namespace changed')
    if encoded(dict(member=member['id'],source=member['source'],source9=list(source9),sha256=member['sha256'],identity=list(member['identity']),output=filename))!=request_raw:
        raise Held('Original conversion request changed')
    for node,row in nodes.items():
        if common.directory_identity(os.lstat(node))!=row:raise Held('Original conversion ancestor changed')
    if common.directory_identity(os.lstat(work))!=work5:raise Held('Original conversion workspace changed')
    for path,row in ((receipt,receipt9),(prepared,output9),(source,tuple(source9))):
        if common.identity(os.lstat(path))!=row:raise Held('Original finalized conversion changed')
    try:
        yield prepared,output_sha
    finally:
        # No callback follows this final original file/directory tape closure.
        policy.check()
        if tuple(sorted(os.listdir(work)))!=names:raise Held('Original conversion namespace changed')
        if encoded(dict(member=member['id'],source=member['source'],source9=list(source9),sha256=member['sha256'],identity=list(member['identity']),output=filename))!=request_raw:
            raise Held('Original conversion request changed')
        for node,row in nodes.items():
            if common.directory_identity(os.lstat(node))!=row:raise Held('Original conversion ancestor changed')
        if common.directory_identity(os.lstat(work))!=work5:raise Held('Original conversion workspace changed')
        for path,row in ((receipt,receipt9),(prepared,output9),(source,tuple(source9))):
            if common.identity(os.lstat(path))!=row:raise Held('Original finalized conversion changed')
