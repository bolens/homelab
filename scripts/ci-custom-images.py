#!/usr/bin/env python3
"""Select custom image builds from the shared inventory and Dorny results."""

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SHARED = [
    ".github/workflows/custom-images.yml",
    ".github/custom-images.json",
    "scripts/ci-custom-images.py",
    "scripts/tests/test_ci_custom_images.py",
]


def filters(images):
    """Include every build-context input, including removed and renamed files."""
    return {image["image"]: [*SHARED, image["context"] + "/**"] for image in images}


def select(images, changed, full=False):
    """Reject invalid detection output instead of silently skipping builds."""
    names = [image["image"] for image in images]
    if not images or len(names) != len(set(names)):
        raise ValueError("Image inventory must be nonempty and unique")
    if full:
        return images
    if not isinstance(changed, list) or any(not isinstance(name, str) or name not in names for name in changed):
        raise ValueError("Invalid changed-image selection")
    return [image for image in images if image["image"] in changed]


def main():
    images = json.loads((ROOT / ".github/custom-images.json").read_text())
    if sys.argv[1:] == ["filters"]:
        select(images, [], full=True)
        print(json.dumps(filters(images)))
    elif sys.argv[1:] == ["matrix"]:
        full = os.environ.get("FULL_RUN") == "true"
        changed = [] if full else json.loads(os.environ["CHANGED_IMAGES"])
        selected = select(images, changed, full)
        # GitHub expands matrices before skipping jobs, so retain a valid
        # placeholder for an explicitly empty selection.
        print("matrix=" + json.dumps({"include": selected or images[:1]}))
        print("any=" + str(bool(selected)).lower())
    else:
        raise SystemExit("usage: ci-custom-images.py filters|matrix")


if __name__ == "__main__":
    main()
