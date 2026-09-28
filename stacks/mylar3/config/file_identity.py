"""Conservative recovery of known single-volume comic filenames."""

from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import unicodedata


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
