"""Checked primary-key publication API patch; never initializes runtime state."""
import ast
from pathlib import Path
import sys

MARKER = '# homelab-publication-api-v1'
METHOD = '''    # homelab-publication-api-v1
    def _publicationControl(self, **kwargs):
        key = mylar.CONFIG.API_KEY
        if (not mylar.CONFIG.API_ENABLED or not isinstance(key, str)
                or len(key) != 32 or self.apikey != key
                or getattr(self, 'apitype', None) != 'normal'):
            self.data = self._failureResponse('Primary API key required')
            return
        if cherrypy.request.method != 'POST' or set(kwargs) != {'request'}:
            self.data = self._failureResponse('Publication protocol requires POST request')
            return
        from mylar import publication_api
        try:
            result = publication_api.execute(kwargs['request'], data_dir=mylar.DATA_DIR,
                library_roots=[mylar.CONFIG.DESTINATION_DIR])
        except (ValueError, OSError, RuntimeError):
            self.data = self._failureResponse('Publication state or request requires review')
        else:
            self.data = self._successResponse(result)

'''


def patched_source(source):
    if MARKER in source:
        if source.count(METHOD) != 1 or source.count("'publicationControl'") != 1:
            raise ValueError('Publication API patch changed')
        ast.parse(source)
        return source
    anchor = "'getVersion', 'checkGithub'"
    method = '    def _getVersion(self, **kwargs):'
    if source.count(anchor) != 1 or source.count(method) != 1:
        raise ValueError('Publication API patch no longer matches this image')
    source = source.replace(anchor, "'publicationControl', " + anchor, 1)
    source = source.replace(method, METHOD + method, 1)
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    source = patched_source((root / 'api.py').read_text())
    for name in ('publication_api.py', 'publication_guard.py', 'publication_fresh.py', 'publication_native.py', 'publication_transaction.py', 'publication_rename.py', 'publication_tagging_recovery.py', 'publication_archive_layout.py', 'publication_archive_derivative.py', 'publication_archive_repair.py', 'publication_archive_diagnostics.py'):
        (root / name).write_text(Path(__file__).with_name(name).read_text())
    (root / 'api.py').write_text(source)
    from patch_publication_processing import main as patch_processing
    patch_processing(root)


if __name__ == '__main__':
    main(sys.argv[1])
