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
    # New optional fields for evidence-backed, workspace-aware execution.
    workspace_root: str | None = Field(default=None)
    artifact_inventory: List[str] = Field(default_factory=list)
    eda_reports: List[str] = Field(default_factory=list)
    reference_files: List[str] = Field(default_factory=list)
    # User-attached files ({"name", "content_base64"}) — images/PDFs/text saved
    # into the workspace's context/uploads/ and digested (vision) before the
    # stage runs. The orchestrator normally writes uploads at task creation;
    # this field supports direct API invocations.
    attachments: List[Dict[str, str]] = Field(default_factory=list)


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

    @app.get("/agent/models")
    def list_models():
        """List models available on the configured LLM provider (Ollama),
        including cloud/local flags and whether vision (image upload) works."""
        provider = os.getenv("LLM_PROVIDER", "mock").strip().lower() or "mock"
        default_model = os.getenv("OLLAMA_MODEL", "").strip()
        models: List[str] = []
        detail: List[Dict[str, Any]] = []
        vision = False
        if provider == "ollama":
            try:
                from llm import list_ollama_models, model_supports_vision

                detail = list_ollama_models()
                models = [m["name"] for m in detail]
                vision = model_supports_vision()
            except Exception:
                models, detail = [], []
        return {
            "provider": provider,
            "default": default_model,
            "models": models,
            "detail": detail,
            "vision": vision,
        }

    @app.post("/agent/invoke")
    def invoke_agent(request: AgentInvokeRequest, fastapi_request: Request):
        if request.attachments:
            # Persist API-supplied attachments into the workspace so the stage
            # handlers (and the vision digest) can see them.
            try:
                from context import files as wsfiles
                from uploads import save_attachments

                workspace = wsfiles.resolve_workspace(request.task_id, request.workspace_root)
                save_attachments(workspace, request.attachments)
            except Exception:
                pass
        result = fastapi_request.app.state.deep_agent_graph.invoke(request.model_dump())
        return {
            "status": "success",
            "agent": result.agent_name,
            "summary": result.summary,
            "diagnostics": result.diagnostics,
            "artifacts": result.artifacts,
            "workspace_files": result.workspace_files,
            "recommended_next": result.recommended_next,
            "structured_conclusion": result.structured_conclusion,
            "artifact_refs": result.artifact_refs,
        }

    return app


app = create_app()
