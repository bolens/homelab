"""Pack membership reservations and authenticated intake APIs."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-pack-intake-v1'


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
        for old,new in (("pack_intake.report(kwargs.get('report'))",
                         "pack_intake.report(kwargs.get('report'), kwargs.get('maintenance_handoff'))"),
                        ("pack_catalog.resolve(kwargs.get('evidence'))",
                         "pack_catalog.resolve(kwargs.get('evidence'), kwargs.get('maintenance_handoff'), kwargs.get('catalog_attempt'))")):
            if old in source:source=replace_once(source,old,new)
        ast.parse(source)
        return source
    source = replace_once(source, "'workflowCommands', 'workflowAcknowledge',", "'workflowCommands', 'workflowAcknowledge', 'packWork', 'packReport', 'packCatalog',")
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
            result = pack_intake.report(kwargs.get('report'), kwargs.get('maintenance_handoff'))
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
            result = pack_catalog.resolve(kwargs.get('evidence'), kwargs.get('maintenance_handoff'), kwargs.get('catalog_attempt'))
        except (ValueError, KeyError, TypeError):
            self.data = self._failureResponse('Invalid catalog evidence')
        else:
            self.data = self._successResponse(result)

    def _getHealth(self, **kwargs):""")
    ast.parse(source)
    return source



def main(directory):
    root = Path(directory)
    changes = {}
    changes[root / 'helpers.py'] = helpers((root / 'helpers.py').read_text())
    changes[root / 'search.py'] = search((root / 'search.py').read_text())
    changes[root / 'api.py'] = api((root / 'api.py').read_text())
    for path, source in changes.items():
        path.write_text(source)
    (root / 'pack_intake.py').write_text(Path(__file__).with_name('pack_intake.py').read_text())
    (root / 'pack_catalog.py').write_text(Path(__file__).with_name('pack_catalog.py').read_text())
    for name in ('pack_bindings.py', 'tagger_pack.py'):
        (root / name).write_text(Path(__file__).with_name(name).read_text())


if __name__ == '__main__':
    main(sys.argv[1])
