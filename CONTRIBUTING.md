# Contributing

Changes should preserve local runtime configuration and keep committed examples
portable.

Before submitting a change:

```bash
make hooks-install
make ci-local
```

Do not commit `stack.env`, `.env`, private keys, credentials, real hostnames,
private addresses, or machine-specific paths. Update `stack.env.example`,
`stack.yaml`, the stack README, and preparation behavior together when a
stack's contract changes.

After adding or renaming a stack, regenerate documentation:

```bash
python3 scripts/build-stack-catalog.py
python3 scripts/build-topology.py --in-place
```

Keep application-specific setup, environment variables, health checks, and
troubleshooting in `stacks/<name>/README.md`. Cross-stack concepts belong in
`documents/`; the root README should remain a short navigation and orientation
page. Update generated documents through their scripts rather than editing
generated sections by hand.

Use focused commits with Conventional Commit subjects. Explain migrations or
behavior changes in the commit body.

Local hooks run staged secret scanning, workflow checks, Dockerfile linting,
dependency configuration validation, repository validation, and whitespace
checks before every commit:

```bash
make hooks-install
```
