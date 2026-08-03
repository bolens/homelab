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


def mermaid_node_id(s: str) -> str:
    """Mermaid node IDs must be alphanumeric or underscore."""
    return s.replace("-", "_")


def mermaid_quote(s: str) -> str:
    """Escape quotes in Mermaid labels."""
    return s.replace('"', "#quot;")


def mermaid_label(s: str) -> str:
    """Markdown-style label: use actual newlines in the diagram source so Mermaid renders line breaks."""
    s = s.replace("\r", " ").replace("\n", " ")  # normalize YAML newlines to space
    content = s.replace("<br/>", "\n").replace("<br>", "\n").replace("`", "'").replace('"', "#quot;")
    return "`" + content + "`"


def _init_line() -> str:
    return "%%{init: {'flowchart': {'curveStyle': 'linear'}}}%%"


def build_mermaid_main(data: dict) -> str:
    """Traffic, ingress, VPN, apps; infra as a single node. Short labels = narrow diagram."""
    lines = [_init_line(), "flowchart TB", ""]
    lines.extend([
        '    subgraph internet["Internet / LAN"]',
        '        users["Clients"]',
        '        outbound["Internet"]',
        "    end",
        "",
    ])
    lines.append('    subgraph ingress["Ingress"]')
    for item in data["ingress"]:
        nid = mermaid_node_id(item["id"])
        line = f'        {nid}["{mermaid_label(item["label"])}"]'
        lines.append(line)
    lines.append("    end")
    lines.append("")
    lines.append('    subgraph vpn["VPN & remote access"]')
    lines.append("        direction TB")
    for item in data["vpn"]:
        nid = mermaid_node_id(item["id"])
        line = f'        {nid}["{mermaid_label(item["label"])}"]'
        lines.append(line)
    lines.append("    end")
    lines.append("")
    lines.append("    internet ~~~ ingress ~~~ vpn")
    lines.append("")
    # App categories: name + short descriptor
    lines.append('    subgraph apps["Application stacks"]')
    lines.append("        direction TB")
    app_ids = [mermaid_node_id(cat["id"]) for cat in data["app_categories"]]
    for cat in data["app_categories"]:
        nid = mermaid_node_id(cat["id"])
        label = cat["name"]
        if cat.get("descriptor"):
            label = f'{label}<br>{cat["descriptor"]}'
        line = f'        {nid}["{mermaid_label(label)}"]'
        lines.append(line)
    lines.append("    end")
    # Invisible chain forces single column = less horizontal spread
    if len(app_ids) > 1:
        chain = " ~~~ ".join(app_ids)
        lines.append(f"    {chain}")
    lines.append("")
    line = '    infra["' + mermaid_label("Infra<br>& monitoring") + '"]'
    lines.append(line)
    lines.append("")
    lines.append("    users --> tunnel")
    lines.append("    users --> caddy")
    lines.append("    tunnel --> caddy")
    lines.append("    users --> wireguard")
    lines.append("    users --> headscale")
    for cat in data["app_categories"]:
        nid = mermaid_node_id(cat["id"])
        lines.append(f"    caddy --> {nid}")
    lines.append("    caddy --> infra")
    lines.append("")
    lines.append("    wireguard -.->|VPN| caddy")
    lines.append("    headscale -.->|mesh| caddy")
    for cat_id in data.get("gluetun_egress", []):
        nid = mermaid_node_id(cat_id)
        lines.append(f"    {nid} -.->|VPN egress| gluetun")
    lines.append("    gluetun -.->|egress| outbound")
    # Mail goes to infra (Postfix lives there); postfix node only exists in the infra diagram
    for cat_id in data.get("smtp_clients", []):
        nid = mermaid_node_id(cat_id)
        lines.append(f"    {nid} -.->|mail| infra")
    return "\n".join(lines)


def build_mermaid_infra(data: dict) -> str:
    """Infrastructure & monitoring nodes and their labeled edges only. TB = vertical layout."""
    lines = [_init_line(), "flowchart TB", ""]
    lines.append('    subgraph infra["Infrastructure & monitoring"]')
    lines.append("        direction TB")
    infra_ids = [mermaid_node_id(item["id"]) for item in data["infra"]]
    for item in data["infra"]:
        nid = mermaid_node_id(item["id"])
        line = f'        {nid}["{mermaid_label(item["label"])}"]'
        lines.append(line)
    lines.append("    end")
    # Invisible chain keeps infra nodes in one column
    if len(infra_ids) > 1:
        chain = " ~~~ ".join(infra_ids)
        lines.append(f"    {chain}")
    lines.append("")
    lines.append('    caddy["caddy"]')
    lines.append('    apps["apps"]')
    lines.append('    users["users"]')
    lines.append("")
    lines.append("    caddy -.->|logs| crowdsec")
    lines.append("    kuma -.->|health| caddy")
    lines.append("    prometheus -.->|scrapes| cadvisor")
    lines.append("    grafana -.->|queries| prometheus")
    lines.append("    watchtower -.->|updates| apps")
    lines.append("    dockergc -.->|cleanup| apps")
    lines.append("    diun -.->|notify| users")
    lines.append("    portainer -.->|manage| apps")
    return "\n".join(lines)


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


def generated_section(mermaid_main: str, mermaid_infra: str, prose: str) -> str:
    return f"""{MARKER_START}
```mermaid
{mermaid_main}
```

#### Infrastructure & monitoring

```mermaid
{mermaid_infra}
```

{prose}
{MARKER_END}"""


def main():
    in_place = "--in-place" in sys.argv
    check = "--check" in sys.argv
    data = load_topology()
    mermaid_main = build_mermaid_main(data)
    mermaid_infra = build_mermaid_infra(data)
    prose = build_prose(data)
    section = generated_section(mermaid_main, mermaid_infra, prose)

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
