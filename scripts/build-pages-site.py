#!/usr/bin/env python3
"""Build the GitHub Pages reference from stack metadata and READMEs."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

import yaml

ROOT = Path(__file__).resolve().parents[1]
STACKS = ROOT / "stacks"
PUBLIC = ROOT / "site" / "public"
REPO_URL = "https://github.com/bolens/homelab"
PUBLIC_ROOT = "https://bolens.github.io/homelab/"
CATEGORY_NAMES = {
    "ai": "AI", "analytics": "Analytics", "backup": "Backup",
    "dev": "Developer tools", "documents": "Documents", "downloads": "Downloads",
    "homeautomation": "Home automation", "infrastructure": "Infrastructure",
    "media": "Media", "monitoring": "Monitoring", "networking": "Networking",
    "productivity": "Productivity", "security": "Security", "storage": "Storage",
    "utility": "Utilities",
}


def summary(readme: Path) -> str:
    current: list[str] = []
    for raw in readme.read_text(encoding="utf-8").splitlines()[1:]:
        line = raw.strip()
        if not line:
            if current:
                text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", " ".join(current))
                text = re.sub(r"[`*_]", "", text)
                return re.sub(r"\s+", " ", text)
            continue
        if line.startswith(("#", "**", "```", "|", "-", "<!--")) or re.match(r"\d+\.", line):
            continue
        current.append(line)
    return "Read the technical setup for details."


def label(value: str) -> str:
    names = {"app_local": "Application login", "none": "No built-in login"}
    return names.get(value, value.replace("_", " ").capitalize())


def header(active: str = "") -> str:
    links = [("Apps", "apps/"), ("How it works", "architecture/"), ("Safety", "safety/")]
    nav = "".join(
        f'<a href="/{"homelab/"}{url}"' + (' aria-current="page"' if name == active else "") + f'>{name}</a>'
        for name, url in links
    )
    return f'''<a class="skip-link" href="#main">Skip to main content</a>
<header class="site-header"><a class="brand" href="/homelab/"><span class="brand-mark" aria-hidden="true"></span> Homelab Atlas</a>
<nav aria-label="Primary navigation">{nav}<a href="{REPO_URL}">Technical docs</a><label class="color-mode-picker"><span>Theme</span><select data-color-mode aria-label="Color theme"><option value="system">System</option><option value="time">Day cycle</option><option value="light">Light</option><option value="dark">Dark</option></select></label></nav></header>'''


def footer() -> str:
    return f'''<footer><p>Homelab Atlas explains what is available. <a href="{REPO_URL}">The repository contains deployment and configuration instructions.</a></p></footer>'''


def page(title: str, description: str, body: str, active: str = "", path: str = "") -> str:
    canonical = f"https://bolens.github.io/homelab/{path}"
    social_title = f"{title} | Homelab Atlas"
    return f'''<!doctype html>
<html lang="en" data-color-mode-storage="homelab-atlas-color-mode"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#050914"><meta name="description" content="{html.escape(description, quote=True)}">
<link rel="canonical" href="{canonical}"><meta property="og:type" content="website"><meta property="og:url" content="{canonical}"><meta property="og:site_name" content="Homelab Atlas">
<meta property="og:title" content="{html.escape(social_title, quote=True)}"><meta property="og:description" content="{html.escape(description, quote=True)}"><meta property="og:image" content="https://bolens.github.io/homelab/social-card.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Homelab Atlas service catalog and architecture guide">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{html.escape(social_title, quote=True)}"><meta name="twitter:description" content="{html.escape(description, quote=True)}"><meta name="twitter:image" content="https://bolens.github.io/homelab/social-card.png"><meta name="twitter:image:alt" content="Homelab Atlas service catalog and architecture guide">
<title>{html.escape(social_title)}</title><link rel="icon" href="/homelab/favicon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="/homelab/apple-touch-icon.png"><link rel="manifest" href="/homelab/site.webmanifest"><script src="/homelab/theme.js"></script><link rel="stylesheet" href="/homelab/styles.css"><link rel="stylesheet" href="/homelab/theme-modes.css"></head>
<body>{header(active)}<main id="main" tabindex="-1">{body}</main>{footer()}</body></html>
'''


def load_stacks() -> list[dict]:
    records = []
    for directory in sorted(path for path in STACKS.iterdir() if path.is_dir()):
        if subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", str(directory.relative_to(ROOT))],
            check=False,
        ).returncode == 0:
            continue
        metadata_path = directory / "stack.yaml"
        readme = directory / "README.md"
        if not metadata_path.exists() or not readme.exists():
            continue
        data = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
        first_line = readme.read_text(encoding="utf-8").splitlines()[0]
        data["display_name"] = first_line.removeprefix("# ").strip() or directory.name
        data["summary"] = summary(readme)
        data["slug"] = directory.name
        data["category_name"] = CATEGORY_NAMES.get(data.get("category", "utility"), label(data.get("category", "utility")))
        records.append(data)
    return records


def risk_tags(item: dict) -> list[tuple[str, str]]:
    tags = []
    if item["data_profile"]["contains_pii"]:
        tags.append(("Personal data", "warning"))
    if item["host_requirements"]["needs_privileged"]:
        tags.append(("Privileged access", "danger"))
    if item["host_requirements"]["uses_host_network"]:
        tags.append(("Host network", "danger"))
    if item["runtime_security"].get("docker_socket_services"):
        tags.append(("Docker control", "danger"))
    if item["runtime_security"].get("floating_image_services"):
        tags.append(("Floating image", "warning"))
    if not tags:
        tags.append(("Standard isolation", "safe"))
    return tags


def cards(items: list[dict]) -> str:
    result = []
    for item in items:
        tags = "".join(f'<span class="tag {kind}">{html.escape(text)}</span>' for text, kind in risk_tags(item))
        result.append(f'''<article class="app-card" data-name="{html.escape(item['display_name'])}" data-category="{html.escape(item['category_name'])}" data-summary="{html.escape(item['summary'], quote=True)}">
<div class="card-meta"><span>{html.escape(item['category_name'])}</span>{tags}</div>
<h2><a href="{item['slug']}/">{html.escape(item['display_name'])}</a></h2><p>{html.escape(item['summary'])}</p>
<a class="text-link" href="{item['slug']}/">What to know <span aria-hidden="true">→</span></a></article>''')
    return "".join(result)


def home(items: list[dict]) -> str:
    categories = sorted({item["category_name"] for item in items})
    category_links = "".join(f'<a class="category" href="apps/?category={quote(name)}">{html.escape(name)}</a>' for name in categories)
    body = f'''<section class="hero"><span class="eyebrow">Your guide to the homelab</span><h1>Find the service that fits the job.</h1>
<p>Browse {len(items)} self-hosted applications by what they do. Each guide explains the service, its dependencies, and the safety choices to review before deployment.</p>
<div class="hero-actions"><a class="button primary" href="apps/">Browse applications</a><a class="button secondary" href="architecture/">See how it works</a></div></section>
<section class="content-section" aria-labelledby="browse-title"><span class="eyebrow">Browse by need</span><h2 id="browse-title">What do you want to run?</h2><div class="category-grid">{category_links}</div></section>
<section class="content-section split" aria-labelledby="reference-title"><div><span class="eyebrow">Two levels of detail</span><h2 id="reference-title">Start here. Build from the repository.</h2></div>
<div><p>This site helps you choose and understand services. When you are ready to deploy one, follow its technical setup in the repository.</p><a class="text-link" href="{REPO_URL}">Open the technical documentation <span aria-hidden="true">→</span></a></div></section>
<section class="content-section" aria-labelledby="topology-title"><div class="section-heading"><div><span class="eyebrow">Interactive map</span><h2 id="topology-title">See how requests reach each service</h2></div><a class="text-link" href="topology.html">Open full screen <span aria-hidden="true">↗</span></a></div>
<p class="section-intro" id="topology-description">The map shows internet access, private access, application groups, shared services, monitoring, and administrator control.</p>
<div class="topology-frame"><iframe src="topology.html" title="Interactive Docker homelab architecture" aria-describedby="topology-description"></iframe></div>
<noscript><p><a href="topology-dark.png">View the static topology image</a>.</p></noscript></section>'''
    return page("Home", "Find and understand the applications available in this Docker homelab.", body)


def catalog(items: list[dict]) -> str:
    options = "".join(f'<option value="{html.escape(name, quote=True)}">{html.escape(name)}</option>' for name in sorted({i["category_name"] for i in items}))
    body = f'''<section class="page-intro"><span class="eyebrow">Application catalog</span><h1>Choose a service by what it does.</h1><p>Search by application name or purpose. Filter by category when you already know the kind of service you need.</p></section>
<section class="catalog-tools" aria-label="Catalog filters"><div><label for="search">Search applications</label><input id="search" type="search" placeholder="Try photo backup, notes, or monitoring"></div>
<div><label for="category">Category</label><select id="category"><option value="">All categories</option>{options}</select></div></section>
<p class="results-status" id="results-status" role="status" aria-live="polite">Showing all {len(items)} applications.</p>
<section class="app-grid" id="app-grid" aria-label="Applications">{cards(items)}</section><p class="empty-state" id="empty-state" hidden>No applications match those filters.</p>
<script src="/homelab/search.js" defer></script>'''
    return page("Applications", "Search the homelab application catalog by name, purpose, or category.", body, "Apps", "apps/")


def detail(item: dict) -> str:
    tags = "".join(f'<span class="tag {kind}">{html.escape(text)}</span>' for text, kind in risk_tags(item))
    dependencies = ", ".join(item.get("shared_resources") or []) or "No shared resources"
    exposure = "Caddy route available; choose an access policy" if item["exposure"]["behind_caddy"] else "No Caddy route in the example"
    backup = "Backups recommended" if item["data_profile"]["recommended_backup"] else "No persistent backup requirement recorded"
    repo = f"{REPO_URL}/tree/main/stacks/{item['slug']}"
    body = f'''<article class="detail"><a class="back-link" href="../">← All applications</a><header class="detail-header"><span class="eyebrow">{html.escape(item['category_name'])}</span><h1>{html.escape(item['display_name'])}</h1><p>{html.escape(item['summary'])}</p><div class="tag-row">{tags}</div></header>
<section aria-labelledby="overview"><h2 id="overview">What to know</h2><dl class="facts"><div><dt>Access</dt><dd>{html.escape(exposure)}</dd></div><div><dt>Login</dt><dd>{html.escape(label(item['auth']['mode']))}</dd></div><div><dt>Shared services</dt><dd>{html.escape(dependencies)}</dd></div><div><dt>Backups</dt><dd>{html.escape(backup)}</dd></div><div><dt>Resource size</dt><dd>{html.escape(label(item['resources']['memory_profile']))}</dd></div><div><dt>Lifecycle</dt><dd>{html.escape(label(item['lifecycle']['status']))}</dd></div></dl></section>
<section class="callout" aria-labelledby="setup"><h2 id="setup">Ready for the technical setup?</h2><p>The stack README documents configuration, storage, networking, deployment, verification, upgrades, and troubleshooting.</p><a class="button primary" href="{repo}">View technical setup</a></section></article>'''
    return page(item["display_name"], item["summary"], body, "Apps", f"apps/{item['slug']}/")


def architecture() -> str:
    body = '''<section class="page-intro"><span class="eyebrow">How it works</span><h1>Four steps connect you to an application.</h1><p>The homelab keeps public, private, and administrative access separate. Applications join only the networks they need.</p></section>
<ol class="steps"><li><strong>You request a service.</strong><p>You use a public hostname, a private network, or an administrator connection.</p></li><li><strong>The access layer checks the route.</strong><p>Cloudflare handles public entry. Private connections stay on the private network.</p></li><li><strong>Caddy sends the request to one application.</strong><p>Separate ingress networks limit which applications can receive each kind of request.</p></li><li><strong>Shared services support the application.</strong><p>Dedicated networks connect storage, databases, downloads, AI tools, and monitoring without exposing them publicly.</p></li></ol>
<section class="callout"><h2>Explore the complete map</h2><p>Use the interactive topology to trace relationships, search for a service, or isolate one part of the system.</p><a class="button primary" href="/homelab/topology.html">Open the topology</a></section>'''
    return page("How it works", "A plain-language guide to homelab access, routing, isolation, and shared services.", body, "How it works", "architecture/")


def safety() -> str:
    body = '''<section class="page-intro"><span class="eyebrow">Safety guide</span><h1>Check the access and data choices before you deploy.</h1><p>Self-hosting moves responsibility for access, updates, and backups to the operator. The catalog marks services that need extra review.</p></section>
<section class="guidance-grid"><article><span class="tag warning">Personal data</span><h2>Protect private records</h2><p>Photos, documents, messages, identity data, and account records need restricted access and tested backups.</p></article><article><span class="tag danger">Privileged access</span><h2>Review host control</h2><p>A privileged container, host networking, or Docker socket access can affect more than one application.</p></article><article><span class="tag safe">Standard isolation</span><h2>Keep the default boundary</h2><p>A standard label means the recorded stack avoids the high-risk runtime flags. You must still review passwords, routes, and storage.</p></article><article><h2>Back up persistent data</h2><p>Back up application data and databases before upgrades. Test that you can restore them.</p></article></section>
<section class="callout"><h2>Use the technical checks before deployment</h2><p>Every stack README lists its configuration and verification steps. The repository also documents shared networks, secrets, monitoring, and troubleshooting.</p><a class="button primary" href="https://github.com/bolens/homelab/blob/main/documents/GETTING-STARTED.md">Read the deployment guide</a></section>'''
    return page("Safety", "Understand access, personal data, host permissions, and backup choices before deploying a service.", body, "Safety", "safety/")


def expected_files(items: list[dict]) -> dict[str, bytes]:
    routes = ["", "apps/", "architecture/", "safety/"] + [
        f"apps/{item['slug']}/" for item in items
    ]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{PUBLIC_ROOT}{route}</loc></url>\n" for route in routes)
        + "</urlset>\n"
    )
    llms = f"""# Homelab Atlas

Homelab Atlas is a public catalog and safety guide for the self-hosted applications defined in the bolens/homelab repository. Each application page summarizes purpose, access, dependencies, persistence, and elevated runtime requirements; the repository remains the source of truth for deployment.

## Documentation

- Home: {PUBLIC_ROOT}
- Application catalog: {PUBLIC_ROOT}apps/
- Architecture: {PUBLIC_ROOT}architecture/
- Safety guide: {PUBLIC_ROOT}safety/
- Interactive topology: {PUBLIC_ROOT}topology.html

## Source

- Repository: {REPO_URL}
- Getting started: {REPO_URL}/blob/main/documents/GETTING-STARTED.md
- Stack definitions: {REPO_URL}/tree/main/stacks
"""
    expected = {
        "index.html": home(items).encode(), "apps/index.html": catalog(items).encode(),
        "architecture/index.html": architecture().encode(), "safety/index.html": safety().encode(),
        "topology.html": (ROOT / "documents/topology.html").read_bytes(),
        "topology-dark.png": (ROOT / "documents/topology-dark.png").read_bytes(),
        "robots.txt": f"User-agent: *\nAllow: /\n\nSitemap: {PUBLIC_ROOT}sitemap.xml\n".encode(),
        "sitemap.xml": sitemap.encode(),
        "llms.txt": llms.encode(),
    }
    for item in items:
        expected[f"apps/{item['slug']}/index.html"] = detail(item).encode()
    data = [{"name": i["display_name"], "category": i["category_name"], "summary": i["summary"], "url": f"apps/{i['slug']}/"} for i in items]
    expected["catalog-data.json"] = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode()
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    items = load_stacks()
    expected = expected_files(items)
    if args.check:
        stale = [name for name, content in expected.items() if not (PUBLIC / name).exists() or (PUBLIC / name).read_bytes() != content]
        if stale:
            raise SystemExit("Pages site is stale: " + ", ".join(stale[:10]))
        print(f"Pages site is current ({len(items)} application pages).")
        return
    for directory in (PUBLIC / "apps", PUBLIC / "architecture", PUBLIC / "safety"):
        if directory.exists():
            shutil.rmtree(directory)
    for name, content in expected.items():
        path = PUBLIC / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print(f"Updated Pages site ({len(items)} application pages).")


if __name__ == "__main__":
    main()
