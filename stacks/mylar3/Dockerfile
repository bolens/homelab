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

FROM lscr.io/linuxserver/mylar3:latest@sha256:5e255755b8d95f8574ba4e260569f4458dffeca623c85a41b200b2440ce3a07d AS libarchive-build
# Release tarball digest is published by the official v3.8.9 release asset.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential=12.9ubuntu3 pkg-config=0.29.2-1ubuntu3 \
        zlib1g-dev=1:1.2.11.dfsg-2ubuntu9.2 libbz2-dev=1.0.8-5ubuntu0.1 \
        liblzma-dev=5.2.5-2ubuntu1.1 libzstd-dev=1.4.8+dfsg-3build1 \
        liblz4-dev=1.9.3-2build2 libacl1-dev=2.3.1-1 \
        libxml2-dev=2.9.13+dfsg-1ubuntu0.13 nettle-dev=3.7.3-1build2 \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -c "import hashlib,urllib.request; data=urllib.request.urlopen('https://github.com/libarchive/libarchive/releases/download/v3.8.9/libarchive-3.8.9.tar.xz',timeout=120).read(33554433); assert len(data)<=33554432 and hashlib.sha256(data).hexdigest()=='888c934f9d95648ecb9163dc8e23ab80a476ecb81a8f1154704a227b5b676dde'; open('/tmp/libarchive.tar.xz','xb').write(data)" \
    && mkdir /tmp/libarchive-source \
    && tar -xf /tmp/libarchive.tar.xz --strip-components=1 -C /tmp/libarchive-source \
    && cd /tmp/libarchive-source \
    && ./configure --prefix=/opt/libarchive --enable-shared --disable-static \
        --disable-bsdtar --disable-bsdcpio --disable-bsdcat --disable-bsdunzip \
        --with-zlib --with-lzma --with-zstd --with-lz4 --with-xml2 --with-nettle \
        --without-openssl --without-mbedtls --without-expat \
    && make -j2 \
    && make check \
    && make install \
    && install -D -m 644 COPYING /opt/libarchive/share/licenses/COPYING \
    && rm -rf /opt/libarchive/include /opt/libarchive/lib/pkgconfig /opt/libarchive/share/man \
    && rm -f /opt/libarchive/lib/*.la

FROM lscr.io/linuxserver/mylar3:latest@sha256:5e255755b8d95f8574ba4e260569f4458dffeca623c85a41b200b2440ce3a07d AS pdf-runtime
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils libarchive13=3.6.0-1ubuntu1.8 \
        zlib1g=1:1.2.11.dfsg-2ubuntu9.2 libbz2-1.0=1.0.8-5ubuntu0.1 \
        liblzma5=5.2.5-2ubuntu1.1 libzstd1=1.4.8+dfsg-3build1 \
        liblz4-1=1.9.3-2build2 libacl1=2.3.1-1 \
        libnettle8=3.7.3-1build2 libhogweed6=3.7.3-1build2 \
        libgmp10=2:6.2.1+dfsg-3ubuntu1 libxml2=2.9.13+dfsg-1ubuntu0.13 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=libarchive-build /opt/libarchive/ /opt/libarchive/
RUN printf '%s\n' /opt/libarchive/lib > /etc/ld.so.conf.d/00-homelab-libarchive.conf \
    && ldconfig \
    && python3 -c "import ctypes,ctypes.util; p=ctypes.util.find_library('archive'); assert p; lib=ctypes.CDLL(p); lib.archive_version_number.restype=ctypes.c_int; assert lib.archive_version_number()==3008009; assert any('/opt/libarchive/lib/libarchive.so.' in line for line in open('/proc/self/maps'))"

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
