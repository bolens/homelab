#!/usr/bin/env python3
"""
Sort only the Public HTTPS section of a Caddyfile A–Z by hostname.
Local and :80 blocks are left unchanged.

Run from the docker/ repo root, e.g.:
  python3 scripts/sort_caddyfile.py [--dry-run|-n] [stacks/caddy/Caddyfile]

With --dry-run, prints the result to stdout and does not modify the file.
"""
import argparse
import sys
from pathlib import Path


def hostname_sort_key(first_line: str) -> str:
    """First host label from a block start line (e.g. 'portainer' from 'portainer.domain.tld {')."""
    first = first_line.split("{")[0].strip().split(",")[0].strip().split()[0].strip()
    # Use first label only so we never need to reference any real domain
    return (first.split(".")[0] if "." in first else first).lower()


def extract_public_blocks(lines: list[str]) -> tuple[list[str], list[tuple[str, list[str]]], list[str]]:
    """
    Split Public HTTPS section into:
      - header lines (comments/blank before first host block),
      - list of (sort_key, block_lines),
      - tail (e.g. trailing :80 { } in example).
    """
    i = 0
    header: list[str] = []
    while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("#")):
        header.append(lines[i])
        i += 1

    blocks: list[tuple[str, list[str]]] = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # Host block: line has " {" and first token looks like host.domain
        first_token = line.split("{")[0].strip().split(",")[0].strip()
        if " {" in line and "." in first_token:
            start = i
            first_line = line
            depth = 0
            j = i
            while j < len(lines):
                for c in lines[j]:
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            block_lines = lines[start : j + 1]
                            key = hostname_sort_key(first_line)
                            blocks.append((key, block_lines))
                            i = j + 1
                            break
                if depth == 0:
                    break
                j += 1
            else:
                i += 1
            continue
        i += 1

    tail: list[str] = lines[i:] if i < len(lines) else []
    return header, blocks, tail


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sort only the Public HTTPS section of a Caddyfile A–Z by hostname."
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print result to stdout instead of overwriting the file",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="stacks/caddy/Caddyfile.example",
        help="path to Caddyfile from repo root (default: stacks/caddy/Caddyfile.example)",
    )
    args = parser.parse_args()

    path = Path(args.path)
    content = path.read_text()

    public_start = content.find("# Public HTTPS")
    if public_start == -1:
        if args.dry_run:
            sys.stdout.write(content)
        else:
            print(f"No '# Public HTTPS' section in {path}; file unchanged.", file=sys.stderr)
        return

    before = content[:public_start].rstrip()
    public_section = content[public_start:]
    lines = public_section.split("\n")

    header, blocks, tail = extract_public_blocks(lines)
    blocks.sort(key=lambda x: x[0])

    header_text = "\n".join(header)
    blocks_text = "\n\n".join("\n".join(bl) for _, bl in blocks)
    tail_text = "\n".join(tail).rstrip() if tail else ""

    result = f"{before}\n\n{header_text}\n\n{blocks_text}"
    if tail_text:
        result += f"\n\n{tail_text}"
    result += "\n"

    if args.dry_run:
        sys.stdout.write(result)
    else:
        path.write_text(result)
        print(f"Sorted Public HTTPS section in {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
