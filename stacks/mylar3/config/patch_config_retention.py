"""Defer configuration-time deletion; it has no owning import/ACK custody."""
from pathlib import Path
import ast
import sys

MARKER = '# homelab-configuration-retention-v1'
PRIOR = "        if self.CLEANUP_CACHE:\n            logger.fdebug('[Cache Cleanup] Cache Cleanup initiated. Will delete items from cache that are no longer needed.')\n            cache_types = ['*.nzb', '*.torrent', '*.html', 'mylar_*', 'html_cache']\n            dir_locations = []\n            dir_locations.append(self.CACHE_DIR)\n            if self.CLEANUP_STRAYS:\n                logger.fdebug('[Cache Cleanup] cbr/cbz cache cleanup option detected. Will remove any detected cbr & cbz files from cache/ddl location.')\n                cache_types.extend(('*.zip', '*.cbr', '*.cbz', '[__*__]'))\n                if all(\n                         [\n                           self.DDL_LOCATION is not None,\n                           self.DESTINATION_DIR is not None,\n                           self.CACHE_DIR != self.DDL_LOCATION,\n                           self.DDL_LOCATION != self.DESTINATION_DIR\n                         ]\n                ):\n                    dir_locations.append(self.DDL_LOCATION)\n            cntr = 0\n            pathlimiter = '**'\n            for y in dir_locations:\n                for x in cache_types:\n                    tmp_path = os.path.join(y, pathlimiter, x)\n                    if x == '[__*__]':\n                        tmp_path = os.path.join(y, pathlimiter, '*' + glob.escape('[__') + '*' + glob.escape('__]'))\n                    for f in glob.glob(tmp_path, recursive=True):\n                        ff = Path(f)\n                        try:\n                            if os.path.isdir(f):\n                                if all([ff.stem != 'html_cache', ff.stem != 'mega']):\n                                    shutil.rmtree(f)\n                            else:\n                                os.remove(f)\n                        except Exception as e:\n                            logger.warn('[ERROR] Unable to remove %s from cache. [%s]' % (f, e))\n                        cntr+=1\n\n            if cntr > 1:\n                logger.fdebug('[Cache Cleanup] Cache Cleanup finished. Cleaned %s items' % cntr)\n            else:\n                logger.fdebug('[Cache Cleanup] Cache Cleanup finished. Nothing to clean!')\n"
REPLACEMENT = """        if self.CLEANUP_CACHE:
            # homelab-configuration-retention-v1
            logger.fdebug('[Cache Cleanup] Deferred; retained sources require owning verified cleanup.')
"""


def patched_source(source):
    if MARKER in source:
        if source.count(MARKER) != 1 or source.count(REPLACEMENT) != 1:
            raise ValueError('Configuration retention boundary changed')
        prior = source.replace(REPLACEMENT, PRIOR, 1)
        if patched_source(prior) != source:
            raise ValueError('Configuration retention placement changed')
        return source
    if source.count(PRIOR) != 1:
        raise ValueError('Expected exact native configuration cleanup boundary')
    source = source.replace(PRIOR, REPLACEMENT, 1)
    ast.parse(source, feature_version=(3, 10))
    return source


def main(directory):
    path = Path(directory) / 'config.py'
    path.write_text(patched_source(path.read_text()))


if __name__ == '__main__':
    main(sys.argv[1])
