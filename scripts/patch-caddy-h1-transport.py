#!/usr/bin/env python3
"""
Ensure plain-HTTP reverse_proxy blocks use HTTP/1.1 to upstreams.

Caddy 2.11 can negotiate h2c with backends that only speak HTTP/1.1 (e.g. Grafana
behind Cloudflare Tunnel → Caddy :80), yielding empty 200 responses. Adding:

    transport http {
        versions 1.1
    }

fixes that. Skips reverse_proxy https://... and transport http { ... tls ... } blocks.

Also patches stacks/caddy/Caddyfile.example and stacks/stoat/caddy/Caddyfile when present.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def is_tls_upstream_block(block: str) -> bool:
    if "reverse_proxy https://" in block.split("\n", 1)[0]:
        return True
    if "tls_insecure_skip_verify" in block:
        return True
    if re.search(r"\btransport\s+http\s*\{", block) and re.search(
        r"\btls\b", block.split("transport", 1)[-1] if "transport" in block else ""
    ):
        # transport http { ... tls ... } → HTTPS to upstream
        return True
    return False


def already_has_versions(block: str) -> bool:
    return bool(re.search(r"^\s*versions\s+1\.1\s*$", block, re.MULTILINE))


def extract_reverse_proxy_block(lines: list[str], start: int) -> tuple[str, int]:
    """Block starts at lines[start] with '{' on same line; returns (text, index_after_block)."""
    buf = [lines[start]]
    depth = lines[start].count("{") - lines[start].count("}")
    i = start + 1
    while i < len(lines) and depth > 0:
        buf.append(lines[i])
        depth += lines[i].count("{") - lines[i].count("}")
        i += 1
    return "\n".join(buf), i


def patch_braced_block(block: str) -> tuple[str, bool]:
    if already_has_versions(block):
        return block, False
    if is_tls_upstream_block(block):
        return block, False
    lines = block.split("\n")
    for idx, line in enumerate(lines):
        if re.search(r"^\s*transport\s+http\s*\{\s*$", line):
            tws = re.match(r"^(\s*)", line).group(1) + "\t"
            rest = lines[idx + 1 :]
            if rest and re.match(r"^\s*versions\s+1\.1\s*$", rest[0]):
                return block, False
            new_lines = lines[: idx + 1] + [f"{tws}versions 1.1"] + lines[idx + 1 :]
            return "\n".join(new_lines), True
    # insert transport before closing brace of reverse_proxy (last line)
    if len(lines) < 2:
        return block, False
    closing = lines[-1]
    base_ws = re.match(r"^(\s*)", closing).group(1)
    inner_ws = base_ws + "\t"
    inner_inner = inner_ws + "\t"
    insert = [
        f"{inner_ws}transport http {{",
        f"{inner_inner}versions 1.1",
        f"{inner_ws}}}",
    ]
    return "\n".join(lines[:-1] + insert + [lines[-1]]), True


def braceless_reverse_proxy_line(line: str) -> str | None:
    stripped = line.lstrip()
    if not stripped.startswith("reverse_proxy ") or stripped.startswith(
        "reverse_proxy https://"
    ):
        return None
    if "{" in stripped:
        return None
    m = re.match(r"^(reverse_proxy\s+)(.+)$", stripped)
    if not m:
        return None
    rest = m.group(2)
    if "#" in rest:
        rest = rest.split("#", 1)[0].rstrip()
    if not rest:
        return None
    return rest


def patch_braceless_line(line: str) -> tuple[str, bool] | None:
    """Convert `\\treverse_proxy host:port` into braced proxy + transport."""
    if "versions 1.1" in line:
        return None
    target = braceless_reverse_proxy_line(line)
    if target is None:
        return None
    ws = line[: len(line) - len(line.lstrip())]
    inner = ws + "\t"
    inner2 = inner + "\t"
    out = "\n".join(
        [
            f"{ws}reverse_proxy {target} {{",
            f"{inner}transport http {{",
            f"{inner2}versions 1.1",
            f"{inner}}}",
            f"{ws}}}",
        ]
    )
    return out, True


def process_file(path: Path) -> bool:
    raw = path.read_text(encoding="utf-8")
    lines = raw.split("\n")
    out: list[str] = []
    i = 0
    changed = False
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if stripped.startswith("reverse_proxy ") and not stripped.startswith(
            "reverse_proxy https://"
        ):
            if "{" in line:
                block, end_i = extract_reverse_proxy_block(lines, i)
                nb, c = patch_braced_block(block)
                if c:
                    changed = True
                out.extend(nb.split("\n"))
                i = end_i
                continue
            patched = patch_braceless_line(line)
            if patched is not None:
                new_text, c = patched
                if c:
                    changed = True
                out.extend(new_text.split("\n"))
                i += 1
                continue
        out.append(line)
        i += 1
    # split/join already preserves a trailing newline via a final "" segment
    new_raw = "\n".join(out)
    if new_raw != raw:
        path.write_text(new_raw, encoding="utf-8")
        return True
    return changed


def main() -> int:
    paths: list[Path] = []
    for pat in (
        "**/caddy_snippet.conf",
        "**/caddy_snippet.conf.example",
        "**/caddy_snippet.conf.template",
    ):
        paths.extend(ROOT.glob(pat))
    # Monolithic / alternate Caddy examples (same h2c issue when tunnel → :80)
    for rel in (
        "stacks/caddy/Caddyfile.example",
        "stacks/stoat/caddy/Caddyfile",
    ):
        p = ROOT / rel
        if p.is_file():
            paths.append(p)
    paths = sorted({p.resolve() for p in paths if p.is_file()})
    n = 0
    for p in paths:
        try:
            if process_file(p):
                print(p.relative_to(ROOT))
                n += 1
        except OSError as e:
            print(f"skip {p}: {e}", file=sys.stderr)
    print(f"Patched {n} file(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
