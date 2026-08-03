#!/usr/bin/env python3
"""
Rebuild blackbox_nonalert + blackbox_http_paths_nonalert from documents/MONITORING-TARGETS.md,
union any existing targets in prometheus.yml.example so nothing is dropped if the doc lags.

Tier-1 alerting jobs (blackbox_public / blackbox_http_paths_public) are left unchanged except
sample_limit sanity; inventory lists are replaced.

Usage (from repo root):
  python3 scripts/sync_blackbox_targets_from_monitoring.py stacks/prometheus/prometheus.yml.example
  python3 scripts/sync_blackbox_targets_from_monitoring.py /home/you/.config/prometheus/prometheus.yml --domain example.com
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "documents" / "MONITORING-TARGETS.md"

TIER1_ROOTS_EXAMPLE = {
    "https://alertmanager.example.com",
    "https://auth.example.com",
    "https://authentik.example.com",
    "https://booking.example.com",
    "https://crowdsec.example.com",
    "https://gitea.example.com",
    "https://grafana.example.com",
    "https://paperless.example.com",
    "https://portainer.example.com",
    "https://prometheus.example.com",
    "https://vault.example.com",
}

CRITICAL_PATHS_EXAMPLE = {
    "http://immich-machine-learning:3003/ping",
    "https://alertmanager.example.com/-/healthy",
    "https://authentik.example.com/",
    "https://crowdsec.example.com/health",
    "https://gitea.example.com/api/healthz",
    "https://immich.example.com/api/server/ping",
    "https://portainer.example.com/api/status",
    "https://prometheus.example.com/-/healthy",
    "https://vault.example.com/alive",
}

# Hosts documented elsewhere or historically probed; merge if missing from MONITORING-TARGETS.md.
EXTRA_ROOTS_EXAMPLE = [
    "https://defectdojo.example.com",
    "https://diagrams-net.example.com",
    "https://logseq-sync.example.com",
]

# Full path probes not reliably derivable from the markdown Path column.
EXTRA_PATHS_EXAMPLE = [
    "https://presidio.example.com/analyzer/health",
    "https://presidio.example.com/anonymizer/health",
    "https://presidio.example.com/image-redactor/health",
]


def _swap_domain(url: str, domain: str) -> str:
    if domain == "example.com":
        return url
    return re.sub(r"\.example\.com\b", f".{domain}", url)


def _extract_markdown_url(cell: str) -> str | None:
    m = re.search(r"\((https?://[^)]+)\)", cell)
    return m.group(1).strip() if m else None


def _normalize_path_fragment(raw: str) -> str | None:
    s = raw.strip().strip("`").strip()
    if not s or s in ("—", "-", "—"):
        return None
    if s.lower() in ("/", "int:", "ext:"):
        return None
    # Strip surrounding quotes
    s = s.strip('"').strip("'")
    # First path token when cell has prose (e.g. "Use path `/x`")
    m = re.search(r"`([^`]+)`", raw)
    if m:
        s = m.group(1).strip()
    if not s.startswith("/"):
        return None
    return s


def parse_monitoring_targets(md_text: str) -> tuple[set[str], set[str]]:
    roots: set[str] = set()
    paths: set[str] = set()
    for line in md_text.splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        if "Monitor name" in line and "URL [Ext]" in line:
            continue
        raw = line.strip()
        if raw.startswith("|"):
            raw = raw[1:]
        if raw.endswith("|"):
            raw = raw[:-1]
        cells = [c.strip() for c in raw.split("|")]
        if len(cells) < 7:
            continue
        ext_cell = cells[1]
        blackbox_cell = cells[5]
        path_cell = cells[6]
        if not blackbox_cell.startswith("✓"):
            continue
        base = _extract_markdown_url(ext_cell)
        if not base or not base.startswith("http"):
            continue
        p = urlparse(base)
        if not p.netloc:
            continue
        root = f"{p.scheme}://{p.netloc}"
        roots.add(root)
        frag = _normalize_path_fragment(path_cell)
        if frag and frag != "/":
            joined = urljoin(root + "/", frag.lstrip("/"))
            paths.add(joined)
    return roots, paths


def extract_job_targets(yaml_text: str, job: str) -> list[str]:
    anchor = f"  - job_name: {job}\n"
    start = yaml_text.find(anchor)
    if start < 0:
        return []
    rest = yaml_text[start:]
    m = re.search(r"\n  (?:- job_name:|# ICMP:)", rest[1:])
    end = start + 1 + m.start()
    block = yaml_text[start:end]
    sc = block.find("    static_configs:\n")
    tline = block.find("      - targets", sc)
    if tline < 0:
        return []
    line_end = block.find("\n", tline) + 1
    rpos = block.find("\n    relabel_configs:", line_end)
    if rpos < 0:
        return []
    chunk = block[line_end:rpos]
    return re.findall(r"^\s+- (https?://\S+|http://immich-machine-learning:\S+)\s*$", chunk, re.M)


def replace_job_targets_block(yaml_text: str, job: str, targets: list[str]) -> str:
    anchor = f"  - job_name: {job}\n"
    start = yaml_text.find(anchor)
    if start < 0:
        raise SystemExit(f"job not found: {job}")
    rest = yaml_text[start:]
    m = re.search(r"\n  (?:- job_name:|# ICMP:)", rest[1:])
    end = start + 1 + m.start()
    block = yaml_text[start:end]
    sc = block.find("    static_configs:\n")
    if sc < 0:
        raise SystemExit(f"static_configs not found for {job}")
    tline = block.find("      - targets", sc)
    if tline < 0:
        raise SystemExit(f"targets key not found for {job}")
    line_end = block.find("\n", tline) + 1
    rpos = block.find("\n    relabel_configs:", line_end)
    if rpos < 0:
        raise SystemExit(f"relabel_configs not found for {job}")
    head = block[:tline] + "      - targets:\n"
    tail = block[rpos:]
    body = "".join(f"          - {t}\n" for t in targets)
    new_block = head + body + tail
    return yaml_text[:start] + new_block + yaml_text[end:]


def bump_sample_limit(yaml_text: str, job: str, limit: int) -> str:
    anchor = f"  - job_name: {job}\n"
    start = yaml_text.find(anchor)
    rest = yaml_text[start:]
    m = re.search(r"\n  (?:- job_name:|# ICMP:)", rest[1:])
    end = start + 1 + m.start()
    block = yaml_text[start:end]
    block2, n = re.subn(r"(?m)^    sample_limit: \d+$", f"    sample_limit: {limit}", block, count=1)
    if n != 1:
        raise SystemExit(f"sample_limit bump failed for {job}")
    return yaml_text[:start] + block2 + yaml_text[end:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prometheus_yml", type=Path)
    ap.add_argument(
        "--domain",
        default="example.com",
        help="Replace .example.com with .yourdomain (default: example.com = no swap)",
    )
    args = ap.parse_args()
    domain = args.domain.strip().lstrip(".")

    md_text = MD_PATH.read_text()
    roots_md, paths_md = parse_monitoring_targets(md_text)

    yml = args.prometheus_yml.read_text()
    existing_non = set(extract_job_targets(yml, "blackbox_nonalert"))
    existing_paths_na = set(extract_job_targets(yml, "blackbox_http_paths_nonalert"))

    tier1 = {_swap_domain(u, domain) for u in TIER1_ROOTS_EXAMPLE}
    critical = {_swap_domain(u, domain) for u in CRITICAL_PATHS_EXAMPLE}

    roots_union = (
        {_swap_domain(u, domain) for u in roots_md}
        | {_swap_domain(u, domain) for u in EXTRA_ROOTS_EXAMPLE}
        | existing_non
    ) - tier1

    paths_union = (
        {_swap_domain(u, domain) for u in paths_md}
        | {_swap_domain(u, domain) for u in EXTRA_PATHS_EXAMPLE}
        | existing_paths_na
    ) - critical

    # Cal.com: doc lists calcom host; tier-1 uses booking — keep both roots (booking tier1, calcom inventory).
    # Dedupe apex vs trailing slash for stability
    def norm_root(u: str) -> str:
        if u.startswith("http") and u.endswith("/") and u.count("/") > 2:
            return u.rstrip("/")
        return u

    roots_sorted = sorted({norm_root(u) for u in roots_union})
    paths_sorted = sorted(paths_union)

    lim_roots = max(400, len(roots_sorted) + 50)
    lim_paths = max(120, len(paths_sorted) + 30)

    yml = replace_job_targets_block(yml, "blackbox_nonalert", roots_sorted)
    yml = replace_job_targets_block(yml, "blackbox_http_paths_nonalert", paths_sorted)
    yml = bump_sample_limit(yml, "blackbox_nonalert", lim_roots)
    yml = bump_sample_limit(yml, "blackbox_http_paths_nonalert", lim_paths)

    args.prometheus_yml.write_text(yml)
    print(
        f"Updated {args.prometheus_yml}: nonalert_roots={len(roots_sorted)} "
        f"paths_nonalert={len(paths_sorted)} sample_limits={lim_roots}/{lim_paths} domain={domain}"
    )


if __name__ == "__main__":
    main()
