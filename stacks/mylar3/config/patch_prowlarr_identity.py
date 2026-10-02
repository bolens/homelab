"""Connect Prowlarr release identity to native search and failed-release checking."""
import ast
from pathlib import Path
import shutil
import sys
from source_patches import replace_once

MARKER = '# homelab-prowlarr-identity-v1'


def patched(name, source):
    if MARKER in source:
        return source
    if name == 'search.py':
        source = replace_once(source, "    elif 'newznab' in nzbprov:\n",
                              "    elif 'newznab' in nzbprov:\n        release = prowlarr_identity.release_id(link)\n        if release is not None:\n            return release\n")
    elif name == 'Failed.py':
        source = replace_once(source, "            chk_fail = myDB.selectone('SELECT * FROM failed WHERE ID=?', [self.id]).fetchone()",
                              '            chk_fail = prowlarr_identity.failed_record(myDB, self.id, self.nzb_name)')
    else:
        raise ValueError('Unsupported Prowlarr identity target')
    source = MARKER + '\nfrom mylar import prowlarr_identity\n' + source
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {root / name: patched(name, (root / name).read_text())
               for name in ('search.py', 'Failed.py')}
    for path, source in changes.items():
        path.write_text(source)
    shutil.copyfile(Path(__file__).with_name('prowlarr_identity.py'), root / 'prowlarr_identity.py')


if __name__ == '__main__':
    main(sys.argv[1])
