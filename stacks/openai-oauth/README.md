# openai-oauth

Community ChatGPT account proxy, built from the pinned [openai-oauth 2.0.0 package](https://github.com/EvanZhouDev/openai-oauth/tree/v2.0.0/packages/openai-oauth). This is a third-party project, not the official OpenAI API. Node and npm dependencies are pinned by digest and lockfile.

The lock overrides `@ai-sdk/provider-utils` to 4.0.33 for the response-size fix in
[GHSA-866g-f22w-33x8](https://github.com/advisories/GHSA-866g-f22w-33x8).
Upstream 2.0.0 still pins the vulnerable version. Remove this override after
upstream adopts a fixed version. The Node 26 image and `make ci-local` test all
three affected response handlers plus chat and streaming compatibility with
synthetic responses, without credentials or provider requests.

## Setup and authentication

1. Run `./prepare-stack.sh`, then `docker compose build --pull=false`.
2. Keep existing Codex credentials separate. This stack stores its own login in the `oauth_auth` volume, owned by UID 1000. Never mount a workstation Codex directory.
3. Run `docker compose -f docker-compose.yml -f docker-compose.login.yml run --rm login`. Open the printed authorization URL and sign in yourself. The temporary callback listens only on host loopback port 1455. On a remote host, first forward `ssh -L 1455:127.0.0.1:1455 user@host`. The login container uses host networking only for this callback and exits after completion.
4. Start the regular service with `docker compose up -d --no-build --pull never`. It has no published ports or Caddy/Cloudflare route.
5. Attach only an authenticated gateway, such as LiteLLM, to `oauth-backend`. This upstream has no inbound API-key enforcement. Never attach it to a broad application or ingress network.

Use LiteLLM's [optional override](../litellm/docker-compose.oauth.yml), preserving its existing image and settings. Add a route to the existing private model configuration after checking the account's `/v1/models` response:

```yaml
model_list:
  - model_name: chatgpt-personal
    litellm_params:
      model: openai/ACCOUNT_MODEL_ID
      api_base: http://openai-oauth:10531/v1
      api_key: unused
```

The dummy upstream key satisfies the OpenAI client. LiteLLM must continue enforcing its real client keys. Clients on `ai-backend` keep `http://litellm:4000/v1` and their existing LiteLLM key. Never replace paid API, local embeddings, speech, or image providers automatically.

## Verification and limitations

Check `docker compose ps` and `/health` from the dedicated network without making an inference request. After login, verify model listing, one short chat completion and streaming through LiteLLM. Anonymous LiteLLM requests must still fail. Preserve existing model routes and conversation data. `/health` alone does not establish account access.

Upstream supports chat completions, Responses, model listing, image generation and edits. It does not provide embeddings or speech. Responses requires full history rather than `previous_response_id` replay. Verify multimodal clients separately because upstream 2.0.0 has a base64 chat-image limitation. Account model access and usage limits still apply.

## Persistence and updates

The auth volume contains sensitive rotating account tokens and must be backed up privately. Stop the service before copying it, restore into an isolated directory, and check file integrity/readability before changing the image or dependency version. Keep the prior image and credentials available until login and a gateway request work. No application chat data is stored here. Do not print logs or authorization URLs in public diagnostics. Re-login with the one-shot command when needed.
