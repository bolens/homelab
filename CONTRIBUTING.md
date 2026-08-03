# Contributing

Changes should preserve local runtime configuration and keep committed examples
portable.

Before submitting a change:

```bash
make validate
make secrets
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

Use focused commits with Conventional Commit subjects. Explain migrations or
behavior changes in the commit body.

Optional local hooks can run the same checks before every commit:

```bash
pre-commit install
```
