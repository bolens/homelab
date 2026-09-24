FROM ghcr.io/bolens/archiving-utils@sha256:9598b387e007054db0ef3a1c7b27374539c6d80161cfd226606a91019d80aac5 AS checked
ENV PYTHONDONTWRITEBYTECODE=1 \
    ARCHIVING_UTILS_BIN=/opt/archiving-utils/bin/archiving-utils
COPY *.py /app/
USER 1000:1000
RUN python3 -m unittest discover -s /app -p 'test_*.py'

FROM ghcr.io/bolens/archiving-utils@sha256:9598b387e007054db0ef3a1c7b27374539c6d80161cfd226606a91019d80aac5
LABEL org.opencontainers.image.source="https://github.com/bolens/homelab" \
      org.opencontainers.image.title="Comic normalization and import recovery"
ENV PYTHONDONTWRITEBYTECODE=1
COPY --from=checked /app/normalize.py /app/maintenance.py /app/import_match.py /app/import_recovery.py /app/guided_match.py /app/
USER 1000:1000
ENTRYPOINT ["python3", "/app/normalize.py"]
CMD []
