# Hashcat

Hashcat is the world's fastest and most advanced password recovery utility supporting hundreds of hash types.

**Website:** https://hashcat.net
**GitHub:** https://github.com/hashcat/hashcat

## Usage

CLI-only tool run on demand via `docker compose run` to crack password hashes using GPU or CPU.
Useful for auditing captured hashes in a pentest lab. Wordlists are mounted read-only from the host.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Review `HASHCAT_WORK_PATH` and `HASHCAT_WORDLIST_DIR`.
3. Build once with `docker compose build hashcat`.
4. Run: `docker compose run --rm hashcat <hashcat args>`.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| HASHCAT_WORDLIST_DIR | No | None | Host path to wordlist directory (mounted read-only) |
| HASHCAT_WORK_PATH | No | ~/security-lab/hashcat/work | Writable job directory |

## Notes

- TZ and locale come from shared.env.
- The base definition is CPU-compatible; add a host-specific Compose override for GPU passthrough.
- No persistent service, use `docker compose run --rm` for each job.
