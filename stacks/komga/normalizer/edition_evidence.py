"""Bounded image-header evidence for editions that cannot be inferred by title."""
import struct
import zipfile
from pathlib import Path


def dimensions(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw) >= 24:
        return struct.unpack('>II', raw[16:24])
    if raw.startswith(b'\xff\xd8'):
        offset = 2
        while offset + 4 <= len(raw):
            if raw[offset] != 255:
                return None
            while offset < len(raw) and raw[offset] == 255:
                offset += 1
            if offset >= len(raw):
                break
            marker = raw[offset]
            offset += 1
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            if offset + 2 > len(raw):
                break
            size = int.from_bytes(raw[offset:offset + 2], 'big')
            if size < 2:
                return None
            if marker in (0xC0, 0xC1, 0xC2) and offset + 7 <= len(raw):
                height, width = struct.unpack('>HH', raw[offset + 3:offset + 7])
                return width, height
            offset += size
    return None


def landscape(path):
    """Three landscape interiors are conflicting print-edition evidence, not proof of digital identity."""
    with zipfile.ZipFile(path) as archive:
        entries = sorted((r for r in archive.infolist() if Path(r.filename).suffix.lower() in ('.png', '.jpg', '.jpeg')),
                         key=lambda r: r.filename)
        if len(entries) < 4:
            return False
        sizes = []
        for entry in entries[1:4]:
            with archive.open(entry) as stream:
                sizes.append(dimensions(stream.read(65536)))
        return all(size and size[0] > size[1] * 1.15 for size in sizes)
