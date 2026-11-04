#!/usr/bin/env bash
# Explicit operator action inside the app container, never called by prepare-stack.sh.
# Download into a new prefix; do not install OS packages or change the server's Node.
set -euo pipefail
umask 022
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
unset NODE_OPTIONS NODE_PATH PYTHONPATH PYTHONHOME BASH_ENV ENV
[[ $(id -u) == 0 ]] || { echo "Run this preparation as container root." >&2; exit 1; }
# The dedicated volume and every ancestor must remain outside agent custody.
python3 - <<'CUSTODY'
import os, stat
for path in ("/", "/opt", "/opt/paperclip-web"):
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise SystemExit("Unsafe toolchain ancestor: " + path)
CUSTODY
exec 8>/opt/paperclip-web/.prepare.lock
flock -n 8 || { echo "Toolchain preparation already running." >&2; exit 75; }
private=$(mktemp -d /opt/paperclip-web/.prepare.XXXXXXXX)
chmod 0700 "$private"
export HOME="$private/home"
mkdir "$HOME"
manifest=${1:?Usage: prepare-web-toolchain.sh /path/to/web-toolchain.json}
# Snapshot a Root-owned operator manifest without following a substituted leaf.
python3 - "$manifest" "$private/manifest.json" <<'MANIFEST'
import os, stat, sys
fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
with os.fdopen(fd, "rb") as source:
    info = os.fstat(source.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or info.st_size > 65536:
        raise SystemExit("Manifest must be a bounded Root-owned regular file, not agent writable")
    with open(sys.argv[2], "xb") as target:
        target.write(source.read(65537))
MANIFEST
manifest=$private/manifest.json
read -r revision nodeversion timeoutseconds heapmib markdownversion uvversion uvurl uvhash pythonversion specifyversion markdownitversion ruffversion zizmorversion < <(node -e '
const c=JSON.parse(require("fs").readFileSync(process.argv[1],"utf8"));
if (!Number.isInteger(c.revision)||c.revision<1||!/^26\.\d+\.\d+$/.test(c.nodeVersion)||!Number.isInteger(c.timeoutSeconds)||c.timeoutSeconds<1||c.timeoutSeconds>1800||!Number.isInteger(c.nodeHeapMiB)||c.nodeHeapMiB<256||c.nodeHeapMiB>2048) process.exit(2);
for (const k of ["markdownlintVersion","uvVersion","pythonVersion","specifyVersion","markdownItVersion","ruffVersion","zizmorVersion"]) if (!/^\d+\.\d+\.\d+$/.test(c[k])) process.exit(2);
if (!/^https:\/\/files\.pythonhosted\.org\/packages\/[a-zA-Z0-9/_.-]+$/.test(c.uvWheelUrl)||!/^uv-/.test(c.uvWheelUrl.split("/").pop())||! /^[a-f0-9]{64}$/.test(c.uvWheelSha256)) process.exit(2);
console.log(c.revision,c.nodeVersion,c.timeoutSeconds,c.nodeHeapMiB,c.markdownlintVersion,c.uvVersion,c.uvWheelUrl,c.uvWheelSha256,c.pythonVersion,c.specifyVersion,c.markdownItVersion,c.ruffVersion,c.zizmorVersion);
' "$manifest")
prefix=/opt/paperclip-web/releases/node-$nodeversion-r$revision
manifesthash=$(sha256sum "$manifest" | cut -d ' ' -f 1)
if [[ -f "$prefix/QUALIFIED" ]]; then
  [[ $(cat "$prefix/manifest.sha256") == "$manifesthash" ]] || { echo 'Manifest changed without a revision bump.' >&2; exit 1; }
  echo "Web toolchain already prepared: $prefix/bin/run"
  exit 0
fi
[[ $(id -u) == 0 ]] || { echo 'Run this preparation as container root.' >&2; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo 'This toolchain requires Linux x86_64.' >&2; exit 1; }
grep -qx 'VERSION_CODENAME=trixie' /etc/os-release || { echo 'Requalify the dependency recipe for this OS.' >&2; exit 1; }
# Refuse to overwrite a partial or operator-owned prefix.
[[ ! -e "$prefix" ]] || { echo 'Toolchain prefix already exists without READY; inspect it first.' >&2; exit 1; }
[[ ! -e /opt/paperclip-web/web || -L /opt/paperclip-web/web ]] || { echo 'Stable entry is not a symlink; inspect it first.' >&2; exit 1; }
mkdir -p /opt/paperclip-web/releases
[[ ! -L /opt/paperclip-web/releases ]] || { echo 'Release directory must not be a symlink.' >&2; exit 1; }
[[ $(stat -c '%u:%a' /opt/paperclip-web/releases) == 0:755 ]] || { echo 'Release directory must be Root-owned 0755.' >&2; exit 1; }
stage=$private/release
mkdir -m 0700 "$stage"
printf '%s\n' "$manifesthash" > "$stage/manifest.sha256"
trap 'echo "Preparation interrupted; retained scratch: $stage" >&2' ERR
mkdir -p "$stage"/{bin,root,apt/lists/partial,apt/archives/partial}
curl --fail --silent --show-error --location --max-time 180 \
  "https://nodejs.org/dist/v$nodeversion/SHASUMS256.txt" -o "$stage/SHASUMS256.txt"
[[ -f "$stage/node-v$nodeversion-linux-x64.tar.xz" ]] || curl --fail --silent --show-error --location --max-time 300 \
  "https://nodejs.org/dist/v$nodeversion/node-v$nodeversion-linux-x64.tar.xz" -o "$stage/node-v$nodeversion-linux-x64.tar.xz"
(cd "$stage"; awk -v archive="node-v$nodeversion-linux-x64.tar.xz" '$2 == archive' SHASUMS256.txt > node-checksum.txt
  test -s node-checksum.txt; sha256sum --check node-checksum.txt)
python3 - "$stage" "$nodeversion" <<'PY'
import pathlib
import sys
import tarfile
stage, version = pathlib.Path(sys.argv[1]), sys.argv[2]
with tarfile.open(stage / f"node-v{version}-linux-x64.tar.xz") as archive:
    archive.extractall(stage, filter="data")
PY
[[ ! -e "$stage/node" ]] || rm -rf -- "$stage/node"
mv "$stage/node-v$nodeversion-linux-x64" "$stage/node"
# Debian's signed repository metadata authenticates the packages. Only download
# missing dependencies and extract them privately; dpkg's installed state is untouched.
aptopts=(-o "Dir::State::lists=$stage/apt/lists" -o "Dir::Cache::archives=$stage/apt/archives")
apt-get "${aptopts[@]}" update
apt-get "${aptopts[@]}" --download-only --no-install-recommends --yes install \
  libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 \
  libcairo2 libcups2t64 libdbus-1-3 libdrm2 libgbm1 libglib2.0-0t64 \
  libnspr4 libnss3 libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 \
  libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 \
  libfontconfig1 libfreetype6 libatomic1 fonts-liberation fonts-noto-color-emoji \
  shellcheck procps unzip zip xz-utils
for package in "$stage"/apt/archives/*.deb; do
  dpkg-deb --extract "$package" "$stage/root"
  dpkg-deb --show "$package" >> "$stage/debian-packages.txt"
done
(cd "$stage"; sha256sum apt/archives/*.deb > deb-checksums.txt)
# Pin auxiliary developer tools alongside Node. uv's frozen download catalog
# supplies a standalone CPython including ensurepip, without altering system Python.
curl --fail --silent --show-error --location --max-time 180 "$uvurl" -o "$stage/uv.whl"
printf '%s  %s\n' "$uvhash" "$stage/uv.whl" | sha256sum --check
python3 - "$stage" <<'PYTHON'
import pathlib, sys, zipfile
stage = pathlib.Path(sys.argv[1])
with zipfile.ZipFile(stage / "uv.whl") as wheel:
    wheel.extractall(stage / "uv-bootstrap")
PYTHON
uvbin=$(find "$stage/uv-bootstrap" -type f -path '*/scripts/uv' -print -quit)
[[ -n "$uvbin" ]]
chmod 0755 "$uvbin"
uvxbin=$(dirname "$uvbin")/uvx
chmod 0755 "$uvxbin"
ln -s "${uvbin#"$stage/"}" "$stage/uv"
ln -s "${uvxbin#"$stage/"}" "$stage/uvx"
[[ $("$uvbin" --version) == "uv $uvversion"* ]]
UV_PYTHON_INSTALL_DIR="$stage/python" UV_PYTHON_BIN_DIR="$stage/python-links" \
  "$uvbin" --no-config python install "$pythonversion"
pythonbin=$(find "$stage/python" -path '*/bin/python3' -print -quit)
[[ -x "$pythonbin" ]]
"$pythonbin" -m venv --copies "$stage/specify"
"$stage/specify/bin/python" -m pip install --disable-pip-version-check \
  "specify-cli @ git+https://github.com/github/spec-kit.git@v$specifyversion" \
  "markdown-it-py==$markdownitversion" "ruff==$ruffversion" "zizmor==$zizmorversion"
"$stage/specify/bin/python" -m pip freeze --all > "$stage/python-packages.txt"
LD_LIBRARY_PATH="$stage/root/usr/lib/x86_64-linux-gnu:$stage/root/lib/x86_64-linux-gnu" \
  PATH="$stage/node/bin:$PATH" "$stage/node/bin/npm" install --prefix "$stage/javascript" \
  --ignore-scripts --no-audit --no-fund --save-exact "markdownlint-cli2@$markdownversion"
# Only official release assets listed with exact digests are accepted.
python3 - "$manifest" "$stage" <<'BINARIES'
import hashlib, json, pathlib, subprocess, sys, tarfile
manifest, stage = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
allowed = {"actionlint": "rhysd/actionlint", "hadolint": "hadolint/hadolint", "gitleaks": "gitleaks/gitleaks"}
for item in json.loads(manifest.read_text())["binaries"]:
    name, url, digest = item["name"], item["url"], item["sha256"]
    if name not in allowed or not url.startswith("https://github.com/" + allowed[name] + "/releases/download/"):
        raise ValueError("Unapproved binary source")
    archive = stage / (name + ".download")
    subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "180", url, "-o", str(archive)], check=True)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError("Checksum mismatch: " + name)
    destination = stage / "bin" / name
    if item["archive"]:
        with tarfile.open(archive) as bundle:
            member = bundle.getmember(name)
            if not member.isfile():
                raise ValueError("Not a regular executable")
            destination.write_bytes(bundle.extractfile(member).read())
    else:
        destination.write_bytes(archive.read_bytes())
    destination.chmod(0o755)
BINARIES
# Relocate the venv's generated entrypoints and interpreter home before promotion.
python3 - "$stage" "$prefix" <<'PYTHON'
import pathlib, sys
stage, prefix = map(pathlib.Path, sys.argv[1:])
for path in [stage / "specify/pyvenv.cfg", *(stage / "specify/bin").iterdir()]:
    if not path.is_file() or path.is_symlink():
        continue
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        continue
    if str(stage) in text:
        path.write_text(text.replace(str(stage), str(prefix)))
PYTHON
cat > "$stage/fonts.conf" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig><dir>$prefix/root/usr/share/fonts</dir><dir>/usr/share/fonts</dir><cachedir>/paperclip/.cache/fontconfig-web</cachedir></fontconfig>
EOF
cat > "$stage/bin/run" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
prefix=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ -f "$prefix/READY" ]] || { echo 'Web toolchain is not ready.' >&2; exit 1; }
[[ $# -gt 0 ]] || { echo 'Usage: run COMMAND [ARG...]' >&2; exit 2; }
export PATH="$prefix/node/bin:$prefix/javascript/node_modules/.bin:$prefix/specify/bin:$prefix/bin:$prefix/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$prefix/root/usr/lib/x86_64-linux-gnu:$prefix/root/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Keep uv operations in agent-owned persistent caches, never the immutable release.
export UV_PYTHON_INSTALL_DIR=/paperclip/.local/share/uv/python
export UV_PYTHON_BIN_DIR=/paperclip/.local/bin
export FONTCONFIG_FILE="$prefix/fonts.conf"
export PLAYWRIGHT_BROWSERS_PATH=/paperclip/.cache/ms-playwright
export NODE_OPTIONS="--max-old-space-size=NODE_HEAP_MIB${NODE_OPTIONS:+ $NODE_OPTIONS}"
# All agents share this one nonblocking lease. Do not poll it when busy.
exec 9>/paperclip/.cache/web-toolchain.lock
flock -n 9 || { echo 'Web toolchain busy; record an owned task dependency and retry after delivery.' >&2; exit 75; }
exec timeout --signal=TERM --kill-after=15s TIMEOUT_SECONDS "$@"
EOF
sed -i "s/NODE_HEAP_MIB/$heapmib/;s/TIMEOUT_SECONDS/$timeoutseconds/" "$stage/bin/run"
chmod 0755 "$stage/bin/run"
cp "$manifest" "$stage/manifest.json"
printf '%s\n' "$manifesthash" > "$stage/manifest.sha256"
[[ $(LD_LIBRARY_PATH="$stage/root/usr/lib/x86_64-linux-gnu:$stage/root/lib/x86_64-linux-gnu" "$stage/node/bin/node" --version) == "v$nodeversion" ]]
printf 'Node %s; private Debian Chromium libraries; %ss limit; one job\n' "$nodeversion" "$timeoutseconds" > "$stage/READY"
# The prefix is immutable for agents; only the lock/cache/workspaces are writable.
chown -R root:root "$stage"
chmod -R a+rX,go-w "$stage"
# uv entrypoints use relative links so stage promotion preserves them.
ln -s ../uv "$stage/bin/uv"
ln -s ../uvx "$stage/bin/uvx"
mv "$stage" "$prefix"
# Qualify relocated interpreters and entrypoints before switching the stable route.
env -i HOME="$HOME" PATH="$prefix/node/bin:$prefix/javascript/node_modules/.bin:$prefix/specify/bin:$prefix/bin:$prefix/root/usr/bin:/usr/bin:/bin" \
  LD_LIBRARY_PATH="$prefix/root/usr/lib/x86_64-linux-gnu:$prefix/root/lib/x86_64-linux-gnu" bash -s > "$prefix/developer-tools-qualification.txt" 2>&1 <<'QUALIFY'
  set -euo pipefail
  markdownlint-cli2 --version
  specify version
  uv --version
  uvx --version
  shellcheck --version
  ruff --version
  actionlint --version
  zizmor --version
  hadolint --version
  gitleaks version
  ps -p $$ -o comm=
  xz --version
  zip -v
  unzip -v
  python3 -c "import ensurepip, markdown_it; print(ensurepip.version())"
  scratch=$(mktemp -d)
  trap 'rm -rf -- "$scratch"' EXIT
  python3 -m venv "$scratch/venv"
  "$scratch/venv/bin/python" -m pip --version
QUALIFY
touch "$prefix/QUALIFIED"
trap - ERR
rm -rf -- "$private"
nextlink=/opt/paperclip-web/.web-next-$$
ln -s "$prefix" "$nextlink"
mv -Tf "$nextlink" /opt/paperclip-web/web
echo "Prepared /opt/paperclip-web/web/bin/run -> $prefix"
echo 'Install each project-pinned Playwright browser as UID 1000 if its cache is missing.'
