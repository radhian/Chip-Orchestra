FROM python:3.12-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG LIBRELANE_FLAKE=github:librelane/librelane
ARG PDK_ROOT=/opt/pdk

ENV DEBIAN_FRONTEND=noninteractive \
    NIX_CONFIG="experimental-features = nix-command flakes" \
    PDK_ROOT=${PDK_ROOT} \
    IVERILOG_BIN=iverilog \
    VVP_BIN=vvp \
    LIBRELANE_BIN=librelane \
    PATH="/root/.nix-profile/bin:/nix/var/nix/profiles/default/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        iverilog \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -m 0755 /nix \
    && chown root /nix \
    && curl -L https://nixos.org/nix/install | sh -s -- --no-daemon \
    && . /root/.nix-profile/etc/profile.d/nix.sh \
    && nix profile add ${LIBRELANE_FLAKE} --accept-flake-config \
    && mkdir -p "${PDK_ROOT}"

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
