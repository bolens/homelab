"""Install primary-key conversion admission and the serial PP worker consumer."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-converted-tagging-v1'


def api(source):
    if MARKER in source:
        return source
    source = replace_once(source, "'getVersion', 'checkGithub'", "'queueConvertedTag', 'getVersion', 'checkGithub'")
    source = replace_once(source, '    def _getVersion(self, **kwargs):', '''    # homelab-converted-tagging-v1
    def _queueConvertedTag(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import converted_tagging
        try:
            result = converted_tagging.admit(kwargs.get('conversion'))
        except (ValueError, TypeError):
            self.data = self._failureResponse('Invalid conversion request')
        except Exception:
            self.data = self._failureResponse('Conversion queue unavailable; retry later')
        else:
            self.data = self._successResponse(result)

    def _getVersion(self, **kwargs):''')
    ast.parse(source)
    return source


def worker(source):
    if MARKER in source:
        return source
    source = replace_once(source, '        else:\n            time.sleep(5)',
        '        else:\n            '+MARKER+'\n            from mylar import converted_tagging\n'
        '            converted_tagging.poll()\n            time.sleep(5)')
    ast.parse(source)
    return source


def rescan(source):
    marker = '# homelab-converted-catalog-v1'
    if marker in source:
        return source
    source = replace_once(source, 'def forceRescan(', '@converted_catalog.rescan\ndef forceRescan(')
    source = marker+'\nfrom mylar import converted_catalog\n'+source
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {root/'api.py': api((root/'api.py').read_text()),
               root/'queues/postprocess.py': worker((root/'queues/postprocess.py').read_text()),
               root/'updater.py': rescan((root/'updater.py').read_text())}
    for path, source in changes.items():
        path.write_text(source)
    for name in ('converted_tagging.py', 'converted_catalog.py'):
        (root/name).write_text(Path(__file__).with_name(name).read_text())


if __name__ == '__main__':
    main(sys.argv[1])
