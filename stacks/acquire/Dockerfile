FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

WORKDIR /data

# Run acquire CLI; use `docker compose run --rm acquire [TARGETS]` (e.g. /data/evidence.vmdk)
# Output: use -o /data/output.tar for the forensic container archive.
ENTRYPOINT ["acquire"]
