# Acquire (Dissect)

Gather forensic artifacts from disk images or a live system into a single archive. [Acquire](https://docs.dissect.tools/en/stable/projects/acquire/index.html) uses the [Dissect](https://dissect.tools/) framework: it collects modules (paths/globs) by profile (`full`, `default`, `minimal`, `none`) and outputs a lightweight container for triage. Supports VMDK, E01, and other formats via Dissect; optional volatile (memory) collection.

**Docs:** https://docs.dissect.tools/en/stable/projects/acquire/  
**GitHub:** https://github.com/fox-it/acquire  
**PyPI:** https://pypi.org/project/acquire/  

## Quick start

1. **Create a data directory** for evidence and output:

   ```bash
   mkdir -p data
   ```

2. **Copy env template** (optional):

   ```bash
   cp stack.env.example stack.env
   ```

3. **Place a disk image** (e.g. `evidence.vmdk`, `disk.e01`) under `data/`, or use a directory for OS-level fallback.

4. **Run acquire** against a disk image (recommended: specify output path):

   ```bash
   docker compose run --rm acquire /data/evidence.vmdk -o /data/output.tar
   ```

   With a profile (e.g. `default`, `minimal`, `full`):

   ```bash
   docker compose run --rm acquire /data/evidence.vmdk --profile default -o /data/output.tar
   ```

   To collect from a directory using OS filesystem access (no raw disk):

   ```bash
   docker compose run --rm acquire --force-fallback /data/capture -o /data/output.tar
   ```

## Configuration

| Item | Details |
|------|---------|
| **Access** | CLI only; no web UI, no host ports. Run via `docker compose run --rm acquire ...`. |
| **Image** | Built locally from Dockerfile (`pip install acquire`). |
| **Storage** | Local `data/` bind-mounted to `/data` for evidence and output. Output files may be root-owned; to access as your user run `chown -R $(id -u):$(id -g) ./data` after a run. |

## Common options

| Option | Description |
|--------|-------------|
| `TARGETS` | Path(s) to disk image(s) or, with `--force-fallback`, directory (default: `local` = host). |
| `-o PATH`, `--output PATH` | Output path for the forensic container archive. |
| `--profile {full,default,minimal,none}` | Collection profile (OS-specific modules). |
| `--force-fallback` | Use OS filesystem access (e.g. for a directory instead of raw disk). |
| `--volatile-profile {default,extensive,none}` | Collect volatile (memory) artifacts where supported. |

Full options: [acquire tool reference](https://docs.dissect.tools/en/stable/tools/acquire.html).

## Notes

- Use only on **authorized** evidence (your own systems or with explicit permission).
- **Live acquisition** (default target `local`) needs raw disk access and is typically run on the host or with privileged access; in Docker, prefer disk image paths or `--force-fallback` with a mounted directory.
- Output is a single archive (the “lightweight container”); analyze it with Dissect or other tools.
