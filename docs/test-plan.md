# Test Plan

## 1. Unit tests
### Orchestrator Service
- [x] `internal/api/tasks_test.go` validates task create/list/get/patch handler behavior with `httptest`
- [x] `internal/middleware/jwt_test.go` validates JWT bearer auth success and failure cases
- [x] `internal/orchestrator/dag_test.go` validates DAG queueing, retry, approval, and dispatch-driven state transitions
- [ ] Redis-backed WebSocket helper serialization coverage is still pending

### Agent Service
- [x] `tests/test_tools.py` validates all 7 tool registry operations with mocked dependencies
- [x] `tests/test_agents.py` validates all 5 agent role selections and deterministic execution outputs
- [ ] Memory read/write flow against SQL storage is still pending
- [x] LangGraph pipeline output shape is exercised through agent role tests and invoke endpoint coverage

### EDA Service
- [x] `tests/test_jobs.py` validates job create/status/report/delete endpoint behavior
- [x] `tests/test_state_machine.py` validates queue worker transitions: `QUEUED -> RUNNING -> COMPLETED/FAILED`
- [x] `tests/test_sse_logs.py` validates SSE log streaming for persisted log lines
- [ ] Additional standalone mock toolchain unit coverage is still pending

## 2. Integration tests
### Orchestrator Service API
- [x] `internal/api/integration_test.go` covers `POST /api/v1/tasks -> GET /api/v1/tasks/:id -> PATCH /api/v1/tasks/:id`
- [ ] Full Orchestrator ↔ Agent HTTP integration remains pending
- [ ] Full Orchestrator ↔ EDA polling integration remains pending

### Agent Service API
- [x] `tests/test_invoke.py` covers `POST /agent/invoke` using FastAPI `TestClient`

### EDA Service API
- [x] `tests/test_integration.py` covers `POST /eda/jobs -> GET /eda/jobs/{id}/status -> GET /eda/jobs/{id}/report`

## 3. End-to-end test
1. Start the full stack with `docker compose up`
2. Login through the Orchestrator Service or let the frontend auto-login
3. Create a new task from the frontend
4. Observe the task move through agent stages and mocked EDA stages
5. Open runbook, workspace, and signoff pages
6. Trigger a stage retry from the Orchestrator API
7. Approve signoff and request export bundle

## 4. WebSocket subscription test
- [ ] Authenticate and request `GET /ws/tasks/{id}/events?token=<jwt>`
- [ ] Create a task or retry a stage
- [ ] Confirm event frames stream stage status changes and artifact notifications in real time

## 5. Regression checklist
- [ ] Branding shows only “Chip Orchestra”, “Orchestrator Service”, and “Orchestrator Plane”
- [ ] Runtime configuration uses MySQL plus Redis only, with no legacy storage assumptions remaining
- [x] Service-local test runners now cover backend suites without requiring live MySQL, Redis, or LLM dependencies
