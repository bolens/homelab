"""Present the pinned weekly list without changing native action handlers."""
from pathlib import Path
import re
import sys
from source_patches import replace_once

MARKER = '<!-- homelab-pullist-ui-v1 -->'
TABLE_OPTIONS = '''                                "sDom": 'lfr<"pull_table_scroll"t>ip',
                                "fnInitComplete": function() {
                                    $('#pull_table').parent('.pull_table_scroll').attr({role:'region',tabindex:0,'aria-label':'Weekly releases and actions; scroll horizontally for all columns'});
                                },
'''


def template(source, css):
    if MARKER in source:
        if source.count(MARKER) != 1 or source.count('id="pullist_page"') != 1:
            raise ValueError('Weekly interface integration changed')
        return source
    start = source.index('        <div>\n           </br></br>') if '        <div>\n           </br></br>' in source else -1
    end = source.index('        <div>\n          <form action="MassWeeklyDownload"', start) if start >= 0 else -1
    if start < 0 or end < 0:
        raise ValueError('Weekly heading source changed')
    old = source[start:end]
    links = re.findall(r'<a href="(pullist\?[^\"]+)" title="(Previous|Next) Week[^\"]*" onclick="arrows_page\(\);">', old)
    if len(links) != 2 or [item[1] for item in links] != ['Previous', 'Next']:
        raise ValueError('Weekly navigation source changed')
    nav = ''.join('<a data-mylar-component="button" href="' + href + '" onclick="arrows_page();">' + direction + ' week</a>' for href, direction in links)
    heading = '''        <div class="pull_heading">
          <div><p class="pull_eyebrow">Release calendar</p><h1>Weekly releases</h1>
          <p class="pull_dates">Week ${weekinfo['weeknumber']} · ${weekinfo['year']} <span>${weekinfo['startweek']} – ${weekinfo['endweek']}</span></p></div>
          <nav class="pull_week_nav" aria-label="Choose release week">''' + nav + '''</nav>
        </div>
        <p class="pull_intro">Browse releases, add series to your watchlist, or request an issue using its row actions. Wanted issues are scheduled for search; a snatched download still needs a confirmed library import.</p>
        <div class="pull_summary"><span>${len(weeklyresults)} releases listed</span><span>Week total: ${wantedcount} wanted</span><span>Updated ${weekinfo['last_update']}</span></div>
'''
    source = source[:start] + heading + source[end:]
    source = replace_once(source, '<%def name="body()">', '<%def name="body()">\n' + MARKER + '\n<section id="pullist_page">')
    body_start = source.index('<%def name="body()">')
    body_end = source.index('</%def>', body_start)
    source = source[:body_end] + '</section>\n' + source[body_end:]
    source = replace_once(source, 'Mass.Add.it.All.NOW</a>', 'Add series by publisher</a>')
    source = replace_once(source, 'Manually check for issues</a>', 'Search wanted issues</a>')
    source = replace_once(source, 'class="button">Download</a>', 'class="button">Copy weekly downloads</a>')
    source = replace_once(source, '<label><big>Choose.Your.Publishers</big></label>', '<label for="publishers"><big>Choose publishers to add</big></label>')
    source = replace_once(source, 'to select every publisher, do not select anything', 'Leave the selection empty to add series from every publisher in this week’s list.')
    source = replace_once(source, '<label>Run automatically when the pull updates?</label>', '<label for="auto_mass_add">Automatically add series when the pull-list updates</label>')
    source = replace_once(source, 'title="Mass publisher selection"', 'title="Add this week’s series by publisher"')
    source = replace_once(source, '<label>Store in Weekly Directory (${weekfold})</label>', '<label for="weekfolder">Use weekly directory (${weekfold})</label>')
    source = replace_once(source, '<form action="MassWeeklyDownload" method="GET" id="MassDownload">', '<form action="MassWeeklyDownload" method="GET" id="MassDownload" class="pull_storage">\n<p>Weekly copies use this directory setting. Changing it saves your preference immediately.</p>')
    source = replace_once(source, '<tr class="grade${grade}">', '<tr class="grade${grade}" data-pull-status="${weekly[\'STATUS\'] | h}">')
    for name in ('publisher', 'comicname', 'comicnumber', 'status', 'options'):
        source = source.replace('<td class="' + name + '">', '<td class="' + name + '" data-label="' + {'publisher':'Publisher','comicname':'Comic','comicnumber':'Issue','status':'Status','options':'Actions'}[name] + '">')
    source = source.replace('<td class="status" data-label="Status">', '<td class="status" data-label="Status"><span class="pull_badge">')
    source = re.sub(r'(<td class="status" data-label="Status">[^\n]+)</td>', r'\1</span></td>', source)
    # The native SHOW_ICONS preference stays intact; include its equivalent
    # text in that branch so actions are understandable without a tooltip.
    def action_label(match):
        image, tail, label = match.groups()
        return image[:-2] + ' alt="" /><span>' + label + '</span>' + tail + label
    source, count = re.subn(r'(<img[^\n]*src="images/[^"/]+"[^\n]*?/>)(\s*%else:\s*<span class="ui-icon ui-icon-plus"></span>)([^\n<]+)', action_label, source)
    if count != 10:
        raise ValueError('Weekly action icon branches changed')
    options_start = source.index('<td class="options" data-label="Actions">')
    options_end = source.index('</td>', options_start)
    actions = source[options_start:options_end]
    source = source[:options_start] + actions.replace('<a ', '<a data-mylar-component="button" ') + source[options_end:]
    source = replace_once(source, '"sSearch": ""', '"sSearch": "Filter releases:"')
    source = replace_once(source, '                                "bDestroy": true,', TABLE_OPTIONS + '                                "bDestroy": true,')
    source = replace_once(source, '<div style="z-index:10;overflow: hidden;margin-top:10px;">', '<div class="pull_legend"><h2>Reading release status</h2>')
    source = replace_once(source, '<small>last updated: ${weekinfo[\'last_update\']}</small>', '<small>One-off downloads are kept outside your watchlist. Release conflicts need review before choosing an issue.</small>')
    source = replace_once(source, 'title="Series is monitored & issue is Wanted"></span> monitored series</td>', 'title="Series is monitored & issue is Wanted"></span> wanted on watchlist</td>')
    source = replace_once(source, 'title="Series is Monitored & issue is Skipped"></span> monitored series</td>', 'title="Series is Monitored & issue is Skipped"></span> skipped on watchlist</td>')
    source = replace_once(source, '<%def name="headIncludes()">', '<%def name="headIncludes()">\n<style>\n' + css + '\n</style>')
    return source


def main(directory):
    path = Path(directory).parent / 'data/interfaces/default/weeklypull.html'
    path.write_text(template(path.read_text(), Path(__file__).with_name('pullist_ui.css').read_text()))


if __name__ == '__main__':
    main(sys.argv[1])
