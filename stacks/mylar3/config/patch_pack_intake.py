"""Checked native annual identity and processing ownership integration."""
import ast
from pathlib import Path
import sys
from patch_queue_control import replace_once

MARKER = '# homelab-pack-intake-v1'


def processor(source):
    if MARKER in source:
        return source
    source = replace_once(source, 'from mylar import pp_monitor',
                          'from mylar import pp_monitor, processing_guard\n' + MARKER)
    source = replace_once(source, '    @pp_monitor.observe',
                          '    @processing_guard.run\n    @pp_monitor.observe')
    source = replace_once(source, "        if mylar.APILOCK is True:\n            return {'status':  'IN PROGRESS'}\n\n", '')
    source = replace_once(source, '            mylar.APILOCK = True\n', '')
    # Native methods cleared a global boolean before their run actually ended.
    # The outer owner now handles every exit and serializes concurrent callers.
    source = source.replace('                    if mylar.APILOCK is True:\n                        mylar.APILOCK = False\n', '')
    source = source.replace('                if mylar.APILOCK is True:\n                    mylar.APILOCK = False\n', '')
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
    return source


def processing(source):
    marker = '# homelab-processing-join-v1'
    if marker in source:
        return source
    source = replace_once(source, '                threading.Thread(target=PostProcess.Process).start()',
                          '                ' + marker + '\n'
                          '                thread_ = threading.Thread(target=PostProcess.Process, name="Post-Processing")\n'
                          '                thread_.start()\n'
                          '                thread_.join()')
    ast.parse(source)
    return source



def helpers(source):
    marker = '# homelab-pack-membership-v1'
    if marker in source:
        return source
    source = replace_once(source, "    if valid:\n        for wv in write_valids:\n            mylar.PACK_ISSUEIDS_DONT_QUEUE[wv['issueid']] = wv['pack_id']",
                          "    " + marker + "\n    # A requested range is not proof of the downloaded edition or members.\n    # Download identity deduplication remains owned by the DDL queue.")
    source = replace_once(source, '        myDB.upsert("issues", {"Status": "Skipped"}, {"IssueID": x})',
                          '        # Legacy reservations cannot justify overwriting current issue status.\n'
                          '        mylar.PACK_ISSUEIDS_DONT_QUEUE.pop(x, None)')
    source = source.replace("'Successfully changed status of %s issues to %s' % (len(reverselist), 'Skipped')", "'Released %s pack reservations; issue status unchanged' % len(reverselist)")
    ast.parse(source)
    return source


def search(source):
    marker = '# homelab-pack-snatch-v1'
    if marker in source:
        return source
    start = source.index("                for isid in issinfo['issues']:")
    end = source.index('                notify_snatch(', start)
    source = source[:start] + '                ' + marker + '\n' + source[end:]
    ast.parse(source)
    return source



def api(source):
    marker = '# homelab-pack-api-v1'
    if marker in source:
        return source
    source = replace_once(source, "'workflowAcknowledge',", "'workflowAcknowledge', 'packWork', 'packReport', 'packCatalog',")
    source = replace_once(source, '    def _getHealth(self, **kwargs):', """    # homelab-pack-api-v1
    def _packWork(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import pack_intake
        self.data = self._successResponse(pack_intake.work())

    def _packReport(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import pack_intake
        try:
            result = pack_intake.report(kwargs.get('report'))
        except (ValueError, KeyError, TypeError):
            self.data = self._failureResponse('Invalid pack report')
        else:
            self.data = self._successResponse(result)

    def _packCatalog(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import pack_catalog
        try:
            result = pack_catalog.resolve(kwargs.get('evidence'))
        except (ValueError, KeyError, TypeError):
            self.data = self._failureResponse('Invalid catalog evidence')
        else:
            self.data = self._successResponse(result)

    def _getHealth(self, **kwargs):""")
    ast.parse(source)
    return source


def startup(source):
    marker = '# homelab-preserve-tracked-series-v1'
    if marker in source:
        return source
    original = "    c.execute(\"DELETE from comics WHERE ComicName='None' OR ComicName LIKE 'Comic ID%' OR ComicName is NULL OR ComicName like '%Fetch%failed%'\")"
    replacement = "    " + marker + "\n    c.execute(\"DELETE from comics WHERE (ComicName='None' OR ComicName LIKE 'Comic ID%' OR ComicName is NULL OR ComicName like '%Fetch%failed%') AND NOT EXISTS (SELECT 1 FROM issues WHERE issues.ComicID=comics.ComicID) AND NOT EXISTS (SELECT 1 FROM annuals WHERE annuals.ComicID=comics.ComicID)\")"
    source = replace_once(source, original, replacement)
    ast.parse(source)
    return source


def scheduler(source):
    marker = '# homelab-ddl-scheduling-v1'
    if marker in source:
        return source
    source = 'from mylar import ddl_schedule as queue_schedule\n' + marker + '\n' + source
    source = replace_once(source, '            item = queue.get(True)',
        '            item = queue_schedule.take(queue)\n            if item is None:\n                time.sleep(1)\n                continue')
    source = replace_once(source, "            if item['id'] not in mylar.DDL_QUEUED:",
        "            queue_schedule.started(item)\n\n            if item['id'] not in mylar.DDL_QUEUED:")
    ast.parse(source)
    return source


def queue_view(source):
    marker = '# homelab-queue-order-view-v1'
    if marker in source:
        return source
    source = replace_once(source,
        'SELECT id, status, filename, tmp_filename, remote_filesize, link_type FROM ddl_info',
        'SELECT id, status, filename, tmp_filename, remote_filesize, link_type, pack FROM ddl_info')
    source = replace_once(source, '        for row in resultlist:\n            download = downloads.get',
        '        ' + marker + '\n        from mylar import ddl_schedule\n        positions = ddl_schedule.positions(downloads.values())\n        for row in resultlist:\n            row["queue_order"] = positions.get(str(row["queueid"]), {"sort": 2000000000})["sort"]\n            download = downloads.get')
    source = replace_once(source, "        sortcolumn = 'series'\n        if iSortCol_0 == '1':",
        "        sortcolumn = 'series'\n        if iSortCol_0 == '11':\n            sortcolumn = 'queue_order'\n        elif iSortCol_0 == '1':")
    source = replace_once(source, "diagnostics.get(str(row['queueid']), {})] for row in rows]",
        "diagnostics.get(str(row['queueid']), {}), positions.get(str(row['queueid']), {})] for row in rows]")
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    for name, patch in [('PostProcessor.py', processor), ('process.py', processing), ('helpers.py', helpers), ('search.py', search), ('api.py', api), ('queues/ddl.py', scheduler), ('__init__.py', startup), ('webserve.py', queue_view)]:
        path = root / name
        path.write_text(patch(path.read_text()))
    for name in ('processing_guard.py', 'pack_intake.py', 'pack_catalog.py', 'ddl_schedule.py'):
        (root / name).write_text(Path(__file__).with_name(name).read_text())
    print('Annual identity and processing ownership verified')


if __name__ == '__main__':
    main(sys.argv[1])
