"""Bounded offline Legacy ComicRack writer for an already owned CBZ workspace."""
import os
from pathlib import Path
import re
import sys
import tempfile

if __package__:
    from .tagger_cli import TagResult
    from .tagger_runtime import run, VERSION_TIMEOUT, TAG_TIMEOUT
else:
    from tagger_cli import TagResult
    from tagger_runtime import run, VERSION_TIMEOUT, TAG_TIMEOUT

VERSION='1.3.5'
SCRIPT='/app/mylar3/comictagger.py'
FIELDS=dict(series='series',issue='issue',title='title',publisher='publisher',
            description='comments',issue_count='issueCount',year='year',month='month',day='day')
ROLES={'Writer','Penciller','Inker','Colorist','Letterer','Cover','Editor'}


def text(value):
    if (not isinstance(value,str) or not value.strip() or '^' in value or '<_~_>' in value
            or any(ord(c)<32 and c not in '\n\r\t' for c in value)):
        raise ValueError('Unrepresentable Legacy metadata')
    return value.replace(',','^,').replace('=','^=')


def metadata_argument(metadata):
    """Use the pinned parser's grammar without dropping unsupported fields."""
    if (not isinstance(metadata,dict) or not metadata
            or set(metadata)-set(FIELDS)-{'credits','web_links','characters','teams','locations'}):
        raise ValueError('Unsupported Legacy metadata')
    values=[]
    for key,value in metadata.items():
        if key in FIELDS:
            if key in ('issue_count','year','month','day'):
                if type(value) is not int or not 1<=value<=9999:raise ValueError('Invalid Legacy number')
                value=str(value)
            values.append(FIELDS[key]+'='+text(value))
        elif key=='credits':
            if not isinstance(value,list) or len(value)>1024:raise ValueError('Invalid Legacy credits')
            for credit in value:
                if (not isinstance(credit,dict) or set(credit)!={'person','role'}
                        or credit['role'] not in ROLES or not isinstance(credit['person'],str)
                        or any(c in credit['person'] for c in ':,')):
                    raise ValueError('Unrepresentable Legacy credit')
                values.append('credit='+credit['role']+':'+text(credit['person']))
        else:
            if not isinstance(value,list) or not 1<=len(value)<=1024:raise ValueError('Invalid Legacy list')
            if key=='web_links':
                if len(value)!=1:raise ValueError('Legacy supports one Web value')
                values.append('webLink='+text(value[0]))
            else:
                for item in value:text(item)
                values.append(key+'='+text(', '.join(value)))
    result=','.join(values)
    if not result or len(result.encode('utf-8'))>65536:raise ValueError('Legacy metadata exceeds bounds')
    return result


def version_supported(result):
    return (result.state=='ok' and result.returncode==0
            and re.search(rb'^ComicTagger 1\.3\.5 \[ninjas\.walk\.alone / SHURIKEN\]$',
                          result.stdout+b'\n'+result.stderr,re.M) is not None)


def save(staged,metadata,*,workdir,timeout=TAG_TIMEOUT):
    staged=Path(staged);workdir=Path(workdir).resolve(strict=True)
    if (staged.is_symlink() or not staged.is_file() or staged.stat().st_nlink!=1
            or staged.suffix.lower()!='.cbz' or workdir not in staged.resolve(strict=True).parents):
        raise ValueError('Expected owned staged CBZ')
    payload=metadata_argument(metadata)
    env={key:value for key,value in os.environ.items() if not key.startswith('PYTHON')}
    env['PYTHONNOUSERSITE']='1'
    with tempfile.TemporaryDirectory(prefix='.legacy-',dir=workdir) as directory:
        prefix=[sys.executable,SCRIPT,'--configfolder',directory]
        probe=run(prefix+['--version'],cwd=workdir,timeout=VERSION_TIMEOUT,env=env)
        if not version_supported(probe):return TagResult('unsupported_version')
        result=run(prefix+['-s','--type','cr','-m',payload,str(staged)],
                   cwd=workdir,timeout=timeout,env=env)
        if result.state!='ok':return TagResult(result.state)
        saved=(result.returncode==0 and re.search(rb'^Save complete\.$',result.stderr,re.M)
               and b'Warning:' not in result.stdout+result.stderr)
        return TagResult('saved' if saved else 'invalid_result')
