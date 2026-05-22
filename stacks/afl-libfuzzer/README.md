# AFL++ / libFuzzer

Coverage-guided fuzzing toolbox (AFL++ and libFuzzer) for discovering crashes and vulnerabilities in binaries and libraries.

**GitHub:** https://github.com/AFLplusplus/AFLplusplus

## Usage

Run interactively via `docker compose run` to fuzz target binaries. No web UI; all interaction is through the container shell. Useful for security research and CI fuzzing pipelines.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. No required environment variables — defaults from shared.env are sufficient for most cases.
3. Mount your target binary or source into the container before running.
4. Deploy: `docker compose run --rm afl-libfuzzer bash`

## Environment variables

No required environment variables. TZ and locale are inherited from shared.env.

## Notes

- This is a CLI-only tool; use `docker compose run` rather than `up -d`.
- AFL++ requires `kernel.core_pattern` and CPU frequency scaling tuned on the host for best performance.
- Use `--privileged` if AFL++ complains about missing /proc settings.
