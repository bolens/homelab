# Validation quickstart

Run foundation tests without dependencies, network or media:

```sh
python3 -m unittest discover -s stacks/mylar3/config -p 'test_tagger_runtime.py'
python3 -m unittest discover -s stacks/mylar3/config -p 'test_tagger_metadata.py'
```

Build the candidate with `docker build -t homelab-mylar3:local stacks/mylar3` and run
`stacks/mylar3/verify-image.sh homelab-mylar3:local` without live mounts. The modern runtime
is included, but native Mylar still uses its original tagger.
Use `make ci-local` for the repository gate.

The candidate gate runs `test_modern_tagger.py` with the isolated Python and real
console command. It also runs as user 1000 in the read-only/no-network verification
container. The source-only upstream-base gate explicitly reports the modern runtime
as absent. Archive publication and live gates remain pending. Optional transport cases use a local controlled HTTP server,
not provider accounts. No live canary or backend switch is part of foundation tests.
