"""A conflicting weekly date must not revoke an existing wanted decision."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

OLD = '''                # if it was previously marked as Wanted (prior to this patch) - let's revert so we don't download the wrong thing repeatidly
                if issuechk['Status'] == 'Wanted':
                    control = {"IssueID":   issuechk['IssueID']}
                    newchk = {'Status': 'Skipped'}
                    myDB.upsert("issues", newchk, control)
'''
NEW = '''                # homelab-weekly-date-intent-v1: retain the catalog decision.
                # This weekly entry remains a mismatch; its date cannot revoke
                # an existing wanted decision for the catalog's exact issue.
'''


def patched(source):
    if NEW in source:
        if source.count(NEW)!=1 or OLD in source:raise ValueError('Ambiguous weekly date intent guard')
    else:source=replace_once(source,OLD,NEW)
    ast.parse(source)
    return source


def template(source):
    old='title="View mismatch reason">${weekly[\'STATUS\']}</a>'
    new='title="Check the weekly release date or issue identity">Release needs review</a>'
    if new not in source:source=replace_once(source,old,new)
    elif source.count(new)!=1 or old in source:raise ValueError('Ambiguous weekly review label')
    old='title="Incorrectly matched series"></span> mismatched</td>'
    new='title="Weekly release date or issue identity needs review"></span> release needs review</td>'
    if new not in source:source=replace_once(source,old,new)
    elif source.count(new)!=1 or old in source:raise ValueError('Ambiguous weekly review legend')
    return source


def main(directory):
    root=Path(directory);path=root/'updater.py'
    view=root.parent/'data/interfaces/default/weeklypull.html'
    source=patched(path.read_text());html=template(view.read_text())
    path.write_text(source);view.write_text(html)


if __name__=='__main__':main(sys.argv[1])
