"""Offline controls: actual installed Clark args; in-memory HTTP/WS, no browser."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('clarkserve', Path(__file__).with_name('clarkserve.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ORIGINS = frozenset({'https://clark.home', 'http://clark.home'})


def stream(raw):
    value = asyncio.StreamReader(limit=m.HEADER)
    value.feed_data(raw)
    value.feed_eof()
    return value


class Writer:
    def __init__(self):
        self.data = bytearray()
        self.closed = False

    def write(self, data):
        self.data.extend(data)

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


class Contracts(unittest.TestCase):
    def test_current_package_options_preserved(self):
        env = {'CLARK_FINGERPRINT_PLATFORM': 'linux', 'CLARK_FINGERPRINT_NETWORK_PROFILE': 'residential', 'CLARK_WEBRTC_POLICY': 'proxy-coherent', 'CLARK_WEBGPU_POLICY': 'coherent', 'CLARK_LAUNCH_HYGIENE': 'off', 'CLARK_PROXY_SERVER': 'http://proxy.example:8080'}
        with patch.dict(os.environ, env, clear=True), patch('clarkbrowser.download.ensure_binary', return_value='/published/chrome'):
            options, argv, _ = m.launch_options(['--port=9222', '--headless=true'])
        self.assertEqual(options.port, 9222)
        self.assertEqual(argv[0], '/published/chrome')
        self.assertIn('--fingerprint-platform=linux', argv)
        self.assertIn('--fingerprint-network-profile=residential', argv)
        self.assertIn('--force-webrtc-ip-handling-policy=disable_non_proxied_udp', argv)
        self.assertNotIn('--enable-unsafe-webgpu', argv)
        self.assertFalse(any('WebGPU' in item for item in argv))
        self.assertIn('--proxy-server=http://proxy.example:8080', argv)
        self.assertIn('--remote-debugging-port=9223', argv)
        self.assertIn('--remote-debugging-address=127.0.0.1', argv)
        self.assertNotIn('--remote-allow-origins=*', argv)

    def test_strict_hygiene_accounts_for_public_adapter(self):
        with patch.dict(os.environ, {'CLARK_LAUNCH_HYGIENE': 'strict'}, clear=True), patch('clarkbrowser.download.ensure_binary') as binary:
            with self.assertRaises(RuntimeError):
                m.launch_options([])
            binary.assert_not_called()

    def test_authenticated_proxy_refuses_without_disclosing_value(self):
        with patch.dict(os.environ, {'CLARK_PROXY_PASSWORD': 'private-test-placeholder'}, clear=True):
            with self.assertRaisesRegex(ValueError, '^authenticated-proxy-not-supported$'):
                m.launch_options([])

    def test_invalid_policy_and_launch_override_refuse(self):
        for args, env in [(['--remote-debugging-port=1'], {}), (['--port=65535'], {}), ([], {'CLARK_WEBGPU_POLICY': 'invalid'}), ([], {'CLARK_PROXY_SERVER': 'http://user:password@proxy.example'})]:
            with self.subTest(args=args, env=env), patch.dict(os.environ, env, clear=True):
                with self.assertRaises((ValueError, RuntimeError)):
                    m.launch_options(args)

    def test_missing_prefetch_refuses_in_smoke_override(self):
        with patch.dict(os.environ, {'CLARK_LAUNCH_HYGIENE': 'off', 'CLARK_BINARY_PATH': '/absent/owned-smoke-chrome'}, clear=True):
            with self.assertRaises(FileNotFoundError):
                m.launch_options([])

    def test_host_scheme_absolute_target_and_framing_refuse(self):
        requests = [b'GET http://evil.example/json/version HTTP/1.1\r\nHost: clark.home\r\n\r\n', b'GET /json/version HTTP/1.1\r\nHost: evil.example/path\r\n\r\n', b'GET /json/version HTTP/1.1\r\nHost: clark.home\r\nHost: other\r\n\r\n', b'GET /json/version HTTP/1.1\r\nHost: clark.home\r\nTransfer-Encoding: chunked\r\n\r\n', b'GET /json/version HTTP/1.1\r\nHost: clark.home\r\nX-Forwarded-Proto: https://evil\r\n\r\n', b'GET /json/version HTTP/1.1\r\nHost: clark.home\r\nOrigin: https://evil.example\r\n\r\n']
        for raw in requests:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                m.request(raw, ORIGINS)
        with self.assertRaises(ValueError):
            m.request(b'X' * (m.HEADER + 1), ORIGINS)

    def test_discovery_rewrites_only_valid_backend_websocket_urls(self):
        original = {'Browser': 'Chrome/148.0.7778.96', 'webSocketDebuggerUrl': 'ws://127.0.0.1:9223/devtools/browser/abc-123'}
        value = json.loads(m.public_document(json.dumps(original).encode(), 'clark.home', 'https', 9223, ORIGINS))
        self.assertEqual(value['Browser'], original['Browser'])
        self.assertEqual(value['webSocketDebuggerUrl'], 'wss://clark.home/devtools/browser/abc-123')
        for url in ('ws://evil.example/devtools/browser/id', 'ws://127.0.0.1:9223/devtools/browser/id?next=evil', 'ws://user@127.0.0.1:9223/devtools/browser/id'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                m.public_document(json.dumps({'webSocketDebuggerUrl': url}).encode(), 'clark.home', 'https', 9223, ORIGINS)
        with self.assertRaises(ValueError):
            m.public_document(b' ' * (m.BODY + 1), 'clark.home', 'http', 9223, ORIGINS)

    def test_matching_foreign_host_and_origin_cannot_bypass_rebinding_guard(self):
        for path, extra in [('/json/version', ''), ('/devtools/browser/abc', 'Upgrade: websocket\r\nConnection: Upgrade\r\n')]:
            raw = ('GET ' + path + ' HTTP/1.1\r\nHost: attacker.example\r\nOrigin: https://attacker.example\r\nX-Forwarded-Proto: https\r\n' + extra + '\r\n').encode()
            with self.assertRaisesRegex(ValueError, 'unapproved-public-origin'):
                m.request(raw, m.configured_origins(9222, 'https://clark.home'))
        with self.assertRaisesRegex(ValueError, 'unapproved-public-origin'):
            m.public_document(b'{}', 'attacker.example', 'https', 9223, ORIGINS)

    def test_only_explicit_origins_extend_fixed_loopback_defaults(self):
        defaults = m.configured_origins(9222, '')
        self.assertEqual(defaults, {'http://127.0.0.1:9222', 'http://localhost:9222', 'http://[::1]:9222'})
        self.assertNotIn('https://clark.home', defaults)
        approved = m.configured_origins(9222, 'https://clark.home,https://clark.local')
        raw = b'GET /json/version HTTP/1.1\r\nHost: clark.home\r\nX-Forwarded-Proto: https\r\n\r\n'
        self.assertEqual(m.request(raw, approved)[2:4], ('clark.home', 'https'))
        with self.assertRaisesRegex(ValueError, 'unapproved-public-origin'):
            m.request(raw.replace(b'https', b'http'), approved)
        for extra in ('https://*.example', 'https://user:secret@clark.home', 'https://clark.home/path', 'https://clark.home#fragment', 'https://clark.home,', 'https://clark.home\n'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                m.configured_origins(9222, extra)


class Relay(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_hostname_host_rewrite_and_all_writers_close(self):
        body = json.dumps({'webSocketDebuggerUrl': 'ws://127.0.0.1:9223/devtools/browser/abc'}).encode()
        upstream, client = Writer(), Writer()
        backend = stream(b'HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
        reader = stream(b'GET /json/version HTTP/1.1\r\nHost: clark.home\r\nX-Forwarded-Proto: https\r\n\r\n')
        transport = m.Transport(9223, ORIGINS)
        with patch.object(asyncio, 'open_connection', return_value=(backend, upstream)) as connect:
            await transport.handle(reader, client)
        self.assertEqual(connect.call_args.args, ('127.0.0.1', 9223))
        self.assertIn(b'host: 127.0.0.1:9223\r\n', upstream.data)
        self.assertIn(b'wss://clark.home/devtools/browser/abc', client.data)
        self.assertTrue(upstream.closed and client.closed)
        self.assertFalse(transport.tasks)

    async def test_websocket_raw_bytes_both_directions_and_no_origin_wildcard(self):
        client, upstream = Writer(), Writer()
        reader = stream(b'GET /devtools/browser/abc HTTP/1.1\r\nHost: clark.home\r\nX-Forwarded-Proto: https\r\nOrigin: https://clark.home\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\nclient\x00frame')
        backend = stream(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\nserver\x00frame')
        with patch.object(asyncio, 'open_connection', return_value=(backend, upstream)):
            await m.Transport(9223, ORIGINS).handle(reader, client)
        self.assertTrue(bytes(upstream.data).endswith(b'client\x00frame'))
        self.assertTrue(bytes(client.data).endswith(b'server\x00frame'))
        self.assertNotIn(b'origin:', bytes(upstream.data))
        self.assertTrue(client.closed and upstream.closed)

    async def test_invalid_request_never_connects_backend(self):
        requests = [b'GET //evil HTTP/1.1\r\nHost: clark.home\r\n\r\n', b'GET /devtools/browser/abc HTTP/1.1\r\nHost: attacker.example\r\nOrigin: https://attacker.example\r\nX-Forwarded-Proto: https\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n']
        for raw in requests:
            client = Writer()
            with self.subTest(raw=raw), patch.object(asyncio, 'open_connection') as connect:
                await m.Transport(9223, ORIGINS).handle(stream(raw), client)
            connect.assert_not_called()
            self.assertTrue(client.closed)
            self.assertIn(b'400 Bad Request', client.data)

    async def test_connection_limit_and_owned_task_cancellation(self):
        transport = m.Transport(9223, ORIGINS)
        tasks = [asyncio.create_task(asyncio.sleep(100)) for _ in range(32)]
        transport.tasks.update(tasks)
        client = Writer()
        with patch.object(asyncio, 'open_connection') as connect:
            await transport.handle(stream(b''), client)
        connect.assert_not_called()
        self.assertTrue(client.closed)
        await transport.close()
        self.assertTrue(all(t.cancelled() for t in tasks))

    async def test_startup_failure_terminates_only_owned_child(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        class Process:
            pid = 424242
            returncode = None
            terminated = False
            def terminate(self):
                self.terminated = True
            def kill(self):
                raise AssertionError('kill not needed after successful terminate')
            async def wait(self):
                self.returncode = 0
                return 0
        child = Process()
        options = SimpleNamespace(port=9222, origins=ORIGINS, data_dir='/tmp/unused-offline-model')
        loop = asyncio.get_running_loop()
        with patch.object(os, 'killpg') as killgroup, patch.object(Path, 'mkdir'), patch.object(loop, 'add_signal_handler'), patch.object(loop, 'remove_signal_handler'), patch.object(asyncio, 'create_subprocess_exec', return_value=child), patch.object(asyncio, 'open_connection', side_effect=OSError), patch.object(asyncio, 'sleep', new_callable=AsyncMock):
            with self.assertRaises(TimeoutError):
                await m.serve(options, ['/not-executed/browser'], {})
        self.assertEqual(killgroup.call_args_list[0].args, (child.pid, __import__('signal').SIGTERM))
        self.assertEqual(killgroup.call_args_list[-1].args, (child.pid, __import__('signal').SIGKILL))

    async def test_ready_adapter_binds_existing_public_port_and_closes(self):
        from types import SimpleNamespace
        class Process:
            pid = 424242
            returncode = None
            async def wait(self):
                self.returncode = 0
                return 0
        class Server:
            closed = False
            def close(self):
                self.closed = True
            async def wait_closed(self):
                pass
        child, server, ready = Process(), Server(), Writer()
        options = SimpleNamespace(port=9222, origins=ORIGINS, data_dir='/tmp/unused-offline-model')
        loop = asyncio.get_running_loop()
        with patch.object(os, 'killpg') as killgroup, patch.object(Path, 'mkdir'), patch.object(loop, 'add_signal_handler'), patch.object(loop, 'remove_signal_handler'), patch.object(asyncio, 'create_subprocess_exec', return_value=child), patch.object(asyncio, 'open_connection', return_value=(None, ready)), patch.object(asyncio, 'start_server', return_value=server) as listen:
            await m.serve(options, ['/not-executed/browser'], {})
        self.assertEqual(listen.call_args.args[1:], ('0.0.0.0', 9222))
        self.assertTrue(server.closed and ready.closed)
        self.assertEqual(killgroup.call_args_list[0].args, (child.pid, __import__('signal').SIGTERM))
        self.assertEqual(killgroup.call_args_list[-1].args, (child.pid, __import__('signal').SIGKILL))

    async def test_error_drain_and_close_wait_are_bounded(self):
        class Stalled(Writer):
            async def drain(self):
                await asyncio.Future()
            async def wait_closed(self):
                await asyncio.Future()
        original = asyncio.wait_for
        observed = []
        async def quick(awaitable, timeout):
            observed.append(timeout)
            return await original(awaitable, 0.001 if timeout in (2, 5) else timeout)
        client = Stalled()
        with patch.object(asyncio, 'wait_for', side_effect=quick):
            await m.Transport(9223, ORIGINS).handle(stream(b'GET //invalid HTTP/1.1\r\nHost: clark.home\r\n\r\n'), client)
        self.assertTrue(client.closed)
        self.assertIn(5, observed)
        self.assertIn(2, observed)

    async def test_signal_setup_failure_still_stops_original_group(self):
        from types import SimpleNamespace
        class Process:
            pid = 424242
            returncode = None
            async def wait(self):
                self.returncode = 0
                return 0
        child = Process()
        loop = asyncio.get_running_loop()
        with patch.object(Path, 'mkdir'), patch.object(loop, 'add_signal_handler', side_effect=RuntimeError('signal-setup')), patch.object(os, 'killpg') as killgroup, patch.object(asyncio, 'create_subprocess_exec', return_value=child) as create:
            with self.assertRaisesRegex(RuntimeError, 'signal-setup'):
                await m.serve(SimpleNamespace(port=9222, origins=ORIGINS, data_dir='/tmp/not-created'), ['/not-executed/browser'], {})
        self.assertTrue(create.call_args.kwargs['start_new_session'])
        self.assertEqual(killgroup.call_args_list[0].args, (child.pid, __import__('signal').SIGTERM))
        self.assertEqual(killgroup.call_args_list[-1].args, (child.pid, __import__('signal').SIGKILL))

    async def test_upgrade_drain_timeout_releases_owned_client(self):
        class Stalled(Writer):
            async def drain(self):
                await asyncio.Future()
        original = asyncio.wait_for
        observed = []
        async def quick(awaitable, timeout):
            observed.append(timeout)
            return await original(awaitable, 0.001 if timeout == 5 else timeout)
        client, upstream = Stalled(), Writer()
        reader = stream(b'GET /devtools/browser/abc HTTP/1.1\r\nHost: clark.home\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n')
        backend = stream(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n')
        transport = m.Transport(9223, ORIGINS)
        with patch.object(asyncio, 'wait_for', side_effect=quick), patch.object(asyncio, 'open_connection', return_value=(backend, upstream)):
            await transport.handle(reader, client)
        self.assertIn(5, observed)
        self.assertTrue(client.closed and upstream.closed)
        self.assertFalse(transport.tasks)


if __name__ == '__main__':
    unittest.main()
