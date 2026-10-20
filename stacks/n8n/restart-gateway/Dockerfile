FROM python:3.14.5-alpine3.22@sha256:6b91e66ab2a880ce9ca5a1b91c70f45963ff71ff68268df056336e1a657d5efd

WORKDIR /app
COPY restart_gateway.py /app/restart_gateway.py

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080
ENTRYPOINT ["python", "/app/restart_gateway.py"]
