#!/usr/bin/env python3
"""
Generate the topology Mermaid diagram and prose from documents/topology.yaml.
Run from the docker/ repo root.

  python3 scripts/build-topology.py           # print generated section to stdout
  python3 scripts/build-topology.py --in-place   # update README.md between markers

Requires: PyYAML (pip install pyyaml)
"""

from pathlib import Path
import re
import sys

try:
    import yaml
except ImportError:
    sys.stderr.write("Need PyYAML: pip install pyyaml\n")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
TOPOLOGY_YAML = REPO_ROOT / "documents" / "topology.yaml"
README_PATH = REPO_ROOT / "README.md"
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


def build_mermaid(data: dict) -> str:
    # Linear edges so GitHub (and other renderers) don't use curves that obscure labels
    lines = [
        "%%{init: {'flowchart': {'curveStyle': 'linear'}}}%%",
        "flowchart TB",
        "    subgraph internet[\"Internet / LAN\"]",
        "        users[\"Clients\"]",
        "        outbound[\"Internet<br>(outbound)\"]",
        "    end",
        "",
    ]
    # Ingress
    lines.append('    subgraph ingress["Ingress"]')
    for item in data["ingress"]:
        nid = mermaid_node_id(item["id"])
        lines.append(f'        {nid}["{mermaid_quote(item["label"])}"]')
    lines.append("    end")
    lines.append("")
    # VPN
    lines.append('    subgraph vpn["VPN & remote access"]')
    lines.append("        direction TB")
    for item in data["vpn"]:
        nid = mermaid_node_id(item["id"])
        lines.append(f'        {nid}["{mermaid_quote(item["label"])}"]')
    lines.append("    end")
    lines.append("")
    # App categories
    lines.append('    subgraph apps["Application stacks"]')
    lines.append("        direction TB")
    for cat in data["app_categories"]:
        nid = mermaid_node_id(cat["id"])
        stack_list = ", ".join(cat["stacks"])
        label = f"{cat['name']}<br>({stack_list})"
        lines.append(f'        {nid}["{mermaid_quote(label)}"]')
    lines.append("    end")
    lines.append("")
    # Infra
    lines.append('    subgraph infra["Infrastructure & monitoring"]')
    lines.append("        direction TB")
    for item in data["infra"]:
        nid = mermaid_node_id(item["id"])
        lines.append(f'        {nid}["{mermaid_quote(item["label"])}"]')
    lines.append("    end")
    lines.append("")
    # Edges: unlabeled first (cleaner layout), then labeled in groups by target/source
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
    # Labeled edges: short labels + longer link (-..->) to space labels and reduce overlap
    lines.append("    wireguard -..->|VPN| caddy")
    lines.append("    headscale -..->|mesh| caddy")
    for cat_id in data.get("gluetun_egress", []):
        nid = mermaid_node_id(cat_id)
        lines.append(f"    {nid} -..->|VPN egress| gluetun")
    lines.append("    gluetun -..->|egress| outbound")
    lines.append("    caddy -..->|logs| crowdsec")
    for cat_id in data.get("smtp_clients", []):
        nid = mermaid_node_id(cat_id)
        lines.append(f"    {nid} -..->|mail| postfix")
    lines.append("    kuma -..->|health| caddy")
    lines.append("    prometheus -..->|scrapes| cadvisor")
    lines.append("    grafana -..->|queries| prometheus")
    lines.append("    watchtower -..->|updates| apps")
    lines.append("    dockergc -..->|cleanup| apps")
    lines.append("    diun -..->|notify| users")
    lines.append("    portainer -..->|manage| apps")
    return "\n".join(lines)


def build_prose(data: dict) -> str:
    cat_bits = [f"**{cat['name']}** – {cat['description']}" for cat in data["app_categories"]]
    categories_para = ". ".join(cat_bits)

    return f"""- **Traffic:** All HTTP(S) to apps and to web UIs (e.g. Uptime Kuma, Grafana) goes through Caddy. Clients reach Caddy directly (local DNS) or via Cloudflare Tunnel; Caddy routes by hostname.
- **VPN & remote access:** **Headscale** – mesh VPN (Tailscale); mesh clients reach Caddy and apps. **WireGuard** – remote-access VPN (UDP 51820); VPN clients connect from outside. **Gluetun** – outbound VPN for containers; media acquisition stacks (e.g. qbittorrent) send traffic through Gluetun to a VPN provider.
- **Application categories:** {categories_para}
- **Infrastructure:** Portainer manages stacks; Watchtower updates images; Docker GC cleans up; Diun notifies on image changes; Uptime Kuma monitors Caddy and app health; Grafana/Prometheus/cAdvisor provide metrics; CrowdSec consumes Caddy logs. **Postfix** – SMTP relay for outbound mail from apps (e.g. Naisho, n8n). Dozzle (behind Caddy) is a log viewer."""


def generated_section(mermaid: str, prose: str) -> str:
    return f"""{MARKER_START}
```mermaid
{mermaid}
```

{prose}
{MARKER_END}"""


def main():
    in_place = "--in-place" in sys.argv
    data = load_topology()
    mermaid = build_mermaid(data)
    prose = build_prose(data)
    section = generated_section(mermaid, prose)

    if in_place:
        readme = README_PATH.read_text(encoding="utf-8")
        if MARKER_START not in readme or MARKER_END not in readme:
            sys.stderr.write("README.md must contain TOPOLOGY_GENERATED_START and TOPOLOGY_GENERATED_END markers.\n")
            sys.exit(1)
        pattern = re.compile(
            re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
            re.DOTALL,
        )
        new_readme = pattern.sub(section, readme)
        if new_readme == readme:
            sys.stderr.write("No change.\n")
        else:
            README_PATH.write_text(new_readme, encoding="utf-8")
            sys.stderr.write("Updated README.md\n")
    else:
        print(section)


if __name__ == "__main__":
    main()
