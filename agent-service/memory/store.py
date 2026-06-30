from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import List

from redis import Redis
from sqlalchemy import DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    stage: Mapped[str] = mapped_column(String(64), index=True)
    agent_name: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text)
    diagnosis: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


@dataclass
class MemoryItem:
    task_id: str
    stage: str
    agent_name: str
    decision: str
    diagnosis: str


class MemoryStore:
    def __init__(self, database_url: str, redis_client: Redis):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.redis = redis_client

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def search_memories(self, task_id: str, stage: str) -> List[MemoryItem]:
        with Session(self.engine) as session:
            stmt = select(AgentMemory).where(AgentMemory.stage == stage).order_by(AgentMemory.created_at.desc()).limit(5)
            rows = session.execute(stmt).scalars().all()
            return [MemoryItem(task_id=row.task_id, stage=row.stage, agent_name=row.agent_name, decision=row.decision, diagnosis=row.diagnosis) for row in rows]

    def save_memory(self, task_id: str, stage: str, agent_name: str, prompt: str, decision: str, diagnosis: str):
        with self.Session() as session:
            row = AgentMemory(
                id=f"{task_id}-{stage}-{int(datetime.utcnow().timestamp())}",
                task_id=task_id,
                stage=stage,
                agent_name=agent_name,
                prompt=prompt,
                decision=decision,
                diagnosis=diagnosis,
            )
            session.add(row)
            session.commit()

    def write_diagnosis_to_redis(self, task_id: str, payload):
        self.redis.set(f"agent:diagnosis:{task_id}", json.dumps(payload))
