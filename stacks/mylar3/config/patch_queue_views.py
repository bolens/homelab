"""Expose diagnostics and import problems using Mylar's existing authentication."""
import ast
from pathlib import Path
import sys
from patch_queue_control import replace_once

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
    source = replace_once(source, '                 if filelocation and os.path.exists(filelocation) is True:', '''                 if active['tmp_filename'] and os.path.isfile(active['tmp_filename']):
                     filelocation = active['tmp_filename']
                 elif filelocation and os.path.isfile(filelocation + '.part'):
                     filelocation += '.part'
                 if filelocation and os.path.exists(filelocation) is True:''')
    ast.parse(source)
    return source


def api(source):
    if MARKER in source:
        return source
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
    return source


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
        return source
    source = replace_once(source, '<th>Retry status</th>', '<th>Download / import status</th>')
    source = replace_once(source,
        "var suffix=d.finished ? (attempts ? ' (' + attempts + (attempts === 1 ? ' attempt)' : ' attempts)') : '') : ' (' + attempts + '/6 attempts)';",
        "var suffix=d.finished ? '' : ' (' + attempts + '/6 attempts)';")
    return replace_once(source,
        "return $('<span>').text(text).html();",
        """// homelab-queue-clarity-v1
                            var label=$('<span>').text(text);
                            if (d.finished && attempts) label.attr('title', 'Downloaded in ' + attempts + (attempts === 1 ? ' attempt' : ' attempts'));
                            return $('<div>').append(label).html();""")


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
