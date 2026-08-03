#!/usr/bin/env bash
set -euo pipefail

# Preview conservative fallback limits for running containers that do not
# already define them. Pass --apply to mutate container runtime settings.
# Prefer persistent, stack-specific limits in Compose.

apply=false
containers=()
while (($#)); do
  case "$1" in
    --apply) apply=true ;;
    --container)
      [[ -n "${2:-}" ]] || { echo "--container requires a name" >&2; exit 2; }
      containers+=("$2")
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--container NAME ...] [--apply]"
      echo "Default: preview proposed runtime-only limits. --apply requires at least one --container."
      echo "Prefer persistent, targeted limits in each stack's Compose file."
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [[ "$apply" == true && ${#containers[@]} -eq 0 ]]; then
  echo "Refusing bulk mutation: --apply requires at least one --container NAME." >&2
  exit 2
fi

if ((${#containers[@]})); then
  container_ids=""
  for container in "${containers[@]}"; do
    id="$(docker ps -q --filter "name=^/${container}$")"
    [[ -n "$id" ]] || { echo "Running container not found: $container" >&2; exit 1; }
    container_ids+="${id}"$'\n'
  done
else
  container_ids="$(docker ps -q)"
fi
if [[ -z "$container_ids" ]]; then
  exit 0
fi

for id in $container_ids; do
  name="$(docker inspect "$id" --format '{{.Name}}' | sed 's#^/##')"
  nano_cpus="$(docker inspect "$id" --format '{{.HostConfig.NanoCpus}}')"
  memory="$(docker inspect "$id" --format '{{.HostConfig.Memory}}')"
  pids="$(docker inspect "$id" --format '{{.HostConfig.PidsLimit}}')"

  cpus="1"
  mem="2g"
  shares="256"
  pids_limit="512"

  case "$name" in
    caddy|cloudflare-tunnel|adguard-home|pihole|unbound|headscale)
      cpus="1"
      mem="1g"
      shares="512"
      ;;
    *postgres*|*mariadb*|*mysql*|*-db|*database*|*redis*|*valkey*|*rabbit*|*mongo*|*meilisearch*)
      cpus="1.5"
      mem="2g"
      shares="384"
      ;;
    plex|jellyfin|emby)
      cpus="6"
      mem="8g"
      shares="384"
      pids_limit="1024"
      ;;
    immich-server|immich-machine-learning|ollama|open-webui|whisper-asr|kokoro-tts)
      cpus="4"
      mem="8g"
      shares="256"
      pids_limit="1024"
      ;;
    baserow|ail-framework|dtrack-apiserver)
      cpus="2"
      mem="6g"
      shares="256"
      pids_limit="1024"
      ;;
    nzbget|rtorrent|flood|sabnzbd|sonarr|radarr|lidarr|readarr|whisparr|prowlarr|bazarr|soulseek|syncthing)
      cpus="2"
      mem="4g"
      shares="256"
      ;;
    code-server|woodpecker-agent|stirling-pdf|paperless-ngx|paperless-gpt|presidio-*)
      cpus="2"
      mem="4g"
      shares="256"
      pids_limit="1024"
      ;;
  esac

  args=(docker update --cpu-shares "$shares")
  if [[ "$nano_cpus" == "0" ]]; then
    args+=(--cpus "$cpus")
  fi
  if [[ "$memory" == "0" ]]; then
    args+=(--memory "$mem")
  fi
  if [[ "$pids" == "0" || "$pids" == "-1" || "$pids" == "<no value>" ]]; then
    args+=(--pids-limit "$pids_limit")
  fi
  args+=("$id")

  if [[ "$apply" == true ]]; then
    "${args[@]}" >/dev/null
  fi
  printf '%-8s %-32s cpus=%-4s memory=%-4s shares=%-3s pids=%s\n' \
    "$([[ "$apply" == true ]] && printf 'applied' || printf 'preview')" \
    "$name" \
    "$([[ "$nano_cpus" == "0" ]] && printf '%s' "$cpus" || printf 'keep')" \
    "$([[ "$memory" == "0" ]] && printf '%s' "$mem" || printf 'keep')" \
    "$shares" \
    "$([[ "$pids" == "0" || "$pids" == "-1" || "$pids" == "<no value>" ]] && printf '%s' "$pids_limit" || printf 'keep')"
done

if [[ "$apply" == false ]]; then
  echo "No changes made. Use --apply only after reviewing the preview." >&2
fi
