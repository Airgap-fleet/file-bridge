# Multi-stage Dockerfile for File Bridge (airgap-file-bridge)
# Uses python:3.12-slim for minimal size

# ==============================================================================
# Stage 1: Builder - build the wheel and install it
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir build

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN python -m build --wheel && pip install --no-cache-dir dist/*.whl

# ==============================================================================
# Stage 2: Runtime - Minimal runtime image
# ==============================================================================
FROM python:3.12-slim AS runtime

# ripgrep powers search_files
RUN apt-get update && apt-get install -y --no-install-recommends \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/airgap-file-bridge /usr/local/bin/airgap-file-bridge

# The folder the AI may use is mounted here at runtime
RUN mkdir -p /sandbox && chown appuser:appuser /sandbox

USER appuser

ENV FILE_BRIDGE_ROOT_PATH=/sandbox
ENV FILE_BRIDGE_READ_ONLY=true
ENV FILE_BRIDGE_MAX_FILE_SIZE=10485760
ENV FILE_BRIDGE_FOLLOW_SYMLINKS=false
ENV FILE_BRIDGE_ALLOW_ABSOLUTE_PATHS=false
ENV FILE_BRIDGE_DEFAULT_ENCODING=utf-8

# The server speaks MCP over stdio: run with `docker run -i`.
ENTRYPOINT ["airgap-file-bridge"]
