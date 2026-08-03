#!/usr/bin/env python3
"""Validate dependency-update configuration before remote CI parses it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
DEPENDABOT = ROOT / ".github" / "dependabot.yml"
RENOVATE = ROOT / "renovate.json"


def fail(message: str) -> None:
    print(f"validate-dependency-config.py: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_dependabot() -> None:
    try:
        config = yaml.safe_load(DEPENDABOT.read_text())
    except (OSError, yaml.YAMLError) as exc:
        fail(f"cannot parse {DEPENDABOT.relative_to(ROOT)}: {exc}")

    if not isinstance(config, dict) or config.get("version") != 2:
        fail("Dependabot config must be a mapping with version: 2")

    updates = config.get("updates")
    if not isinstance(updates, list) or not updates:
        fail("Dependabot config must contain a non-empty updates list")

    seen: set[tuple[str, tuple[str, ...]]] = set()
    semver_cooldowns = {
        "semver-major-days",
        "semver-minor-days",
        "semver-patch-days",
    }
    semver_cooldown_ecosystems = {
        "bundler",
        "cargo",
        "composer",
        "gomod",
        "maven",
        "npm",
        "nuget",
        "pip",
        "pub",
        "swift",
    }

    for index, update in enumerate(updates):
        if not isinstance(update, dict):
            fail(f"updates[{index}] must be a mapping")
        ecosystem = update.get("package-ecosystem")
        if not isinstance(ecosystem, str) or not ecosystem:
            fail(f"updates[{index}] is missing package-ecosystem")
        if "directory" in update:
            directories = (str(update["directory"]),)
        elif isinstance(update.get("directories"), list) and update["directories"]:
            directories = tuple(str(item) for item in update["directories"])
        else:
            fail(f"updates[{index}] must define directory or directories")

        identity = (ecosystem, directories)
        if identity in seen:
            fail(f"duplicate update definition for {ecosystem}: {directories}")
        seen.add(identity)

        schedule = update.get("schedule")
        if not isinstance(schedule, dict) or schedule.get("interval") not in {
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "semiannually",
            "yearly",
        }:
            fail(f"updates[{index}] has an invalid schedule interval")

        cooldown = update.get("cooldown", {})
        if not isinstance(cooldown, dict):
            fail(f"updates[{index}].cooldown must be a mapping")
        unsupported = semver_cooldowns.intersection(cooldown)
        if unsupported and ecosystem not in semver_cooldown_ecosystems:
            keys = ", ".join(sorted(unsupported))
            fail(f"{keys} are unsupported for ecosystem {ecosystem}")


def validate_renovate() -> None:
    try:
        config = json.loads(RENOVATE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {RENOVATE.relative_to(ROOT)}: {exc}")
    if not isinstance(config, dict):
        fail("Renovate config must be a JSON object")
    if not isinstance(config.get("packageRules"), list):
        fail("Renovate config must define packageRules")


def main() -> None:
    validate_dependabot()
    validate_renovate()
    print("Dependency update configuration is valid.")


if __name__ == "__main__":
    main()
