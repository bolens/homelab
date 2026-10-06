"""Checked primary-key POST route for the finite native combined-pass owner."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-combined-publication-v1'
METHOD = '''    # homelab-combined-publication-v1
    def _combinedPublication(self, **kwargs):
        key = mylar.CONFIG.API_KEY
        if (not mylar.CONFIG.API_ENABLED or not isinstance(key, str) or len(key) != 32
                or self.apikey != key or getattr(self, 'apitype', None) != 'normal'):
            self.data = self._failureResponse('Primary API key required')
            return
        if cherrypy.request.method != 'POST' or set(kwargs) != {'request'}:
            self.data = self._failureResponse('Combined publication requires POST request')
            return
        from mylar import combined_publication, publication_native, publication_guard
        try:
            result = combined_publication.execute(kwargs['request'])
        except publication_native.Review:
            self.data = self._failureResponse('Combined publication requires review; originals retained')
        except (publication_guard.Unavailable, ValueError, TypeError, OSError):
            self.data = self._failureResponse('Combined publication request or evidence unavailable')
        else:
            self.data = self._successResponse(result)

'''


def api(source):
    if MARKER in source:
        if source.count(METHOD) != 1 or source.count("'combinedPublication'") != 1:
            raise ValueError('Combined API patch changed')
        ast.parse(source)
        return source
    source = replace_once(source, "'getVersion', 'checkGithub'",
                          "'combinedPublication', 'getVersion', 'checkGithub'")
    source = replace_once(source, '    def _getVersion(self, **kwargs):',
                          METHOD+'    def _getVersion(self, **kwargs):')
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    source = api((root/'api.py').read_text())
    for name in ('combined_publication.py', 'combined_cleanup.py'):
        (root/name).write_text(Path(__file__).with_name(name).read_text())
    (root/'api.py').write_text(source)


if __name__ == '__main__':
    main(sys.argv[1])
