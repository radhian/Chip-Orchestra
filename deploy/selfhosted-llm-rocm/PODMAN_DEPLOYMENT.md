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

On both R9700 and Strix Halo, mount the same network filesystem at the same path:

```bash
sudo mkdir -p /srv/chip-orchestra/workspaces
# then mount your NFS/shared storage here on both hosts
```

Verify both nodes can write and read the same file before continuing.

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
