FROM lscr.io/linuxserver/mylar3:latest@sha256:0b45139c69d8e79478ccf6e85a5cc9368a7e3bc3e4229fe338149f196430ef11 AS tagger-build
# Modern alone uses CPython 3.13, compiled against this same Jammy ABI/ICU.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential=12.9ubuntu3 libicu-dev=70.1-2 pkg-config=0.29.2-1ubuntu3 \
        libssl-dev=3.0.2-0ubuntu1.30 libffi-dev=3.4.2-4 \
        libsqlite3-dev=3.37.2-2ubuntu0.8 zlib1g-dev=1:1.2.11.dfsg-2ubuntu9.2 \
        libbz2-dev=1.0.8-5ubuntu0.1 liblzma-dev=5.2.5-2ubuntu1.1 \
    && rm -rf /var/lib/apt/lists/*
COPY tagger-sources.json /tmp/tagger-sources.json
COPY config/fetch_tagger_sources.py /tmp/fetch_tagger_sources.py
RUN python3 /tmp/fetch_tagger_sources.py /tmp/tagger-sources.json /opt/comictagger/sources
WORKDIR /tmp/tagger-python-source
RUN tar -xf /opt/comictagger/sources/Python-3.13.16.tar.xz --strip-components=1 -C /tmp/tagger-python-source \
    && CFLAGS='-O2 -g0' ./configure --prefix=/opt/tagger-python --without-static-libpython \
        --disable-test-modules --with-ensurepip=install \
    && make -j2 \
    && make install \
    && install -m 644 LICENSE /opt/tagger-python/LICENSE \
    && install -m 644 Doc/license.rst /opt/tagger-python/LICENSES.rst \
    && /opt/tagger-python/bin/python3.13 -I -B -c "import bz2,ctypes,hashlib,lzma,sqlite3,ssl,sys,zlib; assert sys.version_info[:3]==(3,13,16); assert sys._is_gil_enabled(); assert ssl.OPENSSL_VERSION_INFO[:2]==(3,0); assert sqlite3.sqlite_version_info>=(3,15,2)"
WORKDIR /
COPY requirements-build.txt requirements.txt /tmp/tagger-locks/
RUN rm -rf /tmp/tagger-python-source \
    && /opt/tagger-python/bin/python3.13 -m venv --without-pip /opt/tagger-build \
    && /opt/tagger-python/bin/python3.13 -m pip --python /opt/tagger-build/bin/python install --no-cache-dir \
        --require-hashes --no-deps -r /tmp/tagger-locks/requirements-build.txt \
    && /opt/tagger-python/bin/python3.13 -m pip --python /opt/tagger-build/bin/python wheel --no-cache-dir \
        --require-hashes --no-deps --no-build-isolation \
        -r /tmp/tagger-locks/requirements.txt --wheel-dir /tmp/tagger-wheels \
    && /opt/tagger-python/bin/python3.13 -m venv --without-pip /opt/comictagger \
    && /opt/tagger-python/bin/python3.13 -m pip --python /opt/comictagger/bin/python install --no-index --no-deps /tmp/tagger-wheels/*.whl \
    && /opt/tagger-python/bin/python3.13 -m pip --python /opt/comictagger/bin/python check \
    && rm -rf /opt/tagger-python/include /opt/tagger-python/share \
        /opt/tagger-python/lib/pkgconfig /opt/tagger-python/lib/python3.13/config-* \
        /opt/tagger-python/lib/python3.13/ensurepip \
        /opt/tagger-python/lib/python3.13/site-packages/pip \
        /opt/tagger-python/lib/python3.13/site-packages/pip-*.dist-info \
    && rm -f /opt/tagger-python/bin/pip* /opt/tagger-python/bin/*-config \
    && find /opt/tagger-python /opt/comictagger -type d -name __pycache__ -prune -exec rm -rf '{}' +
COPY tagger-NOTICES.md /opt/comictagger/NOTICES.md

FROM lscr.io/linuxserver/mylar3:latest@sha256:0b45139c69d8e79478ccf6e85a5cc9368a7e3bc3e4229fe338149f196430ef11 AS ddl-build
COPY requirements-ddl.txt /tmp/requirements-ddl.txt
RUN python3 -m venv --without-pip /opt/ddl-transport \
    && python3 -m pip --python /opt/ddl-transport/bin/python install --no-cache-dir \
        --require-hashes --no-deps -r /tmp/requirements-ddl.txt \
    && python3 -m pip --python /opt/ddl-transport/bin/python check

COPY ddl-sources.json /tmp/ddl-sources.json
COPY config/fetch_tagger_sources.py /tmp/fetch_ddl_sources.py
RUN python3 /tmp/fetch_ddl_sources.py /tmp/ddl-sources.json /opt/ddl-transport/sources
COPY ddl-NOTICES.md /opt/ddl-transport/NOTICES.md

FROM ghcr.io/bolens/archiving-utils@sha256:2ca2bfa2c4d142d849c3cdd27866867d5337f17ce4dfb92d50bc0d9aeb11654c AS archive-verifier

FROM lscr.io/linuxserver/mylar3:latest@sha256:0b45139c69d8e79478ccf6e85a5cc9368a7e3bc3e4229fe338149f196430ef11 AS libarchive-build
# Release tarball digest is published by the official v3.8.9 release asset.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential=12.9ubuntu3 pkg-config=0.29.2-1ubuntu3 \
        zlib1g-dev=1:1.2.11.dfsg-2ubuntu9.2 libbz2-dev=1.0.8-5ubuntu0.1 \
        liblzma-dev=5.2.5-2ubuntu1.1 libzstd-dev=1.4.8+dfsg-3build1 \
        liblz4-dev=1.9.3-2build2 libacl1-dev=2.3.1-1 \
        libxml2-dev=2.9.13+dfsg-1ubuntu0.14 nettle-dev=3.7.3-1build2 \
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

FROM lscr.io/linuxserver/mylar3:latest@sha256:0b45139c69d8e79478ccf6e85a5cc9368a7e3bc3e4229fe338149f196430ef11 AS pdf-runtime
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils libarchive13=3.6.0-1ubuntu1.9 \
        libssl3=3.0.2-0ubuntu1.30 libffi8=3.4.2-4 libsqlite3-0=3.37.2-2ubuntu0.8 \
        zlib1g=1:1.2.11.dfsg-2ubuntu9.2 libbz2-1.0=1.0.8-5ubuntu0.1 \
        liblzma5=5.2.5-2ubuntu1.1 libzstd1=1.4.8+dfsg-3build1 \
        liblz4-1=1.9.3-2build2 libacl1=2.3.1-1 \
        libnettle8=3.7.3-1build2 libhogweed6=3.7.3-1build2 \
        libgmp10=2:6.2.1+dfsg-3ubuntu1 libxml2=2.9.13+dfsg-1ubuntu0.14 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=libarchive-build /opt/libarchive/ /opt/libarchive/
RUN printf '%s\n' /opt/libarchive/lib > /etc/ld.so.conf.d/00-homelab-libarchive.conf \
    && ldconfig \
    && python3 -c "import ctypes,ctypes.util; p=ctypes.util.find_library('archive'); assert p; lib=ctypes.CDLL(p); lib.archive_version_number.restype=ctypes.c_int; assert lib.archive_version_number()==3008009; assert any('/opt/libarchive/lib/libarchive.so.' in line for line in open('/proc/self/maps'))"

FROM pdf-runtime AS verification-runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    ARCHIVING_UTILS_ROOT=/opt/archiving-utils
COPY --from=archive-verifier /opt/archiving-utils/ /opt/archiving-utils/
COPY --from=tagger-build /opt/tagger-python/ /opt/tagger-python/
COPY --from=tagger-build /opt/comictagger/ /opt/comictagger/

FROM verification-runtime AS tagging-checked
COPY config/verify_tagging_stage.py config/tagging_stage_sources.json /opt/mylar-tagging-stage/
# BEGIN TAGGING STAGE INPUTS
COPY config/archive_monitor.py \
    config/cache_admission.py \
    config/cache_reservation.py \
    config/combined_cleanup.py \
    config/combined_publication.py \
    config/converted_catalog.py \
    config/converted_tagging.py \
    config/file_identity.py \
    config/import_problems.py \
    config/library_metadata.py \
    config/library_status.py \
    config/media_writer.py \
    config/metadata_repair.py \
    config/native_writers.py \
    config/ordinary_import_continuity.py \
    config/ordinary_import_history.py \
    config/ordinary_import_observation.py \
    config/pack_bindings.py \
    config/pack_catalog.py \
    config/pack_intake.py \
    config/patch_publication_guard.py \
    config/patch_publication_processing.py \
    config/pp_monitor.py \
    config/processing_guard.py \
    config/publication_api.py \
    config/publication_archive_adoption.py \
    config/publication_archive_derivative.py \
    config/publication_archive_diagnostics.py \
    config/publication_archive_dispatch.py \
    config/publication_archive_history.py \
    config/publication_archive_layout.py \
    config/publication_archive_owned.py \
    config/publication_archive_preparation_existing.py \
    config/publication_archive_prepare_routes.py \
    config/publication_archive_reader.py \
    config/publication_archive_repair.py \
    config/publication_archive_rollback.py \
    config/publication_archive_verifier.py \
    config/publication_conversion.py \
    config/publication_derivative.py \
    config/publication_filesystem_binding.py \
    config/publication_fresh.py \
    config/publication_guard.py \
    config/publication_identity_adoption.py \
    config/publication_identity_maintenance.py \
    config/publication_identity_readers.py \
    config/publication_lineage.py \
    config/publication_mutation.py \
    config/publication_native.py \
    config/publication_native_configured_scope.py \
    config/publication_reader_lifecycle.py \
    config/publication_reconcile.py \
    config/publication_rename.py \
    config/publication_rescan.py \
    config/publication_retained_api.py \
    config/publication_retained_delivery.py \
    config/publication_retained_finalize.py \
    config/publication_tagging_recovery.py \
    config/publication_transaction.py \
    config/queue_control.py \
    config/queue_progress.py \
    config/release_naming.py \
    config/tagger_adapter.py \
    config/tagger_archive.py \
    config/tagger_attributes.py \
    config/tagger_backend.py \
    config/tagger_cli.py \
    config/tagger_enrichment.py \
    config/tagger_handoff.py \
    config/tagger_legacy.py \
    config/tagger_lookup.py \
    config/tagger_metadata.py \
    config/tagger_native.py \
    config/tagger_nfs.py \
    config/tagger_pack.py \
    config/tagger_runtime.py \
    config/tagger_service.py \
    config/tagger_staging.py \
    config/tagger_supplement.py \
    config/tagger_volume_cache.py \
    config/test_modern_tagger.py \
    config/test_publication_api.py \
    config/test_publication_guard.py \
    config/test_publication_native.py \
    config/test_publication_tagging.py \
    config/test_tagger_lookup.py \
    config/worker_handoff.py \
    config/workflow.py \
    config/workflow_nzb.py \
    config/workflow_store.py \
    /opt/mylar-tagging-inputs/
# END TAGGING STAGE INPUTS
RUN --mount=type=tmpfs,target=/tmp,size=268435456 --mount=type=tmpfs,target=/run/tagging-fixtures,size=67108864 --network=none \
    python3 -I -B -c "import os,sys; p='/run/tagging-fixtures'; os.chmod('/tmp',0o1777); os.chown(p,1000,1000); os.chmod(p,0o700); os.environ['HOME']=p; os.environ['TMPDIR']='/tmp'; os.setgroups([]); os.setgid(1000); os.setuid(1000); assert os.geteuid()==os.getegid()==1000; os.execv(sys.executable,[sys.executable,'-I','-B','/opt/mylar-tagging-stage/verify_tagging_stage.py','--sources','/opt/mylar-tagging-inputs','--manifest','/opt/mylar-tagging-stage/tagging_stage_sources.json','--output',p+'/result.json'])" \
    && install -D -m 0644 /run/tagging-fixtures/result.json /opt/mylar-tagging-stage/verified.json

FROM verification-runtime AS app-checked
COPY --from=ddl-build /opt/ddl-transport/ /opt/ddl-transport/
COPY config/ /opt/mylar3-fixes/
RUN --mount=type=tmpfs,target=/tmp,size=268435456 --mount=type=tmpfs,target=/run/authenticated-fixtures,size=67108864 --network=none python3 -I -B /opt/mylar3-fixes/patch_publication_launch_auth.py /opt/mylar-publication-launch/auth \
    && python3 -I -B /opt/mylar3-fixes/test_standalone_anchor_root.py --disposable-build-fixture \
    && python3 /opt/mylar3-fixes/apply_patches.py /app/mylar3/mylar \
    && chmod 0644 /app/mylar3/mylar/config.py \
    && chmod 0755 /app/mylar3/Mylar.py \
    && python3 -I -B -c "import os,sys; p='/run/authenticated-fixtures'; os.chmod('/tmp',0o1777); os.chown(p,1000,1000); os.chmod(p,0o700); os.environ['HOME']=p; os.environ['TMPDIR']='/tmp'; os.setgroups([]); os.setgid(1000); os.setuid(1000); assert os.geteuid()==os.getegid()==1000; os.mkdir(p+'/.cache',0o700); os.execv(sys.executable,[sys.executable,'-B','/opt/mylar3-fixes/verify_image.py','--phase','remaining'])"

# Both independent branches must pass before any checked artifact can be exported.
FROM app-checked AS checked
RUN --mount=type=bind,from=tagging-checked,source=/opt/mylar-tagging-stage/verified.json,target=/run/tagging-stage-result.json,readonly --network=none \
    python3 -I -B /opt/mylar3-fixes/verify_tagging_stage.py --verify-receipt /opt/mylar3-fixes /run/tagging-stage-result.json

FROM pdf-runtime
LABEL org.opencontainers.image.source="https://github.com/bolens/homelab" \
      org.opencontainers.image.title="Mylar comic automation"
COPY --from=checked /app/mylar3/mylar/ /app/mylar3/mylar/
COPY --from=checked /app/mylar3/lib/mega/mega.py /app/mylar3/lib/mega/mega.py
RUN python3 -I -B -c "import ast; from pathlib import Path; source=Path('/app/mylar3/lib/mega/mega.py').read_text(); assert source.count('# homelab-cache-admission-v1')==1; tree=ast.parse(source); assert all(any(isinstance(node,ast.Call) and ast.unparse(node.func)==name for node in ast.walk(tree)) for name in ('cache_admission.allocation','cache_admission.temporary','reservation.before_write','temp_output_file.promote'))"
# Public verifier leaves and empty fixed bind targets cross this boundary; no authority or private key.
COPY --from=checked /opt/mylar-publication-launch/auth/ /opt/mylar-publication-launch/auth/
# Empty placeholders permit only the scoped broker's three fixed RO leaf mounts.
# This real image-layout smoke gate proves no enrollment or public anchor is baked.
RUN --mount=type=bind,from=checked,source=/opt/mylar3-fixes/patch_publication_launch_auth.py,target=/run/verify-public-auth.py,readonly python3 -I -B -c "import os,stat; from pathlib import Path; p=Path('/opt/mylar-publication-launch'); names=('installation-v1.json','inventory-v1.json','public-ed25519.der'); [(os.close(os.open(p/n,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444))) for n in names]; assert set(os.listdir(p))=={'auth',*names}; assert all(stat.S_ISREG(os.lstat(p/n).st_mode) and os.lstat(p/n).st_uid==os.lstat(p/n).st_gid==0 and stat.S_IMODE(os.lstat(p/n).st_mode)==0o444 and os.lstat(p/n).st_nlink==1 and (p/n).read_bytes()==b'' for n in names)" \
    && python3 -I -B /run/verify-public-auth.py --verify-final /opt/mylar-publication-launch/auth
RUN chmod 0755 /app/mylar3/Mylar.py \
    && python3 -I -B -c "import hashlib,os,stat; from pathlib import Path; p=Path('/opt/mylar-publication-launch/auth'); pins={name: digest.removeprefix('sha256:') for name, digest in {'standalone_launch_auth.py': 'sha256:fd871556d6af8741623f94e760a9e2e838cddeb087ee3a4d15a9e4412842a5a8', 'v3_auth_core.py': 'sha256:b8c688bcf6b40e12c54eba5793cc368079b1050d20ed11170deaeb721ac99c93', 'private_crypto.py': 'sha256:3d888b7155f47b9ae35d99aafd845e0bdaa37cda6cd75ddc91103a02836a6fab'}.items()}; assert set(os.listdir(p))==set(pins) and set(os.listdir(p.parent))=={'auth','installation-v1.json','inventory-v1.json','public-ed25519.der'}; assert all(stat.S_ISDIR(os.lstat(x).st_mode) and os.lstat(x).st_uid==os.lstat(x).st_gid==0 and not os.lstat(x).st_mode & 0o022 for x in (p,*p.parents)); assert all(stat.S_ISREG(os.lstat(p/n).st_mode) and os.lstat(p/n).st_nlink==1 and os.lstat(p/n).st_uid==os.lstat(p/n).st_gid==0 and stat.S_IMODE(os.lstat(p/n).st_mode)==0o444 and hashlib.sha256((p/n).read_bytes()).hexdigest()==d for n,d in pins.items())"
COPY --from=checked /app/mylar3/data/interfaces/default/ /app/mylar3/data/interfaces/default/
COPY --from=checked /opt/mylar3-fixes/health.py /opt/mylar3-fixes/health.py
COPY --from=checked /opt/mylar3-fixes/publication_guard.py /opt/mylar3-fixes/publication_guard.py
COPY --from=archive-verifier /opt/archiving-utils/ /opt/archiving-utils/
COPY --from=checked /opt/mylar3-fixes/tagger_runtime.py /opt/mylar3-fixes/tagger_metadata.py /opt/mylar3-fixes/tagger_cli.py /opt/mylar3-fixes/tagger_archive.py /opt/mylar3-fixes/tagger_adapter.py /opt/mylar3-fixes/
COPY --from=tagger-build /opt/tagger-python/ /opt/tagger-python/
COPY --from=tagger-build /opt/comictagger/ /opt/comictagger/
COPY --from=ddl-build /opt/ddl-transport/ /opt/ddl-transport/

# Execute against the final runtime layer, not the host or a foreign builder ABI.
RUN /opt/comictagger/bin/python -I -B -c "import ctypes,glob,os,platform,sqlite3,ssl,subprocess,sys; import icu; from PIL import Image,features; assert sys.version_info[:3]==(3,13,16) and sys._is_gil_enabled(); assert sys.base_prefix=='/opt/tagger-python'; assert platform.machine()=='x86_64' and os.confstr('CS_GNU_LIBC_VERSION')=='glibc 2.35'; assert icu.ICU_VERSION=='70.1' and Image.__version__=='13.0.0' and features.check('jpg') and features.check('libtiff'); assert ssl.OPENSSL_VERSION_INFO[:2]==(3,0) and sqlite3.sqlite_version_info>=(3,15,2); assert ctypes.sizeof(ctypes.c_void_p)==8; assert subprocess.check_output(['/usr/bin/python3','-I','-B','-c','import sys;print(sys.version_info[:2])'],text=True).strip()=='(3, 10)'; paths=['/opt/tagger-python/bin/python3.13']+glob.glob('/opt/tagger-python/lib/python3.13/lib-dynload/*.so')+glob.glob('/opt/comictagger/lib/python3.13/site-packages/**/*.so',recursive=True); assert len(paths)>20; results=[subprocess.run(['/usr/bin/ldd',p],check=True,capture_output=True,text=True,timeout=10) for p in paths]; assert all('not found' not in r.stdout+r.stderr and '/tmp/' not in r.stdout and '/opt/tagger-build/' not in r.stdout for r in results)"
