# Stack preparation standards

Every top-level directory under `stacks/` has an executable
`prepare-stack.sh`, including CLI-only and pointer stacks. Preparation is
idempotent: it may create missing local files, directories, Docker networks,
and explicitly external named volumes, but it does not overwrite existing
runtime configuration or start containers.

## Required lifecycle

A standard wrapper:

1. Enables `set -euo pipefail`.
2. Resolves its own directory and sources `scripts/prepare-stack-lib.sh`.
3. Calls `prepare_stack_begin`.
4. Copies `stack.env.example` and `caddy_snippet.conf.example` when present.
5. Performs stack-specific config copies or directory preparation.
6. Ensures literal external networks and volumes declared by Compose.
7. Calls `prepare_stack_end`.

The shared end step synchronizes `stack.env` to `.env`, reports unfinished
variable names or Caddy placeholders without printing values, and gives the
operator the next deployment command.

Preparation must never:

- overwrite an existing secret or application config;
- print environment values;
- start, restart, stop, or recreate a container;
- create a media bind directory when a missing remote mount could be the cause;
- silently enable optional GPU, privileged, or alternate-image overrides.

Optional behavior should be described with `prepare_stack_msg`. Copy an
optional override only when the operator explicitly chooses it.

## Audit and maintenance

Run:

```bash
make prepare-audit
make validate
```

The audit covers all top-level stack directories. For Compose stacks it also
compares preparation against literal external networks and volumes. Maintainers
can apply mechanical repairs with:

```bash
python3 scripts/audit-prepare-scripts.py --fix
git diff
```

Always review the complete diff. Nonstandard templates still require a tailored
copy step or an explicit informational message. Use
`scripts/prepare-stack.examples/standard-with-lib.sh` as the starting point for
new stacks.
