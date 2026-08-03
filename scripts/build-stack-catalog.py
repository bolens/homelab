#!/usr/bin/env python3
"""Regenerate documents/STACK-CATALOG.md from stack READMEs."""

import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "documents" / "STACK-CATALOG.md"
STACKS = ROOT / "stacks"


def description(readme: Path) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    for raw in readme.read_text(encoding="utf-8").splitlines()[1:]:
        line = raw.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if line.startswith(("#", "**", "```", "|", "-", "<!--")) or re.match(
            r"\d+\.", line
        ):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    text = next((p for p in paragraphs if len(p) >= 20), "See the stack README for details.")
    text = re.sub(r"\s+", " ", text).replace("|", r"\|")
    return text


def build() -> str:
    rows = [
        "| Stack | What it does |",
        "|---|---|",
    ]
    directories = sorted(path for path in STACKS.iterdir() if path.is_dir())
    for directory in directories:
        ignored = subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", str(directory.relative_to(ROOT))],
            check=False,
        ).returncode == 0
        if ignored:
            continue
        readme = directory / "README.md"
        if not readme.exists():
            raise SystemExit(f"missing stack README: {readme.relative_to(ROOT)}")
        relative = Path("..") / readme.relative_to(ROOT)
        rows.append(
            f"| [**{directory.name}**]({relative.as_posix()}) | {description(readme)} |"
        )
    return "\n".join(rows)


def render() -> str:
    return (
        "# Stack catalog\n\n"
        "Generated from every `stacks/<name>/README.md`. Do not edit the table "
        "directly; run `python3 scripts/build-stack-catalog.py`.\n\n"
        "<!-- STACK_CATALOG_GENERATED_START -->\n"
        f"{build()}\n"
        "<!-- STACK_CATALOG_GENERATED_END -->\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if generated output is stale")
    args = parser.parse_args()
    generated = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != generated:
            raise SystemExit("documents/STACK-CATALOG.md is stale; regenerate it")
        print("Stack catalog is current.")
        return
    OUTPUT.write_text(generated, encoding="utf-8")
    print(f"Updated {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
