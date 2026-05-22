# auth-fuzz

HTTP authentication fuzzer for testing login endpoints against wordlists and brute-force attack patterns.

## Usage

CLI-only tool. Run via `docker compose run` pointing at a target URL. Used in homelab penetration testing to audit login forms, HTTP Basic Auth, and API key endpoints.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. No required environment variables — TZ and locale come from shared.env.
3. Deploy: `docker compose run --rm auth-fuzz <target-url>`

## Environment variables

No required environment variables. TZ and locale are inherited from shared.env.

## Notes

- CLI-only tool; use `docker compose run` rather than `up -d`.
- Only target systems you own or have explicit written permission to test.
- Combine with Burp Suite or ZAP for more comprehensive web-app fuzzing.
