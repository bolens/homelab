# auth-fuzz

HTTP authentication fuzzer for testing login endpoints against wordlists and brute-force attack patterns.

## Usage

CLI-only FFUF workspace. The default command prints FFUF help and the configured wordlist directory is mounted read-only.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Review the wordlist and output paths.
3. Build once with `docker compose build auth-fuzz`.
4. Run: `docker compose run --rm auth-fuzz <ffuf arguments>`.

## Environment variables

`AUTH_FUZZ_WORDLIST_PATH` and `AUTH_FUZZ_OUTPUT_PATH` default under `${HOME}/security-lab`.

## Notes

- CLI-only tool; use `docker compose run` rather than `up -d`.
- Only target systems you own or have explicit written permission to test.
- Combine with Burp Suite or ZAP to test additional web application paths.
