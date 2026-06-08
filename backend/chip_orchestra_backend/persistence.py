"""Durable, config-driven persistence: PostgreSQL (task state + logs) and
S3/MinIO (generated files).

Activates only when configured (``DATABASE_URL`` / S3 creds). Every operation is
defensive — a persistence failure logs a warning and is swallowed so the agent
keeps running on the local file store. This is what makes a fresh clone boot with
an empty DB + bucket and then auto-fill as chips are generated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings

logger = logging.getLogger("chip_orchestra.persistence")


class Persistence:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._engine = None
        self._tasks = None
        self._events = None
        self._files = None
        self._s3 = None
        self._db_ready = False
        self._s3_ready = False
        self._init_db()
        self._init_s3()

    @property
    def db_enabled(self) -> bool:
        return self._db_ready

    @property
    def s3_enabled(self) -> bool:
        return self._s3_ready

    # --- schema / clients --------------------------------------------------
    def _init_db(self) -> None:
        if not self.settings.persistence_enabled:
            return
        try:
            from sqlalchemy import (
                Column,
                DateTime,
                Integer,
                MetaData,
                String,
                Table,
                Text,
                UniqueConstraint,
                create_engine,
            )
            from sqlalchemy.dialects.postgresql import JSONB

            self._engine = create_engine(self.settings.database_url, pool_pre_ping=True, future=True)
            metadata = MetaData()
            self._tasks = Table(
                "tasks", metadata,
                Column("id", String, primary_key=True),
                Column("name", String),
                Column("owner_id", String),
                Column("status", String),
                Column("tone", String),
                Column("current_stage", String),
                Column("created_at", DateTime(timezone=True)),
                Column("updated_at", DateTime(timezone=True)),
                Column("data", JSONB),
            )
            self._events = Table(
                "events", metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("task_id", String, index=True),
                Column("event_id", String),
                Column("time_label", String),
                Column("title", String),
                Column("detail", Text),
                Column("tone", String),
                Column("created_at", DateTime(timezone=True)),
            )
            self._files = Table(
                "files", metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("task_id", String, index=True),
                Column("path", String),
                Column("name", String),
                Column("status", String),
                Column("note", Text),
                Column("object_key", String),
                Column("size", Integer),
                Column("updated_at", DateTime(timezone=True)),
                UniqueConstraint("task_id", "path", name="uq_files_task_path"),
            )
            metadata.create_all(self._engine)
            self._db_ready = True
            logger.info("Postgres persistence enabled.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Postgres persistence disabled (%s): %s", type(exc).__name__, exc)
            self._engine = None
            self._db_ready = False

    def _init_s3(self) -> None:
        if not self.settings.object_storage_enabled:
            return
        try:
            import boto3
            from botocore.config import Config as BotoConfig

            self._s3 = boto3.client(
                "s3",
                endpoint_url=self.settings.s3_endpoint_url,
                aws_access_key_id=self.settings.s3_access_key,
                aws_secret_access_key=self.settings.s3_secret_key,
                region_name=self.settings.s3_region,
                config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 2}),
            )
            bucket = self.settings.s3_bucket
            try:
                self._s3.head_bucket(Bucket=bucket)
            except Exception:  # noqa: BLE001 - create if missing
                self._s3.create_bucket(Bucket=bucket)
            self._s3_ready = True
            logger.info("S3/MinIO object storage enabled (bucket=%s).", bucket)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Object storage disabled (%s): %s", type(exc).__name__, exc)
            self._s3 = None
            self._s3_ready = False

    # --- task state --------------------------------------------------------
    def save_task(self, record_json: dict) -> None:
        if not self._db_ready:
            return
        detail = record_json.get("detail", {})
        try:
            from sqlalchemy.dialects.postgresql import insert

            now = datetime.now(timezone.utc)
            row = {
                "id": detail.get("id"),
                "name": detail.get("name"),
                "owner_id": detail.get("ownerId"),
                "status": detail.get("statusLabel"),
                "tone": detail.get("tone"),
                "current_stage": detail.get("currentStage"),
                "created_at": now,
                "updated_at": now,
                "data": record_json,
            }
            stmt = insert(self._tasks).values(**row)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": row["name"], "owner_id": row["owner_id"], "status": row["status"],
                    "tone": row["tone"], "current_stage": row["current_stage"],
                    "updated_at": now, "data": row["data"],
                },
            )
            with self._engine.begin() as conn:
                conn.execute(stmt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("save_task failed for %s: %s", detail.get("id"), exc)

    def append_event(self, task_id: str, event: dict) -> None:
        if not self._db_ready:
            return
        try:
            with self._engine.begin() as conn:
                conn.execute(self._events.insert().values(
                    task_id=task_id,
                    event_id=event.get("id"),
                    time_label=event.get("time"),
                    title=event.get("title"),
                    detail=event.get("detail"),
                    tone=event.get("tone"),
                    created_at=datetime.now(timezone.utc),
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("append_event failed for %s: %s", task_id, exc)

    def load_tasks(self) -> list[dict]:
        if not self._db_ready:
            return []
        try:
            from sqlalchemy import select

            with self._engine.begin() as conn:
                rows = conn.execute(select(self._tasks.c.data).order_by(self._tasks.c.created_at)).fetchall()
            return [r[0] for r in rows if r[0]]
        except Exception as exc:  # noqa: BLE001
            logger.warning("load_tasks failed: %s", exc)
            return []

    # --- object storage ----------------------------------------------------
    def put_file(self, task_id: str, summary: dict, local_path: Path) -> str | None:
        """Upload a generated file and record its metadata. Returns the object key."""
        key = f"{task_id}/{summary.get('path')}"
        size = local_path.stat().st_size if local_path.exists() else 0
        if self._s3_ready and local_path.exists():
            try:
                self._s3.upload_file(str(local_path), self.settings.s3_bucket, key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("put_file upload failed for %s: %s", key, exc)
        if self._db_ready:
            try:
                from sqlalchemy.dialects.postgresql import insert

                stmt = insert(self._files).values(
                    task_id=task_id, path=summary.get("path"), name=summary.get("name"),
                    status=summary.get("status"), note=summary.get("note"),
                    object_key=key, size=size, updated_at=datetime.now(timezone.utc),
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_files_task_path",
                    set_={"status": summary.get("status"), "note": summary.get("note"),
                          "object_key": key, "size": size, "updated_at": datetime.now(timezone.utc)},
                )
                with self._engine.begin() as conn:
                    conn.execute(stmt)
            except Exception as exc:  # noqa: BLE001
                logger.warning("put_file metadata failed for %s: %s", key, exc)
        return key

    def get_file(self, task_id: str, rel_path: str) -> bytes | None:
        if not self._s3_ready:
            return None
        try:
            obj = self._s3.get_object(Bucket=self.settings.s3_bucket, Key=f"{task_id}/{rel_path}")
            return obj["Body"].read()
        except Exception:  # noqa: BLE001 - not in object storage
            return None

    def put_object(self, key: str, local_path: Path) -> str | None:
        if not self._s3_ready or not local_path.exists():
            return None
        try:
            self._s3.upload_file(str(local_path), self.settings.s3_bucket, key)
            return key
        except Exception as exc:  # noqa: BLE001
            logger.warning("put_object failed for %s: %s", key, exc)
            return None


_persistence: Persistence | None = None


def get_persistence() -> Persistence:
    global _persistence
    if _persistence is None:
        _persistence = Persistence()
    return _persistence
