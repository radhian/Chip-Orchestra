# EDA Service API

## `POST /eda/jobs`
Queues a mock EDA job and persists it to MySQL.

## `GET /eda/jobs/{id}/status`
Returns queued/running/completed/failed state, progress, and final report payload when available.

## `GET /eda/jobs/{id}/report`
Returns the latest normalized report document.

## `GET /eda/jobs/{id}/logs`
Streams job log events as Server-Sent Events (SSE).

## `DELETE /eda/jobs/{id}`
Deletes a persisted job record.

## `GET /health`
Basic Redis-backed liveness check.

## Execution model
- Redis list used as the in-process work queue
- MySQL stores durable job metadata
- Mock toolchain hooks model OpenLane, Verilator, Yosys, KLayout, and Magic execution boundaries
