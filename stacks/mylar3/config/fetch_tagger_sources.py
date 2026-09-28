"""Build-only: retain exact upstream sources alongside installed package notices."""
import hashlib
import json
from pathlib import Path
import sys
import urllib.request


def fetch(manifest, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for item in json.loads(manifest.read_text()):
        name = item['filename']
        if Path(name).name != name or not item['url'].startswith('https://files.pythonhosted.org/'):
            raise ValueError('Unexpected source archive location')
        with urllib.request.urlopen(item['url'], timeout=30) as response:
            content = response.read(50 * 1024 * 1024 + 1)
        if len(content) > 50 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != item['sha256']:
            raise ValueError('Source archive integrity failure')
        (destination/name).write_bytes(content)
    (destination/'manifest.json').write_bytes(manifest.read_bytes())


if __name__ == '__main__':
    fetch(Path(sys.argv[1]), Path(sys.argv[2]))
