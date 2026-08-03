#!/usr/bin/env python3
"""Regenerate the top-level README stack catalog from stack READMEs."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
STACKS = ROOT / "stacks"
START = "<!-- STACK_CATALOG_GENERATED_START -->"
END = "<!-- STACK_CATALOG_GENERATED_END -->"


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
    for directory in sorted(path for path in STACKS.iterdir() if path.is_dir()):
        readme = directory / "README.md"
        if not readme.exists():
            raise SystemExit(f"missing stack README: {readme.relative_to(ROOT)}")
        relative = readme.relative_to(ROOT)
        rows.append(
            f"| [**{directory.name}**]({relative.as_posix()}) | {description(readme)} |"
        )
    return "\n".join(rows)


def main() -> None:
    text = README.read_text(encoding="utf-8")
    generated = f"{START}\n{build()}\n{END}"
    if START in text and END in text:
        text = re.sub(
            rf"{re.escape(START)}.*?{re.escape(END)}",
            generated,
            text,
            flags=re.DOTALL,
        )
    else:
        table_start = text.index("| Stack | What it does |", text.index("## 📦 What’s inside"))
        table_end = text.index("\n\nEach stack has", table_start)
        text = text[:table_start] + generated + text[table_end:]
    README.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
