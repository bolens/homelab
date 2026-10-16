"""Annual identity and post-processing ownership."""

import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = "# homelab-pack-intake-v1"


def duplicate_ownership(source):
    marker = "# homelab-annual-duplicate-ownership-v1"
    if marker in source:
        return source
    source = replace_once(source,
        '''    if IssueID:
        dupchk = myDB.selectone("SELECT * FROM issues WHERE IssueID=?", [IssueID]).fetchone()
    if dupchk is None:
        dupchk = myDB.selectone("SELECT * FROM annuals WHERE IssueID=? AND NOT Deleted", [IssueID]).fetchone()''',
        '''    # homelab-annual-duplicate-ownership-v1
    dupchk = None
    if IssueID:
        annual = myDB.selectone("SELECT * FROM annuals WHERE IssueID=?", [IssueID]).fetchone()
        if annual is not None:
            if annual['Deleted'] or (ComicID is not None and str(annual['ComicID']) != str(ComicID)):
                logger.info('Annual duplicate ownership requires review; retaining source')
                return {'action': None}
            dupchk = annual
        else:
            dupchk = myDB.selectone("SELECT * FROM issues WHERE IssueID=?", [IssueID]).fetchone()
    if dupchk is None:
        dupchk = myDB.selectone("SELECT * FROM annuals WHERE IssueID=? AND NOT Deleted", [IssueID]).fetchone()''')
    ast.parse(source)
    return source


def annual_identity(source):
    marker = '# homelab-annual-filename-identity-v1'
    if marker in source:
        return source
    source = replace_once(source,
        "                        if fl['issueid'] is not None:\n                            story_the_arcs = False",
        """                        if fl['issueid'] is not None:
                            # homelab-annual-filename-identity-v1
                            annual_intent = myDB.selectone('SELECT Deleted FROM annuals WHERE IssueID=?', [fl['issueid']]).fetchone()
                            if annual_intent and annual_intent['Deleted']:
                                logger.info('Deleted annual identity retained for review; skipping import')
                                continue
                            story_the_arcs = False""")
    source = replace_once(source,
        'FROM comics as c JOIN issues as i ON c.ComicID = i.ComicID WHERE i.IssueID=?',
        'FROM comics as c JOIN issues as i ON c.ComicID = i.ComicID WHERE i.IssueID=? AND NOT EXISTS (SELECT 1 FROM annuals a WHERE a.IssueID=i.IssueID)')
    ast.parse(source)
    return source


ANNUAL_LOOKUP_MARKER = '# homelab-annual-release-lookup-v1'
ANNUAL_LOOKUP = """                    # homelab-annual-release-lookup-v1
                    annual_title = annual_alt_title = None
                    if mylar.CONFIG.ANNUALS_ON:
                        try:
                            annual_title = file_identity.annual_release_title(fl['series_name'], fl['issue_year'])
                            annual_alt_title = file_identity.annual_release_title(fl['alt_series'], fl['issue_year'])
                        except ValueError:
                            # Keep literal registered annual titles eligible for their own owner.
                            annual_title = annual_alt_title = None
"""


LATER_ANNUAL_LOOKUP = """                                            try:
                                                release_title = file_identity.annual_release_title(watchmatch['series_name'], watchmatch['issue_year'])
                                            except ValueError:
                                                release_title = None
                                            if release_title is not None:
                                                tmpseriesname = as_d.dynamic_replace(release_title)['mod_seriesname']
"""


def annual_release_lookup(source):
    if ANNUAL_LOOKUP_MARKER in source:
        if (source.count(ANNUAL_LOOKUP) != 1 or 'from mylar import file_identity\n' not in source
                or source.count('file_identity.annual_release_title(') != 4
                or source.count(LATER_ANNUAL_LOOKUP) != 1):
            raise ValueError('Annual release lookup boundary changed')
        return source
    source = replace_once(source, '                    self.matched = False\n',
                          ANNUAL_LOOKUP + '                    self.matched = False\n')
    source = replace_once(source,
        "                            mod_altseriesname = re.sub('2021annual', '', mod_altseriesname, flags=re.I).strip()\n",
        "                            if annual_alt_title is not None:\n"
        "                                mod_altseriesname = as_d.dynamic_replace(annual_alt_title)['mod_seriesname']\n")
    source = replace_once(source,
        "                        mod_seriesname = re.sub('2021annual', '', mod_seriesname, flags=re.I).strip()\n",
        "                        if annual_title is not None:\n"
        "                            mod_seriesname = as_d.dynamic_replace(annual_title)['mod_seriesname']\n")
    source = replace_once(source,
        "                                            tmpseriesname = re.sub('2021annual', '', tmpseriesname, flags=re.I).strip()\n",
        LATER_ANNUAL_LOOKUP)
    source = replace_once(source,
        "                                                    week_dynamicname = re.sub('2021annual', '', week_dynamicname, flags=re.I).strip()\n",
        "                                                    try:\n"
        "                                                        weekly_title = file_identity.annual_release_title(week_comic, str(test[4]))\n"
        "                                                    except ValueError:\n"
        "                                                        weekly_title = None\n"
        "                                                    if weekly_title is not None:\n"
        "                                                        week_dynamicname = as_d.dynamic_replace(weekly_title)['mod_seriesname']\n")
    if 'from mylar import file_identity\n' not in source:
        source = 'from mylar import file_identity\n' + source
    ast.parse(source)
    return source


def processor(source):
    if MARKER in source:
        return annual_release_lookup(annual_identity(source))
    source = replace_once(
        source,
        "from mylar import pp_monitor",
        "from mylar import pp_monitor, processing_guard\n" + MARKER,
    )
    source = replace_once(
        source,
        "    @pp_monitor.observe",
        "    @processing_guard.run\n    @pp_monitor.observe",
    )
    source = replace_once(
        source,
        "        if mylar.APILOCK is True:\n            return {'status':  'IN PROGRESS'}\n\n",
        "",
    )
    source = replace_once(source, "            mylar.APILOCK = True\n", "")
    # Native methods cleared a global boolean before their run actually ended.
    # The outer owner now handles every exit and serializes concurrent callers.
    source = source.replace(
        "                    if mylar.APILOCK is True:\n                        mylar.APILOCK = False\n",
        "",
    )
    source = source.replace(
        "                if mylar.APILOCK is True:\n                    mylar.APILOCK = False\n",
        "",
    )
    before = """                            if csi is None:
                                try:
                                    csi = myDB.selectone(
                                        'SELECT i.ComicID, i.IssueID, i.Issue_Number, c.ComicName, c.ComicYear, c.AgeRating FROM comics as c JOIN issues as i ON c.ComicID = i.ComicID WHERE i.IssueID=?',"""
    after = """                            if csi is None:
                                try:
                                    csi = myDB.selectone(
                                        'SELECT i.ComicID, i.IssueID, i.Issue_Number, i.ReleaseComicName, i.ReleaseComicID, c.ComicName, c.ComicYear, c.AgeRating FROM comics as c JOIN annuals as i ON c.ComicID = i.ComicID WHERE i.IssueID=? AND COALESCE(i.Deleted,0)=0',"""
    source = replace_once(source, before, after)
    ast.parse(source)
    return annual_release_lookup(annual_identity(source))


def processing(source):
    marker = "# homelab-processing-join-v1"
    if marker in source:
        return source
    source = replace_once(
        source,
        "                threading.Thread(target=PostProcess.Process).start()",
        "                " + marker + "\n"
        '                thread_ = threading.Thread(target=PostProcess.Process, name="Post-Processing")\n'
        "                thread_.start()\n"
        "                thread_.join()",
    )
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {}
    changes[root / "PostProcessor.py"] = processor(
        (root / "PostProcessor.py").read_text()
    )
    changes[root / "process.py"] = processing((root / "process.py").read_text())
    changes[root / "helpers.py"] = duplicate_ownership((root / "helpers.py").read_text())
    for path, source in changes.items():
        path.write_text(source)
    (root / "processing_guard.py").write_text(
        Path(__file__).with_name("processing_guard.py").read_text()
    )

    (root / "ordinary_import_history.py").write_text(
        Path(__file__).with_name("ordinary_import_history.py").read_text()
    )
    (root / "ordinary_import_continuity.py").write_text(
        Path(__file__).with_name("ordinary_import_continuity.py").read_text()
    )


if __name__ == "__main__":
    main(sys.argv[1])
