# Multi-stage build for size and security optimization
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies into a separate environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip
RUN pip install .

# Production runner image
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy codebase
COPY . .

# Run as non-privileged system user for security
RUN useradd -u 8888 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "resolveai.main:app", "--host", "0.0.0.0", "--port", "8000"]
