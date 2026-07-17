# OpenROAD (PNR's core tool) has no Debian package and no prebuilt release
# binaries — but the IIC-OSIC-TOOLS image ships a LibreLane-matched build.
# Assemble it with its Ubuntu shared libs + dynamic loader (cross-distro:
# the binaries must run through Ubuntu's ld-linux, never Debian's glibc).
FROM hpretl/iic-osic-tools:latest AS openroad-dist
USER root
RUN mkdir -p /orpkg/syslibs \
    && cp -r /foss/tools/openroad-librelane /orpkg/openroad \
    && for b in openroad sta; do \
         ldd /foss/tools/openroad-librelane/bin/$b 2>/dev/null \
           | awk '/=> \//{print $3}' | grep -v '^/foss' \
           | xargs -I{} cp -Ln {} /orpkg/syslibs/ || true; \
       done \
    && cp -L /lib64/ld-linux-x86-64.so.2 /orpkg/syslibs/ \
    # Ubuntu's Tcl/Tk runtime scripts must match the bundled libtcl (Debian's
    # 8.6.14 scripts + Ubuntu's 8.6.16 lib = "version conflict" in floorplan).
    && cp -r /usr/share/tcltk /orpkg/tcltk \
    # OpenROAD's EMBEDDED Python (odbpy steps) needs its own stdlib — the
    # compiled-in /usr/lib/python3.x doesn't exist in the Debian image
    # ("No module named 're'" at odb-setpowerconnections).
    && PYV=$(ls /usr/lib | grep -E '^python3\.[0-9]+$' | head -1) \
    && mkdir -p /orpkg/pyhome/lib \
    && cp -r /usr/lib/$PYV /orpkg/pyhome/lib/$PYV \
    # magic + netgen: Debian ships no magic at all and its "netgen" is a mesh
    # generator, not the LVS tool — GDS stream-out died on FileNotFoundError.
    && cp -r /foss/tools/magic /orpkg/magic \
    && cp -r /foss/tools/netgen /orpkg/netgen \
    && for e in /orpkg/magic/lib/magic/tcl/magicexec /orpkg/magic/lib/magic/tcl/magicdnull \
                /orpkg/netgen/lib/netgen/tcl/netgenexec; do \
         [ -f "$e" ] && ldd "$e" | awk '/=> \//{print $3}' | grep -v '^/foss' \
           | xargs -I{} cp -Ln {} /orpkg/syslibs/ || true; \
       done \
    && sed -i 's|/foss/tools/magic|/opt/orpkg/magic|g' /orpkg/magic/bin/magic \
    && sed -i 's|/foss/tools/netgen|/opt/orpkg/netgen|g' /orpkg/netgen/bin/netgen

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
    # verilator: LibreLane's Verilator.Lint step aborts the whole hardening
    # flow when the binary is missing (PNR failed with FileNotFoundError).
    && (apt-get install -y --no-install-recommends verilator || true) \
    && rm -rf /var/lib/apt/lists/*

# pyosys: LibreLane 3.x's Generate-JSON-Header/synthesis steps need yosys with
# Python scripting (`yosys -y`); the distro binary lacks it, so the pip wheel's
# bindings are used through the yosys-y shim (_LLN_OVERRIDE_YOSYS).
COPY toolchain/yosys-y /usr/local/bin/yosys-y
RUN chmod +x /usr/local/bin/yosys-y
ENV _LLN_OVERRIDE_YOSYS=/usr/local/bin/yosys-y

# OpenROAD + OpenSTA from the openroad-dist stage, executed via the bundled
# Ubuntu loader (direct execution would hit Debian/Ubuntu glibc clashes).
COPY --from=openroad-dist /orpkg /opt/orpkg
RUN for b in openroad sta; do \
        printf '#!/bin/sh\nexport TCL_LIBRARY=/opt/orpkg/tcltk/tcl8.6 TK_LIBRARY=/opt/orpkg/tcltk/tk8.6\nexport PYTHONHOME=/opt/orpkg/pyhome\nexport PYTHONPATH=/usr/local/lib/python3.12/site-packages${PYTHONPATH:+:$PYTHONPATH}\nexec /opt/orpkg/syslibs/ld-linux-x86-64.so.2 --library-path /opt/orpkg/syslibs:/opt/orpkg/openroad/lib /opt/orpkg/openroad/bin/%s "$@"\n' "$b" > /usr/local/bin/$b \
        && chmod +x /usr/local/bin/$b; \
    done \
    && for e in magic/lib/magic/tcl/magicexec magic/lib/magic/tcl/magicdnull \
                netgen/lib/netgen/tcl/netgenexec; do \
        [ -f /opt/orpkg/$e ] || continue; \
        mv /opt/orpkg/$e /opt/orpkg/$e.elf; \
        printf '#!/bin/sh\nexport TCL_LIBRARY=/opt/orpkg/tcltk/tcl8.6 TK_LIBRARY=/opt/orpkg/tcltk/tk8.6\nexec /opt/orpkg/syslibs/ld-linux-x86-64.so.2 --library-path /opt/orpkg/syslibs:/opt/orpkg/openroad/lib /opt/orpkg/%s.elf "$@"\n' "$e" > /opt/orpkg/$e; \
        chmod +x /opt/orpkg/$e; \
    done \
    && ln -sf /opt/orpkg/magic/bin/magic /usr/local/bin/magic \
    && ln -sf /opt/orpkg/netgen/bin/netgen /usr/local/bin/netgen \
    # magicdnull/magicexec/netgenexec HARDCODE /foss/tools/... script paths at
    # compile time — without this symlink magic starts but never loads its own
    # Tcl commands (WriteLEF produced no LEF and the antenna check crashed).
    && mkdir -p /foss/tools \
    && ln -sfn /opt/orpkg/magic /foss/tools/magic \
    && ln -sfn /opt/orpkg/netgen /foss/tools/netgen \
    && openroad -version

# LibreLane / OpenLane (Python orchestrator) + Volare (PDK manager) + render libs.
# librelane is the maintained fork; openlane is the fallback. gdstk + matplotlib
# power the GDS/waveform/metrics PNG renders.
RUN pip install --no-cache-dir librelane || pip install --no-cache-dir openlane \
    && pip install --no-cache-dir volare matplotlib pyosys \
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
