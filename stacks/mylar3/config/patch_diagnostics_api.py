"""Add authenticated health and failed-download commands to the pinned API."""

import ast
from pathlib import Path
import sys

MARKER = "# homelab-health-api-v1"
WAIT_MARKER = "# homelab-health-writer-wait-v1"
HEALTH_RESULT = """        # homelab-health-writer-wait-v1
        try:
            wait = float(kwargs.get('writer_wait', 0))
            result = worker_health.snapshot(writer_wait=wait)
        except (ValueError, TypeError):
            self.data = self._failureResponse('Invalid health observation')
            return
        self.data = self._successResponse(result)"""
HEALTH_METHOD = """    def _getHealth(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import worker_health
""" + HEALTH_RESULT + '\n'


def checked_health(source):
    nodes=[n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='_getHealth']
    expected=ast.parse('class API:\n'+HEALTH_METHOD).body[0].body[0]
    if source.count(WAIT_MARKER)!=1 or len(nodes)!=1 or ast.dump(nodes[0])!=ast.dump(expected):
        raise ValueError('Waiting health API no longer matches this image')
    return source


def patched_source(source):
    if MARKER in source:
        if WAIT_MARKER in source:
            return checked_health(source)
        old = '        self.data = self._successResponse(worker_health.snapshot())'
        if source.count(old) != 1:
            raise ValueError('Existing health API no longer matches this image')
        source = source.replace(old, HEALTH_RESULT, 1)
        return checked_health(source)
    before = "'getVersion', 'checkGithub'"
    if (
        source.count(before) != 1
        or source.count("    def _getVersion(self, **kwargs):") != 1
    ):
        raise ValueError("Health API patch no longer matches this image")
    source = source.replace(before, "'getHealth', 'reportFailedDownload', " + before, 1)
    methods = """    # homelab-health-api-v1
    def _getHealth(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import worker_health
        self.data = self._successResponse(worker_health.snapshot())

    def _reportFailedDownload(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import failed_downloads
        try:
            result = failed_downloads.report_failed(kwargs['issueid'], kwargs['comicid'], kwargs['release'])
        except (KeyError, ValueError):
            self.data = self._failureResponse('Failed-download mapping or settings require review')
        else:
            self.data = self._successResponse(result)

"""
    methods = methods.replace('        self.data = self._successResponse(worker_health.snapshot())', HEALTH_RESULT, 1)
    source = source.replace(
        "    def _getVersion(self, **kwargs):",
        methods + "    def _getVersion(self, **kwargs):",
        1,
    )
    return checked_health(source)


def main(directory):
    path = Path(directory) / "api.py"
    source = patched_source(path.read_text())
    for name in ("worker_health.py", "failed_downloads.py"):
        (Path(directory) / name).write_text(Path(__file__).with_name(name).read_text())
    (Path(directory) / "cooldown_health.py").write_text(
        Path(__file__).with_name("cooldown_health.py").read_text()
    )
    path.write_text(source)
    print("Mylar authenticated reliability API verified")


if __name__ == "__main__":
    main(sys.argv[1])
