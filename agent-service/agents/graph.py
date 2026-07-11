from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import END, StateGraph

from context import files as wsfiles

from .result import AgentResult
from .stage_handlers import StageContext, dispatch

__all__ = ["AgentResult", "DeepAgentGraph"]

# Stage -> agent role mapping (preserved from the original graph).
STAGE_AGENTS = {
    "SPEC_INGEST": "SpecInterpreter",
    "PLAN": "FlowAssistant",
    "RTL_GEN": "RTLAuthor",
    "RTL_REPAIR": "RTLAuthor",
    "TB_GEN": "Verifier",
    "SIM": "Verifier",
    "LINT": "Diagnoser",
    "SYNTH": "Diagnoser",
    "PNR": "Diagnoser",
    "DRC_LVS": "Diagnoser",
    "SIGNOFF": "FlowAssistant",
    "EXPORT": "FlowAssistant",
    "FLOW_ASSISTANT": "FlowAssistant",
}


class DeepAgentGraph:
    def __init__(self, tool_registry, memory_store):
        self.tool_registry = tool_registry
        self.memory_store = memory_store
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(dict)
        workflow.add_node("load_memory", self.load_memory)
        workflow.add_node("select_agent", self.select_agent)
        workflow.add_node("execute_agent", self.execute_agent)
        workflow.add_node("persist_feedback", self.persist_feedback)
        workflow.set_entry_point("load_memory")
        workflow.add_edge("load_memory", "select_agent")
        workflow.add_edge("select_agent", "execute_agent")
        workflow.add_edge("execute_agent", "persist_feedback")
        workflow.add_edge("persist_feedback", END)
        return workflow.compile()

    def invoke(self, payload: Dict[str, Any]) -> AgentResult:
        state = self.graph.invoke(payload)
        return state["result"]

    def load_memory(self, state: Dict[str, Any]) -> Dict[str, Any]:
        stage = state.get("stage", "FLOW_ASSISTANT")
        task_id = state.get("task_id", "")
        memories = self.memory_store.search_memories(task_id=task_id, stage=stage)
        state["memories"] = memories
        return state

    def select_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        stage = state.get("stage", "FLOW_ASSISTANT")
        state["agent_name"] = STAGE_AGENTS.get(stage, "FlowAssistant")
        return state

    def execute_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        stage = state.get("stage", "FLOW_ASSISTANT")
        task_id = state.get("task_id", "")
        agent_name = state.get("agent_name", "FlowAssistant")
        context = dict(state.get("context", {}))
        context.setdefault("agent_name", agent_name)

        workspace_root = state.get("workspace_root") or context.get("workspace_root")
        try:
            workspace = wsfiles.resolve_workspace(task_id, workspace_root)
        except Exception:  # noqa: BLE001 - never fail stage on workspace resolution
            workspace = None

        stage_ctx = StageContext(
            task_id=task_id,
            stage=stage,
            prompt=state.get("prompt", ""),
            context=context,
            workspace=workspace,
            memories=state.get("memories", []),
            artifact_inventory=state.get("artifact_inventory", []),
            eda_reports=state.get("eda_reports", []),
            reference_files=state.get("reference_files", []),
        )
        result = dispatch(stage_ctx)

        for tool_name in state.get("tools", []):
            if tool_name in self.tool_registry.tools:
                self.tool_registry.tools[tool_name](
                    task_id=task_id,
                    stage=stage,
                    payload={"summary": result.summary, "agent": result.agent_name},
                )

        state["result"] = result
        return state

    def persist_feedback(self, state: Dict[str, Any]) -> Dict[str, Any]:
        result: AgentResult = state["result"]
        self.memory_store.save_memory(
            task_id=state.get("task_id", ""),
            stage=state.get("stage", "FLOW_ASSISTANT"),
            agent_name=result.agent_name,
            prompt=state.get("prompt", ""),
            decision=result.summary,
            diagnosis=result.diagnostics[0]["detail"] if result.diagnostics else "",
            artifact_refs=result.artifact_refs,
            structured_conclusion=result.structured_conclusion,
        )
        self.memory_store.write_diagnosis_to_redis(state.get("task_id", ""), {
            "agent": result.agent_name,
            "stage": state.get("stage", "FLOW_ASSISTANT"),
            "summary": result.summary,
            "recommended_next": result.recommended_next,
        })
        return state
