FROM lscr.io/linuxserver/mylar3:latest@sha256:5e255755b8d95f8574ba4e260569f4458dffeca623c85a41b200b2440ce3a07d AS tagger-build
# The pinned final base already supplies ICU 70; compilation tools stay here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential=12.9ubuntu3 libicu-dev=70.1-2 \
        python3-dev=3.10.6-1~22.04.1 pkg-config=0.29.2-1ubuntu3 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-build.txt requirements.txt /tmp/tagger-locks/
RUN python3 -m venv --without-pip /opt/tagger-build \
    && python3 -m pip --python /opt/tagger-build/bin/python install --no-cache-dir \
        --require-hashes --no-deps -r /tmp/tagger-locks/requirements-build.txt \
    && python3 -m pip --python /opt/tagger-build/bin/python wheel --no-cache-dir \
        --require-hashes --no-deps --no-build-isolation \
        -r /tmp/tagger-locks/requirements.txt --wheel-dir /tmp/tagger-wheels \
    && python3 -m venv --without-pip /opt/comictagger \
    && python3 -m pip --python /opt/comictagger/bin/python install --no-index --no-deps /tmp/tagger-wheels/*.whl \
    && python3 -m pip --python /opt/comictagger/bin/python check

COPY tagger-sources.json /tmp/tagger-sources.json
COPY config/fetch_tagger_sources.py /tmp/fetch_tagger_sources.py
RUN python3 /tmp/fetch_tagger_sources.py /tmp/tagger-sources.json /opt/comictagger/sources
COPY tagger-NOTICES.md /opt/comictagger/NOTICES.md

FROM lscr.io/linuxserver/mylar3:latest@sha256:5e255755b8d95f8574ba4e260569f4458dffeca623c85a41b200b2440ce3a07d AS ddl-build
COPY requirements-ddl.txt /tmp/requirements-ddl.txt
RUN python3 -m venv --without-pip /opt/ddl-transport \
    && python3 -m pip --python /opt/ddl-transport/bin/python install --no-cache-dir \
        --require-hashes --no-deps -r /tmp/requirements-ddl.txt \
    && python3 -m pip --python /opt/ddl-transport/bin/python check

COPY ddl-sources.json /tmp/ddl-sources.json
COPY config/fetch_tagger_sources.py /tmp/fetch_ddl_sources.py
RUN python3 /tmp/fetch_ddl_sources.py /tmp/ddl-sources.json /opt/ddl-transport/sources
COPY ddl-NOTICES.md /opt/ddl-transport/NOTICES.md

FROM ghcr.io/bolens/archiving-utils@sha256:9598b387e007054db0ef3a1c7b27374539c6d80161cfd226606a91019d80aac5 AS archive-verifier

FROM lscr.io/linuxserver/mylar3:latest@sha256:5e255755b8d95f8574ba4e260569f4458dffeca623c85a41b200b2440ce3a07d AS pdf-runtime
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils libarchive13 \
    && rm -rf /var/lib/apt/lists/*

FROM pdf-runtime AS checked
ENV PYTHONDONTWRITEBYTECODE=1
COPY --from=archive-verifier /opt/archiving-utils/ /opt/archiving-utils/
COPY --from=tagger-build /opt/comictagger/ /opt/comictagger/
COPY --from=ddl-build /opt/ddl-transport/ /opt/ddl-transport/
COPY config/ /opt/mylar3-fixes/
RUN --network=none python3 /opt/mylar3-fixes/apply_patches.py /app/mylar3/mylar \
    && python3 /opt/mylar3-fixes/verify_image.py

FROM pdf-runtime
LABEL org.opencontainers.image.source="https://github.com/bolens/homelab" \
      org.opencontainers.image.title="Mylar comic automation"
COPY --from=checked /app/mylar3/mylar/ /app/mylar3/mylar/
COPY --from=checked /app/mylar3/data/interfaces/default/ /app/mylar3/data/interfaces/default/
COPY --from=checked /opt/mylar3-fixes/health.py /opt/mylar3-fixes/health.py
COPY --from=checked /opt/mylar3-fixes/publication_guard.py /opt/mylar3-fixes/publication_guard.py
COPY --from=archive-verifier /opt/archiving-utils/ /opt/archiving-utils/
COPY --from=checked /opt/mylar3-fixes/tagger_runtime.py /opt/mylar3-fixes/tagger_metadata.py /opt/mylar3-fixes/tagger_cli.py /opt/mylar3-fixes/tagger_archive.py /opt/mylar3-fixes/tagger_adapter.py /opt/mylar3-fixes/
COPY --from=tagger-build /opt/comictagger/ /opt/comictagger/
COPY --from=ddl-build /opt/ddl-transport/ /opt/ddl-transport/
