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
    size = received_bytes(row, directory)
    return '%d%%' % min(100, max(0, (size or 0) * 100 // total))


def received_bytes(row, directory):
    """Resolve provider basenames against DDL_LOCATION, never the process cwd.

    Pixel stores a basename; Mega/external providers may store an absolute path.
    Prefer temporary bytes, then the published filename during rename/handoff.
    A missing observation is distinct from an empty file and is not a failure.
    """
    paths = []
    for value in (row['tmp_filename'], row['filename']):
        if not value:
            continue
        if not os.path.isabs(value):
            if not directory:
                continue
            value = os.path.join(directory, value)
        paths.extend((value + '.part', value))
    for path in paths:
        try:
            if os.path.isfile(path):
                return os.stat(path).st_size
        except OSError:
            # Download publication/post-processing can move a file mid-poll.
            continue
    return None
