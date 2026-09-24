"""Add authenticated health and failed-download commands to the pinned API."""
import ast
from pathlib import Path
import sys

MARKER = '# homelab-health-api-v1'


def patched_source(source):
    if MARKER in source:
        return source
    before = "'getVersion', 'checkGithub'"
    if source.count(before) != 1 or source.count('    def _getVersion(self, **kwargs):') != 1:
        raise ValueError('Health API patch no longer matches this image')
    source = source.replace(before, "'getHealth', 'reportFailedDownload', " + before, 1)
    methods = '''    # homelab-health-api-v1
    def _getHealth(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import reliability
        self.data = self._successResponse(reliability.snapshot())

    def _reportFailedDownload(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import reliability
        try:
            result = reliability.report_failed(kwargs['issueid'], kwargs['comicid'], kwargs['release'])
        except (KeyError, ValueError):
            self.data = self._failureResponse('Failed-download mapping or settings require review')
        else:
            self.data = self._successResponse(result)

'''
    source = source.replace('    def _getVersion(self, **kwargs):', methods + '    def _getVersion(self, **kwargs):', 1)
    ast.parse(source)
    return source


def main(directory):
    path = Path(directory) / 'api.py'
    source = patched_source(path.read_text())
    helper = Path(directory) / 'reliability.py'
    if helper.exists() and 'homelab-reliability-v1' not in helper.read_text():
        raise ValueError('Refusing to overwrite an upstream reliability module')
    helper.write_text(Path(__file__).with_name('reliability.py').read_text())
    path.write_text(source)
    print('Mylar authenticated reliability API verified')


if __name__ == '__main__':
    main(sys.argv[1])
