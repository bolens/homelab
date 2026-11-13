#!/usr/bin/env bash
# Public-source build only. Does not run Docker, install a unit or touch live state.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
output=${1:?usage: build-agent.sh NEW_EMPTY_OUTPUT_DIRECTORY}
# Refuse an existing output, including a dangling symlink.
[[ ! -e "$output" && ! -L "$output" ]]
mkdir -m 700 -- "$output"
output=$(cd -- "$output" && pwd)
test "$(go env GOVERSION)" = go1.27.3
export HOME="$output/home" GOPATH="$output/gopath" GOCACHE="$output/gocache" GOMODCACHE="$output/gomodcache"
mkdir -m 700 -- "$HOME"
export GOAUTH=off GOENV=off GOTOOLCHAIN=local GOPROXY=https://proxy.golang.org GOSUMDB=sum.golang.org
export GOPRIVATE='' GONOPROXY='' GONOSUMDB='' GOINSECURE=''
export GOMAXPROCS=2 GOMEMLIMIT=2GiB GOFLAGS='-mod=readonly -p=2' CGO_ENABLED=0 GOOS=linux GOARCH=amd64
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
python3 - "$root" <<'PYTHON'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for patch in json.loads((root / 'source.json').read_text())['patches']:
    assert hashlib.sha256((root / patch['path']).read_bytes()).hexdigest() == patch['sha256']
PYTHON
curl --fail --silent --show-error --location --proto '=https' \
  'https://codeload.github.com/woodpecker-ci/woodpecker/tar.gz/3f1bb0bd0db28e410ad797034d75780116122c91' \
  --output "$output/upstream.tar.gz"
printf '%s  %s\n' 253dd24b6f4c4ac733c92bb962b4522d6a8b1fa7ffb9024b566665ab9bb551e7 "$output/upstream.tar.gz" | sha256sum --check --strict
mkdir "$output/source" "$output/image"
tar --extract --gzip --file "$output/upstream.tar.gz" --directory "$output/source" --strip-components=1 --no-same-owner
cd -- "$output/source"
for patch in network-create.patch cgroup-parent.patch; do
  git apply --check "$root/$patch"
  git apply "$root/$patch"
done
go test ./pipeline/backend/docker | tee "$output/backend-tests.log"
go build -buildvcs=false -trimpath -ldflags '-s -w -X go.woodpecker-ci.org/woodpecker/v3/version.Version=3.20.1+networkcreate.1.cgroupparent.1' \
  -o "$output/image/woodpecker-agent" ./cmd/agent
cp -- "$root/Dockerfile" "$output/image/Dockerfile"
sha256sum "$output/image/woodpecker-agent" > "$output/binary.sha256"
go version -m "$output/image/woodpecker-agent" > "$output/binary-build-info.txt"
printf '%s\n' 'Source and binary ready. Docker image build and deployment require separate review.'
