# Build Rust extension + install SDK into a venv, then copy to slim runtime.
FROM rust:1-bookworm AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-venv python3-dev build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . .
RUN python3 -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --upgrade pip \
    && pip install -r requirements.txt httpx starlette uvicorn \
    && maturin develop --release \
    && pip show mom

FROM python:3.12-slim-bookworm
RUN useradd -m -u 10001 mom
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    MOM_BACKEND=local \
    MOM_HOST=0.0.0.0 \
    MOM_PORT=8080 \
    MOM_WEIGHTS_DIR=/app/weights \
    PYTHONUNBUFFERED=1
WORKDIR /app
USER mom
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')" || exit 1
CMD ["python", "-m", "mom.server"]
