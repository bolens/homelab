"""Close cached HTML and update only the pinned BeautifulSoup call aliases."""
import ast
from collections import Counter
from pathlib import Path
import sys

MARKER = '# homelab-getcomics-parser-compat-v1'
PRIOR = "        soup = BeautifulSoup(open(title + '.html', encoding='utf-8'), 'html.parser')\n"
CURRENT = """        # homelab-getcomics-parser-compat-v1
        with open(title + '.html', encoding='utf-8') as cached_html:
            soup = BeautifulSoup(cached_html, 'html.parser')
"""
# Exact active call sites from the retained original getcomics fixture. Comments
# and the pre-existing page_list.find_all call remain byte-for-byte unchanged.
CALLS = {
    'soup.findAll("article")': ('soup.find_all("article")', 1),
    'soup.findAll("p", {"style": "text-align: center;"})':
        ('soup.find_all("p", {"style": "text-align: center;"})', 1),
    "possible_more.findAll('li')": ("possible_more.find_all('li')", 1),
    'soup.findAll("h3")': ('soup.find_all("h3")', 1),
    "nxt.findAll('li')": ("nxt.find_all('li')", 1),
    'option_find.findNext(text=True)': ('option_find.find_next(string=True)', 5),
    'linkline.findNext(text=True)': ('linkline.find_next(string=True)', 2),
    'sb.findNext(text=True)': ('sb.find_next(string=True)', 1),
    'x.findNext(text=True)': ('x.find_next(string=True)', 2),
}


def _replace_calls(source, *, reverse=False):
    tree = ast.parse(source, feature_version=(3, 10))
    replacements = {new if reverse else old: (old if reverse else new, count)
                    for old, (new, count) in CALLS.items()}
    found = Counter()
    edits = []
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in ('findAll', 'findNext', 'find_all', 'find_next', 'find'):
            continue
        text = ast.get_source_segment(source, node)
        if text in replacements:
            after, _ = replacements[text]
            found[text] += 1
            # ast columns count UTF-8 bytes; decode the line prefix before
            # converting them to Python string offsets.
            start = offsets[node.lineno - 1] + len(lines[node.lineno - 1].encode()[:node.col_offset].decode())
            end = offsets[node.end_lineno - 1] + len(lines[node.end_lineno - 1].encode()[:node.end_col_offset].decode())
            edits.append((start, end, after))
        elif isinstance(node.func, ast.Attribute) and (
                node.func.attr in ('findAll', 'findNext')
                or (node.func.attr in ('find', 'find_all', 'find_next')
                    and any(k.arg == 'text' for k in node.keywords))):
            raise ValueError('Unexpected deprecated getcomics parser call')
    if found != Counter({text: count for text, (_, count) in replacements.items()}):
        raise ValueError('Expected exact getcomics parser call census')
    for start, end, after in sorted(edits, reverse=True):
        source = source[:start] + after + source[end:]
    return source


def patched_source(source):
    if MARKER in source:
        if source.count(MARKER) != 1 or source.count(CURRENT) != 1 or PRIOR in source:
            raise ValueError('Cached HTML context changed')
        prior = _replace_calls(source, reverse=True).replace(CURRENT, PRIOR, 1)
        if patched_source(prior) != source:
            raise ValueError('Getcomics compatibility placement changed')
        return source
    if source.count(PRIOR) != 1 or CURRENT in source:
        raise ValueError('Expected exact cached HTML parser boundary')
    changed = _replace_calls(source).replace(PRIOR, CURRENT, 1)
    ast.parse(changed, feature_version=(3, 10))
    return changed


def main(directory):
    path = Path(directory) / 'getcomics.py'
    original = path.read_text()
    changed = patched_source(original)
    if changed != original:
        path.write_text(changed)


if __name__ == '__main__':
    main(sys.argv[1])
