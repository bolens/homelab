# Dissect target 3.25.1 requires CPython 3.13 pathlib/glob internals.
FROM python:3.13-slim-bookworm@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && python -m pip check \
    && acquire --help >/dev/null

WORKDIR /data

# Run acquire CLI; use `docker compose run --rm acquire [TARGETS]` (e.g. /data/evidence.vmdk)
# Output: use -o /data/output.tar for the forensic container archive.
ENTRYPOINT ["acquire"]
