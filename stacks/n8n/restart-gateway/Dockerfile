FROM python:3.13.13-alpine3.22@sha256:e81548ac35b07a3bd4805f275107592ef458b1e893c0e04d45aedaa19416cca5

WORKDIR /app
COPY restart_gateway.py /app/restart_gateway.py

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080
ENTRYPOINT ["python", "/app/restart_gateway.py"]
