# OPLedger — single image: FastAPI backend serving the vanilla JS frontend.
# Build with Podman (or Docker): podman build -t opledger:latest .
FROM python:3.12-slim

# SQLCipher runtime for AES-256 encryption at rest.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libsqlcipher0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better layer caching.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Application code and static frontend.
COPY backend ./backend
COPY frontend ./frontend
COPY config ./config

# Encrypted data volume (DB + first-run config tree).
ENV OPLEDGER_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 8080

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
