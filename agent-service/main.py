from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from redis import Redis

from agents import DeepAgentGraph
from memory import MemoryStore
from tools import ToolRegistry


class AgentInvokeRequest(BaseModel):
    task_id: str
    stage: str = Field(default="FLOW_ASSISTANT")
    prompt: str
    tools: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, str] = Field(default_factory=dict)
    instructions: Dict[str, Any] = Field(default_factory=dict)


def build_services():
    database_url = os.getenv("DATABASE_URL", "mysql+pymysql://chip:chip@mysql:3306/chip_orchestra")
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    memory_store = MemoryStore(database_url=database_url, redis_client=redis_client)
    memory_store.create_tables()
    tool_registry = ToolRegistry(redis_client)
    graph = DeepAgentGraph(tool_registry, memory_store)
    return redis_client, memory_store, tool_registry, graph


def _assign_services(app: FastAPI, redis_client: Redis, memory_store: MemoryStore, tool_registry: ToolRegistry, deep_agent_graph: DeepAgentGraph | Any):
    app.state.redis_client = redis_client
    app.state.memory_store = memory_store
    app.state.tool_registry = tool_registry
    app.state.deep_agent_graph = deep_agent_graph


def create_app(
    *,
    redis_client: Redis | None = None,
    memory_store: MemoryStore | None = None,
    tool_registry: ToolRegistry | None = None,
    deep_agent_graph: DeepAgentGraph | Any | None = None,
) -> FastAPI:
    if any(dep is not None for dep in (redis_client, memory_store, tool_registry, deep_agent_graph)):
        if not all(dep is not None for dep in (redis_client, memory_store, tool_registry, deep_agent_graph)):
            raise ValueError("redis_client, memory_store, tool_registry, and deep_agent_graph must be provided together")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not hasattr(app.state, "deep_agent_graph"):
            built = build_services()
            _assign_services(app, *built)
        try:
            yield
        finally:
            close = getattr(app.state.redis_client, "close", None)
            if callable(close):
                close()

    app = FastAPI(title="Chip Orchestra Agent Service", version="0.1.0", lifespan=lifespan)

    if all(dep is not None for dep in (redis_client, memory_store, tool_registry, deep_agent_graph)):
        _assign_services(app, redis_client, memory_store, tool_registry, deep_agent_graph)

    @app.get("/health")
    def health(request: Request):
        return {
            "status": "ok",
            "redis": request.app.state.redis_client.ping(),
        }

    @app.post("/agent/invoke")
    def invoke_agent(request: AgentInvokeRequest, fastapi_request: Request):
        result = fastapi_request.app.state.deep_agent_graph.invoke(request.model_dump())
        return {
            "status": "success",
            "agent": result.agent_name,
            "summary": result.summary,
            "diagnostics": result.diagnostics,
            "artifacts": result.artifacts,
            "workspace_files": result.workspace_files,
            "recommended_next": result.recommended_next,
        }

    return app


app = create_app()
