#!/usr/bin/env python3
"""
Generate the topology document from documents/topology.yaml.
Run from the docker/ repo root.

  python3 scripts/build-topology.py           # print generated section to stdout
  python3 scripts/build-topology.py --in-place   # update documents/TOPOLOGY.md
  python3 scripts/build-topology.py --check      # fail if generated output is stale

Requires: PyYAML (pip install pyyaml)
"""

from pathlib import Path
import sys

try:
    import yaml
except ImportError:
    sys.stderr.write("Need PyYAML: pip install pyyaml\n")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
TOPOLOGY_YAML = REPO_ROOT / "documents" / "topology.yaml"
OUTPUT_PATH = REPO_ROOT / "documents" / "TOPOLOGY.md"
MARKER_START = "<!-- TOPOLOGY_GENERATED_START -->"
MARKER_END = "<!-- TOPOLOGY_GENERATED_END -->"


def load_topology():
    with open(TOPOLOGY_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_prose(data: dict) -> str:
    cat_bits = [f"**{cat['name']}** – {cat['description']}" for cat in data["app_categories"]]
    categories_para = ". ".join(cat_bits)

    # Application stacks detail: each category with full description and stack list
    stack_detail_lines = []
    for cat in data["app_categories"]:
        stacks_str = ", ".join(cat["stacks"])
        stack_detail_lines.append(f"- **{cat['name']}:** {cat['description']} Stacks: {stacks_str}.")
    stacks_detail = "\n".join(stack_detail_lines)

    main = f"""- **Traffic:** All HTTP(S) to apps and to web UIs (e.g. Uptime Kuma, Grafana) goes through Caddy. Clients reach Caddy directly (local DNS) or via Cloudflare Tunnel; Caddy routes by hostname.
- **VPN & remote access:** **Headscale** – mesh VPN (Tailscale); mesh clients reach Caddy and apps. **WireGuard** – remote-access VPN (UDP 51820); VPN clients connect from outside. **Gluetun** – outbound VPN for containers; media acquisition stacks (e.g. qbittorrent) send traffic through Gluetun to a VPN provider.
- **Application categories:** {categories_para}
- **Application stacks (detail):** Each category and what it does:
{stacks_detail}
- **Infrastructure:** Portainer manages stacks; Watchtower updates images; Docker GC cleans up; Diun notifies on image changes; Uptime Kuma monitors Caddy and app health; Grafana/Prometheus/cAdvisor provide metrics; CrowdSec consumes Caddy logs. **MinIO** provides S3-compatible object storage, often used as a backend for apps and backups; **Restic** handles scheduled backups to object storage; **Scrutiny** monitors disk SMART health. **Postfix** – SMTP relay for outbound mail from apps (e.g. Naisho, n8n). Dozzle (behind Caddy) is a log viewer."""

    relations = data.get("relations", [])
    if not relations:
        return main
    rel_bullets = []
    for r in relations:
        from_id = r.get("from", "")
        to_id = r.get("to", "")
        label = r.get("label")
        desc = r.get("description", "")
        arrow = f"**{from_id} → {to_id}**"
        if label:
            arrow += f" ({label})"
        rel_bullets.append(f"{arrow}: {desc}")
    rel_section = "- **Relations:**\n  - " + "\n  - ".join(rel_bullets)
    return main + "\n" + rel_section


def generated_section(prose: str) -> str:
    return f"""{MARKER_START}
[![Docker homelab architecture](topology-dark.png)](topology.html)

[Open the interactive architecture diagram](topology.html). Its controls support
theme switching, pan and zoom, relationship tracing, and export. The checked
[Archify source](topology.architecture.json) records the diagram's components
and connections.

{prose}
{MARKER_END}"""


def main():
    in_place = "--in-place" in sys.argv
    check = "--check" in sys.argv
    data = load_topology()
    prose = build_prose(data)
    section = generated_section(prose)

    document = (
        "# Homelab topology\n\n"
        "Generated from `documents/topology.yaml`. Do not edit the generated "
        "section directly.\n\n"
        f"{section.rstrip()}\n"
    )
    if check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
        if current != document:
            sys.stderr.write("documents/TOPOLOGY.md is stale; regenerate it.\n")
            sys.exit(1)
        print("Topology document is current.")
    elif in_place:
        OUTPUT_PATH.write_text(document, encoding="utf-8")
        sys.stderr.write("Updated documents/TOPOLOGY.md\n")
    else:
        print(document, end="")


if __name__ == "__main__":
    main()
