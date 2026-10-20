"""Finite stdin-only HTTP helper for original disposable bootstrap roles.

Executed by the owning producer in its exact native container. No URL, key or
response body is logged. Komga contracts are from tag 1.28.1 (not v1.28.1):
https://github.com/gotson/komga/tree/1.28.1/komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest
"""
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request

LIMIT = 8 * 1024**2


class Held(ValueError):
    pass


def need(value, reason):
    if not value:
        raise Held(reason)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def decode(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'duplicate-field')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs)


def identifier(value):
    need(type(value) is str and re.fullmatch('[A-Za-z0-9_-]{1,128}', value), 'identifier')
    return value


def request(value):
    need(type(value) is dict and set(value) == {'kind', 'base', 'key', 'operation', 'arguments', 'seconds'}, 'request-schema')
    need(type(value['seconds']) is int and 1 <= value['seconds'] <= 30, 'timeout')
    base = value['base']; parsed = urllib.parse.urlsplit(base)
    need(parsed.scheme == 'http' and parsed.hostname and parsed.port and not parsed.username
         and not parsed.password and not parsed.query and not parsed.fragment
         and '..' not in parsed.path.split('/') and '\\' not in base, 'origin')
    need(type(value['key']) is str and 1 <= len(value['key']) <= 256
         and not any(c in value['key'] for c in '\r\n'), 'private-key')
    op, args = value['operation'], value['arguments']
    need(type(args) is dict, 'arguments')
    binary = False
    if value['kind'] == 'native':
        need(parsed.hostname == '127.0.0.1' and len(value['key']) == 32, 'native-origin-key')
        need(op in ('health', 'status', 'prepare-fresh', 'initialize-bootstrap'), 'native-operation')
        expected = {'epoch', 'backup'} if op == 'prepare-fresh' else {'token'} if op == 'initialize-bootstrap' else set()
        need(set(args) == expected, 'native-arguments')
        form = {'cmd': 'getHealth' if op == 'health' else 'publicationControl', 'apikey': value['key']}
        if op != 'health':
            form['request'] = encode(dict(version=1, action=op, **args)).decode()
        body = urllib.parse.urlencode(form).encode()
        method, route = 'POST', '/api'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    else:
        need(value['kind'] == 'reader' and parsed.path in ('', '/'), 'reader-origin')
        headers = {'X-API-Key': value['key'], 'Content-Type': 'application/json'}
        method, body = 'GET', None
        if op in ('principal', 'libraries', 'books'):
            need(not args, 'reader-arguments')
            route = {'principal': '/api/v2/users/me', 'libraries': '/api/v1/libraries',
                     'books': '/api/v1/books/list?page=0&size=1000'}[op]
            if op == 'books':
                method, body = 'POST', b'{}'
        elif op == 'create-library':
            need(set(args) == {'name', 'root'} and type(args['name']) is str and args['name']
                 and type(args['root']) is str and args['root'].startswith('/')
                 and '..' not in args['root'].split('/'), 'library-arguments')
            method, route = 'POST', '/api/v1/libraries'
            body = encode(dict(args, scanOnStartup=False, scanInterval='DISABLED',
                               emptyTrashAfterScan=False, convertToCbz=False, repairExtensions=False,
                               scanForceModifiedTime=False, scanDirectoryExclusions=[], hashPages=True))
        elif op == 'scan':
            need(set(args) == {'library'}, 'scan-arguments')
            method, route, body = 'POST', '/api/v1/libraries/' + identifier(args['library']) + '/scan', b'{}'
        elif op in ('book', 'pages', 'page', 'set-progress'):
            need(set(args) == ({'book', 'page'} if op == 'page' else {'book'}), 'book-arguments')
            route = '/api/v1/books/' + identifier(args['book'])
            if op == 'pages':
                route += '/pages'
            elif op == 'page':
                need(type(args['page']) is int and 1 <= args['page'] <= 1000, 'page-number')
                route += '/pages/' + str(args['page']) + '?contentNegotiation=false'
                binary = True
            elif op == 'set-progress':
                method, route, body = 'PATCH', route + '/read-progress', encode(dict(page=1, completed=False))
        else:
            raise Held('reader-operation')
    return urllib.request.Request(base.rstrip('/') + route, data=body, method=method, headers=headers), binary


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise Held('redirect-refused')


def perform(value):
    outgoing, binary = request(value)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(outgoing, timeout=value['seconds']) as response:
        need(200 <= response.status < 300, 'http-status')
        raw = response.read(LIMIT + 1)
        need(len(raw) <= LIMIT, 'response-limit')
    if binary:
        need(raw, 'empty-page')
        return dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    return None if not raw else decode(raw)


def main():
    try:
        need(sys.flags.isolated and sys.dont_write_bytecode and os.geteuid()==1000
             and len(sys.argv)==4 and sys.argv[:2]==['-c','--owning-disposable-bootstrap-http-v1']
             and all(re.fullmatch('[0-9a-f]{64}',x) for x in sys.argv[2:]), 'owning-disposable-invocation-required')
        raw = sys.stdin.buffer.read(LIMIT + 1); need(0 < len(raw) <= LIMIT, 'stdin-limit')
        result = perform(decode(raw))
        sys.stdout.buffer.write(encode(dict(result=result)) + b'\n')
        return 0
    except Exception:
        # HTTP exceptions can contain request credentials or remote data.
        sys.stdout.buffer.write(b'{"held":"disposable-bootstrap-http"}\n')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
