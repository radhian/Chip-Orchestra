#!/usr/bin/env python3
"""Expose a loopback-only Ollama server to Docker containers.

Ollama's default systemd setup binds 127.0.0.1:11434, which containers cannot
reach through host.docker.internal. The clean fix is OLLAMA_HOST=0.0.0.0 in a
systemd override (install.sh attempts that first, it needs sudo). When sudo is
unavailable this unprivileged forwarder is used instead:

    listen 0.0.0.0:11435  ->  forward to 127.0.0.1:11434

Usage: scripts/ollama-docker-proxy.py [listen_port] [target_port]
"""
import asyncio
import sys

LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 11435
TARGET_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 11434


async def pump(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle(client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
    try:
        upstream_r, upstream_w = await asyncio.open_connection("127.0.0.1", TARGET_PORT)
    except OSError:
        client_w.close()
        return
    await asyncio.gather(pump(client_r, upstream_w), pump(upstream_r, client_w))


async def main() -> None:
    server = await asyncio.start_server(handle, "0.0.0.0", LISTEN_PORT)
    print(f"ollama-docker-proxy: 0.0.0.0:{LISTEN_PORT} -> 127.0.0.1:{TARGET_PORT}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
