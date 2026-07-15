FROM python:3.12-slim

# iverilog is bundled so the deep agents' compile-check-on-write loop can
# verify generated RTL (iverilog -tnull) without a round-trip to eda-service.
# git enables the reference-anchor shallow clone (no GitHub API rate limits).
ENV DEBIAN_FRONTEND=noninteractive \
    IVERILOG_BIN=iverilog
RUN apt-get update \
    && apt-get install -y --no-install-recommends iverilog git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
