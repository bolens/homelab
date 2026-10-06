"""Checked explicit adopted-lineage publication routes; discovery remains held."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-reviewed-derivative-v1'
METHOD = '''    # homelab-reviewed-derivative-v1
    def _reviewedDerivative(self, status, **kwargs):
        key = mylar.CONFIG.API_KEY
        if (not mylar.CONFIG.API_ENABLED or not isinstance(key, str) or len(key) != 32
                or self.apikey != key or getattr(self, 'apitype', None) != 'normal'):
            self.data = self._failureResponse('Primary API key required')
            return
        if cherrypy.request.method != 'POST' or set(kwargs) != {'token'}:
            self.data = self._failureResponse('Reviewed derivative requires POST token')
            return
        from mylar import library_metadata, publication_native, publication_guard
        try:
            result = library_metadata.reviewed_derivative(kwargs['token'], status=status)
        except publication_native.Review:
            self.data = self._failureResponse('Reviewed derivative requires review; originals retained')
        except (publication_guard.Unavailable, ValueError, TypeError, OSError):
            self.data = self._failureResponse('Reviewed derivative evidence unavailable')
        else:
            self.data = self._successResponse(result)

    def _commitReviewedDerivative(self, **kwargs):
        return self._reviewedDerivative(False, **kwargs)

    def _reviewedDerivativeStatus(self, **kwargs):
        return self._reviewedDerivative(True, **kwargs)

'''


def api(source):
    if MARKER in source:
        if source.count(METHOD) != 1 or any(source.count(repr(name)) != 1 for name in ('commitReviewedDerivative', 'reviewedDerivativeStatus')):
            raise ValueError('Reviewed derivative API patch changed')
        ast.parse(source)
        return source
    source = replace_once(source, "'getVersion', 'checkGithub'",
                          "'commitReviewedDerivative', 'reviewedDerivativeStatus', 'getVersion', 'checkGithub'")
    source = replace_once(source, '    def _getVersion(self, **kwargs):', METHOD+'    def _getVersion(self, **kwargs):')
    ast.parse(source)
    return source


def main(directory):
    root=Path(directory)
    source=api((root/'api.py').read_text())
    for name in ('publication_lineage.py', 'publication_derivative.py', 'library_metadata.py'):
        (root/name).write_text(Path(__file__).with_name(name).read_text())
    (root/'api.py').write_text(source)


if __name__ == '__main__':
    main(sys.argv[1])
