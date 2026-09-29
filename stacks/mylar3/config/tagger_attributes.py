"""Bounded exact preservation of user attributes and file access ACLs."""
import base64
import os

MAX_VALUE = 65536
MAX_TOTAL = 131072


def allowed(name):
    return (type(name) is str and '\0' not in name and len(name.encode()) <= 255
            and (name.startswith('user.') or name in ('system.nfs4_acl', 'system.posix_acl_access')))


def validate(values):
    if type(values) is not dict or len(values) > 64:
        raise ValueError('Invalid attribute manifest')
    total = 0
    for name, encoded in values.items():
        if not allowed(name) or type(encoded) is not str or len(encoded) > 4 * ((MAX_VALUE + 2) // 3):
            raise ValueError('Unsupported attribute')
        value = base64.b64decode(encoded, validate=True)
        if len(value) > MAX_VALUE or base64.b64encode(value).decode('ascii') != encoded:
            raise ValueError('Invalid attribute encoding')
        total += len(value)
    if total > MAX_TOTAL:
        raise ValueError('Oversized attributes')
    return values


def capture(path):
    names = os.listxattr(path, follow_symlinks=False)
    if len(names) > 64 or any(not allowed(name) for name in names):
        raise ValueError('Unsupported file attributes')
    return validate({name:base64.b64encode(os.getxattr(path, name, follow_symlinks=False)).decode('ascii')
                     for name in names})


def apply(path, values):
    validate(values)
    current = capture(path)
    for name in current.keys() - values.keys():
        os.removexattr(path, name, follow_symlinks=False)
    for name, encoded in values.items():
        os.setxattr(path, name, base64.b64decode(encoded), follow_symlinks=False)
    if capture(path) != values:
        raise ValueError('Attributes did not round trip')
