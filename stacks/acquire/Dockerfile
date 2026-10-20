# Dissect target 3.25.1 requires CPython 3.13 pathlib/glob internals.
FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && python -m pip check \
    && acquire --help >/dev/null

WORKDIR /data

# Run acquire CLI; use `docker compose run --rm acquire [TARGETS]` (e.g. /data/evidence.vmdk)
# Output: use -o /data/output.tar for the forensic container archive.
ENTRYPOINT ["acquire"]
