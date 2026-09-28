# Validation quickstart

Run foundation tests without dependencies, network or media:

```sh
python3 -m unittest discover -s stacks/mylar3/config -p 'test_tagger_runtime.py'
python3 -m unittest discover -s stacks/mylar3/config -p 'test_tagger_metadata.py'
```

Build the candidate with `docker build -t homelab-mylar3:local stacks/mylar3` and run
`stacks/mylar3/verify-image.sh homelab-mylar3:local` without live mounts. The foundation
is checked during the build but is not copied into the active native backend.
Use `make ci-local` for the repository gate.

Later real-CLI/archive gates need the locked runtime and generated local fixtures.
Their commands will be recorded when implemented. Do not mark them complete from
mocked subprocess tests. Optional transport cases use a local controlled HTTP server,
not provider accounts. No live canary or backend switch is part of foundation tests.
