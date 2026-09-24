"""Replace the legacy active panel while preserving native queue data and actions."""
from pathlib import Path
import sys
from patch_queue_control import replace_once

MARKER = '<!-- homelab-ddl-responsive-v1 -->'


def between(source, start, end, value):
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError('DDL UI source changed; review the candidate image')
    first = source.index(start)
    last = source.index(end, first)
    return source[:first] + value + source[last:]


def template(source):
    if MARKER in source:
        return source
    files = Path(__file__).parent
    source = between(source, '            <div id="paddingheader">', '             <div class="table_wrapper">',
                     MARKER + '\n' + (files/'ddl_active.html').read_text())
    source = replace_once(source, '            %endif', '</section></div>')
    source = replace_once(source, '        <link rel="stylesheet" href="interfaces/${interface}/css/data_table.css">',
                          '        <link rel="stylesheet" href="interfaces/${interface}/css/data_table.css">\n<style>\n' + (files/'ddl_queue.css').read_text() + '</style>')
    source = between(source, '        var ImportTimer = setInterval', '        function queueBytes', '')
    source = between(source, '        function activecheck()', '        function initThisPage()', (files/'ddl_queue.js').read_text() + '\n')
    source = between(source, '            $("#btn_container #btn_menu #arestartddl', '            if ( $.fn.dataTable.isDataTable', '')
    source = between(source, '                                    val = full[3]', '                           }         ', '                                    return ddlRowActions(full);\n')
    source = replace_once(source, '''return '<span title="' + full[0] + '"></span><a href="comicDetails?ComicID=' + full[7] + '">' + full[0] + '</a>';''',
                          '''return '<a href="comicDetails?ComicID=' + encodeURIComponent(full[7]) + '">' + ddlText(full[0]) + '</a>';''')
    for index in (1, 8, 2, 3, 4):
        source = replace_once(source, 'return full[%d];' % index, 'return ddlText(full[%d]);' % index)
    source = between(source, "                         //nRow.children[0].id", '                         return nRow;',
                     '''                         var labels=['Series','Size','Provider','Progress','Status','Updated','Actions','Received','Speed','Last progress','Download / import status'];
                         $('td',nRow).each(function(index){$(this).attr('data-label',labels[index]);});
''')
    source = replace_once(source, '        <script src="js/libs/full_numbers_no_ellipses.js"></script>', '')
    source = source.replace('No information available', 'No DDL downloads in the queue or history.')
    # Keep queue-wide actions separate from per-download controls, with unique IDs.
    source = between(source, '                      <a id="menu_link_refresh" href="#" title="Restart stalled queue"', '                </div>',
                     '                      <button id="ddl_restart_queue" type="button">Restart queued downloads</button>\n'
                     '                      <button id="ddl_clear_queue" type="button">Clear queued entries</button>\n')
    return source


def main(directory):
    path = Path(directory).parent/'data/interfaces/default/queue_management.html'
    path.write_text(template(path.read_text()))
    print('Responsive DDL queue interface verified')


if __name__ == '__main__':
    main(sys.argv[1])
