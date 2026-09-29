"""Private stdin/stdout discovery protocol, executed only in the isolated curl venv."""
import base64
from http.cookiejar import Cookie, CookieJar
import json
import sys

MAX_BODY = 8 * 1024 * 1024


def fetch(value):
    from curl_cffi import requests
    from curl_cffi.curl import CURL_WRITEFUNC_ERROR
    body = bytearray()
    exceeded = False
    def receive(chunk):
        nonlocal exceeded
        if len(body) + len(chunk) > MAX_BODY:
            exceeded = True
            return CURL_WRITEFUNC_ERROR
        body.extend(chunk)
        return len(chunk)
    jar = CookieJar()
    for cookie in value['cookies']: jar.set_cookie(Cookie(**cookie))
    try:
        with requests.Session(cookies=jar, trust_env=False, retry=0, impersonate='chrome',
                              max_redirects=30) as session:
            response = session.request(value['method'], value['url'], headers=value['headers'],
                data=base64.b64decode(value['body'], validate=True),
                timeout=tuple(value['timeout']), allow_redirects=value['allow_redirects'],
                proxies=value['proxies'], verify=value['verify'], cert=value['cert'],
                content_callback=receive, stream=False)
            try:
                cookies = [dict(version=c.version, name=c.name, value=c.value, port=c.port,
                    port_specified=c.port_specified, domain=c.domain, domain_specified=c.domain_specified,
                    domain_initial_dot=c.domain_initial_dot, path=c.path, path_specified=c.path_specified,
                    secure=c.secure, expires=c.expires, discard=c.discard, comment=c.comment,
                    comment_url=c.comment_url, rest=c._rest, rfc2109=c.rfc2109) for c in session.cookies.jar]
                return dict(state='ok', status=response.status_code, url=response.url,
                            headers=dict(response.headers), cookies=cookies,
                            body=base64.b64encode(body).decode())
            finally:
                response.close()
    except requests.exceptions.Timeout: return {'state':'timeout'}
    except requests.exceptions.SSLError: return {'state':'tls'}
    except requests.exceptions.TooManyRedirects: return {'state':'redirect'}
    except requests.exceptions.ConnectionError: return {'state':'connection'}
    except requests.exceptions.RequestException:
        return {'state':'body_limit' if exceeded else 'failed'}


if __name__ == '__main__':
    try:
        raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024: raise ValueError('Request too large')
        result = fetch(json.loads(raw))
    except Exception:
        result = {'state':'failed'}
    sys.stdout.write(json.dumps(result))
