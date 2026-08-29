FROM python:3.11-slim

LABEL maintainer="Artic Company SAS <contact@articc.top>"
LABEL description="Ultra-lightweight Modular Model Context Protocol (MCP) Gateway with Admin Panel"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    MCP_DATA_DIR=/app/data

WORKDIR /app

# Install minimal system dependencies for GPG & crypto
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg \
    gpg-agent \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy source code and default assets
COPY src/ /app/src/

# Ensure data directory exists
RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["python3", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
