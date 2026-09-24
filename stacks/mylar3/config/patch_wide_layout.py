"""Add a theme-neutral desktop layout override to Mylar's shared template."""
from pathlib import Path
import sys
from patch_queue_control import replace_once

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
    block = START + '\n<style>\n' + css + '</style>\n' + END
    if START in source:
        if source.count(START) != 1 or source.count(END) != 1:
            raise ValueError('Ambiguous wide-layout block; review source')
        start = source.index(START)
        finish = source.index(END, start) + len(END)
        return source[:start] + block + source[finish:]
    return replace_once(source, '${next.headIncludes()}', '${next.headIncludes()}\n' + block)


def main(directory):
    path = Path(directory).parent/'data/interfaces/default/base.html'
    css = Path(__file__).with_name('wide_layout.css').read_text()
    path.write_text(template(path.read_text(), css))
    print('Mylar fluid desktop layout verified')


if __name__ == '__main__':
    main(sys.argv[1])
