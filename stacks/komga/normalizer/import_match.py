"""Conservative regular-issue matching; never authorizes release blacklisting."""
from contextlib import closing
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
import zipfile


def title(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def number(value):
    try:
        result = Decimal(str(value).strip())
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def metadata(path):
    if not zipfile.is_zipfile(path):
        return {}
    with zipfile.ZipFile(path) as archive:
        entries = [i for i in archive.infolist() if Path(i.filename).name.casefold() == 'comicinfo.xml']
        if not entries:
            return {}
        if len(entries) != 1 or entries[0].file_size > 262144:
            raise ValueError('Ambiguous or oversized metadata')
        raw = archive.read(entries[0])
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsupported XML declarations')
    root = ET.fromstring(raw)
    if root.tag != 'ComicInfo':
        raise ValueError('Unsupported metadata root')
    result = {}
    for child in root:
        if child.tag in result:
            raise ValueError('Repeated metadata field')
        result[child.tag] = child.text or ''
    return result


def catalog(database):
    with closing(sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)) as db:
        return db.execute('SELECT i.IssueID,i.ComicID,i.Status,i.Issue_Number,i.IssueDate,c.ComicName,c.ComicYear '
                          'FROM issues i JOIN comics c ON c.ComicID=i.ComicID').fetchall()


def match(path, database, rows=None):
    """Return one identity only when all available supported evidence agrees."""
    try:
        meta = metadata(path)
    except (ValueError, ET.ParseError, zipfile.BadZipFile, OSError, RuntimeError):
        return None
    tagged = re.findall(r'\[__(\d+)__\]', path.name)
    web_ids = re.findall(r'https?://(?:www\.)?comicvine\.gamespot\.com/[^\s<>]*?4000-(\d+)(?:/|\b)', meta.get('Web', ''))
    ids = set(tagged + web_ids)
    if len(ids) > 1 or len(tagged) > 1:
        return None
    evidence = []
    if meta.get('Series') and meta.get('Number'):
        year = meta.get('Volume', '')
        if re.fullmatch(r'(?:19|20)\d{2}', year):
            evidence.append((title(meta['Series']), number(meta['Number']), year, 'series'))
        elif re.fullmatch(r'(?:19|20)\d{2}', meta.get('Year', '')):
            evidence.append((title(meta['Series']), number(meta['Number']), meta['Year'], 'issue'))
        elif not ids:
            return None
    # A parenthesized filename year is treated strictly as the series start year.
    clean = re.sub(r'\[__\d+__\]', '', path.stem).strip()
    parsed = re.fullmatch(r'(.+?)\s+#?(\d+(?:\.\d+)?)\s+\(((?:19|20)\d{2})\)(?:\s+\([^)]*\))*', clean)
    if parsed:
        evidence.append((title(parsed[1]), number(parsed[2]), parsed[3], 'series'))
    if not ids and not evidence:
        return None
    if rows is None:
        rows = catalog(database)
    candidates = []
    for row in rows:
        if ids and str(row[0]) not in ids:
            continue
        if meta.get('Series') and title(meta['Series']) != title(row[5]):
            continue
        if meta.get('Number') and (number(meta['Number']) is None or number(meta['Number']) != number(row[3])):
            continue
        if any(not key or issue is None or key != title(row[5]) or issue != number(row[3])
               or year != (str(row[6]) if kind == 'series' else str(row[4])[:4])
               for key, issue, year, kind in evidence):
            continue
        candidates.append(row)
    if len(candidates) != 1 or candidates[0][2] == 'Downloaded':
        return None
    row = candidates[0]
    return {'issueid': str(row[0]), 'comicid': str(row[1])}
