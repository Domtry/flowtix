FROM python:3.11-slim

WORKDIR /app

COPY infrastructure/docker/zscaler-ca.crt /usr/local/share/ca-certificates/zscaler-ca.crt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev ca-certificates && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

COPY packages/ ./packages/
COPY services/ ./services/
COPY agents/ ./agents/
COPY apps/api/ ./apps/api/

RUN pip install --no-cache-dir \
    ./apps/api \
    ./packages/security \
    ./packages/observability \
    ./packages/process_schema \
    ./packages/execution_contracts \
    ./services/data_engine \
    ./services/resource_manager \
    ./services/ai \
    greenlet temporalio pandas openpyxl psutil cryptography aiosqlite

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "apps.api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
