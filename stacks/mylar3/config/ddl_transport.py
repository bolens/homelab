"""Opt-in bounded discovery; archive transfers retain their requests owner."""
import base64
from functools import wraps
import json as jsonlib
import os
from pathlib import Path
import subprocess

import requests

PYTHON = Path('/opt/ddl-transport/bin/python')
WORKER = Path(__file__).with_name('ddl_transport_worker.py')
CHOICES = ('requests', 'curl')
MAX_BODY = 8 * 1024 * 1024


def choice(value):
    if type(value) is not str or value not in CHOICES:
        raise ValueError('Choose Requests or Curl for DDL discovery.')
    return value


def status():
    return {'curl_available': PYTHON.is_file() and WORKER.is_file(),
            'message': 'Curl affects provider discovery only. Archive downloads continue using Requests.'}


def validate_update(value):
    selected = choice(value)
    if selected == 'curl' and not status()['curl_available']:
        raise ValueError('Curl discovery is unavailable in this image.')
    return selected


def cookies_out(jar):
    return [dict(version=c.version, name=c.name, value=c.value, port=c.port,
                 port_specified=c.port_specified, domain=c.domain,
                 domain_specified=c.domain_specified, domain_initial_dot=c.domain_initial_dot,
                 path=c.path, path_specified=c.path_specified, secure=c.secure,
                 expires=c.expires, discard=c.discard, comment=c.comment,
                 comment_url=c.comment_url, rest=c._rest, rfc2109=c.rfc2109) for c in jar]


def cookies_in(values):
    from http.cookiejar import Cookie
    jar = requests.cookies.RequestsCookieJar()
    for value in values:
        jar.set_cookie(Cookie(**value))
    return jar


class CurlSession(requests.Session):
    """One bounded child per page; isolated native dependencies and no retry layer."""
    def request(self, method, url, params=None, data=None, headers=None, cookies=None,
                files=None, auth=None, timeout=None, allow_redirects=True, proxies=None,
                hooks=None, stream=None, verify=None, cert=None, json=None):
        if files or hooks:
            raise requests.RequestException('Unsupported discovery request mode')
        prepared = self.prepare_request(requests.Request(method, url, headers=headers,
            data=data, params=params, auth=auth, cookies=cookies, json=json))
        options = self.merge_environment_settings(prepared.url, proxies or {}, stream, verify, cert)
        wait = timeout if timeout is not None else (30, 30)
        values = wait if isinstance(wait, (tuple, list)) else (wait, wait)
        if len(values) != 2 or any(type(v) not in (int, float) or not 0 < v <= 30 for v in values):
            raise requests.RequestException('Discovery timeout must be between 0 and 30 seconds')
        body = prepared.body or b''
        if isinstance(body, str): body = body.encode()
        if not isinstance(body, bytes) or len(body) > 1024 * 1024:
            raise requests.RequestException('Discovery request body is unsupported or too large')
        # The scoped jar owns redirect cookie policy.
        request_headers = {k:v for k,v in prepared.headers.items() if k.lower() != 'cookie'}
        payload = dict(method=prepared.method, url=prepared.url, headers=request_headers,
            body=base64.b64encode(body).decode(), cookies=cookies_out(prepared._cookies),
            timeout=list(values), allow_redirects=bool(allow_redirects),
            proxies=options['proxies'], verify=options['verify'], cert=options['cert'])
        encoded = jsonlib.dumps(payload).encode()
        if len(encoded) > 2 * 1024 * 1024:
            raise requests.RequestException('Discovery request exceeds its limit')
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith('PYTHON')}
        env['PYTHONNOUSERSITE'] = '1'
        try:
            child = subprocess.run([str(PYTHON), str(WORKER)], input=encoded,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=sum(values)+5,
                env=env, check=False)
            if child.returncode or len(child.stdout) > 12 * 1024 * 1024:
                raise ValueError('Invalid discovery worker result')
            result = jsonlib.loads(child.stdout)
        except subprocess.TimeoutExpired:
            raise requests.Timeout('DDL discovery timed out') from None
        except (OSError, ValueError):
            raise requests.ConnectionError('DDL discovery worker unavailable') from None
        try:
            state = result['state']
            if state not in ('ok', 'timeout', 'tls', 'redirect', 'connection', 'body_limit', 'failed'):
                raise ValueError('Invalid worker state')
            if state == 'ok':
                content = base64.b64decode(result['body'], validate=True)
                if len(content) > MAX_BODY or type(result['status']) is not int or not 100 <= result['status'] <= 599:
                    raise ValueError('Invalid worker response')
                response = requests.Response()
                response.status_code = result['status']
                response.url = result['url']
                response.headers = requests.structures.CaseInsensitiveDict(result['headers'])
                response._content = content
                response._content_consumed = True
                response.encoding = requests.utils.get_encoding_from_headers(response.headers)
                response.request = prepared
                response.cookies = cookies_in(result['cookies'])
                self.cookies = response.cookies.copy()
                return response
        except (KeyError, TypeError, ValueError):
            raise requests.ConnectionError('Invalid DDL discovery worker response') from None
        error = {'timeout': requests.Timeout, 'tls': requests.exceptions.SSLError,
                 'redirect': requests.TooManyRedirects, 'connection': requests.ConnectionError}.get(state, requests.RequestException)
        raise error('DDL discovery ' + state) from None



class DiscoveryRequests(requests.Session):
    def __init__(self):
        super().__init__()
        self._responses = []

    def request(self, *args, **kwargs):
        kwargs.setdefault('timeout', (30, 30))
        response = super().request(*args, **kwargs)
        self._responses.append(response)
        return response

    def close(self):
        for response in self._responses:
            response.close()
        self._responses.clear()
        super().close()


def session(selected):
    try: selected = validate_update(selected)
    except ValueError:
        raise requests.RequestException('DDL discovery backend unavailable or invalid') from None
    return DiscoveryRequests() if selected == 'requests' else CurlSession()


def discovery(function):
    """Capture preference at the outer operation; nested calls retain that owner."""
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        import mylar
        depth = getattr(self, '_discovery_depth', 0)
        if not depth:
            current = session(getattr(mylar.CONFIG, 'DDL_DISCOVERY_BACKEND', 'requests'))
            current.cookies.update(self.session.cookies)
            current.proxies.update(self.session.proxies)
            self._discovery_session = current
        self._discovery_depth = depth + 1
        try:
            return function(self, *args, **kwargs)
        finally:
            self._discovery_depth -= 1
            if not self._discovery_depth:
                self.session.cookies = self._discovery_session.cookies.copy()
                self._discovery_session.close()
    return wrapped
