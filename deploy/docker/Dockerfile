FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY troodon ./troodon
COPY spec ./spec

RUN pip install --no-cache-dir -e .

RUN useradd -m -u 10001 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data

USER appuser

ENV TROODON_DB=/data/troodon.sqlite
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "troodon.node.app:create_app_from_config", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
