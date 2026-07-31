# Podman Deployment: Distributed AMD (Strix Halo Agent + R9700 Core)

This guide runs the same distributed AMD architecture described in `AMD_DISTRIBUTED_ARCHITECTURE.md` with Podman instead of Docker. The compose files (`docker-compose.r9700-core.yml`, `docker-compose.strix-agent.yml`) are reused as-is; only the runtime and a few Podman-specific flags change.

## 1. Why Podman here

Podman is a good fit for this deployment because it is daemonless, supports rootless containers, integrates with systemd for auto-restart, and is the default container engine on RHEL/Fedora-family hosts often used with AMD ROCm. It is broadly Docker-CLI compatible, so the existing compose files work with minimal changes.

## 2. Install

On each node (Fedora/RHEL family):

```bash
sudo dnf -y install podman podman-compose
podman --version
podman-compose --version
```

On Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get -y install podman
pip3 install --user podman-compose
```

Either `podman compose` (the Docker-Compose provider shim) or `podman-compose` (the native Python tool) works. This guide uses `podman-compose` because it is the most predictable across distros.

## 3. Podman-specific differences vs Docker

There are four things to handle that differ from the Docker path:

1. **Rootful vs rootless.** Binding to a fixed private IP such as `172.16.1.36:3306` and mounting `/srv/chip-orchestra/workspaces` is simplest with rootful Podman (`sudo podman-compose ...`). Rootless Podman can bind low ports only with extra sysctl settings and remaps file ownership, which complicates the shared workspace. For this deployment, use rootful Podman.
2. **`host.docker.internal`.** The Strix agent uses `extra_hosts: host.docker.internal:host-gateway`. Podman supports `host-gateway` in recent versions; on older Podman, replace it with `host.containers.internal`, which Podman provides automatically.
3. **SELinux volume labels.** On SELinux-enforcing hosts, bind mounts need a `:z` or `:Z` suffix or the container cannot read the workspace. Set `WORKSPACE_MOUNT_FLAG=:z` in your env and Podman relabels the shared mount. If SELinux is permissive/disabled, leave it empty.
4. **`platform: linux/amd64`.** `eda-service` pins `linux/amd64`. On AMD x86_64 hosts this is native; Podman honors the platform key. No emulation needed.

## 4. Prepare the shared workspace

Podman (unlike Docker) does **not** auto-create bind-mount source directories, so
a missing `/srv/chip-orchestra/workspaces` fails the run with
`statfs /srv/chip-orchestra/workspaces: no such file or directory`. Create it
first. Use the helper (run as root — it also handles SELinux labels):

```bash
sudo ./scripts/prepare_host.sh
# or point it at your shared storage mount:
sudo WORKSPACE_HOST_PATH=/mnt/nfs/chip-orchestra/workspaces ./scripts/prepare_host.sh
```

Or do it manually on both R9700 and Strix Halo, mounting the same network
filesystem at the same path:

```bash
sudo mkdir -p /srv/chip-orchestra/workspaces
sudo chmod 0777 /srv/chip-orchestra/workspaces
# then mount your NFS/shared storage here on both hosts
```

Verify both nodes can write and read the same file before continuing.

> **Rootless will fail here.** The compose binds services to the fixed LAN IP
> (`172.16.1.36:3306`, `:6379`, `:8002`). Rootless Podman cannot bind a specific
> non-loopback host IP and errors with `bind: cannot assign requested address`
> plus `rootless netns: ... permission denied`. Run the whole stack with rootful
> Podman (`sudo`). If you truly must stay rootless, set the bind hosts to
> `0.0.0.0` in your env (`MYSQL_BIND_HOST=0.0.0.0 REDIS_BIND_HOST=0.0.0.0
> EDA_BIND_HOST=0.0.0.0`) — but rootful is the supported path.
>
> **Rootless → rootful storage gotcha.** Images you built earlier as a rootless
> user live in `~/.local/share/containers` and are invisible to rootful Podman
> (`/var/lib/containers`). The first `sudo podman-compose ... up -d --build`
> rebuilds them under root storage — that is expected, not a bug.

## 5. R9700 core with Podman

On R9700:

```bash
cd Chip-Orchestra/deploy/selfhosted-llm-rocm
cp r9700-core.env.example r9700-core.env
# edit secrets, model ids
# on SELinux hosts also set: WORKSPACE_MOUNT_FLAG=:z

sudo podman-compose --env-file r9700-core.env -f docker-compose.r9700-core.yml up -d --build

curl -fsS http://172.16.1.36:8080/health
curl -fsS http://172.16.1.36:8002/health
```

### 5a. R9700 core rootless (no sudo)

If you have no `sudo` on the host, run everything as your user. Two things must
change, both captured in `r9700-core.rootless.env.example`:

1. **Bind `0.0.0.0`, not the LAN IP.** Rootless Podman cannot bind a fixed
   non-loopback host IP, so `MYSQL_BIND_HOST`/`REDIS_BIND_HOST`/`EDA_BIND_HOST`
   are set to `0.0.0.0`. Ports are still reachable on `172.16.1.36` from other
   nodes; all ports here are >1024 so no privileged-port sysctl is needed.
2. **Workspace under `$HOME`, not `/srv`.** You can't create `/srv/...` without
   root. `prepare_host.sh` (run without sudo) makes `~/chip-orchestra/workspaces`
   for you; set the same absolute path as `WORKSPACE_HOST_PATH` in the env file
   (env-file values are not shell-expanded, so write the full path, not `$HOME`).

```bash
cd Chip-Orchestra/deploy/selfhosted-llm-rocm
cp r9700-core.rootless.env.example r9700-core.rootless.env
# edit WORKSPACE_HOST_PATH to an absolute $HOME path, plus secrets

# One-shot: creates the workspace dir FROM the env file, then brings the stack up.
./scripts/podman_up.sh r9700-core.rootless.env -f docker-compose.r9700-core.yml

curl -fsS http://172.16.1.36:8080/health
curl -fsS http://172.16.1.36:8002/health
```

> Doing it in two steps instead? Always pass the env file to `prepare_host.sh`
> so it creates the *exact* path compose will mount (no drift), then bring it up:
> ```bash
> ./scripts/prepare_host.sh r9700-core.rootless.env
> podman-compose --env-file r9700-core.rootless.env -f docker-compose.r9700-core.yml up -d --build
> ```
> The `statfs .../workspaces: no such file or directory` error means this prep
> step was skipped or created a different path than `WORKSPACE_HOST_PATH`.

If you still hit `rootless netns: ... permission denied`, it is usually a stale
rootless state or a missing subuid range: run `podman system migrate`, confirm
`newuidmap` exists (`uidmap` package), and check that `/etc/subuid` and
`/etc/subgid` contain a range for your user (an admin adds it once with
`sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER`).
The `uidmap` package and the one-time subuid line are the only steps that ever
need an admin; everything else is fully unprivileged.

## 6. Strix Halo agent with Podman

On Strix Halo:

```bash
cd Chip-Orchestra/deploy/selfhosted-llm-rocm
cp strix-agent.env.example strix-agent.env
# edit MYSQL_PASSWORD, OPENAI_MODEL
# on SELinux hosts also set: WORKSPACE_MOUNT_FLAG=:z

sudo podman-compose --env-file strix-agent.env -f docker-compose.strix-agent.yml up -d --build

curl -fsS http://172.16.1.10:8001/health
curl -fsS http://172.16.1.10:8001/agent/models
```

### 6a. Strix Halo rootless (no sudo)

Same idea as §5a, plus one extra: this node runs the GLM server on the GPU, and
rootless GPU passthrough needs `group_add: [keep-groups]` instead of the rootful
`video`/`render` group names (under rootless those names resolve to mapped GIDs
that don't grant access to the host `/dev/dri` render node). That delta lives in
`docker-compose.strix-full.rootless.yml`, which you layer on top of the base file.
You must be in the host `render` (and usually `video`) group first:

```bash
id -nG | tr ' ' '\n' | grep -E 'render|video'   # must list render (and video)
```

Then:

```bash
cd Chip-Orchestra/deploy/selfhosted-llm-rocm
cp strix-agent.rootless.env.example strix-agent.rootless.env
# edit WORKSPACE_HOST_PATH and MODEL_DIR to absolute $HOME paths, plus secrets
MODEL_DIR=/home/$USER/chip-orchestra/models ./scripts/prepare_host.sh   # no sudo: makes workspace + model dir

podman-compose --env-file strix-agent.rootless.env \
  -f docker-compose.strix-full.yml -f docker-compose.strix-full.rootless.yml up -d --build

curl -fsS http://172.16.1.10:8001/health
curl -fsS http://172.16.1.10:8001/agent/models
curl -fsS http://172.16.1.10:10000/v1/models      # GLM server
```

If `rocminfo`/GLM can't see the GPU rootless, it is almost always group
membership: confirm `render` is in `id -nG`; if you were just added, log out and
back in (or `newgrp render`) so the new group takes effect. The subuid/`uidmap`
note from §5a applies here too.

## 7. Validate cross-node flow

From R9700:

```bash
curl -fsS http://172.16.1.10:8001/health
curl -fsS http://172.16.1.10:8001/agent/models
bash scripts/check_amd_infra_models.sh
```

Then run one small chip task (UART FIFO / ALU / NanoCGRA-lite) before a larger design.

## 8. Auto-start on boot with systemd (recommended for Podman)

Podman's strongest advantage over Docker Compose here is native systemd integration. After the stacks are healthy, generate unit files so the containers survive reboots without a background daemon.

Per-container units:

```bash
cd /etc/systemd/system
sudo podman generate systemd --files --name chip-orchestra-r9700_orchestrator-service_1
sudo systemctl daemon-reload
sudo systemctl enable --now container-chip-orchestra-r9700_orchestrator-service_1
```

Repeat for each container on the node. For a cleaner long-term setup, migrate to Quadlet units (`/etc/containers/systemd/*.container`), which are the modern Podman-native replacement for `generate systemd`.

A ready-to-use helper is included:

```bash
sudo bash scripts/podman_systemd_enable.sh
```

It discovers running Chip Orchestra containers via Podman and generates + enables systemd units for each one.

## 9. Rollback / teardown

```bash
# R9700
sudo podman-compose --env-file r9700-core.env -f docker-compose.r9700-core.yml down

# Strix Halo
sudo podman-compose --env-file strix-agent.env -f docker-compose.strix-agent.yml down
```

To also remove named volumes on a node:

```bash
sudo podman volume ls
sudo podman volume rm <volume-name>
```

## 10. Gotchas specific to Podman

The most common issues are: forgetting `:z`/`:Z` on SELinux hosts so the workspace is unreadable; using rootless Podman and then failing to bind `172.16.1.36:3306`; and stale `host.docker.internal` on old Podman — use `host.containers.internal` if `host-gateway` is unsupported. If `podman-compose` build fails on the multi-stage images, build images first with `podman build` and set `pull_policy: never`, or use `podman compose` (the provider shim) which tracks Docker Compose behavior more closely.

## 11. Short-name / registries.conf build errors

If a build fails with:

```
Error: creating build container: short-name "hpretl/iic-osic-tools@sha256:..."
did not resolve to an alias and no unqualified-search registries are defined
in "/etc/containers/registries.conf"
```

Podman (unlike Docker) refuses to guess the registry for an unqualified image
name. There are two fixes; this repo already applies the first one.

**Fix A — fully-qualified images (already done in this branch).** Every
`FROM` line in `eda-service`, `orchestrator-service`, `agent-service` and
`frontend` Dockerfiles is pinned to `docker.io/...` (official images use the
`docker.io/library/...` path). This removes any dependence on host registry
config, so the build works on a clean Podman install. Nothing to do.

**Fix B — registries.conf (only needed for other/unpinned images).** The
common reason the `echo ... | sudo tee -a` fix "does not work" is a TOML
gotcha: `registries.conf` usually ends with one or more `[[registry]]` table
blocks, and appending to the *bottom* of the file puts the key *inside* the
last table, where it is ignored. The key must sit at the very **top**, before
any `[[registry]]` header:

```bash
# put it at the top, not the bottom
sudo sed -i '1i unqualified-search-registries = ["docker.io"]' /etc/containers/registries.conf
# also check drop-ins don't override it
grep -R "unqualified-search-registries\|short-name-mode" /etc/containers/registries.conf.d/ 2>/dev/null
```

Then verify Podman parsed it (any error here means the file is malformed):

```bash
podman info --format '{{.Registries}}'
```
