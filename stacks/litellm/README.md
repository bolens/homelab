# LiteLLM

OpenAI-compatible **LLM proxy** for Ollama, OpenAI, Anthropic, Azure, and [many other providers](https://docs.litellm.ai/docs/providers).

**Docs:** https://docs.litellm.ai/docs/proxy/docker_quick_start
**GitHub:** https://github.com/BerriAI/litellm
**Image:** `ghcr.io/berriai/litellm:main-stable` (pin a release tag in production)

## Quick start

1. `./prepare-stack.sh`, creates local config and ensures `ai-backend` plus `ingress-public`.
2. Set **`LITELLM_MASTER_KEY`**, **`UI_USERNAME`**, **`UI_PASSWORD`**, and **`POSTGRES_PASSWORD`** (plus optional **`POSTGRES_USER`** / **`POSTGRES_DB`**) in `stack.env` (see `stack.env.example`). **`UI_PASSWORD` = `LITELLM_MASTER_KEY`** is a common choice. Compose injects **`DATABASE_URL`** into the proxy container from those Postgres variables (bundled **`litellm-postgres`**); without a DB the Admin UI reports **"Not connected to DB!"**. The container reads **`UI_*`** from **`stack.env`** only (not from Compose `environment:` interpolation for those vars). Re-run **`./prepare-stack.sh`** after editing `stack.env` so **`.env`** stays aligned for bind-mount path interpolation (`LITELLM_CONFIG_FILE`).
3. Edit **`~/.config/litellm/config.yaml`** (or the path in **`LITELLM_CONFIG_FILE`**), default includes one Ollama model at `http://ollama:11434`; add models and `os.environ/...` API keys as needed.
4. `docker compose up -d` (after prepare, `.env` is a copy of `stack.env` with paths expanded for bind mounts)
5. Ensure **`stacks/litellm/caddy_snippet.conf`** is on the Caddy host (this repo's **`stacks/caddy`** compose bind-mounts **`../../stacks`** to **`/etc/caddy/import/stacks`**, which matches **`import ... stacks/*/caddy_snippet.conf`**). Reload after edits, e.g. from the caddy stack dir: **`docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile`**.

## Caddy path layout (this stack's snippet)

| Public URL | Upstream |
|------------|----------|
| `https://<host>/` | Dashboard (exact `/` is rewritten to upstream `/ui/`; Swagger stays under `/api/…`) |
| `https://<host>/api/v1/...` | OpenAI-compatible API (prefix stripped) |
| `https://<host>/api/docs`, `/api/openapi.json`, `/api/health/liveliness`, … | Same as upstream root paths after stripping `/api` |
| Old `https://<host>/v1/...` | **308** to `/api/v1/...` |
| `https://<host>/litellm/...` | Pass-through (CEL: path is **`/litellm`** or starts with **`/litellm/`**, avoids Caddy **`/litellm/*`** one-segment-only matching) |
| `https://<host>/.well-known/litellm-ui-config` | Optional pass-through (same JSON as under **`/litellm/`**) |
| `https://<host>/ui/*/favicon.ico` and **`/ui/*/*/favicon.ico`** | **Rewrite** → **`/ui/favicon.ico`** (two `handle` lines; deeper paths need another rule or upstream fix) |
| `https://<host>/ui/login`, **`/ui/v2/login`**, … (**POST**) | **`uri strip_prefix /ui`** → upstream **`/login`** or **`/v2/login`** (POST to `/ui/v2/...` alone upstream returns **405**) |
| `https://<host>/login`, **`/v2/login`**, … (**POST**) | Pass-through (not rewritten to **`/ui/...`**) |
| **`/get/*`**, **`/get_image`**, **`/organization/*`**, **`/project/*`**, **`/sso/*`**, **`/policy/*`**, **`/policies/*`**, **`/prompts/*`**, **`/guardrails/*`**, **`/callbacks/*`**, **`/config/*`**, **`/config_overrides/*`**, **`/credential*`**, **`/credentials*`**, **`/customer*`**, **`/end_user*`**, **`/end_users*`**, **`/budget*`**, **`/cache*`**, **`/global*`**, **`/router*`**, **`/cloudzero*`**, **`/alerting*`**, **`/email*`**, **`/claude-code*`**, **`/schedule/*`**, **`/search_tools/*`**, **`/tag/*`**, **`/vector_store/*`**, **`/in_product_nudges`**, **`/v2/*`**, **`/callback`** (OAuth) | Admin UI & proxy management APIs (pass-through via a CEL prefix matcher; the default SPA rule would otherwise prefix **`/ui`** and cause **404**/**405**). Do not use legacy **`path /callback*`**, it matches **`/callbacks`**. |

**Docker-only clients** (same Docker network as `litellm`) should keep **`http://litellm:4000/v1`**, no `/api` prefix (traffic does not go through this Caddy layout).

## Integration

| Client | Setting |
|--------|---------|
| **Open WebUI** | Through Caddy: API base **`https://<host>/api/v1`** (not `/v1` at host root). On **`ai-backend`**: **`http://litellm:4000/v1`**. API key = `LITELLM_MASTER_KEY` or a LiteLLM virtual key. |
| **LibreChat / n8n** | Any field expecting an OpenAI-compatible base URL + API key |
| **Ollama** | Keep `http://ollama:11434` for direct pulls; LiteLLM adds routing, keys, and extra backends |

## Portainer

- Repository compose path: `stacks/litellm/docker-compose.yml`.
- Run `./prepare-stack.sh` on the host so `~/.config/litellm/config.yaml` and `stack.env` exist (or paste their contents / bind-mount paths in Portainer).
- Attach the app to **`ai-backend`** and **`ingress-public`**; PostgreSQL stays private.

## Health

- In-container: `GET http://127.0.0.1:4000/health/liveliness` (upstream spelling)
- Through this Caddy snippet: **`GET https://<host>/api/health/liveliness`**

## Notes

- **Admin UI Usage (`?page=usage`) and SVG `NaN`:** if every model has **$0** spend (typical for Ollama with no pricing), some chart builds can throw **`rect` x/width/y `NaN`**. Set tiny **`input_cost_per_token`** / **`output_cost_per_token`** under each model's **`litellm_params`** in **`config.yaml`** (see **`litellm_config.yaml.example`**) so **`/global/spend/*`** returns non-zero spend; then hard-refresh the UI.
- **CSP report-only + `/cdn-cgi/challenge-platform`:** if the console reports violations against **`script-src 'unsafe-inline' 'unsafe-eval'`** or **`connect-src 'none'`** for Cloudflare's **`…/cdn-cgi/challenge-platform/…`** scripts, that is almost always **Cloudflare bot / challenge scripts** colliding with a **Content-Security-Policy-Report-Only** policy (from Cloudflare **Transform / Security Headers** or similar). **Report-only does not block anything**, it only logs. To reduce noise: relax or remove that report-only CSP for this hostname, lower **Security Level** / bot sensitivity for **`litellm.example.com`**, or accept the messages. This stack's **Caddy snippet does not set that CSP**; fixing it is in **Cloudflare** (or whatever adds the header), not in the proxy routes here.
- **Browser console noise:** messages from **`console-log.service.ts`**, **`runtime.lastError`**, **`Failed to set badge state`**, or **`bitwarden_*`** / **`bootstrap-autofill-overlay.js`** are almost always **password-manager extensions** (e.g. Bitwarden), not LiteLLM. Use a private window or disable the extension on this site to confirm.
- **Postgres** ships with this stack (`litellm-postgres`, volume **`litellm_pgdata`**). Set **`POSTGRES_PASSWORD`** in **`stack.env`**; **`DATABASE_URL`** is built in **`docker-compose.yml`**. **External DB:** remove the **`postgres`** service, remove the **`DATABASE_URL`** line under the **`litellm`** service **`environment:`** block, and set **`DATABASE_URL`** in **`stack.env`** yourself ([upstream deploy](https://docs.litellm.ai/docs/proxy/deploy#deploy-with-database)).
- Do not commit **`stack.env`** or secrets inside **`~/.config/litellm/config.yaml`**; use `os.environ/VAR` for keys.
