# Minimal container to run unit tests for the pipeline
# Uses Python 3.11 for broad compatibility with deps
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (optional, kept minimal)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

# Copy source
COPY . /app

# Default command runs only unit tests (skips integration)
CMD ["pytest", "-m", "not integration", "-q"]
