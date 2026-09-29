"""Keep global notifications usable on static pages without reload targets."""
from pathlib import Path
import sys
from source_patches import replace_once


def template(source):
    marker = '// homelab-static-page-events-v1'
    if marker in source: return source
    anchor = '''                    var tt = document.getElementById("page_name");
                    if (data.status == 'success'){'''
    return replace_once(source, anchor, '''                    var tt = document.getElementById("page_name");
                    // homelab-static-page-events-v1
                    // Static pages display the notification without refreshing absent tables/tabs.
                    if (!tt) {
                        if (data.status == 'success' || data.status == 'failure') {
                            $('#ajaxMsg').addClass(data.status == 'success' ? 'success' : 'error').fadeIn().delay(3000).fadeOut();
                        }
                        return;
                    }
                    if (data.status == 'success'){''')


def main(directory):
    path = Path(directory).parent/'data/interfaces/default/base.html'
    path.write_text(template(path.read_text()))


if __name__ == '__main__': main(sys.argv[1])
