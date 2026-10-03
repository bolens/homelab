"""Conservative recovery of known single-volume comic filenames."""

from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile


def validate_rescan(database, series, file_lists, *, booktype=None):
    """Reject contradictory identities before native rescan can delete or reassign files."""
    comic_id = series["ComicID"]
    issues = database.select("SELECT * FROM issues WHERE ComicID=?", [comic_id])
    annuals = database.select("SELECT * FROM annuals WHERE ComicID=?", [comic_id])
    owners = {}
    for row in issues:
        owners.setdefault(str(row["IssueID"]), []).append((row, False))
    for row in annuals:
        if str(row["Deleted"]).casefold() not in ("1", "true"):
            owners.setdefault(str(row["IssueID"]), []).append((row, True))
    siblings = database.select(
        "SELECT * FROM comics WHERE ComicName=? AND ComicYear=?",
        [series["ComicName"], series["ComicYear"]],
    )
    ambiguous = sum(row["Type"] == series["Type"] for row in siblings) > 1
    booktype = booktype or series["Type"]

    def field(row, key):
        return row[key] if key in row.keys() else None

    def title(value):
        return ''.join(re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', value).casefold().replace('&', 'and')))

    def number(value):
        if value is None:
            return None
        value = re.sub(r'annual|special', '', str(value), flags=re.I).strip().replace('_', ' ')
        if "Director's Cut" not in value:
            value = re.sub(r"[\#']", '', value)
        try:
            result = Decimal(value)
            return result if result.is_finite() else None
        except InvalidOperation:
            return value.casefold() or None

    for listing in file_lists:
        for entry in listing.get("comiclist", []):
            filename = entry["ComicFilename"]
            path = Path(entry["ComicLocation"]) / filename
            if Path(filename).name != filename or any(p.is_symlink() for p in (path, *path.parents)):
                raise ValueError("Rescan identity review required: unsafe archive path")
            fields = {}
            if path.suffix.casefold() == ".cbz" or zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as archive:
                    metadata = [info for info in archive.infolist()
                                if Path(info.filename).name.casefold() == "comicinfo.xml"]
                    if len(metadata) > 1:
                        raise ValueError("Rescan identity review required: ambiguous ComicInfo")
                    if metadata:
                        if metadata[0].file_size > 262144:
                            raise ValueError("Rescan identity review required: oversized ComicInfo")
                        raw = archive.read(metadata[0]).decode("utf-8-sig")
                        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", raw, re.I):
                            raise ValueError("Rescan identity review required: unsafe ComicInfo")
                        root = ET.fromstring(raw)
                        if root.tag != "ComicInfo":
                            raise ValueError("Rescan identity review required: invalid ComicInfo")
                        for child in root:
                            if child.tag in ("Series", "Number", "Web", "Volume"):
                                if child.tag in fields:
                                    raise ValueError("Rescan identity review required: repeated identity field")
                                fields[child.tag] = (child.text or "").strip()
            elif path.suffix.casefold() in ('.cbr', '.cb7'):
                raise ValueError('Rescan identity review required: convert archive before metadata verification')
            annual_mode = bool(entry.get('AnnualComicID')) or bool(re.search(r'annual|special', str(entry.get('JusttheDigits')), re.I))
            names = [row['ReleaseComicName'] for row in annuals if not row['Deleted']] if annual_mode else [series['ComicName']]
            if not annual_mode:
                names.extend(part for part in (field(series, 'AlternateSearch') or '').split('##') if part and '!!' not in part)
            if fields.get('Series') and title(fields['Series']) not in {title(name) for name in names}:
                raise ValueError('Rescan identity review required: metadata series contradicts catalog')
            volume = fields.get('Volume', '')
            version = re.fullmatch(r'v?(\d+)', str(series['ComicVersion'] or ''), re.I)
            if not annual_mode and ((re.fullmatch(r'(?:19|20)\d{2}', volume) and volume != str(series['ComicYear']))
                    or (version and volume.isdigit() and len(volume) < 4 and int(volume) != int(version[1]))):
                raise ValueError('Rescan identity review required: metadata volume contradicts catalog')
            effective = entry.get('JusttheDigits')
            if ((booktype in ('TPB', 'GN', 'HC') and len(issues) > 1)
                    or (booktype == 'One-Shot' and len(issues) == 1 and effective is None)):
                selected = entry.get('SeriesVolume') if entry.get('SeriesVolume') is not None else effective
                effective = re.sub(r'[^0-9]', '', str(selected)) if selected is not None else None
            if effective is None and booktype in ('TPB', 'GN', 'HC', 'One-Shot'):
                effective = '1'
            parsed = number(effective)
            tagged = number(fields.get("Number"))
            if parsed is not None and tagged is not None and parsed != tagged:
                raise ValueError("Rescan identity review required: filename and ComicInfo numbers differ")
            ids = set(re.findall(r"4000-(\d+)(?:[/\s?#]|$)", fields.get("Web", "")))
            if ids:
                if len(ids) != 1:
                    raise ValueError("Rescan identity review required: conflicting catalog IDs")
                candidates = owners.get(next(iter(ids)), [])
                matches = []
                for row, annual in candidates:
                    title = row["ReleaseComicName"] if annual else series["ComicName"]
                    if fields.get("Series") and fields["Series"].casefold() != title.casefold():
                        continue
                    if tagged is not None and tagged != number(row["Issue_Number"]):
                        continue
                    if parsed is None or parsed != number(row['Issue_Number']):
                        continue
                    if annual and str(entry.get("AnnualComicID")) != str(row["ReleaseComicID"]):
                        continue
                    if not annual and entry.get("AnnualComicID"):
                        continue
                    matches.append(row)
                if len(matches) != 1:
                    raise ValueError("Rescan identity review required: catalog identity contradicts series")
            elif ambiguous:
                version = re.fullmatch(r"v?(\d+)", str(series["ComicVersion"] or ""), re.I)
                explicit = set(re.findall(r"\b(?:v|vol\.?|volume)\s*(\d+)\b", path.stem, re.I))
                if not version or explicit != {version[1]}:
                    raise ValueError("Rescan identity review required: ambiguous series volume")


def single_issue_number(database, comic_id, total):
    if str(total) != "1":
        return None
    rows = database.select(
        "SELECT Issue_Number FROM issues WHERE ComicID=? LIMIT 2", [comic_id]
    )
    return rows[0]["Issue_Number"] if len(rows) == 1 else None


def single_volume_match(checker, filename):
    """Conservative filename recovery; neither folder membership nor type is identity."""
    kind = getattr(checker, "comic_type", None)
    number = getattr(checker, "single_issue_number", None)
    if kind not in ("One-Shot", "GN", "Graphic Novel", "TPB", "HC") or number is None:
        return None
    folder = Path(checker.dir or "")
    if not checker.dir or not folder.is_dir():
        return None
    target = folder / filename
    if Path(filename).name != filename or target.is_symlink() or not target.is_file():
        return None
    # Parenthesized groups are not all disposable scanner metadata: a number,
    # annual, edition, or variant marker can identify a different comic. Only
    # plain publication years are safe to ignore for this conservative fallback.
    groups = re.findall(r"\(([^)]*)\)|\[([^\]]*)\]", target.stem)
    if any(
        not re.fullmatch(r"(?:19|20)\d{2}", (left or right).strip())
        for left, right in groups
    ):
        return None
    names = [checker.watchcomic or ""]
    names.extend(
        part
        for part in (checker.AlternateSearch or "").split("##")
        if part and part != "None" and "!!" not in part
    )

    def tokens(value, metadata=False):
        value = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", value) if metadata else value
        return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold())

    file_tokens = tokens(target.stem, metadata=True)
    valid_name = False
    for name in names:
        wanted = tokens(name)
        if not wanted or file_tokens[: len(wanted)] != wanted:
            continue
        suffix = file_tokens[len(wanted) :]
        if not suffix:
            valid_name = True
        elif len(suffix) == 1:
            try:
                valid_name = Decimal(suffix[0]) == Decimal(str(number))
            except InvalidOperation:
                pass
        if valid_name:
            break
    if not valid_name:
        return None
    try:
        files = [
            p
            for p in folder.iterdir()
            if p.is_file()
            and p.suffix.lower() in (".cbz", ".cbr", ".cb7", ".cbt", ".pdf")
        ]
    except OSError:
        return None
    markers = ("primer", "ashcan", "preview", "sneak peek")

    # Marker files are retained, not treated as the catalog's sole issue.
    def marker(path):
        return any(
            word in path.stem.casefold()
            and word not in (checker.watchcomic or "").casefold()
            for word in markers
        )

    candidates = [p for p in files if not marker(p)]
    if candidates != [target]:
        return None
    return str(number), checker.watchcomic, "GN" if kind == "Graphic Novel" else kind
