#!/usr/bin/env bash
# Copy Ubuntu 24.04 libflite1 + libjxl runtime libs for Playwright WebKit on distros
# where SONAMEs differ (e.g. Arch). Requires podman or docker.
#
# Usage:
#   ./e2e/scripts/sync-webkit-ubuntu-libs.sh
#   LD_LIBRARY_PATH="$HOME/.local/lib/playwright-webkit-extras:$LD_LIBRARY_PATH" pnpm run e2e:webkit

set -euo pipefail

OUT="${PLAYWRIGHT_WEBKIT_EXTRA_LIBS:-$HOME/.local/lib/playwright-webkit-extras}"
IMG="${PLAYWRIGHT_WEBKIT_UBUNTU_IMAGE:-docker.io/library/ubuntu:24.04}"

if command -v podman >/dev/null 2>&1; then
  RUN=(podman run --rm -i --pull=newer)
elif command -v docker >/dev/null 2>&1; then
  RUN=(docker run --rm -i --pull=always)
else
  echo "Install podman or docker first." >&2
  exit 1
fi

mkdir -p "$OUT"

"${RUN[@]}" -v "$OUT:/out" "$IMG" bash -s <<'EOS'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates libflite1

# Runtime SONAME varies by Ubuntu point release (0.7 vs 0.8).
apt-get install -y -qq libjxl0.8 2>/dev/null || apt-get install -y -qq libjxl0.7

case "$(uname -m)" in
  x86_64) libdir=/usr/lib/x86_64-linux-gnu ;;
  aarch64) libdir=/usr/lib/aarch64-linux-gnu ;;
  *) libdir=/usr/lib ;;
esac
if [[ ! -d "$libdir" ]]; then
  libdir=/usr/lib
fi

shopt -s nullglob
for f in "$libdir"/libflite_cmu*.so*; do
  cp -a "$f" /out/
done
for f in "$libdir"/libjxl.so*; do
  cp -a "$f" /out/
done

cd /out
if [[ ! -e libjxl.so.0.8 ]]; then
  cand=$(ls -1 libjxl.so.0.* 2>/dev/null | head -1 || true)
  if [[ -n "${cand:-}" ]]; then
    ln -sf "$cand" libjxl.so.0.8
    echo "Symlinked libjxl.so.0.8 -> $cand (if WebKit crashes, remove and try another libjxl build)." >&2
  fi
fi

echo "Copied libraries:" >&2
ls -la /out >&2
EOS

if ! compgen -G "$OUT/libflite_cmu*.so*" >/dev/null && ! compgen -G "$OUT/libjxl.so*" >/dev/null; then
  echo "No libraries were copied into $OUT. Check container runtime output above." >&2
  exit 1
fi

# Also copy extras into existing Playwright WebKit bundle libs so MiniBrowser can resolve
# them without relying on LD_LIBRARY_PATH propagation.
wk_dirs=()
for wk in "$HOME"/.cache/ms-playwright/webkit-*; do
  [[ -d "$wk" ]] && wk_dirs+=("$wk")
done
for wk in /tmp/cursor-sandbox-cache/*/playwright/webkit-*; do
  [[ -d "$wk" ]] && wk_dirs+=("$wk")
done

for wk in "${wk_dirs[@]}"; do
  for target in "$wk/minibrowser-gtk/lib" "$wk/minibrowser-wpe/lib"; do
    [[ -d "$target" ]] || continue
    cp -a "$OUT"/libflite_cmu*.so* "$target"/ 2>/dev/null || true
    cp -a "$OUT"/libjxl.so* "$target"/ 2>/dev/null || true
  done
done

echo ""
echo "Extras directory: $OUT"
echo "Run WebKit e2e with:"
echo "  export LD_LIBRARY_PATH=\"$OUT:\$LD_LIBRARY_PATH\""
echo "  pnpm run e2e:webkit"
