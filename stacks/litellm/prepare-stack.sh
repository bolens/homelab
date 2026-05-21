#!/usr/bin/env bash
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env

_lit_cfg_default="${HOME}/.config/litellm/config.yaml"
_lit_cfg="$_lit_cfg_default"
if [[ -f stack.env ]]; then
  line=$(grep -E '^LITELLM_CONFIG_FILE=' stack.env 2>/dev/null | tail -1) || true
  if [[ -n "${line}" ]]; then
    val="${line#*=}"
    val="${val%$'\r'}"
    val="${val#\"}"
    val="${val%\"}"
    val="${val#\'}"
    val="${val%\'}"
    [[ -n "$val" ]] && _lit_cfg="$val"
  fi
fi
_lit_cfg="$(prepare_stack__expand_home_in_path "$_lit_cfg")"
_lit_dir="$(dirname "$_lit_cfg")"
mkdir -p "$_lit_dir"

if [[ ! -f "$_lit_cfg" ]]; then
  if [[ -f "$_PREPDIR/litellm_config.yaml" ]]; then
    cp "$_PREPDIR/litellm_config.yaml" "$_lit_cfg"
    prepare_stack_msg "migrated existing stacks/litellm/litellm_config.yaml -> $_lit_cfg"
  else
    cp "$_PREPDIR/litellm_config.yaml.example" "$_lit_cfg"
    prepare_stack_msg "created $_lit_cfg from litellm_config.yaml.example — edit model_list for your Ollama models and providers."
  fi
else
  prepare_stack_msg "LiteLLM config already exists at $_lit_cfg (left unchanged)."
fi

if [[ -f stack.env ]] && ! grep -qE '^LITELLM_CONFIG_FILE=' stack.env; then
  {
    echo ""
    echo "# Host path to LiteLLM proxy YAML (bind-mounted read-only as /app/config.yaml)"
    echo 'LITELLM_CONFIG_FILE=${HOME}/.config/litellm/config.yaml'
  } >> stack.env
  prepare_stack_msg "appended LITELLM_CONFIG_FILE to stack.env (default under ~/.config/litellm/)"
fi

prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "monitor"

# Compose volume interpolation does not always expand ${HOME} from .env; rewrite that line to an absolute path in .env only.
litellm_prepare__expand_config_path_in_dotenv() {
  [[ -f .env ]] || return 0
  local line val exp tmp
  line=$(grep -E '^LITELLM_CONFIG_FILE=' .env 2>/dev/null | tail -1) || return 0
  [[ -n "$line" ]] || return 0
  val="${line#*=}"
  val="${val%$'\r'}"
  val="${val#\"}"
  val="${val%\"}"
  val="${val#\'}"
  val="${val%\'}"
  exp="$(prepare_stack__expand_home_in_path "$val")"
  [[ "$val" != "$exp" ]] || return 0
  tmp="$(mktemp)"
  grep -vE '^LITELLM_CONFIG_FILE=' .env >"$tmp"
  printf 'LITELLM_CONFIG_FILE=%s\n' "$exp" >>"$tmp"
  mv "$tmp" .env
  prepare_stack_msg "expanded LITELLM_CONFIG_FILE in .env for Docker volume interpolation"
}

litellm_prepare__expand_config_path_in_dotenv
prepare_stack_end
