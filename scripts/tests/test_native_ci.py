"""Exercise native tool boundaries and required validation coverage without network."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/ci' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


TOOLS = module('bootstrap-native-tools')
DOTNET = module('check-dotnet-controls')
LINKS = module('check-native-links')
REGISTER = module('register-native-compose')


class ArchiveBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.destination = self.root / 'tools'
        self.destination.mkdir()
        self.outside = self.root / 'preserve'
        self.outside.write_text('unrelated')

    def archive(self, entries, *, zipped=False):
        archive = self.root / ('fixture.zip' if zipped else 'fixture.tar')
        if zipped:
            with zipfile.ZipFile(archive, 'w') as output:
                for name, kind in entries:
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    info.external_attr = (kind | 0o4755) << 16
                    output.writestr(info, b'executable')
        else:
            with tarfile.open(archive, 'w') as output:
                for name, kind in entries:
                    info = tarfile.TarInfo(name)
                    info.type = kind
                    info.size = 10 if kind == tarfile.REGTYPE else 0
                    info.linkname = '../preserve' if kind == tarfile.SYMTYPE else ''
                    output.addfile(info, io.BytesIO(b'executable') if info.size else None)
        return archive, {'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                         'format': 'zip' if zipped else 'tar', 'member': 'tool', 'output': 'bin/tool'}

    def test_tar_selects_only_one_regular_member_and_never_extracts_other_paths(self):
        archive, spec = self.archive([('../preserve', tarfile.REGTYPE), ('tool', tarfile.REGTYPE)])
        TOOLS.install(archive, spec, self.destination)
        self.assertEqual((self.destination / 'bin/tool').read_bytes(), b'executable')
        self.assertEqual(self.outside.read_text(), 'unrelated')
        self.assertEqual((self.destination / 'bin/tool').stat().st_mode & 0o7777, 0o755)

    def test_nested_tar_member_uses_the_actual_lychee_manifest_layout(self):
        spec = json.loads(TOOLS.MANIFEST.read_text())['tools']['lychee'].copy()
        self.assertEqual(spec['member'], 'lychee-x86_64-unknown-linux-gnu/lychee')
        archive, fixture = self.archive([(spec['member'], tarfile.REGTYPE)])
        spec['sha256'] = fixture['sha256']
        TOOLS.install(archive, spec, self.destination)
        self.assertEqual((self.destination / spec['output']).read_bytes(), b'executable')

    def test_tar_duplicate_selected_member_and_links_are_rejected(self):
        for entries in [[('tool', tarfile.REGTYPE)] * 2, [('tool', tarfile.SYMTYPE)]]:
            with self.subTest(entries=entries):
                archive, spec = self.archive(entries)
                with self.assertRaises(ValueError):
                    TOOLS.install(archive, spec, self.destination)
        self.assertFalse((self.destination / 'bin/tool').exists())
        self.assertEqual(self.outside.read_text(), 'unrelated')

    def test_zip_traversal_namespace_and_special_files_are_rejected(self):
        cases = [('../preserve', stat.S_IFREG), ('/preserve', stat.S_IFREG),
                 ('chrome-linux64/../../preserve', stat.S_IFREG),
                 ('other/tool', stat.S_IFREG), ('chrome-linux64/link', stat.S_IFLNK),
                 ('chrome-linux64/device', stat.S_IFCHR)]
        for entry in cases:
            with self.subTest(entry=entry):
                archive, spec = self.archive([entry], zipped=True)
                with self.assertRaises(ValueError):
                    TOOLS.install(archive, spec, self.destination)
        self.assertEqual(self.outside.read_text(), 'unrelated')

    def test_zip_strips_setuid_and_expansion_is_bounded(self):
        archive, spec = self.archive([('chrome-linux64/chrome', stat.S_IFREG)], zipped=True)
        with patch.object(TOOLS, 'MAX_EXPANDED', 1), self.assertRaises(ValueError):
            TOOLS.install(archive, spec, self.destination)
        TOOLS.install(archive, spec, self.destination)
        self.assertEqual((self.destination / 'chrome/chrome-linux64/chrome').stat().st_mode & 0o7777,
                         0o755)

    def test_checksum_mismatch_prevents_installation(self):
        archive, spec = self.archive([('tool', tarfile.REGTYPE)])
        spec['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'checksum'):
            TOOLS.install(archive, spec, self.destination)
        self.assertFalse((self.destination / 'bin/tool').exists())

    def test_unsafe_sources_are_denied_before_network(self):
        for url in ['http://github.com/tool', 'https://evil.invalid/tool',
                    'https://user:password@github.com/tool', 'https://github.com:444/tool']:
            with self.subTest(url=url), patch.object(TOOLS.urllib.request, 'urlopen') as request:
                with self.assertRaises(ValueError):
                    TOOLS.fetch({'url': url, 'sha256': 'a' * 64}, self.root / 'download')
                request.assert_not_called()


    def test_download_redirect_size_and_checksum_boundaries(self):
        class Response:
            def __init__(self, url, body):
                self.url = url
                self.body = io.BytesIO(body)

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def geturl(self):
                return self.url

            def read1(self, count):
                return self.body.read(count)

        spec = {'url': 'https://github.com/project/releases/download/v1/tool',
                'sha256': hashlib.sha256(b'executable').hexdigest()}
        cases = [('http://github.com/tool', b'executable', 'redirect'),
                 ('https://evil.invalid/tool', b'executable', 'redirect'),
                 ('https://release-assets.githubusercontent.com/tool', b'wrong', 'checksum')]
        for index, (url, body, message) in enumerate(cases):
            with self.subTest(url=url), patch.object(TOOLS.urllib.request, 'urlopen',
                                                    return_value=Response(url, body)):
                with self.assertRaisesRegex(ValueError, message):
                    TOOLS.fetch(spec, self.root / f'download-{index}')
        with patch.object(TOOLS.urllib.request, 'urlopen', return_value=Response(spec['url'], b'executable')), \
                patch.object(TOOLS, 'MAX_DOWNLOAD', 1), self.assertRaisesRegex(ValueError, 'bound'):
            TOOLS.fetch(spec, self.root / 'oversized')
        with patch.object(TOOLS.urllib.request, 'urlopen', return_value=Response(
                'https://release-assets.githubusercontent.com/tool', b'executable')):
            TOOLS.fetch(spec, self.root / 'valid')
        self.assertEqual((self.root / 'valid').read_bytes(), b'executable')

    def test_download_completion_depends_on_payload_not_elapsed_clock(self):
        class Response(io.BytesIO):
            def geturl(self):
                return 'https://storage.googleapis.com/tool'

            def read1(self, _count):
                return self.read(2)

        payload = b'complete checksum-bound tool'
        spec = {'url': 'https://storage.googleapis.com/tool',
                'sha256': hashlib.sha256(payload).hexdigest()}
        with patch.object(TOOLS.urllib.request, 'urlopen', return_value=Response(payload)) as request, \
                patch('time.monotonic', side_effect=[0, 0, 181, 362, 543]):
            TOOLS.fetch(spec, self.root / 'progressing')
        self.assertEqual((self.root / 'progressing').read_bytes(), payload)
        self.assertEqual(request.call_args.kwargs['timeout'], 15)

    def test_stalled_download_still_propagates_socket_timeout(self):
        class Response(io.BytesIO):
            def geturl(self):
                return 'https://storage.googleapis.com/tool'

            def read1(self, _count):
                raise TimeoutError('socket made no progress')

        spec = {'url': 'https://storage.googleapis.com/tool', 'sha256': 'a' * 64}
        with patch.object(TOOLS.urllib.request, 'urlopen', return_value=Response(b'')), \
                self.assertRaisesRegex(TimeoutError, 'socket made no progress'):
            TOOLS.fetch(spec, self.root / 'stalled')

    def test_cli_refuses_existing_or_indirect_destinations_before_download(self):
        with patch.object(TOOLS.platform, 'system', return_value='Linux'), \
                patch.object(TOOLS.platform, 'machine', return_value='x86_64'), \
                patch.object(TOOLS, 'fetch') as fetch:
            for arguments in [['--destination', str(self.destination), 'node'],
                              ['--destination', 'relative', 'node'],
                              ['--destination', str(self.root / 'new'), 'unknown'],
                              ['--destination', str(self.root / 'new'), 'node', 'node']]:
                with self.subTest(arguments=arguments), patch('sys.argv', ['bootstrap', *arguments]), \
                        self.assertRaises(SystemExit):
                    TOOLS.main()
            alias = self.root / 'alias'
            alias.symlink_to(self.destination, target_is_directory=True)
            with patch('sys.argv', ['bootstrap', '--destination', str(alias / 'new'), 'node']), \
                    self.assertRaises(SystemExit):
                TOOLS.main()
            fetch.assert_not_called()


class ComposeRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.container = self.root / 'container'
        self.container.mkdir()
        (self.container / '.dockerenv').touch()
        self.tools = self.root / 'tools'
        self.source = self.tools / 'docker-config/cli-plugins/docker-compose'
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b'verified fixture executable')
        self.source.chmod(0o755)
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps({'tools': {'compose': {
            'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()}}}))
        self.patch = patch.object(REGISTER, 'MANIFEST', manifest)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.target = self.container / 'usr/local/lib/docker/cli-plugins/docker-compose'

    def register(self):
        REGISTER.register(self.tools, container_root=self.container, uid=0)

    def test_system_plugin_is_independent_of_fixture_home_and_docker_config(self):
        self.register()
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(self.target.resolve(), self.source)
        empty = self.root / 'isolated-config'
        empty.mkdir()
        with patch.dict('os.environ', HOME=str(empty), DOCKER_CONFIG=str(empty), clear=False):
            self.register()
            self.assertEqual(self.target.resolve(), self.source)
            self.assertEqual(list(empty.iterdir()), [])

    def test_host_nonroot_or_symlink_marker_is_refused_before_writes(self):
        with self.assertRaises(ValueError):
            REGISTER.register(self.tools, container_root=self.container, uid=1000)
        (self.container / '.dockerenv').unlink()
        with self.assertRaises(ValueError):
            self.register()
        (self.container / '.dockerenv').symlink_to(self.source)
        with self.assertRaises(ValueError):
            self.register()
        self.assertFalse((self.container / 'usr').exists())

    def test_wrong_checksum_and_unrelated_existing_plugin_are_preserved(self):
        self.source.write_bytes(b'unexpected content')
        with self.assertRaises(ValueError):
            self.register()
        self.assertFalse((self.container / 'usr').exists())
        self.source.write_bytes(b'verified fixture executable')
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b'preserve unrelated plugin')
        with self.assertRaises(ValueError):
            self.register()
        self.assertEqual(self.target.read_bytes(), b'preserve unrelated plugin')

    def test_indirect_system_directory_never_writes_outside_container_root(self):
        outside = self.root / 'preserve'
        outside.mkdir()
        (self.container / 'usr').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.register()
        self.assertEqual(list(outside.iterdir()), [])


class MandatoryCoverageTests(unittest.TestCase):
    def test_dotnet_result_rejects_skips_failures_and_incomplete_execution(self):
        result = unittest.TestResult()
        result.testsRun = 9
        DOTNET.completed(result)
        for skipped, count, failures in [([('test', 'missing SDK')], 9, []),
                                         ([], 0, []), ([], 8, []), ([], 9, [('test', 'failure')])]:
            result.skipped, result.testsRun, result.failures = skipped, count, failures
            with self.subTest(count=count, skipped=skipped), self.assertRaises(RuntimeError):
                DOTNET.completed(result)

    def test_dotnet_prerequisite_refuses_absent_or_wrong_compilers(self):
        with patch.object(DOTNET.shutil, 'which', return_value=None), self.assertRaises(RuntimeError):
            DOTNET.prerequisite()
        with patch.object(DOTNET.shutil, 'which', return_value='/tool'), \
                patch.object(DOTNET.subprocess, 'check_output', side_effect=['9.0.1', 'v26.7.0']), \
                self.assertRaises(RuntimeError):
            DOTNET.prerequisite()
        with patch.object(DOTNET.shutil, 'which', return_value='/tool'), \
                patch.object(DOTNET.subprocess, 'check_output', side_effect=['10.0.403', 'v26.7.0']):
            DOTNET.prerequisite()

    def test_native_core_and_explicit_sdk_jdk_lanes_are_unconditional(self):
        pipeline = yaml.safe_load((ROOT / '.woodpecker.yml').read_text())
        self.assertEqual(pipeline['clone']['git']['settings'], {'depth': 0, 'partial': False})
        self.assertEqual(pipeline['when'][0]['event'], ['push', 'pull_request', 'manual', 'cron'])
        steps = {step['name']: step for step in pipeline['steps']}
        for name in ['gitleaks', 'repository-validation', 'source-and-workflow-policy',
                     'komga-source-controls', 'kavita-dotnet-controls', 'site-quality',
                     'publisher-broker-tests']:
            self.assertNotIn('when', steps[name])
            self.assertRegex(steps[name]['image'], r'@sha256:[0-9a-f]{64}$')
        self.assertEqual(steps['weekly-documentation-links']['when']['event'], ['cron', 'manual'])
        self.assertIn(steps['kavita-dotnet-controls']['image'],
                      (ROOT / 'stacks/kavita/independent/Dockerfile').read_text())
        self.assertIn('21-jdk-noble@sha256:', steps['komga-source-controls']['image'])

    def test_only_pure_hosted_jobs_have_the_default_off_retirement_guard(self):
        jobs = {'repository-validation.yml': ['validate', 'site-quality'], 'source-lint.yml': ['lint'],
                'workflow-security.yml': ['audit'], 'dockerfile-lint.yml': ['hadolint'],
                'weekly-maintenance.yml': ['repository', 'links'], 'spec-kit.yml': ['validate']}
        for name, expected in jobs.items():
            workflow = yaml.safe_load((ROOT / '.github/workflows' / name).read_text())
            for job in expected:
                guard = workflow['jobs'][job]['if']
                self.assertIn("vars.WOODPECKER_LINUX_CI != 'true'", guard)
                self.assertNotIn('WOODPECKER_PUBLISHING', guard)
        for name in ['custom-images.yml', 'pages.yml']:
            self.assertNotIn('WOODPECKER_LINUX_CI', (ROOT / '.github/workflows' / name).read_text())

    def test_manifest_preserves_chrome_channel_and_locked_test_packages(self):
        tools = json.loads(TOOLS.MANIFEST.read_text())['tools']
        for spec in tools.values():
            self.assertRegex(spec['sha256'], r'^[0-9a-f]{64}$')
            self.assertTrue(spec['url'].startswith('https://'))
        self.assertEqual(tools['node']['version'], '26.7.0')
        self.assertEqual(tools['chrome']['version'], '157.0.8103.38')
        self.assertIn("channel: 'chrome'", (ROOT / 'playwright.config.js').read_text())
        lock = json.loads((ROOT / 'package-lock.json').read_text())
        self.assertEqual(lock['packages']['node_modules/@playwright/test']['version'], '1.64.1')


class LinkPolicyTests(unittest.TestCase):
    def test_arguments_reuse_the_exact_weekly_policy(self):
        policy = LINKS.arguments()
        self.assertIn('--offline', policy['internal'])
        self.assertIn('--include-fragments', policy['internal'])
        self.assertIn('200,204,206,403,429', policy['external'])
        self.assertNotIn('--offline', policy['external'])

    def test_internal_errors_fail_while_external_report_remains_nonblocking(self):
        with patch.object(LINKS.subprocess, 'run', return_value=subprocess.CompletedProcess([], 2)), \
                self.assertRaises(SystemExit):
            LINKS.main()
        with patch.object(LINKS.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 2)]) as run:
            LINKS.main()
            self.assertEqual(run.call_count, 2)
        with patch.object(LINKS.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 0), subprocess.TimeoutExpired([], 180)]), \
                patch('sys.stderr', new_callable=io.StringIO) as report:
            LINKS.main()
            self.assertIn('report incomplete', report.getvalue())
            self.assertIn('no external-link success established', report.getvalue())
        with patch.object(LINKS.subprocess, 'run', side_effect=subprocess.TimeoutExpired([], 180)), \
                self.assertRaises(subprocess.TimeoutExpired):
            LINKS.main()
        with patch.object(LINKS.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 0), FileNotFoundError('lychee')]), \
                self.assertRaises(FileNotFoundError):
            LINKS.main()


if __name__ == '__main__':
    unittest.main()
