# AFL++ / libFuzzer

Coverage-guided fuzzing toolbox (AFL++ and libFuzzer) for discovering crashes and vulnerabilities in binaries and libraries.

**GitHub:** https://github.com/AFLplusplus/AFLplusplus

## Usage

Run interactively via `docker compose run` to fuzz target binaries. No web UI; all interaction is through the container shell. Useful for security research and CI fuzzing pipelines.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Review `AFL_SOURCE_PATH` and `AFL_OUTPUT_PATH`.
3. Place your target source or binary under the configured source directory.
4. Deploy: `docker compose run --rm afl-libfuzzer bash`

## Environment variables

The source and output paths default under `${HOME}/security-lab/afl`.

## Notes

- This is a CLI-only tool; use `docker compose run` rather than `up -d`.
- AFL++ requires `kernel.core_pattern` and CPU frequency scaling tuned on the host for best performance.
- The default container has no network and does not require privileged mode.
