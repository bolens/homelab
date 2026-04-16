#!/usr/bin/env bash
# Guard for Playwright WebKit runtime libs on non-Ubuntu hosts.
# - If required SONAMEs are already resolvable, no-op.
# - If missing and not CI, auto-run sync-webkit-ubuntu-libs.sh.
# - If missing and CI, fail with a clear message.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
EXTRA_LIBS_DIR="${PLAYWRIGHT_WEBKIT_EXTRA_LIBS:-$HOME/.local/lib/playwright-webkit-extras}"

collect_webkit_dirs() {
  local -a dirs=()
  local wk
  for wk in "$HOME"/.cache/ms-playwright/webkit-*; do
    [[ -d "$wk" ]] && dirs+=("$wk")
  done
  for wk in /tmp/cursor-sandbox-cache/*/playwright/webkit-*; do
    [[ -d "$wk" ]] && dirs+=("$wk")
  done
  printf '%s\n' "${dirs[@]}"
}

has_missing_webkit_runtime_libs() {
  local wk="$1"
  local pattern='libflite_cmu_|libjxl\.so\.0\.8|libicu(data|i18n|uc)\.so\.74'

  local ld_path="$EXTRA_LIBS_DIR"
  if [[ -n "${LD_LIBRARY_PATH:-}" ]]; then
    ld_path="$EXTRA_LIBS_DIR:$LD_LIBRARY_PATH"
  fi

  if [[ -x "$wk/minibrowser-wpe/bin/MiniBrowser" ]]; then
    if ! LD_LIBRARY_PATH="$ld_path" ldd "$wk/minibrowser-wpe/bin/MiniBrowser" 2>&1 | rg -q "($pattern).*(not found)"; then
      :
    else
      return 0
    fi
  fi

  local gtk_lib
  for gtk_lib in "$wk"/minibrowser-gtk/lib/libwebkitgtk-*.so*; do
    [[ -f "$gtk_lib" ]] || continue
    if LD_LIBRARY_PATH="$ld_path" ldd "$gtk_lib" 2>&1 | rg -q "($pattern).*(not found)"; then
      return 0
    fi
  done

  return 1
}

mapfile -t WEBKIT_DIRS < <(collect_webkit_dirs)
if [[ ${#WEBKIT_DIRS[@]} -eq 0 ]]; then
  echo "No Playwright WebKit bundles found; skipping local runtime guard." >&2
  exit 0
fi

missing=0
for wk in "${WEBKIT_DIRS[@]}"; do
  if has_missing_webkit_runtime_libs "$wk"; then
    missing=1
    break
  fi
done

if [[ "$missing" -eq 0 ]]; then
  echo "Playwright WebKit runtime libraries look good." >&2
  exit 0
fi

if [[ "${CI:-}" == "true" ]]; then
  echo "Missing Playwright WebKit runtime libraries in CI. Ensure Ubuntu deps are installed with:" >&2
  echo "  pnpm --filter client exec playwright install --with-deps webkit" >&2
  exit 1
fi

echo "Missing Playwright WebKit runtime libraries detected; syncing Ubuntu libs..." >&2
bash "$ROOT_DIR/e2e/scripts/sync-webkit-ubuntu-libs.sh"

missing_after_sync=0
for wk in "${WEBKIT_DIRS[@]}"; do
  if has_missing_webkit_runtime_libs "$wk"; then
    missing_after_sync=1
    break
  fi
done

if [[ "$missing_after_sync" -eq 1 ]]; then
  echo "WebKit runtime libs are still missing after sync." >&2
  echo "Check unresolved SONAMEs with:" >&2
  echo "  ldd ~/.cache/ms-playwright/webkit-*/minibrowser-gtk/lib/libwebkitgtk-6.0.so* | rg 'not found'" >&2
  exit 1
fi

echo "WebKit runtime guard passed after sync." >&2
