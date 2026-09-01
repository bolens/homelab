#!/usr/bin/env python3
"""Validate the generated GitHub Pages structure and local links."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "site" / "public"


class Document(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html_lang = ""
        self.title = False
        self.h1 = 0
        self.main = 0
        self.nav_labels = 0
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.iframes_without_title = 0
        self.metadata: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.html_lang = values.get("lang") or ""
        elif tag == "title":
            self.title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "main":
            self.main += 1
        elif tag == "nav" and values.get("aria-label"):
            self.nav_labels += 1
        elif tag == "iframe" and not values.get("title"):
            self.iframes_without_title += 1
        elif tag == "meta":
            key = values.get("name") or values.get("property")
            if key:
                self.metadata.add(key)
        if values.get("id"):
            self.ids.add(values["id"] or "")
        for attribute in ("href", "src"):
            if values.get(attribute):
                self.links.append(values[attribute] or "")


def local_target(source: Path, raw: str) -> tuple[Path, str] | None:
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc or raw.startswith(("mailto:", "tel:", "data:")):
        return None
    path = unquote(parts.path)
    if path.startswith("/homelab/"):
        target = PUBLIC / path.removeprefix("/homelab/")
    elif path.startswith("/"):
        return None
    else:
        target = source.parent / path
    if not path:
        target = source
    if target.is_dir() or path.endswith("/"):
        target = target / "index.html"
    return target.resolve(), parts.fragment


def main() -> None:
    problems: list[str] = []
    html_files = sorted(PUBLIC.rglob("*.html"))
    app_pages = list((PUBLIC / "apps").glob("*/index.html"))
    if len(app_pages) < 200:
        problems.append(f"expected at least 200 application pages, found {len(app_pages)}")
    parsed: dict[Path, Document] = {}
    for asset in ("favicon.svg", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "social-card.png", "site.webmanifest"):
        if not (PUBLIC / asset).is_file():
            problems.append(f"site/public/{asset}: missing discovery asset")
    for path in html_files:
        doc = Document()
        doc.feed(path.read_text(encoding="utf-8"))
        parsed[path.resolve()] = doc
        relative = path.relative_to(ROOT)
        is_topology = path == PUBLIC / "topology.html"
        if doc.html_lang != "en":
            problems.append(f"{relative}: missing lang=en")
        if not doc.title:
            problems.append(f"{relative}: missing title")
        if not is_topology and doc.h1 != 1:
            problems.append(f"{relative}: expected one h1, found {doc.h1}")
        if not is_topology and doc.main != 1:
            problems.append(f"{relative}: expected one main, found {doc.main}")
        if not is_topology and doc.nav_labels == 0:
            problems.append(f"{relative}: navigation needs an accessible label")
        if doc.iframes_without_title:
            problems.append(f"{relative}: iframe needs a title")
        if not is_topology:
            for key in ("description", "og:type", "og:url", "og:site_name", "og:title", "og:description",
                        "og:image", "og:image:width", "og:image:height", "og:image:alt", "twitter:card",
                        "twitter:title", "twitter:description", "twitter:image", "twitter:image:alt"):
                if key not in doc.metadata:
                    problems.append(f"{relative}: missing {key} metadata")
    for source, doc in parsed.items():
        for raw in doc.links:
            local = local_target(source, raw)
            if local is None:
                continue
            target, fragment = local
            if not target.exists():
                problems.append(f"{source.relative_to(ROOT)}: broken link {raw}")
            elif fragment and target.suffix == ".html":
                target_doc = parsed.get(target)
                if target_doc is not None and fragment not in target_doc.ids:
                    problems.append(f"{source.relative_to(ROOT)}: missing fragment {raw}")
    css = (PUBLIC / "styles.css").read_text(encoding="utf-8")
    for requirement in (":focus-visible", "prefers-reduced-motion", "color-scheme: dark", "[hidden]"):
        if requirement not in css:
            problems.append(f"site/public/styles.css: missing {requirement}")
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"Pages site is valid ({len(html_files)} HTML files, {len(app_pages)} application pages).")


if __name__ == "__main__":
    main()
