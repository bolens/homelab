"""Verify the current Nodepad overlay in a fresh tree from its pinned base.

Reuse only an existing public Git object store and matching installed dependencies;
never reset, fetch, or modify the contributor's prepared checkout.
"""
import io
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "stacks/nodepad"


def main():
    source = Path(os.environ.get("NODEPAD_UPSTREAM_ROOT", str(STACK / "repo"))).resolve()
    revision = re.search(r"^UPSTREAM_REVISION=([0-9a-f]{40})$",
                         (STACK / "clone-repo.sh").read_text(), re.M).group(1)
    git_environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("GIT_")}
    git_environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                           GIT_NO_REPLACE_OBJECTS="1")
    try:
        archive = subprocess.check_output(["git", "-C", str(source), "archive", revision],
                                          env=git_environment)
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Prepare the pinned Nodepad source with clone-repo.sh first.") from exc
    with tempfile.TemporaryDirectory(prefix="nodepad-source-check-") as raw:
        tree = Path(raw)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(tree, filter="data")
        for patch in sorted((STACK / "patches").glob("*.patch")):
            subprocess.run(["patch", "--batch", "--no-backup-if-mismatch", "-p1"],
                           cwd=tree, input=patch.read_bytes(), check=True,
                           stdout=subprocess.DEVNULL)
        if (tree / "package-lock.json").read_bytes() != (source / "package-lock.json").read_bytes():
            raise SystemExit("Nodepad dependencies do not match the pinned patched lockfile.")
        dependencies = source / "node_modules"
        if not (dependencies / ".bin/tsc").is_file():
            raise SystemExit("Run npm ci in the prepared Nodepad source first.")
        (tree / "node_modules").symlink_to(dependencies, target_is_directory=True)
        (tree / "next-env.d.ts").write_text('/// <reference types="next" />\n'
                                           '/// <reference types="next/image-types/global" />\n')
        environment = dict(os.environ, NODEPAD_SOURCE_DIR=str(tree))
        subprocess.run(["bash", str(STACK / "verify-litellm.sh")],
                       env=environment, check=True)


if __name__ == "__main__":
    main()
