"""Prefer declared native comic archives among already matching releases."""
import re
from urllib.parse import unquote, urlsplit


def declared_format(text):
    match = re.search(r'\bformat\s*:\s*((?:CBZ|CBR|PDF)(?:\s*[,/+&]\s*(?:CBZ|CBR|PDF))*)\b',
                      str(text or ''), re.I)
    return match[1].upper() if match else ''


def rank(value):
    entry = value.get('entry', value)
    if not isinstance(entry, dict):
        return 1
    formats = set(re.findall(r'\b(?:CBZ|CBR|PDF)\b', str(entry.get('download_format', '')).upper()))
    for field in ('filename', 'title', 'link'):
        text = str(entry.get(field) or '')
        if field == 'link':
            try:
                text = unquote(urlsplit(text).path)  # Never interpret query tokens as formats.
            except ValueError:
                text = ''
        formats.update(re.findall(r'(?i)\.(cbz|cbr|pdf)(?=$|[\s)\]])', text))
    formats = {value.upper() for value in formats}
    if formats.intersection({'CBZ', 'CBR'}):
        return 0
    return 2 if 'PDF' in formats else 1


def first(checker, entries, info, prefer_pack=False):
    """Bound lookahead after a match; never weaken native identity/quality checks."""
    best, best_key, remaining = None, None, None
    iterator = iter(entries)
    while True:
        try:
            entry = next(iterator)
        except StopIteration:
            break
        except Exception:
            if best is not None:
                return best  # Optional lookahead must not lose a verified fallback.
            raise
        match = checker._process_entry(entry, info)
        if match is not None:
            key = (bool(match['pack']) != bool(prefer_pack), rank(match))
            if best is None or key < best_key:
                best, best_key = match, key
            if key == (False, 0):
                return match
            if remaining is None:
                remaining = 100
        if remaining is not None:
            remaining -= 1
            if remaining <= 0:
                break
    return best


def ordered(matches):
    """Keep pack slots and unrelated provider policy; sort formats within each kind."""
    result = list(matches)
    for pack in (False, True):
        positions = [i for i, row in enumerate(result) if bool(row.get('pack')) == pack]
        choices = sorted((result[i] for i in positions), key=rank)
        for index, choice in zip(positions, choices):
            result[index] = choice
    return result
