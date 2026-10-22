FROM python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83

WORKDIR /app

# Build explicitly versioned compatibility metadata from verified upstream wheels.
ADD --checksum=sha256:7b880072131b7a064e6500b9db2f64bd33eb3b396702825330c507243b617f4d https://files.pythonhosted.org/packages/44/aa/24faf02767f0586d9b23ca4348e3a6eaafec63acd56ecf9f1332b326076b/ghunt-2.3.4-py3-none-any.whl /tmp/upstream/ghunt-2.3.4-py3-none-any.whl
ADD --checksum=sha256:63dd33bb94cde15ad9e5b666dbba8fedf71b72a4935d6fb9a92931e69402c9ff https://files.pythonhosted.org/packages/26/85/ec72f6c885703d18f3b09769645e950e14c7d0cc0a0e35d94127983f666f/alive_progress-3.3.0-py3-none-any.whl /tmp/upstream/alive_progress-3.3.0-py3-none-any.whl
COPY build-compat-wheels.py /tmp/build-compat-wheels.py
RUN python -I -B /tmp/build-compat-wheels.py /tmp/upstream /tmp/wheels
COPY requirements.txt /tmp/requirements.txt
COPY audit-dependencies.py /tmp/audit-dependencies.py
COPY test-runtime-compatibility.py /tmp/test-runtime-compatibility.py
RUN pip install --no-cache-dir --no-deps --require-hashes --find-links=/tmp/wheels -r /tmp/requirements.txt \
    && python -I -B /tmp/audit-dependencies.py \
    && python -I -B /tmp/test-runtime-compatibility.py \
    && ghunt --help > /dev/null \
    && rm -rf /tmp/upstream /tmp/wheels

# Default workdir for outputs (mounted as a volume in docker-compose)
WORKDIR /data

# Run GHunt CLI; use `docker compose run --rm ghunt <command>` (e.g. `ghunt login`, `ghunt email ...`)
ENTRYPOINT ["ghunt"]
