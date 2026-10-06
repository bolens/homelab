"""Install primary-key naming APIs and explicit final scanner parsing."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-release-naming-v1'
PRINT_FIELDS = '''        printed = release_naming.print_fields(self, modfilename)
        if printed:
            series_name = printed["series"]
            series_name_decoded = unicodedata.normalize("NFKD", series_name)
            issue_number = printed["number"]
            issue_year = printed["year"]
            issue_volume = printed["volume"]
'''


def api(source):
    if MARKER in source:
        lines=source.splitlines(keepends=True)
        methods=[node for node in ast.walk(ast.parse(source)) if isinstance(node,ast.FunctionDef)
                 and node.name in ('_getReleaseNaming','_renameLibraryFile','_releaseNamingStatus')]
        if len(methods)!=3:raise ValueError('Release naming API methods changed')
        for node in sorted(methods,key=lambda node:node.lineno,reverse=True):
            block=''.join(lines[node.lineno-1:node.end_lineno])
            if 'except publication_native.Review:' not in block:
                block=replace_once(block,'        from mylar import release_naming\n',
                    '        from mylar import release_naming, publication_native\n')
                block=replace_once(block,'        except (ValueError, TypeError):\n',
                    "        except publication_native.Review:\n            self.data = self._failureResponse('Release naming needs review')\n        except (ValueError, TypeError):\n")
                lines[node.lineno-1:node.end_lineno]=[block]
        source=''.join(lines);ast.parse(source)
        return source
    source = replace_once(source, "'getVersion', 'checkGithub'", "'getReleaseNaming', 'renameLibraryFile', 'releaseNamingStatus', 'getVersion', 'checkGithub'")
    methods = []
    for command, call in [('getReleaseNaming', "get(kwargs.get('source'))"),
                          ('renameLibraryFile', "rename(kwargs.get('naming'))"),
                          ('releaseNamingStatus', "status(kwargs.get('token'))")]:
        methods.append('''    def _COMMAND(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import release_naming, publication_native
        try:
            result = release_naming.CALL
        except publication_native.Review:
            self.data = self._failureResponse('Release naming needs review')
        except (ValueError, TypeError):
            self.data = self._failureResponse('Release naming needs review')
        except Exception:
            self.data = self._failureResponse('Release naming unavailable; inspect its journal')
        else:
            self.data = self._successResponse(result)

'''.replace('COMMAND', command).replace('CALL', call))
    source = replace_once(source, '    def _getVersion(self, **kwargs):',
                          '    '+MARKER+'\n'+''.join(methods)+'    def _getVersion(self, **kwargs):')
    ast.parse(source)
    return source


def scanner(source):
    if MARKER in source:
        if 'release_naming.print_fields(self, modfilename)' not in source:
            source = replace_once(source, '        collected = release_naming.collected(self, modfilename)\n', PRINT_FIELDS+'        collected = release_naming.collected(self, modfilename)\n')
        old = 'release_naming.release_number(modfilename)'
        if old in source:
            return replace_once(source, old, 'release_naming.release_number(modfilename, self)')
        return source
    source = replace_once(source, '        scangroup = None\n',
                          '        '+MARKER+'\n        modfilename, scangroup = release_naming.scanner(modfilename)\n')
    source = replace_once(source, '        recovered = file_identity.single_volume_match(self, filename)\n',
                          PRINT_FIELDS+'        collected = release_naming.collected(self, modfilename)\n'
                          '        if collected:\n'
                          '            series_name = collected["series"]\n'
                          '            series_name_decoded = unicodedata.normalize("NFKD", series_name)\n'
                          '            issue_number = issue_volume = collected["number"]\n'
                          '            issue_year = collected["year"]\n'
                          '            booktype = collected["kind"]\n'
                          '        release_number = release_naming.release_number(modfilename, self)\n'
                          '        if release_number is not None:\n            issue_number = release_number\n'
                          '        recovered = file_identity.single_volume_match(self, filename)\n')
    source = 'from mylar import release_naming\n'+source
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    for name, adapter in [('api.py', api), ('filechecker.py', scanner)]:
        path = root/name; path.write_text(adapter(path.read_text()))
    (root/'release_naming.py').write_text(Path(__file__).with_name('release_naming.py').read_text())


if __name__ == '__main__':main(sys.argv[1])
