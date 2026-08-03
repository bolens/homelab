#!/usr/bin/env bash
set -euo pipefail

# Apply conservative limits to running containers which do not already define
# them. Existing explicit CPU and memory limits always win.
#
# These are runtime limits, so this script is safe to re-run after a Compose or
# Watchtower recreation.

container_ids="$(docker ps -q)"
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
    args+=(--memory "$mem" --memory-swap "$mem")
  fi
  if [[ "$pids" == "0" || "$pids" == "-1" || "$pids" == "<no value>" ]]; then
    args+=(--pids-limit "$pids_limit")
  fi
  args+=("$id")

  "${args[@]}" >/dev/null
  printf '%-32s cpus=%-4s memory=%-4s shares=%-3s pids=%s\n' \
    "$name" \
    "$([[ "$nano_cpus" == "0" ]] && printf '%s' "$cpus" || printf 'keep')" \
    "$([[ "$memory" == "0" ]] && printf '%s' "$mem" || printf 'keep')" \
    "$shares" \
    "$([[ "$pids" == "0" || "$pids" == "-1" || "$pids" == "<no value>" ]] && printf '%s' "$pids_limit" || printf 'keep')"
done
