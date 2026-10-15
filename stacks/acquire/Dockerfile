# Dissect target 3.25.1 requires CPython 3.13 pathlib/glob internals.
FROM python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && python -m pip check \
    && acquire --help >/dev/null

WORKDIR /data

# Run acquire CLI; use `docker compose run --rm acquire [TARGETS]` (e.g. /data/evidence.vmdk)
# Output: use -o /data/output.tar for the forensic container archive.
ENTRYPOINT ["acquire"]
