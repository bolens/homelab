"""Install the modern service in Mylar's namespace without selecting its backend."""
from pathlib import Path
import sys

MODULES = ('tagger_runtime.py','tagger_metadata.py','tagger_cli.py','tagger_archive.py',
           'tagger_adapter.py','tagger_lookup.py','tagger_service.py')


def main(directory):
    root = Path(directory)
    for name in MODULES:
        (root/name).write_text(Path(__file__).with_name(name).read_text())


if __name__ == '__main__':
    main(sys.argv[1])
