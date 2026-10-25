"""Conservative, one-shot missing-ebook supplementation. Private receipts are required."""
import argparse
import json
import os
from pathlib import Path
import re
import unicodedata
import urllib.parse
import urllib.request


def words(value):
    text = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode().lower()
    return re.findall(r'[a-z0-9]+', text)


def match_candidate(book, author, candidate):
    """Require title words, author evidence and an explicit ebook format."""
    if candidate.get('in_library') or candidate.get('media_type', 'ebook') not in ('', 'ebook'):
        return False
    if candidate.get('download_protocol') == 'nzb':
        return False
    fmt = candidate.get('format', '').lower().strip('.')
    if fmt not in ('epub', 'pdf', 'mobi', 'azw3'):
        return False
    if candidate.get('size', 0) > 500 * 1024 * 1024:
        return False
    expected = ' '.join(words(book['title']))
    advertised = ' '.join(words(candidate.get('title', '')))
    for marker in ('graphic novel', 'graphic adaptation', 'comic', 'manga',
                   'study guide', 'summary', 'abridged', 'illustrated', 'annotated'):
        if re.search(r'\b' + marker + r'\b', expected) and not re.search(r'\b' + marker + r'\b', advertised):
            return False
    title = words(book['title'])
    if title and title[0] in ('a', 'an', 'the'):
        title = title[1:]
    found = words(candidate.get('title', ''))
    if not title or not found:
        return False
    # Contiguous title matching avoids combining unrelated words from packs.
    if not any(found[i:i + len(title)] == title for i in range(len(found) - len(title) + 1)):
        return False
    author_words = set(words(author))
    advertised_author = set(words(candidate.get('author', '')))
    evidence = advertised_author | set(found)
    if not author_words or not author_words <= evidence:
        return False
    # Explicit metadata must agree even when the release title names the author.
    if advertised_author and advertised_author != author_words:
        return False
    allowed = set(words(book['title']) + words(author)) | {
        'epub', 'pdf', 'mobi', 'azw3', 'ebook', 'ebooks', 'retail', 'digital',
        'novel', 'edition', 'revised', 'illustrated', 'scan', 'ocr', 'the',
        'and', 'by', 'with', 'book', 'books', 'original', 'updated', 'english', 'eng', 'en'}
    if any(word not in allowed and not re.fullmatch(r'(?:v?[0-9]+(?:st|nd|rd|th)?)', word)
           for word in found):
        return False
    if re.search(r'\b(audiobook|unabridged|mp3|m4b|collection|omnibus|complete works)\b', candidate.get('title', ''), re.I):
        return False
    if candidate.get('language') and candidate['language'].lower() not in ('en', 'eng', 'english'):
        return False
    if candidate.get('download_protocol') == 'torrent' and candidate.get('seeders', 0) < 1:
        return False
    return bool(candidate.get('download_url') or candidate.get('magnet_url') or
                candidate.get('epub_url') or candidate.get('md5'))


class API:
    def __init__(self, url, key):
        self.url = url.rstrip('/')
        self.key = key

    def call(self, path, data=None):
        request = urllib.request.Request(self.url + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'X-Api-Key': self.key, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=100) as response:
            return json.load(response)


def acquire(bookshelf, librarr, receipts, limit, apply=False):
    receipts.mkdir(mode=0o700, parents=True, exist_ok=True)
    authors = {a['id']: a['authorName'] for a in bookshelf.call('/api/v1/author')}
    missing = bookshelf.call('/api/v1/wanted/missing?page=1&pageSize=1000&monitored=true')['records']
    queued = {r.get('bookId') for r in bookshelf.call('/api/v1/queue?page=1&pageSize=1000').get('records', [])}
    stats = {'searched': 0, 'submitted': 0, 'no_confident_match': 0, 'already_owned_or_queued': 0, 'receipt_blocked': 0, 'failed': 0}
    for book in missing:
        receipt = receipts / (str(book['id']) + '.json')
        if book['id'] in queued:
            stats['already_owned_or_queued'] += 1
            continue
        if receipt.exists():
            stats['receipt_blocked'] += 1
            continue
        if stats['searched'] >= limit:
            break
        stats['searched'] += 1
        author = authors[book['authorId']]
        query = urllib.parse.urlencode({'q': book['title'].split(':')[0], 'author': author})
        try:
            results = librarr.call('/api/search?' + query).get('results', [])
            matches = [r for r in results if match_candidate(book, author, r)]
            matches.sort(key=lambda r: (r.get('format', '').lower() == 'epub', r.get('score', 0), r.get('seeders', 0)), reverse=True)
            if not matches:
                stats['no_confident_match'] += 1
                continue
            selected = matches[0]
            data = {'book_id': book['id'], 'title': book['title'], 'author': author,
                    'candidate': selected, 'state': 'reviewed'}
            if apply:
                fresh = bookshelf.call('/api/v1/book/' + str(book['id']))
                queued_now = bookshelf.call('/api/v1/queue?page=1&pageSize=1000').get('records', [])
                if fresh.get('statistics', {}).get('bookFileCount', 0) or any(r.get('bookId') == book['id'] for r in queued_now):
                    stats['already_owned_or_queued'] += 1
                    continue
                # Persist intent BEFORE submission so an uncertain response cannot cause a repeat grab.
                data['state'] = 'submission_pending'
                fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as handle:
                    json.dump(data, handle)
                payload = {key: selected[key] for key in (
                    'source', 'title', 'author', 'source_id', 'download_url', 'magnet_url',
                    'info_hash', 'guid', 'md5', 'url', 'download_protocol') if key in selected}
                if not payload.get('download_url') and selected.get('epub_url'):
                    payload['download_url'] = selected['epub_url']
                payload['media_type'] = 'ebook'
                payload['title'] = book['title']
                payload['author'] = author
                result = librarr.call('/api/download', payload)
                data.update(state='submitted' if result.get('success') else 'rejected', response=result)
                receipt.write_text(json.dumps(data, indent=2))
                stats['submitted'] += int(bool(result.get('success')))
                stats['failed'] += int(not result.get('success'))
            else:
                # Review never creates an acquisition receipt that would prevent a later apply.
                review = receipts / ('review-' + str(book['id']) + '.json')
                review.write_text(json.dumps(data, indent=2))
                review.chmod(0o600)
        except Exception as error:
            stats['failed'] += 1
            # Keep uncertain intent receipts. Error strings can contain private URLs.
            if receipt.exists():
                data = json.loads(receipt.read_text())
                data.update(state='needs_review', error_type=type(error).__name__)
                receipt.write_text(json.dumps(data, indent=2))
        print(json.dumps(stats), flush=True)
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bookshelf-url', required=True)
    parser.add_argument('--librarr-url', required=True)
    parser.add_argument('--keys-file', required=True, type=Path,
                        help='Private JSON with bookshelf_api_key and librarr_api_key')
    parser.add_argument('--receipts', required=True, type=Path)
    parser.add_argument('--limit', type=int, default=25)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error('limit must be between 1 and 1000')
    if args.keys_file.stat().st_mode & 0o077:
        parser.error('keys file must be private to its owner')
    keys = json.loads(args.keys_file.read_text())
    stats = acquire(API(args.bookshelf_url, keys['bookshelf_api_key']),
                    API(args.librarr_url, keys['librarr_api_key']), args.receipts, args.limit, args.apply)
    print(json.dumps(stats))


if __name__ == '__main__':
    main()
