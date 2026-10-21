#!/usr/bin/env python3
# Copyright 2026 Clark Labs Inc. SPDX-License-Identifier: MIT
# Adapted from bin/clarkserve at 96f79abdc7b8611a1dafd23a2d16c5f20d99ba4e.
# Keep Chromium private; expose only CDP discovery and raw WebSocket transport.
import argparse
import asyncio
import contextlib
import ipaddress
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
import re
import signal
import sys
from urllib.parse import urlsplit

HEADER = 16384
BODY = 1048576
PATH = re.compile(r'/devtools/(?:browser|page)/[A-Za-z0-9_-]{1,128}')
DISCOVERY = {'/json', '/json/', '/json/list', '/json/list/', '/json/version', '/json/version/'}
LOG = logging.getLogger('clarkserve')


def authority(value):
    if not value or len(value) > 300 or any(c in value for c in '/\\@?# \t\r\n'):
        raise ValueError('invalid-host')
    try:
        parsed = urlsplit('//' + value)
        port = parsed.port
    except ValueError:
        raise ValueError('invalid-host') from None
    host = parsed.hostname
    if not host or parsed.username or parsed.password:
        raise ValueError('invalid-host')
    if value.endswith(':') or port is not None and not 1 <= port <= 65535:
        raise ValueError('invalid-port')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r'(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host):
            raise ValueError('invalid-host') from None
        if any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-') for label in host.split('.')):
            raise ValueError('invalid-host')
    return value


def configured_origins(port, additional=None):
    origins = {f'http://localhost:{port}', f'http://127.0.0.1:{port}', f'http://[::1]:{port}'}
    if additional is None:
        additional = os.environ.get('CLARK_CDP_ORIGINS', '')
    if len(additional) > 4096:
        raise ValueError('origin-config-bound')
    extras = additional.split(',') if additional else []
    if len(extras) > 16:
        raise ValueError('origin-config-count')
    for value in extras:
        url = urlsplit(value)
        if url.scheme not in {'http', 'https'} or url.path or url.query or url.fragment or url.username or url.password:
            raise ValueError('invalid-configured-origin')
        host = authority(url.netloc)
        if value != url.scheme + '://' + host:
            raise ValueError('invalid-configured-origin')
        origins.add(value)
    return frozenset(origins)


def request(raw, origins):
    if len(raw) > HEADER or not raw.endswith(b'\r\n\r\n'):
        raise ValueError('header-bound')
    lines = raw[:-4].decode('ascii').split('\r\n')
    if len(lines) > 65:
        raise ValueError('header-count')
    first = lines.pop(0).split(' ')
    if len(first) != 3 or first[0] != 'GET' or first[2] != 'HTTP/1.1':
        raise ValueError('request-line')
    path = first[1]
    if path not in DISCOVERY and not PATH.fullmatch(path):
        raise ValueError('unsupported-target')
    headers = {}
    for line in lines:
        key, colon, value = line.partition(':')
        if not colon or not re.fullmatch(r'[A-Za-z0-9-]+', key) or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('header-shape')
        key = key.lower()
        if key in headers:
            raise ValueError('duplicate-header')
        headers[key] = value.strip()
    if 'content-length' in headers or 'transfer-encoding' in headers:
        raise ValueError('request-body')
    host = authority(headers.get('host', ''))
    scheme = headers.get('x-forwarded-proto', 'http')
    if scheme not in {'http', 'https'}:
        raise ValueError('invalid-scheme')
    public_origin = scheme + '://' + host
    if public_origin not in origins:
        raise ValueError('unapproved-public-origin')
    if 'origin' in headers and headers['origin'] != public_origin:
        raise ValueError('foreign-origin')
    websocket = path not in DISCOVERY
    if websocket and (headers.get('upgrade', '').lower() != 'websocket' or 'upgrade' not in {x.strip().lower() for x in headers.get('connection', '').split(',')}):
        raise ValueError('websocket-upgrade')
    if not websocket and 'upgrade' in headers:
        raise ValueError('unexpected-upgrade')
    return path, headers, host, scheme, websocket


def public_document(raw, host, scheme, backend_port, origins):
    if len(raw) > BODY:
        raise ValueError('body-bound')
    authority(host)
    if scheme + '://' + host not in origins:
        raise ValueError('unapproved-public-origin')
    if scheme not in {'http', 'https'}:
        raise ValueError('invalid-scheme')
    value = json.loads(raw)
    rows = value if isinstance(value, list) else [value]
    if len(rows) > 256 or not all(isinstance(row, dict) for row in rows):
        raise ValueError('discovery-shape')
    for row in rows:
        if 'webSocketDebuggerUrl' in row:
            if not isinstance(row['webSocketDebuggerUrl'], str):
                raise ValueError('backend-websocket-shape')
            url = urlsplit(row['webSocketDebuggerUrl'])
            if url.scheme != 'ws' or url.hostname != '127.0.0.1' or url.port != backend_port or not PATH.fullmatch(url.path) or url.query or url.fragment or url.username or url.password:
                raise ValueError('backend-websocket-origin')
            row['webSocketDebuggerUrl'] = ('wss' if scheme == 'https' else 'ws') + '://' + host + url.path
    return json.dumps(value, separators=(',', ':')).encode()


async def close_writer(writer):
    writer.close()
    with contextlib.suppress(OSError, asyncio.TimeoutError):
        await asyncio.wait_for(writer.wait_closed(), 2)


async def pump(reader, writer):
    while True:
        block = await asyncio.wait_for(reader.read(65536), 300)
        if not block:
            return
        writer.write(block)
        await asyncio.wait_for(writer.drain(), 30)


class Transport:
    def __init__(self, backend_port, origins=None):
        self.backend_port = backend_port
        self.origins = configured_origins(backend_port - 1) if origins is None else origins
        self.tasks = set()

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        if len(self.tasks) >= 32:
            await close_writer(writer)
            return
        self.tasks.add(task)
        upstream = None
        upgraded = False
        try:
            raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 10)
            path, headers, host, scheme, websocket= request(raw, self.origins)
            backend, upstream = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', self.backend_port, limit=HEADER), 5)
            # Origin is validated above; Chrome's loopback listener sees its own Host.
            forwarded = {k: v for k, v in headers.items() if k not in {'host', 'origin', 'x-forwarded-proto', 'connection'}}
            forwarded['host'] = '127.0.0.1:' + str(self.backend_port)
            forwarded['connection'] = 'Upgrade' if websocket else 'close'
            upstream.write(('GET ' + path + ' HTTP/1.1\r\n' + ''.join(k + ': ' + v + '\r\n' for k, v in forwarded.items()) + '\r\n').encode('ascii'))
            await asyncio.wait_for(upstream.drain(), 5)
            response = await asyncio.wait_for(backend.readuntil(b'\r\n\r\n'), 10)
            if len(response) > HEADER:
                raise ValueError('backend-header-bound')
            if websocket:
                if not response.startswith(b'HTTP/1.1 101 '):
                    raise ValueError('backend-upgrade')
                writer.write(response)
                await asyncio.wait_for(writer.drain(), 5)
                upgraded = True
                pipes = [asyncio.create_task(pump(reader, upstream)), asyncio.create_task(pump(backend, writer))]
                try:
                    done, _ = await asyncio.wait(pipes, return_when=asyncio.FIRST_COMPLETED)
                    for finished in done:
                        finished.result()
                finally:
                    for pipe in pipes:
                        pipe.cancel()
                    await asyncio.gather(*pipes, return_exceptions=True)
            else:
                if not response.startswith(b'HTTP/1.1 200 '):
                    raise ValueError('backend-discovery-status')
                fields = {}
                for line in response[:-4].decode('ascii').split('\r\n')[1:]:
                    key, colon, val = line.partition(':')
                    if not colon or key.lower() in fields:
                        raise ValueError('backend-header-shape')
                    fields[key.lower()] = val.strip()
                if 'transfer-encoding' in fields or 'content-encoding' in fields or not fields.get('content-length', '').isdigit():
                    raise ValueError('backend-framing')
                size = int(fields['content-length'])
                if size > BODY:
                    raise ValueError('body-bound')
                body = public_document(await asyncio.wait_for(backend.readexactly(size), 10), host, scheme, self.backend_port, self.origins)
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
                await asyncio.wait_for(writer.drain(), 5)
        except (ValueError, UnicodeError, asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, OSError):
            if not upgraded:
                writer.write(b'HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
                with contextlib.suppress(OSError, asyncio.TimeoutError):
                    await asyncio.wait_for(writer.drain(), 5)
        finally:
            if upstream is not None:
                await close_writer(upstream)
            await close_writer(writer)
            self.tasks.discard(task)

    async def close(self):
        for task in tuple(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


def launch_options(argv):
    if version('clark-browser') != '0.2.1':
        raise ValueError('review-Clark-adapter-for-package-version')
    from clarkbrowser.browser import _cohere_browser_env, _resolve_args
    from clarkbrowser.download import ensure_binary
    from clarkbrowser.hygiene import apply_launch_hygiene
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=9222)
    parser.add_argument('--headless', choices=('true', 'false'), default='true')
    parser.add_argument('--data-dir', default='/tmp/clarkserve')
    options, extra = parser.parse_known_args(argv)
    if not 1 <= options.port < 65535 or any(x.startswith(('--remote-', '--user-data-dir', '--proxy-')) for x in extra):
        raise ValueError('unsupported-launch-override')
    if os.environ.get('CLARK_PROXY_USERNAME') or os.environ.get('CLARK_PROXY_PASSWORD'):
        raise ValueError('authenticated-proxy-not-supported')
    options.origins = configured_origins(options.port)
    proxy = os.environ.get('CLARK_PROXY_SERVER')
    if proxy:
        parsed = urlsplit(proxy)
        if parsed.scheme not in {'http', 'https', 'socks5'} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment or any(c.isspace() for c in proxy):
            raise ValueError('invalid-proxy-server')
        authority(parsed.netloc)
        extra.append('--proxy-server=' + proxy)
    chrome = _resolve_args(extra, True, None, None, None, None, None, options.headless == 'true')
    chrome += ['--remote-debugging-port=' + str(options.port + 1), '--remote-debugging-address=127.0.0.1', '--user-data-dir=' + options.data_dir, '--no-first-run', '--no-default-browser-check']
    if options.headless == 'true':
        chrome.append('--headless=new')
    # Account for public adapter exposure when applying the upstream strict policy.
    apply_launch_hygiene(LOG, chrome + ['--remote-debugging-address=0.0.0.0'], {})
    env = _cohere_browser_env(chrome, {}).get('env', os.environ.copy())
    return options, [ensure_binary(), *chrome], env


async def serve(options, command, env):
    Path(options.data_dir).mkdir(mode=0o700, parents=True, exist_ok=True)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    handlers = []
    transport = Transport(options.port + 1, options.origins)
    server = None
    waiter = None
    stopped = None
    proc = await asyncio.create_subprocess_exec(*command, env=env, start_new_session=True)
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
            handlers.append(sig)
        for _ in range(100):
            if stop.is_set():
                return
            if proc.returncode is not None:
                raise RuntimeError('chromium-startup-exit')
            try:
                _, ready = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', options.port + 1), 0.2)
                await close_writer(ready)
                break
            except (OSError, asyncio.TimeoutError):
                await asyncio.sleep(0.1)
        else:
            raise TimeoutError('chromium-readiness')
        server = await asyncio.start_server(transport.handle, '0.0.0.0', options.port, limit=HEADER)
        waiter = asyncio.create_task(proc.wait())
        stopped = asyncio.create_task(stop.wait())
        await asyncio.wait([waiter, stopped], return_when=asyncio.FIRST_COMPLETED)
        if proc.returncode not in (None, 0):
            raise RuntimeError('chromium-exit')
    finally:
        primary = sys.exc_info()[1]
        cleanup = None
        if server is not None:
            try:
                server.close()
                await asyncio.wait_for(server.wait_closed(), 2)
            except Exception as error:
                cleanup = error
        try:
            await transport.close()
        except Exception as error:
            cleanup = cleanup or error
        # The session was created above for this original Chromium child only.
        # Signal its group even if the leader exited while descendants remain.
        try:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(proc.wait(), 5)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
                await asyncio.wait_for(proc.wait(), 5)
            # Do not abandon a residual process in the original owned session.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
        except Exception as error:
            cleanup = cleanup or error
        for task in (waiter, stopped):
            if task is not None:
                task.cancel()
        await asyncio.gather(*[task for task in (waiter, stopped) if task is not None], return_exceptions=True)
        for sig in handlers:
            try:
                loop.remove_signal_handler(sig)
            except Exception as error:
                cleanup = cleanup or error
        if cleanup is not None:
            if primary is None:
                raise cleanup
            LOG.error('launcher-cleanup-refused; original failure retained')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    settings, command, environment = launch_options(sys.argv[1:])
    asyncio.run(serve(settings, command, environment))
