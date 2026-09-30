"""Verified PDF reading derivatives; original document remains the preservation master."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import zipfile


class Pending(Exception):
    """A preserved PDF is queued for rendering outside the media writer lock."""


def render_pending(worker):
    task = getattr(worker, 'pdf_pending', None)
    if task is None:
        return
    worker.pdf_pending = None
    worker.pdf_defer = False
    try:
        derivative(worker, task[1])
    except Exception as exc:
        worker.pdf_failures[task[0]] = (time.time(), str(exc))
    finally:
        worker.pdf_defer = True


def policy(config):
    value = config.get('pdf_conversion', {})
    if not isinstance(value, dict) or type(value.get('enabled', False)) is not bool:
        raise ValueError('Invalid PDF conversion policy')
    result = {'enabled': value.get('enabled', False)}
    for key, default, low, high in (('long_edge_pixels', 3200, 512, 6000),
                                   ('max_pages', 1000, 1, 1000)):
        current = value.get(key, default)
        if type(current) is not int or not low <= current <= high:
            raise ValueError('Invalid PDF conversion ' + key)
        result[key] = current
    return result


def run(arguments, timeout=60):
    result = subprocess.run(arguments, capture_output=True, timeout=timeout,
                            env=dict(os.environ, LC_ALL='C'))
    # Parser warnings can describe missing objects/images. Do not publish a
    # seemingly successful render with omitted content or leak document text.
    if result.returncode or result.stderr:
        raise ValueError('PDF inspection/rendering reported an error; original retained')
    return result.stdout.decode('utf-8', errors='replace')


def page_count(source, maximum):
    value = run(['pdfinfo', str(source)])
    if not re.search(r'^Encrypted:\s+no\s*$', value, re.M):
        raise ValueError('Encrypted PDF retained without conversion')
    match = re.search(r'^Pages:\s+(\d+)\s*$', value, re.M)
    if not match or not 0 < int(match[1]) <= maximum:
        raise ValueError('PDF page count exceeds configured limits')
    return int(match[1])


def derivative(worker, source):
    """Return a checked CBZ, retaining a durable PDF independently of imports."""
    from normalize import digest, identity, save, sync_directory
    from PIL import Image
    options = policy(worker.config)
    if not options['enabled']:
        raise ValueError('PDF conversion is disabled')
    source = Path(source)
    if source.is_symlink() or not source.is_file():
        raise ValueError('PDF source is missing or linked')
    before = identity(source)
    limit = worker.config.get('max_expanded_bytes', 2147483648)
    if before[1] > limit:
        raise ValueError('PDF source exceeds configured size limit')
    checksum = digest(source)
    key = hashlib.sha256(json.dumps([checksum, options], sort_keys=True).encode()).hexdigest()
    directory = worker.state / 'pdf-derivatives' / key
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    original, output, receipt = (directory / name for name in ('original.pdf', 'pages.cbz', 'receipt.json'))
    if any(p.is_symlink() for p in (directory, original, output, receipt)):
        raise ValueError('Linked PDF recovery state')
    if not original.exists():
        if shutil.disk_usage(directory).free < before[1] * 2 + 128 * 1024**2:
            raise ValueError('Insufficient PDF recovery storage')
        pending = directory / 'original.pending'
        pending.unlink(missing_ok=True)
        shutil.copyfile(source, pending)
        with pending.open('rb') as stream:
            os.fsync(stream.fileno())
        if digest(pending) != checksum or identity(source) != before:
            raise ValueError('PDF source changed while preserving original')
        os.link(pending, original)
        pending.unlink()
        sync_directory(directory)
    if digest(original) != checksum:
        raise ValueError('Preserved PDF changed; review recovery state')
    if not receipt.exists() and getattr(worker, 'pdf_defer', False):
        failures = getattr(worker, 'pdf_failures', {})
        if key in failures and time.time() - failures[key][0] < 3600:
            raise ValueError(failures[key][1])
        failures.pop(key, None)
        if getattr(worker, 'pdf_pending', None) is None:
            worker.pdf_pending = (key, original)
        raise Pending('PDF saved; waiting for page rendering')
    if receipt.exists():
        record = json.loads(receipt.read_text())
        if (record.get('version') != 1 or record.get('source_sha256') != checksum
                or record.get('options') != options or not output.is_file()
                or digest(output) != record.get('output_sha256')):
            raise ValueError('PDF derivative receipt or content changed')
        # Archive validation is also required on reuse, not just a cache hit.
        if worker.info(output) != record['inventory']:
            raise ValueError('PDF derivative inventory changed')
    else:
        if output.exists():
            # No caller can receive this private output before its receipt commits.
            # After a crash it is safe to regenerate from the verified PDF.
            output.unlink()
        for temporary in directory.glob('render-*'):
            if temporary.is_symlink() or not temporary.is_dir():
                raise ValueError('Unexpected PDF rendering recovery path')
            shutil.rmtree(temporary)
        count = page_count(original, options['max_pages'])
        started = time.monotonic()
        pages, total = [], 0
        with tempfile.TemporaryDirectory(prefix='render-', dir=directory) as temporary:
            temporary = Path(temporary)
            archive_path = temporary / 'pages.cbz'
            with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_STORED) as archive:
                for index in range(1, count + 1):
                    remaining = 600 - (time.monotonic() - started)
                    if remaining <= 0:
                        raise ValueError('PDF conversion exceeded time limit')
                    page_space = 2 * 3 * options['long_edge_pixels'] ** 2 + 128 * 1024**2
                    if shutil.disk_usage(directory).free < page_space:
                        raise ValueError('Insufficient PDF rendering storage')
                    page = temporary / ('page-%05d.png' % index)
                    raster = page.with_suffix('.ppm')
                    run(['pdftoppm', '-singlefile', '-f', str(index), '-l', str(index),
                         '-scale-to', str(options['long_edge_pixels']), str(original), str(page.with_suffix(''))],
                        timeout=min(60, remaining))
                    with Image.open(raster) as image:
                        if image.format != 'PPM' or max(image.size) > options['long_edge_pixels']:
                            raise ValueError('PDF rendered page exceeds dimension limit')
                        image.load()  # Decode every page before archiving it.
                        dimensions = list(image.size)
                        image.save(page, format='PNG', compress_level=1)
                    raster.unlink()
                    with Image.open(page) as image:
                        image.load()
                    total += page.stat().st_size
                    if total > limit:
                        raise ValueError('PDF rendered pages exceed expanded size limit')
                    pages.append({'name': page.name, 'dimensions': dimensions, 'sha256': digest(page)})
                    archive.write(page, page.name)
                    page.unlink()
            inventory = worker.info(archive_path)
            if inventory['page_count'] != count or [p['sha256'] for p in inventory['pages']] != [p['sha256'] for p in pages]:
                raise ValueError('PDF archive page verification failed')
            if identity(source) != before or digest(source) != checksum:
                raise ValueError('PDF source changed during rendering')
            with archive_path.open('rb') as stream:
                os.fsync(stream.fileno())
            # Commit receipt after atomic no-clobber output publication.
            os.link(archive_path, output)
            sync_directory(directory)
            version = subprocess.run(['pdftoppm', '-v'], capture_output=True, text=True, check=True).stderr.splitlines()[0]
            record = {'version': 1, 'source_sha256': checksum, 'original': str(original),
                      'options': options, 'renderer': version, 'pages': pages, 'inventory': inventory,
                      'output_sha256': digest(output), 'completed_at': time.time()}
            save(receipt, record)
    if identity(source) != before or digest(source) != checksum:
        raise ValueError('PDF source changed during derivative verification')
    return output
