#!/usr/bin/env bash
# Sync .local hostnames from one config to Avahi and /etc/hosts (or hblock footer).
# From docker repo root: ./scripts/sync-local-hosts.sh [--print|--apply]
#
# Setup:
#   cp scripts/local-hosts.conf.example scripts/local-hosts.conf
#   Edit scripts/local-hosts.conf (one name per line: harbor, gitea, ...)
#
# Usage:
#   --print   Show what would be written (default).
#   --apply   Write to /etc/avahi/hosts and either /etc/hblock/footer or /etc/hosts (requires sudo).
#
# When hblock is installed: --apply writes only /etc/hblock/footer (no /etc/hosts). Run
#   'sudo hblock' to regenerate /etc/hosts with the footer. When hblock is not installed:
#   --apply writes /etc/hosts directly (no footer). So .local entries live in one place only.
#
# Requires: avahi-daemon. After --apply, restart Avahi: sudo systemctl restart avahi-daemon

set -e

# Resolve script path so repo/config are found when run with sudo (cwd may be /root)
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || realpath "${BASH_SOURCE[0]}" 2>/dev/null || true)"
[[ -z "$SCRIPT_PATH" ]] && SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_DIR:-$(dirname "$SCRIPT_PATH")}"
# If still relative, resolve against current dir
[[ "$SCRIPT_DIR" != /* ]] && SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
CONF="${CONF:-$REPO_ROOT/scripts/local-hosts.conf}"

BEGIN_MARKER='# BEGIN docker-local'
END_MARKER='# END docker-local'

usage() {
  echo "Usage: $0 [--print|--apply]" >&2
  echo "  --print  (default) Print lines for /etc/avahi/hosts, /etc/hosts, and hblock footer" >&2
  echo "  --apply  Write to /etc/avahi/hosts and (if hblock) /etc/hblock/footer else /etc/hosts (sudo)" >&2
  exit 1
}

get_ip() {
  if command -v hostname >/dev/null 2>&1 && hostname -I 2>/dev/null | awk '{print $1}' | grep -q .; then
    hostname -I 2>/dev/null | awk '{print $1}'
  else
    ip -4 route get 1 2>/dev/null | awk '{print $7}' || true
  fi
}

read_names() {
  local f="$1"
  if [[ ! -f "$f" ]]; then
    echo "Config not found: $f (copy from scripts/local-hosts.conf.example)" >&2
    return 1
  fi
  grep -v '^#' "$f" | grep -v '^[[:space:]]*$' | tr -d '\r'
}

APPLY=
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --print)  APPLY= ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
  shift
done

IP=$(get_ip)
if [[ -z "$IP" ]]; then
  echo "Could not detect host IP (tried hostname -I and ip route get 1)" >&2
  exit 1
fi

NAMES=()
while IFS= read -r n; do
  [[ -n "$n" ]] && NAMES+=( "$n" )
done < <(read_names "$CONF" || exit 1)

if [[ ${#NAMES[@]} -eq 0 ]]; then
  echo "No names in $CONF" >&2
  exit 1
fi

# Build "IP  name.local" lines
LINES=""
for name in "${NAMES[@]}"; do
  LINES="$LINES$IP  $name.local"$'\n'
done
LINES="${LINES%$'\n'}"

if [[ -n "$APPLY" ]]; then
  if [[ $EUID -ne 0 ]]; then
    echo "Run with sudo for --apply" >&2
    exit 1
  fi
  {
    echo "# Avahi static hosts - managed by scripts/sync-local-hosts.sh"
    echo "# Generated from local-hosts.conf. Do not edit by hand."
    for name in "${NAMES[@]}"; do echo "$IP  $name.local"; done
  } > /etc/avahi/hosts
  echo "Wrote /etc/avahi/hosts"

  if command -v hblock >/dev/null 2>&1; then
    # hblock is used: write footer to user's config (consistent with sources.list, allow.list)
    FOOTER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/hblock"
    if [[ -n "$SUDO_USER" ]]; then
      REAL_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
      FOOTER_DIR="${REAL_HOME}/.config/hblock"
    fi
    FOOTER_FILE="$FOOTER_DIR/footer.list"
    if mkdir -p "$FOOTER_DIR" 2>/dev/null; then
      {
        echo "# .local entries from scripts/sync-local-hosts.sh (local-hosts.conf)"
        echo "# hblock appends this file when you run: hblock -F $FOOTER_FILE"
        for name in "${NAMES[@]}"; do echo "$IP  $name.local"; done
      } > "$FOOTER_FILE"
      [[ -n "$SUDO_USER" ]] && chown "$SUDO_USER" "$FOOTER_FILE" 2>/dev/null || true
      echo "Wrote $FOOTER_FILE (run hblock with -F $FOOTER_FILE, e.g. sudo hblock -S ... -A ... -O /etc/hosts -F $FOOTER_FILE)"
    fi
  else
    # no hblock: write .local block to /etc/hosts directly
    if grep -q "$BEGIN_MARKER" /etc/hosts 2>/dev/null; then
      sed -i "/$BEGIN_MARKER/,/$END_MARKER/d" /etc/hosts
    fi
    echo "" >> /etc/hosts
    echo "$BEGIN_MARKER" >> /etc/hosts
    for name in "${NAMES[@]}"; do echo "$IP  $name.local"; done >> /etc/hosts
    echo "$END_MARKER" >> /etc/hosts
    echo "Updated /etc/hosts (block between $BEGIN_MARKER and $END_MARKER)"
  fi

  echo "Restart Avahi: systemctl restart avahi-daemon"
else
  echo "# Add to /etc/avahi/hosts (then: sudo systemctl restart avahi-daemon)"
  echo "# ---"
  echo "$LINES"
  echo ""
  if command -v hblock >/dev/null 2>&1; then
    echo "# hblock detected: --apply will write ~/.config/hblock/footer.list (run hblock with -F that path)"
    echo "# Add to ~/.config/hblock/footer.list:"
  else
    echo "# Add to /etc/hosts (or run this script with sudo --apply):"
    echo "# ---"
    echo "$BEGIN_MARKER"
  fi
  echo "$LINES"
  command -v hblock >/dev/null 2>&1 || echo "$END_MARKER"
fi
