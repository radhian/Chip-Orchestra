FROM python:3.12-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG PDK_ROOT=/opt/pdk

ENV DEBIAN_FRONTEND=noninteractive \
    PDK_ROOT=${PDK_ROOT} \
    IVERILOG_BIN=iverilog \
    VVP_BIN=vvp \
    LIBRELANE_BIN=librelane

# System tools: iverilog for RTL simulation
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        iverilog \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

# LibreLane via pip (Python package — no Nix required)
# openlane is the stable PyPI release; librelane is the newer fork.
# We install both so either binary resolves from PATH.
RUN pip install --no-cache-dir librelane || pip install --no-cache-dir openlane \
    && mkdir -p "${PDK_ROOT}"

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
