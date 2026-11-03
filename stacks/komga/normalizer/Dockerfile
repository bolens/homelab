FROM ghcr.io/bolens/archiving-utils@sha256:2ca2bfa2c4d142d849c3cdd27866867d5337f17ce4dfb92d50bc0d9aeb11654c AS runtime
USER root
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl poppler-utils python3-pil python3-xxhash fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

FROM runtime AS checked
ENV PYTHONDONTWRITEBYTECODE=1 \
    ARCHIVING_UTILS_BIN=/opt/archiving-utils/bin/archiving-utils
COPY *.py /app/
COPY standalone_launch_auth/ /app/standalone_launch_auth/
COPY ordinary_observation_fixtures/ /app/ordinary_observation_fixtures/
RUN python3 -I -B /app/patch_publication_launch_auth.py /opt/mylar-publication-launch/auth
USER 1000:1000
RUN python3 -I -B -c "import sys; sys.path.insert(0, '/opt/mylar-publication-launch/auth'); from private_crypto import _TargetExperiment; runtime = _TargetExperiment(); assert runtime._execute(['version']).returncode == 0"
# Fault controls mutate only their private source copy, never the installed tree.
RUN test_root="$(mktemp -d)" \
    && cp -R /app/. "${test_root}/" \
    && PYTHONPATH="${test_root}" python3 -m unittest test_normalizer_state_binding test_selected_catalog test_selected_prepare test_pack_recurring \
    && python3 -m unittest discover -s "${test_root}" -p 'test_*.py' \
    && rm -rf "${test_root}"

FROM runtime
LABEL org.opencontainers.image.source="https://github.com/bolens/homelab" \
      org.opencontainers.image.title="Comic normalization and import recovery"
ENV PYTHONDONTWRITEBYTECODE=1
COPY --from=checked /app/cache_reservation.py /app/worker_cache.py /app/normalize.py /app/maintenance.py /app/import_match.py /app/import_recovery.py /app/guided_match.py /app/pack_recovery.py /app/pack_only.py /app/edition_evidence.py /app/media_writer.py /app/writer_cycle.py /app/normalizer_state_binding.py /app/reader_scan.py /app/pdf_conversion.py /app/release_naming.py /app/naming_worker.py /app/
COPY --from=checked /app/publication_guard.py /app/publication_evidence.py /app/publication_metadata.py /app/publication_zip.py /app/publication_lock.py /app/publication_derivative_evidence.py /app/
COPY --from=checked /app/publication_identity_adoption.py /app/publication_identity_readers.py /app/publication_filesystem_binding.py /app/
COPY --from=checked /app/publication_archive_layout.py /app/publication_archive_derivative.py /app/publication_archive_repair.py /app/publication_archive_diagnostics.py /app/
COPY --from=checked /app/ordinary_import_observation.py /app/ordinary_import_ack.py /app/native_handoff.py /app/reader_handoff.py /app/maintenance_report.py /app/conversion_handoff.py /app/combined_handoff.py /app/archive_repair_handoff.py /app/
COPY --from=checked /app/retained_pack_handoff.py /app/retained_pack_operations.py /app/retained_pack_control.py /app/archive_terminal_observation.py /app/
COPY --from=checked /opt/mylar-publication-launch/auth/ /opt/mylar-publication-launch/auth/
RUN --mount=type=bind,from=checked,source=/app/patch_publication_launch_auth.py,target=/run/verify-public-auth.py,readonly python3 -I -B -c "import os; from pathlib import Path; p=Path('/opt/mylar-publication-launch'); [(os.close(os.open(p/n,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444))) for n in ('installation-v1.json','inventory-v1.json','public-ed25519.der')]" \
    && python3 -I -B /run/verify-public-auth.py --verify-final /opt/mylar-publication-launch/auth
USER 1000:1000
ENTRYPOINT ["python3", "/app/normalize.py"]
CMD []
