"""Present native Manage workflows with shared components and explicit scan intent."""
from source_patches import replace_once

MARKER = '<!-- homelab-manage-review-v1 -->'

SCAN_FUNCTIONS = '''        var CheckEnabled = false;
        var ImportTimer = null;
        function clearScanAction() {
            $('#comicScan input[name="scan"]').remove();
            $('#forcescan').prop('checked', false);
        };
        function addScanAction() {
            $('#comicScan input[name="scan"]').remove();
            $('<input>', {type:'hidden', name:'scan', id:'scan', value:'1'}).appendTo('#comicScan');
            turniton();
        };
        function statuscheck() {
            if (!CheckEnabled || ImportTimer !== null) return;
            ImportTimer = setInterval(function() {
                $.get('Check_ImportStatus', function(data) {
                    if (data && data.error !== undefined) {
                        $('#manage_import_feedback').text(data.error);
                        turnitoff();
                        return;
                    }
                    $('#importstatus').val(data);
                    $('#manage_import_feedback').text(data);
                    if (data === 'Import completed.') turnitoff();
                }).fail(function() {
                    $('#manage_import_feedback').text('Status unavailable. Reload this page to check the scan.');
                    turnitoff();
                });
            }, 5000);
        };
        function turnitoff() {
            CheckEnabled = false;
            if (ImportTimer !== null) clearInterval(ImportTimer);
            ImportTimer = null;
        };
        function turniton() {
            CheckEnabled = true;
            statuscheck();
        };
        $(window).on('pagehide.manage', turnitoff);
'''


TABS_FUNCTIONS = """
        function refreshManageTab() {
            var panel = $('#tabs > .ui-tabs-panel:visible');
            if (!panel.length) return;
            panel.load(window.location.href + ' #' + panel.attr('id') + ' > *', function() {
                initThisPage();
                if (window.MylarComponents) window.MylarComponents.enhance(panel[0]);
            });
        };
        function manageTabsState(index) {
            var tabs = $('#tabs > ul > li > a');
            $('#tabs > ul').attr('role', 'tablist').attr('aria-label', 'Manage workflows');
            tabs.each(function(i) {
                var id = 'manage_tab_' + (i + 1);
                $(this).attr({id:id, role:'tab', 'aria-controls':'tabs-' + (i + 1),
                    'aria-selected':i === index ? 'true' : 'false', tabindex:i === index ? 0 : -1});
                $('#tabs-' + (i + 1)).attr({role:'tabpanel', 'aria-labelledby':id});
            });
        };
        function initManageTabs() {
            window.refreshTab = refreshManageTab;
            manageTabsState($('#tabs').tabs('option', 'selected'));
            $('#tabs').off('tabsselect.manageTabs').on('tabsselect.manageTabs', function(event, ui) {
                manageTabsState(ui.index);
            });
            $('#tabs > ul > li > a').off('keydown.manageTabs').on('keydown.manageTabs', function(event) {
                var tabs = $('#tabs > ul > li > a'), index = tabs.index(this);
                if (event.key === 'ArrowRight') index = (index + 1) % tabs.length;
                else if (event.key === 'ArrowLeft') index = (index + tabs.length - 1) % tabs.length;
                else if (event.key === 'Home') index = 0;
                else if (event.key === 'End') index = tabs.length - 1;
                else return;
                event.preventDefault();
                $('#tabs').tabs('select', index);
                tabs.eq(index).focus();
            });
        };
"""


def template(source, body, css):
    if MARKER in source:
        return source
    body_start = source.index('<%def name="body()">')
    body_end = source.index('</%def>', body_start)
    original_body = source[body_start:body_end]
    for anchor in ('id="comicScan"', 'id="manual_process"', 'id="tabs-4"'):
        if original_body.count(anchor) != 1:
            raise ValueError('Manage form boundary changed; review source')
    source = source[:body_start] + '<%def name="body()">\n' + MARKER + '\n' + body + '\n' + source[body_end:]
    source = replace_once(source, '<%def name="headIncludes()">', '<%def name="headIncludes()">\n<style>\n' + css + '\n</style>')
    header_start = source.index('<%def name="headerIncludes()">')
    header_end = source.index('</%def>', header_start)
    if 'href="activity"' not in source[header_start:header_end]:
        source = replace_once(source, '<div id="subhead_menu">', '<div id="subhead_menu">\n<a href="activity">Activity</a>')
    source = replace_once(source, '        var CheckEnabled = true;', '')
    start = source.index('        function addScanAction() {')
    end = source.index('        function interactive_process()', start)
    source = source[:start] + SCAN_FUNCTIONS + '\n' + source[end:]
    source = replace_once(source, '$("#imps").click(function(){', '$("#imps").off("click.manageOptions").on("click.manageOptions", function(){')
    source = replace_once(source, "$('#nzb_folder').on('click', function(){", "$('#nzb_folder').off('click.manageManual').on('click.manageManual', function(){")
    source = replace_once(source, "$('#manual_process').click(function () {", "$('#manual_process').off('click.manageManual').on('click.manageManual', function () {")
    source = replace_once(source, '        function startTime() {', '        var ClockTimer = null;\n        function startTime() {\n                if (ClockTimer !== null) clearTimeout(ClockTimer);')
    source = replace_once(source, '                var t = setTimeout(startTime, 500);', '                ClockTimer = setTimeout(startTime, 500);')
    source = replace_once(source, "$(window).on('pagehide.manage', turnitoff);", "var ResumeImport = false;\n        $(window).on('pagehide.manage', function() { ResumeImport = CheckEnabled; turnitoff(); if (ClockTimer !== null) clearTimeout(ClockTimer); ClockTimer = null; });\n        $(window).on('pageshow.manage', function(event) { if (event.originalEvent && event.originalEvent.persisted) { startTime(); if (ResumeImport) turniton(); } });")
    source = source.replace("statuschk.innerHTML = obj['message'];", "$(statuschk).text(obj['message']);")
    source = replace_once(source, '                                varlength = 135 - obj[\'message\'].length;\n                                nzb_folder.setAttribute("size", varlength);', '')
    old = "$('#ajaxMsg').html(\"<div class='msg'><span class='ui-icon ui-icon-check'></span>\"+obj['message']+\"</div>\");"
    source = source.replace(old, "$('#ajaxMsg').empty().append($('<div>').addClass('msg').text(obj['message']));")
    source = replace_once(source, '        function initThisPage() {', TABS_FUNCTIONS + '\n        function initThisPage() {')
    source = replace_once(source, '                jQuery( "#tabs" ).tabs();', '                jQuery( "#tabs" ).tabs();\n                initManageTabs();')
    return source


def install(templates, files):
    path = templates / 'manage.html'
    path.write_text(template(path.read_text(), (files/'manage_body.html').read_text(),
                             (files/'manage_ui.css').read_text()))
