#!/usr/bin/env python3
"""Validate stack.yaml catalog metadata and optionally create missing records."""

from __future__ import annotations

import argparse
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
STACKS = REPO / "stacks"
REQUIRED = {
    "name",
    "default_port",
    "databases",
    "health",
    "monitoring",
    "shared_resources",
    "type",
    "category",
    "exposure",
    "data_profile",
    "host_requirements",
    "links",
    "backup",
    "volumes",
    "auth",
    "resources",
    "placement",
    "lifecycle",
}
TYPES = {"api", "cli_tool", "service", "web_app"}
PROFILES = {"small", "medium", "large"}
GPU_PROFILES = {"none", "required"}
NESTED_REQUIRED = {
    "health": {"endpoint", "internal_only"},
    "monitoring": {"prometheus", "uptime_kuma", "blackbox_exporter", "grafana_dashboard"},
    "exposure": {"behind_caddy", "public_by_default", "recommended_hostname"},
    "data_profile": {"contains_pii", "contains_logs_only", "recommended_backup"},
    "host_requirements": {"needs_gpu", "needs_privileged", "uses_host_network"},
    "links": {"homepage", "docs", "repo"},
    "backup": {"priority", "schedule_hint"},
    "auth": {"mode", "sso_provider", "access_policy"},
    "resources": {"cpu_profile", "memory_profile", "storage_profile", "gpu_profile"},
    "placement": {"preferred_node", "colocation_group"},
    "lifecycle": {"status", "replacement_for", "notes"},
}
TYPE_OVERRIDES = {
    "cowrie": "service", "databasus": "web_app", "dbgate": "web_app",
    "dionaea-conpot": "service", "dispatcharr": "web_app", "ersatztv": "web_app",
    "gitlab": "web_app", "gitlab-runners": "service", "gotenberg": "api",
    "netboot.xyz": "web_app", "netbox": "web_app", "ombi": "web_app",
    "openspeedtest": "web_app", "peanut": "web_app", "postiz": "web_app",
    "rustfs": "api", "scrypted": "web_app", "tika": "api",
    "rtorrent": "service", "rutorrent": "web_app",
}
PORT_OVERRIDES = {
    "cowrie": 2222, "dbgate": 3000, "ersatztv": 8409, "flood": 3000,
    "gotenberg": 3000, "netboot.xyz": 3000, "netbox": 8080, "ombi": 3579,
    "openspeedtest": 3000, "peanut": 3000, "rtorrent": None, "rutorrent": 80,
    "scrypted": 10443, "tika": 9998,
}
CATEGORIES = {
    "afl-libfuzzer": "security", "asking": "ai", "atomic-red-team": "security",
    "auth-fuzz": "security", "cowrie": "security", "databasus": "backup",
    "dbgate": "dev", "dionaea-conpot": "security", "dispatcharr": "media",
    "ersatztv": "media", "flood": "downloads", "gitlab": "dev",
    "gitlab-runners": "dev", "gotenberg": "documents", "grafana-alloy": "monitoring",
    "handbrake": "media", "harbor": "dev", "hashcat": "security",
    "influxdb": "monitoring", "kali": "security", "kometa": "media",
    "maloja": "media", "matomo": "analytics", "netboot.xyz": "networking",
    "netbox": "networking", "netexec": "security", "ombi": "media",
    "opengist": "dev", "openspeedtest": "networking", "peanut": "infrastructure",
    "pgadmin": "dev", "pocketbase": "dev", "postiz": "productivity",
    "presidio": "security", "pwntools-gdb": "security", "rackula": "utility",
    "resilio": "storage", "responder-mitm6": "security", "rtorrent": "downloads",
    "rustfs": "storage", "rutorrent": "downloads", "scrypted": "homeautomation",
    "tailscale-exporter": "monitoring", "tautulli": "media",
    "thelounge": "productivity", "tika": "documents",
}


def compose_for(directory: Path) -> dict[str, Any]:
    path = directory / "docker-compose.yml"
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return value if isinstance(value, dict) else {}


def services(compose: dict[str, Any]) -> list[dict[str, Any]]:
    value = compose.get("services") or {}
    return [item for item in value.values() if isinstance(item, dict)]


def infer_port(directory: Path, compose: dict[str, Any]) -> int | None:
    candidates: list[str] = []
    for service in services(compose):
        candidates.append(str((service.get("healthcheck") or {}).get("test", "")))
        for value in service.get("expose") or []:
            candidates.append(str(value))
        for value in service.get("ports") or []:
            candidates.append(str(value).split(":")[-1].split("/")[0])
    caddy = directory / "caddy_snippet.conf.example"
    if caddy.exists():
        candidates.insert(0, caddy.read_text(encoding="utf-8", errors="replace"))
    for text in candidates:
        match = re.search(r"(?:https?://[^:/\s]+:|reverse_proxy\s+[^:\s]+:)(\d+)", text)
        if not match and text.isdigit():
            match = re.match(r"(\d+)", text)
        if match:
            return int(match.group(1))
    return None


def infer_links(directory: Path) -> dict[str, str | None]:
    readme = directory / "README.md"
    text = readme.read_text(encoding="utf-8", errors="replace") if readme.exists() else ""
    def url(label: str) -> str | None:
        match = re.search(rf"\*\*(?:{label}):\*\*\s*(https?://\S+)", text, re.I)
        return match.group(1).rstrip(".,)") if match else None
    return {"homepage": url("Website|Homepage"), "docs": url("Docs"), "repo": url("GitHub")}


def infer_metadata(directory: Path) -> dict[str, Any]:
    compose = compose_for(directory)
    stack_services = services(compose)
    port = PORT_OVERRIDES.get(directory.name, infer_port(directory, compose))
    caddy = (directory / "caddy_snippet.conf.example").exists() and port is not None
    stack_type = TYPE_OVERRIDES.get(
        directory.name,
        "web_app" if caddy or port else ("service" if compose else "cli_tool"),
    )
    networks = compose.get("networks") or {}
    shared = sorted(
        str((value or {}).get("name", key))
        for key, value in networks.items()
        if isinstance(value, dict) and value.get("external") is True
    )
    compose_volumes = compose.get("volumes") or {}
    volumes = []
    for key, value in compose_volumes.items():
        value = value if isinstance(value, dict) else {}
        volumes.append({
            "name": str(value.get("name", key)),
            "role": "app_data",
            "critical": True,
            **({"external": True} if value.get("external") is True else {}),
        })
    cpus = max((float(item.get("cpus", 0) or 0) for item in stack_services), default=0)
    memory_text = " ".join(str(item.get("mem_limit", "")) for item in stack_services).lower()
    large_memory = bool(re.search(r"(?:[1-9]\d|[8-9])g", memory_text))
    gpu = any(item.get("gpus") for item in stack_services)
    privileged = any(item.get("privileged") is True for item in stack_services)
    host_network = any(item.get("network_mode") == "host" for item in stack_services)
    monitored = stack_type == "web_app"
    return {
        "name": directory.name,
        "default_port": port,
        "databases": [],
        "health": {"endpoint": "/", "internal_only": not monitored},
        "monitoring": {
            "prometheus": False,
            "uptime_kuma": {"external": monitored, "internal": monitored},
            "blackbox_exporter": monitored,
            "grafana_dashboard": False,
        },
        "shared_resources": shared,
        "type": stack_type,
        "category": CATEGORIES.get(directory.name, "utility"),
        "exposure": {
            "behind_caddy": caddy,
            "public_by_default": False,
            "recommended_hostname": f"{directory.name}.yourdomain.com" if caddy else None,
        },
        "data_profile": {
            "contains_pii": False,
            "contains_logs_only": False,
            "recommended_backup": bool(volumes),
        },
        "host_requirements": {
            "needs_gpu": gpu,
            "needs_privileged": privileged,
            "uses_host_network": host_network,
        },
        "links": infer_links(directory),
        "backup": {"priority": "medium" if volumes else "low", "schedule_hint": "weekly" if volumes else "manual"},
        "volumes": volumes,
        "auth": {"mode": "app_local" if monitored else "none", "sso_provider": None, "access_policy": "access_full_site"},
        "resources": {
            "cpu_profile": "large" if cpus >= 4 else ("medium" if cpus >= 2 else "small"),
            "memory_profile": "large" if large_memory else ("medium" if cpus >= 2 else "small"),
            "storage_profile": "medium" if volumes else "small",
            "gpu_profile": "required" if gpu else "none",
        },
        "placement": {"preferred_node": None, "colocation_group": None},
        "lifecycle": {"status": "stable", "replacement_for": None, "notes": ""},
    }


def validate(directory: Path, metadata: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(metadata, dict):
        return ["metadata root must be a mapping"]
    missing = sorted(REQUIRED - metadata.keys())
    if missing:
        problems.append(f"missing top-level keys: {', '.join(missing)}")
    unknown = sorted(metadata.keys() - REQUIRED)
    if unknown:
        problems.append(f"unknown top-level keys: {', '.join(unknown)}")
    if metadata.get("name") != directory.name:
        problems.append(f"name must equal directory name '{directory.name}'")
    if metadata.get("type") not in TYPES:
        problems.append(f"type must be one of {sorted(TYPES)}")
    resources = metadata.get("resources") or {}
    for key in ("cpu_profile", "memory_profile", "storage_profile"):
        if resources.get(key) not in PROFILES:
            problems.append(f"resources.{key} must be one of {sorted(PROFILES)}")
    if resources.get("gpu_profile") not in GPU_PROFILES:
        problems.append(f"resources.gpu_profile must be one of {sorted(GPU_PROFILES)}")
    port = metadata.get("default_port")
    if port is not None and (not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535):
        problems.append("default_port must be null or an integer from 1 to 65535")
    for key in ("databases", "shared_resources", "volumes"):
        if not isinstance(metadata.get(key), list):
            problems.append(f"{key} must be a list")
    for index, volume in enumerate(metadata.get("volumes") or []):
        if not isinstance(volume, dict):
            problems.append(f"volumes[{index}] must be a mapping")
            continue
        if volume.get("name") in {"name", "external", None}:
            problems.append(f"volumes[{index}].name is invalid")
        if volume.get("role") not in {"app_data", "cache", "config", "database", "logs", "media"}:
            problems.append(f"volumes[{index}].role is invalid")
        if not isinstance(volume.get("critical"), bool):
            problems.append(f"volumes[{index}].critical must be boolean")
        if "external" in volume and not isinstance(volume.get("external"), bool):
            problems.append(f"volumes[{index}].external must be boolean")
    for group, expected in NESTED_REQUIRED.items():
        value = metadata.get(group)
        if not isinstance(value, dict):
            problems.append(f"{group} must be a mapping")
            continue
        missing_nested = sorted(expected - value.keys())
        if missing_nested:
            problems.append(f"{group} missing keys: {', '.join(missing_nested)}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-missing", action="store_true", help="create conservative metadata for missing stacks")
    parser.add_argument(
        "--refresh-inferred",
        action="store_true",
        help="refresh untracked inferred records for stacks in the reviewed category map",
    )
    args = parser.parse_args()
    failures: list[str] = []
    warnings: list[str] = []
    changed: list[str] = []
    directories = sorted(path for path in STACKS.iterdir() if path.is_dir())
    for directory in directories:
        yaml_path = directory / "stack.yaml"
        yml_path = directory / "stack.yml"
        if yml_path.exists():
            failures.append(f"{directory.name}: use stack.yaml, not stack.yml")
        if (
            args.refresh_inferred
            and directory.name in CATEGORIES
            and yaml_path.exists()
        ):
            # Refresh only records not tracked by Git; tracked metadata remains
            # authoritative and must be edited deliberately.
            tracked = subprocess.run(
                ["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(yaml_path.relative_to(REPO))],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode == 0
            if not tracked:
                yaml_path.write_text(
                    yaml.safe_dump(infer_metadata(directory), sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
                changed.append(directory.name)
        if not yaml_path.exists() and args.fix_missing:
            yaml_path.write_text(
                yaml.safe_dump(infer_metadata(directory), sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            yaml_path.chmod(yaml_path.stat().st_mode | stat.S_IRUSR | stat.S_IWUSR)
            changed.append(directory.name)
        if not yaml_path.exists():
            failures.append(f"{directory.name}: missing stack.yaml")
            continue
        try:
            metadata = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            failures.append(f"{directory.name}: invalid YAML: {exc}")
            continue
        failures.extend(f"{directory.name}: {problem}" for problem in validate(directory, metadata))
        compose_path = directory / "docker-compose.yml"
        has_managed_bundle = any(directory.glob("*/docker-compose*.yml")) or any(
            directory.glob("*/docker-compose*.yaml")
        )
        lifecycle_status = (metadata.get("lifecycle") or {}).get("status")
        if (
            not compose_path.exists()
            and not has_managed_bundle
            and metadata.get("type") != "cli_tool"
            and lifecycle_status != "external"
        ):
            warnings.append(
                f"{directory.name}: metadata describes {metadata.get('type')} but docker-compose.yml is absent"
            )
        if compose_path.exists():
            compose = compose_for(directory)
            stack_services = services(compose)
            requirements = metadata.get("host_requirements") or {}
            resources = metadata.get("resources") or {}
            compose_gpu = any(item.get("gpus") for item in stack_services)
            if compose_gpu and not requirements.get("needs_gpu"):
                warnings.append(f"{directory.name}: Compose requires a GPU but host_requirements.needs_gpu is false")
            if compose_gpu and resources.get("gpu_profile") != "required":
                warnings.append(f"{directory.name}: Compose requires a GPU but resources.gpu_profile is not required")
            if any(item.get("privileged") is True for item in stack_services) and not requirements.get("needs_privileged"):
                warnings.append(f"{directory.name}: Compose is privileged but host_requirements.needs_privileged is false")
            if any(item.get("network_mode") == "host" for item in stack_services) != bool(requirements.get("uses_host_network")):
                warnings.append(f"{directory.name}: host networking metadata disagrees with Compose")
            compose_volumes = {
                str((value or {}).get("name", key))
                for key, value in (compose.get("volumes") or {}).items()
                if not isinstance(value, dict) or isinstance((value or {}).get("name", key), str)
            }
            metadata_volumes = {
                str(item.get("name"))
                for item in (metadata.get("volumes") or [])
                if isinstance(item, dict) and item.get("name")
            }
            for volume in sorted(compose_volumes - metadata_volumes):
                warnings.append(f"{directory.name}: Compose volume '{volume}' is absent from metadata")
    for name in changed:
        print(f"FIX   {name}: created stack.yaml")
    for failure in failures:
        print(f"FAIL  {failure}")
    for warning in warnings:
        print(f"WARN  {warning}")
    print(
        f"Audited {len(directories)} stack metadata records: "
        f"{len(failures)} failure(s), {len(warnings)} warning(s), {len(changed)} change(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
