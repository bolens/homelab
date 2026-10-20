# Dissect target 3.25.1 requires CPython 3.13 pathlib/glob internals.
FROM python:3.13-slim-bookworm@sha256:ed86c82274b3c69b52fb5820f358f0bd7df0b603332063cb5c6e32bd220c3e6e

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && python -m pip check \
    && acquire --help >/dev/null

WORKDIR /data

# Run acquire CLI; use `docker compose run --rm acquire [TARGETS]` (e.g. /data/evidence.vmdk)
# Output: use -o /data/output.tar for the forensic container archive.
ENTRYPOINT ["acquire"]
