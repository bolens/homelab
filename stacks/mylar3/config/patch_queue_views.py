"""Expose diagnostics and import problems using Mylar's existing authentication."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-queue-views-v1'


def server(source):
    if MARKER in source:
        return source
    source = replace_once(source, '    def queueManage(self):', '''    # homelab-queue-views-v1
    def importProblems(self):
        from mylar import import_problems
        return serve_template(templatename='import_problems.html', title='Import problems', **import_problems.view())
    importProblems.exposed = True

    def queueManage(self):''')
    source = replace_once(source, "        rows = [[row['series'], row['size'], row['progress'], row['status'], row['updated_date'], row['queueid'], row['issueid'], row['comicid'], row['linktype']] for row in rows]", "        from mylar import queue_control\n        diagnostics = queue_control.diagnostics(downloads.values())\n        rows = [[row['series'], row['size'], row['progress'], row['status'], row['updated_date'], row['queueid'], row['issueid'], row['comicid'], row['linktype'], diagnostics.get(str(row['queueid']), {})] for row in rows]")
    source = replace_once(source, '                 if filelocation and os.path.exists(filelocation) is True:\n                     filesize = os.stat(filelocation).st_size', """                 from mylar.queue_progress import received_bytes
                 filesize = received_bytes(active, mylar.CONFIG.DDL_LOCATION)
                 if filesize is not None:""")
    source = replace_once(source,
        "                 statline = '%s does not exist.</br> This probably needs to be restarted (use the option in the GUI)' % filelocation",
        "                 statline = 'Downloading (waiting for file activity)'")
    source = replace_once(source,
        "                 statline = 'No filename assigned for %s.</br> This was probably never started successfully - you should restart the download (use the option in the GUI)' % infoline",
        "                 statline = 'Downloading (preparing file)'")
    source = replace_once(source,
        "             return json.dumps({'a_id': active['id'], 'status': statline, 'percent': 0})",
        "             return json.dumps({'a_id': active['id'], 'status': statline, 'percent': 0, 'a_series': active['series'], 'a_year': active['year'], 'a_filename': active['filename'], 'a_size': active['size']})")
    ast.parse(source)
    return source


def api(source):
    if MARKER in source:
        return report_api(source)
    source = replace_once(source, "'getHealth', 'reportFailedDownload',", "'getHealth', 'reportFailedDownload', 'reportImportProblems',")
    source = replace_once(source, '    def _getHealth(self, **kwargs):', '''    # homelab-queue-views-v1
    def _reportImportProblems(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import import_problems
        try:
            result = import_problems.report(kwargs.get('report'))
        except (ValueError, TypeError, KeyError):
            self.data = self._failureResponse('Invalid import-problems report')
        else:
            self.data = self._successResponse(result)

    def _getHealth(self, **kwargs):''')
    ast.parse(source)
    return report_api(source)


def report_api(source):
    marker='# homelab-maintenance-report-handoff-v1'
    nodes=[node for node in ast.walk(ast.parse(source)) if isinstance(node,ast.FunctionDef) and node.name=='_reportImportProblems']
    if len(nodes)!=1:raise ValueError('Expected one import diagnostic report endpoint')
    node=nodes[0]
    attempts=[item for item in node.body if isinstance(item,ast.Try)]
    if len(attempts)!=1:raise ValueError('Diagnostic report admission boundary changed')
    attempt=attempts[0]
    if marker in source:
        calls=[item for item in ast.walk(attempt) if isinstance(item,ast.Call) and ast.unparse(item.func)=='worker_handoff.admit']
        expected=ast.parse("worker_handoff.admit(kwargs.get('maintenance_handoff'), 'reportImportProblems', {key: kwargs.get(key, '') for key in ('report', 'processing', 'guidance', 'report_binding')})").body[0]
        if (len(calls)!=1 or len(attempt.body)<2 or not isinstance(attempt.body[0],ast.ImportFrom)
                or attempt.body[0].module!='mylar' or ast.dump(attempt.body[1])!=ast.dump(expected)):
            raise ValueError('Diagnostic report handoff guard changed')
        return source
    lines=source.splitlines(keepends=True)
    prefix=' '*attempt.body[0].col_offset
    addition=prefix+marker+'\n'+prefix+'from mylar import worker_handoff\n'+prefix+"worker_handoff.admit(kwargs.get('maintenance_handoff'), 'reportImportProblems', {key: kwargs.get(key, '') for key in ('report', 'processing', 'guidance', 'report_binding')})\n"
    lines.insert(attempt.body[0].lineno-1,addition)
    result=''.join(lines);ast.parse(result);return result


def template(source):
    if '// homelab-queue-views-v1' in source:
        return completion_template(source)
    source = replace_once(source, '<div id="subhead_menu">', '<div id="subhead_menu">\n                      <a href="importProblems">Import problems</a>')
    source = replace_once(source, '<th id="qoptions">Options</th>', '<th id="qoptions">Options</th>\n                  <th>Received</th><th>Speed</th><th>Last progress</th><th>Retry status</th>')
    anchor = '                    "columnDefs": ['
    additions = '''                    "columnDefs": [
                        // homelab-queue-views-v1
                        {"targets": [7], "sortable": false, "data": null, "render": function(data,type,full) {
                            return queueBytes((full[9] || {}).bytes || 0);
                        }},
                        {"targets": [8], "sortable": false, "data": null, "render": function(data,type,full) {
                            return queueBytes((full[9] || {}).speed || 0) + '/s';
                        }},
                        {"targets": [9], "sortable": false, "data": null, "render": function(data,type,full) {
                            var age=(full[9] || {}).last_progress_seconds;
                            return age == null ? '--' : age + 's ago';
                        }},
                        {"targets": [10], "sortable": false, "data": null, "render": function(data,type,full) {
                            var d=full[9] || {};
                            var text=(d.reason || 'Waiting') + ' (' + (d.attempts || 0) + '/6 attempts)';
                            if (d.cooldown_seconds > 0) text += '; retry in ' + d.cooldown_seconds + 's';
                            return $('<span>').text(text).html();
                        }},'''
    source = replace_once(source, anchor, additions)
    source = replace_once(source, '        function activecheck() {', '''        function queueBytes(value) {
            var units=['B','KiB','MiB','GiB']; var index=0;
            while (value >= 1024 && index < units.length-1) { value /= 1024; index++; }
            return value.toFixed(index ? 1 : 0) + ' ' + units[index];
        }
        function activecheck() {''')
    return completion_template(source)


def management_template(source):
    if '<!-- homelab-import-navigation-v1 -->' in source:
        return source
    anchor = '<a id="menu_link_edit" href="queueManage">Manage DDL Queue</a>'
    return replace_once(source, anchor, anchor + '\n            <!-- homelab-import-navigation-v1 -->\n            <a id="menu_link_edit" href="importProblems">Import problems</a>')


def completion_template(source):
    source = source.replace('<a href="importProblems">Import problems</a>', '<a id="menu_link_edit" href="importProblems">Import problems</a>')
    if '// homelab-queue-completion-v1' in source:
        return clarity_template(source)
    source = replace_once(source,
        "var text=(d.reason || 'Waiting') + ' (' + (d.attempts || 0) + '/6 attempts)';",
        """// homelab-queue-completion-v1
                            var attempts=d.attempts || 0;
                            var suffix=d.finished ? (attempts ? ' (' + attempts + (attempts === 1 ? ' attempt)' : ' attempts)') : '') : ' (' + attempts + '/6 attempts)';
                            var text=(d.reason || 'Waiting') + suffix;""")
    return clarity_template(source)


def clarity_template(source):
    if '// homelab-queue-clarity-v1' in source:
        return mirror_template(source)
    source = replace_once(source, '<th>Retry status</th>', '<th>Download / import status</th>')
    source = replace_once(source,
        "var suffix=d.finished ? (attempts ? ' (' + attempts + (attempts === 1 ? ' attempt)' : ' attempts)') : '') : ' (' + attempts + '/6 attempts)';",
        "var suffix=d.finished ? '' : ' (' + attempts + '/6 attempts)';")
    source = replace_once(source,
        "return $('<span>').text(text).html();",
        """// homelab-queue-clarity-v1
                            var label=$('<span>').text(text);
                            if (d.finished && attempts) label.attr('title', 'Downloaded in ' + attempts + (attempts === 1 ? ' attempt' : ' attempts'));
                            return $('<div>').append(label).html();""")
    return mirror_template(source)



def mirror_template(source):
    if '// homelab-mirror-status-v1' in source:
        return source
    source = replace_once(source,
        "var suffix=d.finished ? '' : ' (' + attempts + '/6 attempts)';",
        "// homelab-mirror-status-v1\n                            var suffix='';")
    return replace_once(source,
        "if (d.finished && attempts) label.attr('title', 'Downloaded in ' + attempts + (attempts === 1 ? ' attempt' : ' attempts'));",
        """if (d.finished && attempts) label.attr('title', 'Downloaded in ' + attempts + (attempts === 1 ? ' attempt' : ' attempts'));
                            else if (!d.finished) label.attr('title', 'Download attempts used: ' + attempts + '; retry limit: ' + (d.attempt_limit || 6) + '. This limit is not a mirror count.');""")


def main(directory):
    root = Path(directory)
    templates = root.parent / 'data/interfaces/default'
    changes = {root/'webserve.py': server((root/'webserve.py').read_text()),
               root/'api.py': api((root/'api.py').read_text()),
               templates/'queue_management.html': template((templates/'queue_management.html').read_text()),
               templates/'manage.html': management_template((templates/'manage.html').read_text())}
    for path, value in changes.items():
        path.write_text(value)
    (templates/'import_problems.html').write_text(Path(__file__).with_name('import_problems.html').read_text())
    print('Queue diagnostics and authenticated import-problems view verified')


if __name__ == '__main__':
    main(sys.argv[1])
