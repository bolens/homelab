#!/usr/bin/env bash
# Download one reviewed, version-bound plugin. Does not start or reload Gotify.
set -euo pipefail
_PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$_PLUGIN_DIR"
[[ "$(uname -m)" == x86_64 ]] || { echo "This lock targets amd64 only; build and verify a matching architecture first." >&2; exit 1; }
[[ ! -L plugins ]] || { echo "Refusing a symlinked plugin directory." >&2; exit 1; }
mapfile -t _PLUGIN_LOCK < <(python3 -c 'import json; p=json.load(open("plugins.lock.json"))["plugins"][0]; print(p["url"]); print(p["sha256"])')
mkdir -p plugins
_PLUGIN_TEMP="$(mktemp)"
trap 'rm -f "$_PLUGIN_TEMP"' EXIT
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "${_PLUGIN_LOCK[0]}" -o "$_PLUGIN_TEMP"
printf '%s  %s\n' "${_PLUGIN_LOCK[1]}" "$_PLUGIN_TEMP" | sha256sum --check --status
if [[ -e plugins/authentik.so ]]; then
  cmp --silent "$_PLUGIN_TEMP" plugins/authentik.so || { echo "Existing plugin differs; preserve it and review an explicit upgrade." >&2; exit 1; }
else
  install -m 0644 "$_PLUGIN_TEMP" plugins/authentik.so
fi
echo "Verified Authentik plugin is staged. Use the optional plugins Compose file after backing up Gotify."
