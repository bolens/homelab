"""Deterministic public ioctl payloads, NOT real filesystem capability proof."""
from contextlib import contextmanager
import struct

import publication_filesystem_binding as filesystem


@contextmanager
def kernel_bytes():
    real = filesystem.fcntl.ioctl
    def fixture(fd, request, buffer, mutate):
        if type(fd) is not int or mutate is not True:
            raise AssertionError('Unexpected kernel fixture interface')
        if request == filesystem.FS_INFO and len(buffer) == 1024:
            buffer[16:32] = bytes(range(1, 17))
        elif request == filesystem.SUBVOL_INFO and len(buffer) == 504:
            struct.pack_into('<Q', buffer, 0, 5)
            buffer[296:312] = bytes(range(17, 33))
        else:
            raise AssertionError('Unexpected kernel ioctl fixture request')
        return 0
    filesystem.fcntl.ioctl = fixture
    try:
        yield
    finally:
        filesystem.fcntl.ioctl = real
