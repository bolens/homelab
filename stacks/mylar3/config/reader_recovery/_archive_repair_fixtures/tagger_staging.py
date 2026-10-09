"""Private automatic-output ownership; never infer a successful library import."""
import json
import os
from pathlib import Path
import re
import stat

if __package__:
    from .tagger_adapter import fingerprint, sync
    from .tagger_archive import identity, regular
else:
    from tagger_adapter import fingerprint, sync
    from tagger_archive import identity, regular

TOKEN = re.compile(r'[0-9a-f]{32}\Z')


class Staging:
    def __init__(self, root, receipts):
        self.root, self.receipts = Path(root).absolute(), Path(receipts).absolute()
        for path in (self.root, self.receipts):
            if '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
                raise ValueError('Linked staging state')
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise ValueError('Expected private staging state')

    def save(self, record):
        path = self.receipts/(record['token']+'.json')
        temporary = path.with_suffix('.new')
        if temporary.exists() or temporary.is_symlink():
            raise ValueError('Interrupted staging receipt; review required')
        fd = os.open(temporary, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump(record,stream,allow_nan=False);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path);sync(self.receipts)

    def allocate(self, token, source, before, stamp):
        if not TOKEN.fullmatch(token):raise ValueError('Invalid stage token')
        folder=self.root/('mylar_modern_'+token);folder.mkdir(mode=0o700);sync(self.root)
        record=dict(version=1,token=token,source=str(source),before=before,source_identity=list(stamp),
                    folder_identity=list(identity(folder.stat())[:2]),filename=source.name,state='copying')
        self.save(record)
        return folder/source.name

    def read(self, path):
        with regular(path) as stream:
            info = os.fstat(stream.fileno())
            if info.st_nlink != 1 or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError('Invalid staging receipt ownership')
            raw=stream.read(65537)
        if len(raw)>65536:raise ValueError('Oversized staging receipt')
        record=json.loads(raw)
        if (type(record) is not dict or type(record.get('version')) is not int or record.get('version')!=1
                or not TOKEN.fullmatch(str(record.get('token',''))) or path.name!=record['token']+'.json'
                or record.get('state') not in ('copying','ready','retained','cleaned')
                or type(record.get('filename')) is not str or record['filename'] in ('','.','..')
                or Path(record['filename']).name!=record['filename']
                or any(ord(c)<32 for c in record['filename'])
                or type(record.get('source')) is not str or not Path(record['source']).is_absolute()
                or '..' in Path(record['source']).parts
                or not re.fullmatch('[0-9a-f]{64}',str(record.get('before','')))):
            raise ValueError('Invalid staging receipt')
        for key,size in (('source_identity',5),('folder_identity',2)):
            if type(record.get(key)) is not list or len(record[key])!=size or any(type(n) is not int for n in record[key]):
                raise ValueError('Invalid staging identity')
        if record.get('after') is not None and not re.fullmatch('[0-9a-f]{64}',str(record['after'])):
            raise ValueError('Invalid staged digest')
        return record

    def ready(self, token, target):
        path=self.receipts/(token+'.json');record=self.read(path)
        if Path(target)!=self.root/('mylar_modern_'+token)/record['filename']:
            raise ValueError('Unexpected staging target')
        record.update(state='ready',after=fingerprint(target));self.save(record)

    def recover(self):
        if any(p.suffix != '.json' for p in self.receipts.iterdir()):
            raise ValueError('Interrupted staging receipt; review required')
        known=set();retained=0
        for path in self.receipts.glob('*.json'):
            record=self.read(path);folder=self.root/('mylar_modern_'+record['token']);known.add(folder.name)
            if record['state']=='cleaned':
                if folder.exists() or folder.is_symlink():raise ValueError('Cleaned stage reappeared')
                continue
            if not folder.exists() and not folder.is_symlink():
                record['state']='cleaned';self.save(record);continue
            info=folder.lstat()
            if not stat.S_ISDIR(info.st_mode) or list(identity(info)[:2])!=record['folder_identity']:
                raise ValueError('Staging directory changed')
            target=folder/record['filename'];entries=list(folder.iterdir())
            if entries:
                safe=False
                if entries==[target] and not target.is_symlink() and target.is_file() and target.stat().st_nlink==1:
                    try:
                        source=Path(record['source'])
                        safe=(not any(p.is_symlink() for p in (source,*source.parents))
                              and list(identity(source.lstat()))==record['source_identity']
                              and fingerprint(source)==record['before']
                              and fingerprint(target)==record.get('after',record['before']))
                    except (OSError,ValueError):pass
                if not safe:
                    if record['state'] != 'retained':
                        record['state']='retained';self.save(record)
                    retained+=1;continue
                target.unlink();sync(folder)
            folder.rmdir();sync(self.root);record['state']='cleaned';self.save(record)
        if any(path.name not in known for path in self.root.iterdir()):
            raise ValueError('Unowned automatic staging; review required')
        return retained
