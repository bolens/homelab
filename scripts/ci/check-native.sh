#!/usr/bin/env bash
# Portable checks use an exact-revision disposable clone and per-image tool state.
set -euo pipefail
umask 022
mode=${1:-}
case "$mode" in repository|policy|komga|dotnet|site|links) ;; *) echo 'unknown native check' >&2; exit 2 ;; esac
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
# Nested clones cannot inherit hook/index routing or maintainer Git configuration.
while IFS= read -r variable; do
    case "$variable" in GIT_*) unset "$variable" ;; esac
done < <(compgen -e)
source_revision=$(git -C "$source_root" rev-parse HEAD)
if [[ -n "${CI_COMMIT_SHA:-}" ]]; then test "$source_revision" = "$CI_COMMIT_SHA"; fi
test "$(git -C "$source_root" rev-parse --is-shallow-repository)" = false
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0
scratch=$(mktemp -d /tmp/homelab-native.XXXXXXXX)
# Public source/tools only: UID1000 fixtures must traverse to the Python venv.
# Keep listing/writes private; nested fixture directories retain their own modes.
chmod 0711 "$scratch"
unprivileged=''
trap 'if [[ -n "$unprivileged" ]]; then rm -rf -- "$unprivileged"; fi; rm -rf -- "$scratch"' EXIT
mkdir "$scratch/tmp" "$scratch/cache"
export TMPDIR="$scratch/tmp" XDG_CACHE_HOME="$scratch/cache" PIP_CACHE_DIR="$scratch/cache/pip" npm_config_cache="$scratch/cache/npm"
git clone --quiet --no-hardlinks --no-checkout "$source_root" "$scratch/source"
git -C "$scratch/source" checkout --quiet --detach "$source_revision"
cd -- "$scratch/source"
test "$(git rev-parse HEAD)" = "$source_revision"
bootstrap() {
    timeout 240s python3 scripts/ci/bootstrap-native-tools.py --destination "$scratch/tools" "$@"
    export PATH="$scratch/tools/bin:$PATH"
}
python_tools() {
    python3 -m venv "$scratch/venv"
    "$scratch/venv/bin/pip" install --disable-pip-version-check --only-binary=:all: --require-hashes -r .github/requirements-native-ci.txt
    export PATH="$scratch/venv/bin:$PATH"
}
npm_tools() {
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci --ignore-scripts --no-audit --no-fund
}
case "$mode" in
    repository)
        bootstrap docker compose
        export DOCKER_CONFIG="$scratch/tools/docker-config" DOCKER_HOST="unix://$scratch/no-engine.sock"
        unset DOCKER_CONTEXT DOCKER_CERT_PATH DOCKER_TLS_VERIFY DOCKER_API_VERSION
        # Fixtures deliberately replace HOME/DOCKER_CONFIG. Use Docker's standard
        # container-global plugin lookup without exposing any shared credentials.
        python3 scripts/ci/register-native-compose.py --tools "$scratch/tools"
        expected_compose=$(python3 -c 'import json; print(json.load(open("scripts/ci/native-tools.json"))["tools"]["compose"]["version"])')
        test "$(DOCKER_CONFIG="$scratch/isolated-docker-config" docker compose version --short)" = "$expected_compose"
        python_tools
        npm_tools
        make validate-strict
        ;;
    policy)
        bootstrap actionlint hadolint
        python_tools
        shared=$(python3 -c 'import yaml; print(yaml.safe_load(open(".github/workflows/source-lint.yml"))["jobs"]["lint"]["with"]["tooling-ref"])')
        spec=$(python3 -c 'import yaml; print(yaml.safe_load(open(".github/workflows/spec-kit.yml"))["jobs"]["validate"]["with"]["tooling-ref"])')
        fetch() {
            [[ "$1" =~ ^[0-9a-f]{40}$ ]]
            git init --quiet "$2"
            git -C "$2" fetch --quiet --depth=1 https://github.com/bolens/.github.git "$1"
            git -C "$2" checkout --quiet --detach FETCH_HEAD
            test "$(git -C "$2" rev-parse HEAD)" = "$1"
        }
        fetch "$shared" "$scratch/shared"
        npm ci --ignore-scripts --no-audit --no-fund --prefix "$scratch/shared/tools/source-lint"
        make source-lint SOURCE_LINT_TOOLING="$scratch/shared"
        fetch "$spec" "$scratch/spec"
        python3 "$scratch/spec/scripts/validate-spec-kit.py" --expected-version current "$PWD"
        actionlint
        zizmor --offline --min-severity medium --min-confidence medium .github .pre-commit-config.yaml
        mapfile -d '' -t dockerfiles < <(git ls-files -z -- '**/Dockerfile' 'Dockerfile')
        test "${#dockerfiles[@]}" -gt 0
        hadolint --config .hadolint.yaml --failure-threshold error "${dockerfiles[@]}"
        python3 -m unittest discover -s scripts/tests -p test_native_ci.py
        ;;
    komga)
        python_tools
        test -n "${JAVA_HOME:-}"
        export JAVA_HOME_21="$JAVA_HOME"
        "$JAVA_HOME_21/bin/java" -version
        if (( EUID == 0 )); then
            # The owning compiler/fixture gates require a caller-owned source copy.
            # Descriptor-custody fixtures open every parent directory read-only.
            # Keep their private actor tree outside the traversal-only public scratch.
            unprivileged=$(mktemp -d /tmp/homelab-komga.XXXXXXXX)
            mkdir "$unprivileged/tmp" "$unprivileged/cache" "$unprivileged/source"
            chown 1000:1000 "$unprivileged" "$unprivileged/tmp" "$unprivileged/cache" "$unprivileged/source"
            # Archive only the tested revision: no Git metadata, ignored or live state.
            # pipefail preserves both producer and unprivileged extraction failures.
            git archive "$source_revision" | setpriv --reuid=1000 --regid=1000 --clear-groups \
                tar --extract --no-same-owner --directory "$unprivileged/source"
            env HOME="$unprivileged" TMPDIR="$unprivileged/tmp" XDG_CACHE_HOME="$unprivileged/cache" \
                PIP_CACHE_DIR="$unprivileged/cache/pip" npm_config_cache="$unprivileged/cache/npm" \
                setpriv --reuid=1000 --regid=1000 --clear-groups make -C "$unprivileged/source" komga-source-check
        else
            make komga-source-check
        fi
        ;;
    dotnet)
        bootstrap node
        python_tools
        export DOTNET_CLI_HOME="$scratch/dotnet" NUGET_PACKAGES="$scratch/nuget"
        export DOTNET_CLI_USE_MSBUILD_SERVER=0 MSBUILDDISABLENODEREUSE=1 UseSharedCompilation=false
        export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 DOTNET_NOLOGO=1
        python3 scripts/ci/check-dotnet-controls.py
        ;;
    site)
        npm_tools
        # Playwright1.64.1 owns the OS dependency list; it does not install a browser here.
        node_modules/.bin/playwright install-deps chrome
        bootstrap chrome
        export HOMELAB_CHROME_EXECUTABLE_PATH="$scratch/tools/chrome/chrome-linux64/chrome"
        version=$("$HOMELAB_CHROME_EXECUTABLE_PATH" --version)
        [[ "$version" == 'Google Chrome for Testing 157.0.8103.38'* ]]
        CI=true npm run test:site:ci -- --workers=2
        ;;
    links)
        bootstrap lychee
        python_tools
        python3 scripts/ci/check-native-links.py
        ;;
esac
