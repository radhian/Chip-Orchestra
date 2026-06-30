# Agent Service API

## `POST /agent/invoke`
Receives a structured request from the Orchestrator Service:
```json
{
  "task_id": "tsk_001",
  "stage": "RTL_GEN",
  "prompt": "Execute RTL generation",
  "tools": ["write_artifact", "track_task_progress"],
  "context": {
    "task_name": "uart_tx_controller"
  }
}
```

Response:
```json
{
  "status": "success",
  "agent": "RTLAuthor",
  "summary": "...",
  "diagnostics": [],
  "artifacts": [],
  "workspace_files": {},
  "recommended_next": "..."
}
```

## `GET /health`
Basic service liveness check with Redis connectivity.

## Internal behavior
- Uses a LangGraph-style state graph
- Loads prior decisions from MySQL
- Writes current diagnosis summaries into Redis
- Supports the tool registry: `update_task_status`, `track_task_progress`, `get_user_context`, `submit_eda_job`, `get_eda_result`, `read_artifact`, `write_artifact`
