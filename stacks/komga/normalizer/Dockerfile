FROM ghcr.io/bolens/archiving-utils@sha256:9598b387e007054db0ef3a1c7b27374539c6d80161cfd226606a91019d80aac5 AS runtime
USER root
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils python3-pil python3-xxhash fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

FROM runtime AS checked
ENV PYTHONDONTWRITEBYTECODE=1 \
    ARCHIVING_UTILS_BIN=/opt/archiving-utils/bin/archiving-utils
COPY *.py /app/
COPY ordinary_observation_fixtures/ /app/ordinary_observation_fixtures/
USER 1000:1000
# Fault controls mutate only their private source copy, never the installed tree.
RUN test_root="$(mktemp -d)" \
    && cp -R /app/. "${test_root}/" \
    && python3 -m unittest discover -s "${test_root}" -p 'test_*.py' \
    && rm -rf "${test_root}"

FROM runtime
LABEL org.opencontainers.image.source="https://github.com/bolens/homelab" \
      org.opencontainers.image.title="Comic normalization and import recovery"
ENV PYTHONDONTWRITEBYTECODE=1
COPY --from=checked /app/normalize.py /app/maintenance.py /app/import_match.py /app/import_recovery.py /app/guided_match.py /app/pack_recovery.py /app/edition_evidence.py /app/media_writer.py /app/writer_cycle.py /app/reader_scan.py /app/pdf_conversion.py /app/release_naming.py /app/naming_worker.py /app/
COPY --from=checked /app/publication_guard.py /app/publication_evidence.py /app/publication_metadata.py /app/publication_zip.py /app/publication_lock.py /app/publication_derivative_evidence.py /app/
COPY --from=checked /app/publication_archive_layout.py /app/publication_archive_derivative.py /app/publication_archive_repair.py /app/publication_archive_diagnostics.py /app/
COPY --from=checked /app/ordinary_import_observation.py /app/ordinary_import_ack.py /app/native_handoff.py /app/reader_handoff.py /app/maintenance_report.py /app/conversion_handoff.py /app/combined_handoff.py /app/archive_repair_handoff.py /app/
COPY --from=checked /app/retained_pack_handoff.py /app/retained_pack_operations.py /app/archive_terminal_observation.py /app/
USER 1000:1000
ENTRYPOINT ["python3", "/app/normalize.py"]
CMD []
