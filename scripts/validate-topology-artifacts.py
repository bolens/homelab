#!/usr/bin/env python3
"""Validate the checked Archify topology source and rendered artifacts."""

from __future__ import annotations

import html
import json
from pathlib import Path
import struct
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = REPO_ROOT / "documents"
SOURCE = DOCUMENTS / "topology.architecture.json"
ARTIFACT = DOCUMENTS / "topology.html"
PREVIEW = DOCUMENTS / "topology.png"
INDEX = DOCUMENTS / "TOPOLOGY.md"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_source() -> dict:
    try:
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {SOURCE.relative_to(REPO_ROOT)}: {error}")
    if data.get("schema_version") != 1:
        fail("topology source must use schema_version 1")
    if data.get("diagram_type") != "architecture":
        fail("topology source must use diagram_type architecture")
    if data.get("meta", {}).get("quality_profile") != "showcase":
        fail("topology source must use the showcase quality profile")
    return data


def validate_graph(data: dict) -> None:
    components = data.get("components")
    connections = data.get("connections")
    if not isinstance(components, list) or not components:
        fail("topology source has no components")
    if len(components) > 12:
        fail("topology source exceeds the 12-component readability limit")
    if not isinstance(connections, list) or not connections:
        fail("topology source has no connections")

    ids = [component.get("id") for component in components]
    if any(not isinstance(component_id, str) or not component_id for component_id in ids):
        fail("every topology component needs a non-empty id")
    if len(ids) != len(set(ids)):
        fail("topology component ids must be unique")

    known = set(ids)
    for connection in connections:
        source = connection.get("from")
        target = connection.get("to")
        if source not in known or target not in known:
            fail(f"connection endpoint is unknown: {source!r} -> {target!r}")


def validate_html(data: dict) -> None:
    try:
        rendered = ARTIFACT.read_text(encoding="utf-8")
    except OSError as error:
        fail(f"cannot read {ARTIFACT.relative_to(REPO_ROOT)}: {error}")
    if rendered.count("<svg") != 1:
        fail("topology HTML must contain exactly one SVG diagram")
    if "Docker homelab architecture" not in rendered:
        fail("topology HTML has the wrong title")
    for component in data["components"]:
        label = html.escape(component.get("label", ""), quote=True)
        if label and label not in rendered:
            fail(f"topology HTML is missing component label {label!r}")


def validate_preview() -> None:
    try:
        raw = PREVIEW.read_bytes()
    except OSError as error:
        fail(f"cannot read {PREVIEW.relative_to(REPO_ROOT)}: {error}")
    if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        fail("topology preview is not a valid PNG")
    width, height = struct.unpack(">II", raw[16:24])
    if width < 1440 or height < 900:
        fail(f"topology preview is too small: {width}x{height}")


def validate_index() -> None:
    try:
        index = INDEX.read_text(encoding="utf-8")
    except OSError as error:
        fail(f"cannot read {INDEX.relative_to(REPO_ROOT)}: {error}")
    for target in ("topology.html", "topology.png", "topology.architecture.json"):
        if target not in index:
            fail(f"topology index does not link {target}")
    if "```mermaid" in index:
        fail("topology index must not contain a Mermaid diagram")


def main() -> None:
    data = load_source()
    validate_graph(data)
    validate_html(data)
    validate_preview()
    validate_index()
    print("Archify topology artifacts are valid.")


if __name__ == "__main__":
    main()
