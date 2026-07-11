FROM python:3.12-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG PDK_ROOT=/opt/pdk

ENV DEBIAN_FRONTEND=noninteractive \
    PDK_ROOT=${PDK_ROOT} \
    PDK=gf180mcuD \
    IVERILOG_BIN=iverilog \
    VVP_BIN=vvp \
    LIBRELANE_BIN=librelane \
    YOSYS_BIN=yosys \
    STA_BIN=sta \
    KLAYOUT_BIN=klayout \
    DOT_PATH=dot

# System EDA tooling. iverilog+vvp (sim), yosys (synth/schematic), graphviz
# (schematic PNG), klayout (GDS view/DRC/LVS). netgen/magic/opensta are best
# effort: installed when the distro provides them, otherwise the runners
# degrade gracefully (they detect a missing binary and skip/fallback).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        cmake \
        curl \
        g++ \
        git \
        graphviz \
        iverilog \
        libboost-dev \
        xz-utils \
        yosys \
        zlib1g-dev \
    && (apt-get install -y --no-install-recommends klayout || true) \
    && (apt-get install -y --no-install-recommends netgen || true) \
    && (apt-get install -y --no-install-recommends magic || true) \
    && (apt-get install -y --no-install-recommends opensta || true) \
    && rm -rf /var/lib/apt/lists/*

# LibreLane / OpenLane (Python orchestrator) + Volare (PDK manager) + render libs.
# librelane is the maintained fork; openlane is the fallback. gdstk + matplotlib
# power the GDS/waveform/metrics PNG renders.
RUN pip install --no-cache-dir librelane || pip install --no-cache-dir openlane \
    && pip install --no-cache-dir volare matplotlib \
    && pip install --no-cache-dir "gdstk" || pip install --no-cache-dir --no-build-isolation gdstk || echo "gdstk optional – KLayout fallback will be used" \
    && mkdir -p "${PDK_ROOT}"

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x pdk/setup_pdk.sh 2>/dev/null || true
EXPOSE 8002
# Auto-install the PDK (via Volare) if PDK_ROOT is empty, then start the service.
CMD ["bash", "-lc", "pdk/setup_pdk.sh || true; uvicorn main:app --host 0.0.0.0 --port 8002"]
