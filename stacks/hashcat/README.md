# Hashcat

Hashcat is the world's fastest and most advanced password recovery utility supporting hundreds of hash types.

**Website:** https://hashcat.net
**GitHub:** https://github.com/hashcat/hashcat

## Usage

CLI-only tool run on demand via `docker compose run` to crack password hashes using GPU or CPU.
Useful for auditing captured hashes in a pentest lab. Wordlists are mounted read-only from the host.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. No required variables — optionally set HASHCAT_WORDLIST_DIR to your host wordlist path.
3. For GPU acceleration ensure the NVIDIA/AMD container runtime is installed on the host.
4. Run: `docker compose run --rm hashcat <hashcat args>`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| HASHCAT_WORDLIST_DIR | No | — | Host path to wordlist directory (mounted read-only) |

## Notes

- TZ and locale come from shared.env.
- GPU passthrough requires nvidia-container-toolkit or equivalent AMD runtime on the host.
- No persistent service — use `docker compose run --rm` for each job.
