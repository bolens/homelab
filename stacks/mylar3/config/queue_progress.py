"""Format queue progress without assuming every provider exposes a total size."""
import os


def progress(row, directory):
    if row['status'] == 'Completed':
        return '100%'
    if row['status'] == 'Queued':
        return '0%'
    if row['status'] not in ('Downloading', 'Incomplete'):
        return '--'
    try:
        total = int(row['remote_filesize'])
    except (TypeError, ValueError):
        total = 0
    if total <= 0:
        return 'Unknown'
    # These providers write to tmp_filename until their download finishes.
    if row['link_type'] in ('GC-Mega', 'GC-Pixel', 'DDL-Ext'):
        path = row['tmp_filename']
    else:
        path = os.path.join(directory, row['filename']) if row['filename'] and directory else None
        if row['tmp_filename'] and os.path.isfile(row['tmp_filename']):
            path = row['tmp_filename']
        elif path and os.path.isfile(path + '.part'):
            path += '.part'
    try:
        size = os.path.getsize(path) if path else 0
    except OSError:
        size = 0
    return '%d%%' % min(100, max(0, size * 100 // total))
