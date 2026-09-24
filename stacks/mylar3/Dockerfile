FROM lscr.io/linuxserver/mylar3:latest@sha256:93d24dc4d5c467d86e77eb278dd90aa19cdc7a90e87cf507abbfff7a5d937ef4 AS checked
ENV PYTHONDONTWRITEBYTECODE=1
COPY config/ /opt/mylar3-fixes/
RUN sh /opt/mylar3-fixes/20-ddl-fix.sh \
    && python3 /opt/mylar3-fixes/verify_image.py

FROM lscr.io/linuxserver/mylar3:latest@sha256:93d24dc4d5c467d86e77eb278dd90aa19cdc7a90e87cf507abbfff7a5d937ef4
LABEL org.opencontainers.image.source="https://github.com/bolens/homelab" \
      org.opencontainers.image.title="Mylar comic automation"
COPY --from=checked /app/mylar3/mylar/ /app/mylar3/mylar/
COPY --from=checked /app/mylar3/data/interfaces/default/ /app/mylar3/data/interfaces/default/
COPY --from=checked /opt/mylar3-fixes/health.py /opt/mylar3-fixes/health.py
