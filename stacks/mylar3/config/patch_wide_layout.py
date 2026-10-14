"""Add a theme-neutral desktop layout override to Mylar's shared template."""
from pathlib import Path
import sys
from source_patches import replace_once
from patch_manage_ui import install as install_manage_ui

START = '<!-- homelab-wide-layout-v1 -->'
END = '<!-- /homelab-wide-layout-v1 -->'


def template(source, css):
    if 'id="homelab_queue_nav"' not in source:
        source = replace_once(source, '<ul id="nav">', '<ul id="nav">\n'
            '<li class="homelab_desktop_nav"><a href="home">Library</a></li>\n'
            '<li class="homelab_desktop_nav" id="homelab_queue_nav"><details><summary>Queues</summary>\n'
            '<div class="homelab_queue_links"><a href="queueManage">DDL queue</a>\n'
            '<a href="postProcessing">Post-processing</a><a href="importProblems">Import problems</a></div>\n'
            '</details></li>')
        source = replace_once(source, '</head>', '<script>\n'
            'document.addEventListener("DOMContentLoaded", function() {\n'
            ' var menu=document.querySelector("#homelab_queue_nav details");\n'
            ' document.addEventListener("click", function(e) {if(!menu.contains(e.target)) menu.open=false;});\n'
            ' document.addEventListener("keydown", function(e) {if(e.key==="Escape" && menu.open) {menu.open=false;menu.querySelector("summary").focus();}});\n'
            ' document.querySelectorAll("header #nav a").forEach(function(a) {\n'
            '  if(new URL(a.href).pathname===location.pathname) {a.setAttribute("aria-current","page");if(menu.contains(a)) menu.classList.add("current");}\n'
            ' });\n'
            '});\n</script>\n</head>')
    if '<div class="homelab_queue_links"><a href="activity">' not in source:
        source = replace_once(source, '<div class="homelab_queue_links">',
                              '<div class="homelab_queue_links"><a href="activity">Activity</a>')
    block = START + '\n<style>\n' + css + '</style>\n' + END
    if START in source:
        if source.count(START) != 1 or source.count(END) != 1:
            raise ValueError('Ambiguous wide-layout block; review source')
        start = source.index(START)
        finish = source.index(END, start) + len(END)
        return source[:start] + block + source[finish:]
    return replace_once(source, '${next.headIncludes()}', '${next.headIncludes()}\n' + block)


def history_template(source, css, javascript):
    """Keep native history endpoints while making review and mutations explicit."""
    marker = '<!-- homelab-history-review-v1 -->'
    if marker in source:
        return source
    if source.count('<%def name="headerIncludes()">') != 1:
        raise ValueError('History header boundary changed; review candidate image')
    start = source.index('<%def name="headerIncludes()">')
    end = source.index('</%def>', start) + len('</%def>')
    header = '''<%def name="headerIncludes()">
<div id="subhead_container"><div id="subhead_menu">
<a id="menu_link_edit" href="activity">Activity</a><a id="menu_link_check" href="queueManage">Download queue</a>
<a id="menu_link_manualmeta" href="postProcessing">Post-processing</a><a id="history_problems" href="importProblems">Import problems</a><a id="history_logs" href="logs">View logs</a>
</div></div>
</%def>'''
    original = source[start:end]
    links = []
    for line in original.splitlines():
        if 'onclick="doAjaxCall(' in line:
            # Preserve the native endpoint and response attributes.
            line = line.replace('id="menu_link_delete" ', '')
            question = ('Clear the download log? Do not use this while downloads or post-processing are active. This cannot be undone.'
                        if 'wipenzblog' in line else 'Clear these history records? This cannot be undone.')
            line = line.replace('onclick="', 'onclick="if(!window.confirm(\'' + question + '\'))return false;')
            line = line.replace('Wipe NZBLOG', 'Clear download log')
            links.append(line.strip())
    if len(links) != 5:
        raise ValueError('History maintenance actions changed; review candidate image')
    source = source[:start] + header + source[end:]
    source = replace_once(source, '<input type="hidden" id="page_name" value="history" />',
                          '<input type="hidden" id="page_name" value="history" />\n' + marker + '\n<div id="history_review">')
    source = replace_once(source, '<th id="select" align="left"></th>', '<th id="select" scope="col">Select</th>')
    source = replace_once(source, 'alt="History"', 'alt=""')
    source = replace_once(source, "return '[<a id=\"retry\" name=\"retry\" title=\"Retry search for issue\" href=\"#\">retry</a>]';", "return '<a id=\"retry\" name=\"retry\" title=\"Retry search for issue\" href=\"#\">Retry search</a>';")
    source = replace_once(source, '<form action="markissues"',
        '<p class="history_help">History records acquisition and processing events. Snatched means a download was requested. Post-Processed records a finished processing step; check confirmed imports before retrying a search. Bulk actions apply to selected issues and all their history entries.</p>\n<form action="markissues"')
    source = replace_once(source, '<div id="markissue">Mark selected issues as',
        '<div id="markissue" class="history_tools"><span id="history_selected" role="status">0 issues selected on this page</span><button type="button" id="history_select_page">Select page</button><button type="button" id="history_clear_selection">Clear selection</button><label for="history_bulk_action">Selected issues</label>')
    source = replace_once(source,
        '<select name="action" onChange="doAjaxCall(\'markissues\',$(this),\'table\',true,\'post\');" data-success="selected issues marked">',
        '<select id="history_bulk_action" name="action" disabled data-success="selected issues marked">')
    source = replace_once(source, '<option value="Clear">Clear</option>', '<option value="Clear">Clear history / reset status</option>')
    source = replace_once(source, '                selected issues',
        '                <button id="history_apply" type="button" disabled>Apply to selected</button>')
    source = replace_once(source, '        </form>',
        '        </form>\n<details class="history_maintenance"><summary>History maintenance</summary><p>Clearing records removes history evidence. Review current downloads and processing before clearing records or retrying searches. These controls do not establish a successful library import.</p><div class="history_maintenance_links">' + '\n'.join(links) + '</div></details>\n</div>')
    source = replace_once(source, "                     $('html,body').scrollTop(0);", '                     // Preserve the current scroll position on redraw.')
    source = replace_once(source, '<%def name="javascriptIncludes()">',
        '<%def name="javascriptIncludes()">\n<script>\n' + javascript + '\n</script>')
    source = replace_once(source, '<%def name="headIncludes()">',
        '<%def name="headIncludes()">\n<style>\n' + css + '\n</style>')
    return source


def catalog_template(source, page, css, javascript):
    """Style native library and Wanted tables without replacing their data routes."""
    marker = '<!-- homelab-catalog-review-v1 -->'
    if marker in source:
        return source
    wanted = page == 'upcoming'
    value = 'upcoming' if wanted else 'index'
    anchor = '<input type="hidden" id="page_name" value="' + value + '" />'
    intro = ('<nav class="catalog_nav" aria-label="Page sections"><a href="#wanted_table_wrapper">Wanted issues</a><a href="#tabs">Upcoming and availability</a><a href="activity">Activity</a></nav>'
             if wanted else '<h1>Library</h1><p class="catalog_help">Browse your tracked series. Open a comic to review its issues and files. Have shows library issue counts. Publication status and monitoring status are shown separately.</p><nav class="catalog_nav" aria-label="Library actions"><a href="upcoming">Review Wanted issues</a><a href="activity">View activity</a></nav>')
    source = replace_once(source, anchor, anchor + '\n' + marker + '\n<div id="catalog_review">' + intro)
    if wanted:
        source = source.replace('Force Check Tier-1', 'Search Tier-1 now').replace('Force Check Selected', 'Search selected')
        source = replace_once(source, 'alt="Wanted Issues"', 'alt=""')
        source = replace_once(source, 'Wanted Issues (<span id="wanted_count"></span>)', 'Wanted Issues <span id="wanted_count" class="catalog_total"></span>')
        source = replace_once(source, 'alt="Upcoming Issues"', 'alt=""')
        source = replace_once(source, '<div style="position:absolute;float:left;display:none;" id="markissue">Mark selected issues as',
            '<div style="display:none;" id="markissue"><span id="catalog_selected" role="status">0 issues selected on this page</span><label for="mark_issues">Change selected issues to</label>')
        source = replace_once(source, ' onChange="mark_the_issues()"', '')
        source = replace_once(source, '<input type="hidden" value="Go">', '<button type="button" id="catalog_apply" disabled>Apply to selected</button>')
        source = replace_once(source, 'id="wanted-select-all" class="checkbox"', 'id="wanted-select-all" class="checkbox" aria-label="Select issues on this page"')
        source = replace_once(source, '<th id="tier">SearchTier</th>', '<th id="tier">Search tier / added</th>')
        source = replace_once(source, '        <span style="vertical-align: middle;">', '<p class="catalog_help">Use the status filters to narrow the backlog. Select issues to search them or apply a status change. Marking an issue Downloaded or Archived does not import a file.</p>\n        <span style="vertical-align: middle;">')
        source = replace_once(source, 'No history information available', 'No issues match the current Wanted filters')
        source = replace_once(source, '<small style="float: right; vertical-align: middle;">Date shown in SearchTier is when the issue was added to the Wanted list</small>', '<p class="catalog_help">The search-tier date is when the issue was added to Wanted, rather than its release date.</p>')
        # Native checkbox state clears on each server-side redraw.
        source = replace_once(source, "$('#wanted_table-select-all')", "$('#wanted-select-all')")
    else:
        source = replace_once(source, '<th id="active">Active</th>', '<th id="active">Monitoring</th>')
        start = source.index('      <div style="z-index:10;overflow: hidden;margin-top:10px;">')
        end = source.index('</%def>', start)
        source = source[:start] + '<p class="catalog_legend">Monitoring: Active series are tracked. Paused series wait for you to resume them. Loading and Error describe catalog updates. Removed from ComicVine identifies unavailable provider records.</p>\n' + source[end:]
    body_start = source.index('<%def name="body()">')
    body_end = source.index('</%def>', body_start)
    source = source[:body_end] + '</div>\n' + source[body_end:]
    source = replace_once(source, '<%def name="headIncludes()">', '<%def name="headIncludes()">\n<style>\n' + css + '\n</style>')
    source = replace_once(source, '<%def name="javascriptIncludes()">', '<%def name="javascriptIncludes()">\n<script>\n' + javascript + '\n</script>')
    return source


def component_template(source, css, javascript):
    if 'data-mylar-theme=' not in source:
        source = replace_once(source, '<body>', '<body data-mylar-theme="${interface | h}">')
    marker = '<!-- homelab-components-v1 -->'
    finish = '<!-- /homelab-components-v1 -->'
    block = marker + '\n<style>\n' + css + '\n</style><script>\n' + javascript + '\n</script>\n' + finish
    if marker in source:
        if source.count(marker)!=1 or source.count(finish)!=1:
            raise ValueError('Ambiguous component integration; review source')
        start=source.index(marker);end=source.index(finish,start)+len(finish)
        return source[:start]+block+source[end:]
    return replace_once(source,'</head>',block+'\n</head>')


def login_template(source, css):
    source=component_template(source,css,'')
    if 'homelab-login-v1' in source:
        return source
    source=replace_once(source,'<meta charset="UTF-8">','<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<!-- homelab-login-v1 -->')
    source=replace_once(source,'<img src="${http_root}images/mylarlogo.png" />','<img src="${http_root}images/mylarlogo.png" alt="Mylar" />')
    source=replace_once(source,'<input type="text" placeholder="username"','<h1>Sign in to Mylar</h1><label for="current_username">Username</label><input type="text" placeholder="username"')
    source=replace_once(source,'required autofocus autocomplete/>','required autofocus autocomplete="username"/>')
    source=replace_once(source,'<input type="password" placeholder="password"','<label for="current_password">Password</label><input type="password" placeholder="password"')
    source=replace_once(source,'required autocomplete/>','required autocomplete="current-password"/>')
    source=replace_once(source,'<button>Sign in</button>','<button type="submit">Sign in</button>')
    source=replace_once(source,'</body>','</form>\n</body>')
    return source


def main(directory):
    path = Path(directory).parent/'data/interfaces/default/base.html'
    css = Path(__file__).with_name('wide_layout.css').read_text()
    files = Path(__file__).parent
    path.write_text(component_template(template(path.read_text(), css),
        (files/'mylar_components.css').read_text(), (files/'mylar_components.js').read_text()))
    maintenance=path.with_name('maintenance_base.html')
    maintenance.write_text(component_template(maintenance.read_text(),
        (files/'mylar_components.css').read_text(), (files/'mylar_components.js').read_text()))
    login=path.with_name('login.html')
    login.write_text(login_template(login.read_text(),
        (files/'mylar_components.css').read_text()+(files/'login_ui.css').read_text()))
    history = path.with_name('history.html')
    files = Path(__file__).parent
    history.write_text(history_template(history.read_text(),
        (files/'history_ui.css').read_text(), (files/'history_ui.js').read_text()))
    for name in ('index', 'upcoming'):
        catalog = path.with_name(name + '.html')
        catalog.write_text(catalog_template(catalog.read_text(), name,
            (files/'catalog_ui.css').read_text(), (files/'catalog_ui.js').read_text()))
    install_manage_ui(path.parent, files)
    from patch_pullist_ui import main as patch_pullist
    patch_pullist(directory)
    print('Mylar fluid desktop layout verified')


if __name__ == '__main__':
    main(sys.argv[1])
