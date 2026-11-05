# Preserve AI settings across updates

Keep the deployment selection, application state and provider controls together.
The tracked stacks are portable examples. Private configuration and databases own
the deployed model choices, defaults, credentials and spending limits.

## Save the complete deployment selection

For each stack, keep the ordered list of base and private override files in
`COMPOSE_FILE` inside its private `stack.env`. Include maintenance overrides for
storage, image selection and client defaults as well as AI-provider overrides.
On Linux, for example:

```dotenv
COMPOSE_FILE=docker-compose.yml:/path/to/private/compose.ai.yml:/path/to/private/compose.maintenance.yml
```

Run the stack's preparation script after editing `stack.env`. Preparation preserves
that source file and refreshes `.env` from it. An override selection saved only in
`.env` is lost at the next preparation. Keep the same Compose project name so
project-scoped volumes retain their identities.

Compare the selection with the running container's
`com.docker.compose.project.config_files` label before redeploying. Then use
`docker compose config --quiet` to validate it. Review the rendered image, build
arguments, mounts, networks and environment privately when checking equivalence.
Full rendered configuration can contain credentials.

With `pkexec docker`, pass explicit `--project-directory /path/to/stack` and
`--env-file /path/to/stack/.env` options so the elevated process uses the intended
stack and its saved file selection.

An explicit `-f` list must include every required override. Deployment editors and
update helpers must preserve the same selection. Later files can override earlier
values, so keep their order. See Docker's [Compose environment variables][compose-env]
and [merge rules][compose-merge].

## Preserve each application's source of truth

| Component | State to retain |
| --- | --- |
| LiteLLM | The private YAML selected by `LITELLM_CONFIG_FILE`, `stack.env`, PostgreSQL data volume and any private Compose overrides. Database-backed models, virtual-key permissions and budgets live in PostgreSQL. Preserve `STORE_MODEL_IN_DB` when using database-backed model management. |
| GitHub Copilot upstream | The operator-configured token directory and its mount, together with `GITHUB_COPILOT_TOKEN_DIR`. A token directory inside a replaceable container is insufficient. |
| Open WebUI | `open_webui_data`, including its SQLite database. Connections, model filters, defaults, embeddings and speech settings can be database-backed. Keep any storage/cache overrides selected. |
| LibreChat | MongoDB, `librechat_data`, authentication configuration, private custom-endpoint YAML and its bind selection. Keep scoped inference keys in private environment configuration. |
| Vane | Its configured data and uploads volumes. Provider choices and preferences are in the data volume. Retain `VANE_DATA_VOLUME` and `VANE_DATA_EXTERNAL` when reusing a legacy Perplexica volume. |
| Open Notebook | Both the SurrealDB database and `/app/data` volume, plus private environment configuration. Registered models, credentials and defaults require the existing database. |
| Nodepad | Browser-owned notes and provider selection at the same site origin, private server-side LiteLLM settings and the build arguments for first-visit defaults. Docker volume backups do not include browser storage. |
| Paperless-GPT | Private environment settings and prompt/data volumes. Keep the existing chat and vision providers/models when retaining a dormant cloud connection. |
| Paperless-AI next | Private environment settings and the data volume, including runtime provider overrides. Preserve the active local provider separately from optional custom cloud settings. |

Use each stack's README and Compose file for its exact volume and bind names.
Record the effective database directory as well as the declared volume name.
Include private bind files and Compose selectors in configuration backups.

Nodepad's `NEXT_PUBLIC_*` defaults are compiled into the image. Retain the build
arguments when rebuilding. A registry image uses its own compiled defaults.
Runtime environment changes do not rebuild the client bundle. Existing browser
settings remain a separate source of truth.

## Retain the spending controls

Preserve the complete LiteLLM model parameters and virtual-key configuration,
including rate limits, retry policy, fallbacks, disabled models and model access
lists. Keep provider-required routing headers and model-specific compatibility
settings when editing a database-backed deployment. Follow the partial-update
guidance in the [LiteLLM README](../stacks/litellm/README.md#integration).

Provider-side controls persist outside Docker. Retain the existing Cloudflare AI
Gateway spend/rate rules and its required route header, OpenRouter key budget,
Copilot paid-usage policy, and API credit/billing settings. A LiteLLM rate limit
does not replace a provider spending limit. Keep optional trial models out of
automatic document processing when that is the operator's policy.

## Verify an update

Before changing an image or deployment, follow the [live-operation workflow](../AGENTS.md#live-configuration-and-updates):
capture the current configuration and data baseline, back up affected persistent
state, and verify an isolated restore. Keep credentials and backup contents private.

After the update, compare the deployed project, file selection, mounts and effective
settings with that baseline. Check application defaults, model choices, key
permissions, provider routing and budgets. Verify original records and file contents,
then run bounded synthetic requests through the applications' configured connections.
Keep disabled or unfunded providers disabled and avoid changing defaults for testing.

Retain the prior compatible image and verified backup until data and behavior checks
pass. Clean up only temporary copies created for that operation. Future database
migrations need the owning stack's compatibility and rollback checks as well.

[compose-env]: https://docs.docker.com/compose/how-tos/environment-variables/envvars/
[compose-merge]: https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/
