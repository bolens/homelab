# pwntools-gdb

pwntools + GDB/pwndbg is a containerized CTF and exploit-development environment with Python pwntools and a patched GDB.

**GitHub:** https://github.com/Gallopsled/pwntools

## Usage

This is a CLI-only development container for CTF challenges and binary exploitation research.
Run it interactively with `docker compose run` rather than as a persistent background service.
No web UI or reverse proxy is needed.

## Setup

1. Copy `stack.env.example` to `stack.env` and review `PWNTOOLS_WORKSPACE_PATH`.
2. Run `./prepare-stack.sh` to prepare local files.
3. Use `docker compose run --rm pwntools-gdb bash` to enter the environment.

## Environment variables

No required environment variables. TZ/locale come from `shared.env`.

## Notes

- Designed for interactive use via `docker compose run`, not `docker compose up -d`.
- The definition grants `SYS_PTRACE` and disables seccomp for GDB, without privileged mode.
- Networking is disabled by default.
