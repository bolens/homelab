#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="${NODEPAD_SOURCE_DIR:-$ROOT/repo}"
cd "$source_dir"
node --check lib/server/litellm-proxy.mjs
node --test tests/litellm-proxy.test.mjs tests/litellm-client.test.cjs
config="$(mktemp "$source_dir/.litellm-tsconfig.XXXXXX.json")"
trap 'rm -f "$config"' EXIT
cat > "$config" <<'JSON'
{
  "extends": "./tsconfig.json",
  "compilerOptions": {"incremental": false},
  "include": ["next-env.d.ts", "lib/ai-settings.ts", "components/project-sidebar.tsx", "app/api/litellm/[[...path]]/route.ts"],
  "exclude": ["node_modules"]
}
JSON
./node_modules/.bin/tsc --noEmit --project "$config"
