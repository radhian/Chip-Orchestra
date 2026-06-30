import { getStoredToken, getTaskEventsWebSocketUrl } from '@/api/auth'
import type {
  ApprovalPayload,
  ArtifactItem,
  CreateTaskInput,
  DiagnosisItem,
  ExportBundleResponse,
  ListTasksParams,
  RunbookEvent,
  SignoffStatus,
  TaskDetail,
  TaskStage,
  TaskSummary,
  WorkspaceFileContent,
  WorkspaceFileSummary,
} from '@/types/orchestra'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080').replace(/\/$/, '')

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { error?: string; message?: string }
    return payload.error ?? payload.message ?? `${response.status} ${response.statusText}`
  } catch {
    return `${response.status} ${response.statusText}`
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredToken()
  const headers = new Headers(init?.headers ?? undefined)

  if (!headers.has('Content-Type') && init?.body) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    throw new Error(await parseError(response))
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

function mapStageStatus(status: string): TaskStage['status'] {
  switch (status) {
    case 'SUCCEEDED':
    case 'RELEASED':
      return 'done'
    case 'RUNNING':
    case 'DISPATCHING':
      return 'active'
    case 'FAILED':
      return 'failed'
    default:
      return 'queued'
  }
}

function mapTaskSummary(item: Record<string, unknown>): TaskSummary {
  const owner = (item.owner as { id?: string; full_name?: string } | undefined) ?? {}
  return {
    id: String(item.id ?? item.task_id ?? ''),
    name: String(item.name ?? 'Untitled task'),
    description: String(item.description ?? 'No description provided.'),
    ownerName: String(item.ownerName ?? owner.full_name ?? 'Unassigned'),
    ownerId: String(item.ownerId ?? owner.id ?? ''),
    currentStage: String(item.currentStage ?? item.current_stage ?? 'Unknown'),
    etaLabel: String(item.etaLabel ?? 'Unknown'),
    statusLabel: String(item.statusLabel ?? item.status ?? 'Unknown'),
    tone: String(item.tone ?? 'running') as TaskSummary['tone'],
    repoName: String(item.repoName ?? item.repo_source ?? item.template_id ?? 'N/A'),
  }
}

function mapTaskDetail(payload: TaskDetail): TaskDetail {
  return {
    ...payload,
    description: payload.description || payload.name,
    repoName: payload.repoName || 'N/A',
    stages: payload.stages ?? [],
    attempts: payload.attempts ?? [],
  }
}

export async function listTasks(params: ListTasksParams = {}): Promise<{ items: TaskSummary[]; total: number }> {
  const query = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== null) {
      query.set(key, String(value))
    }
  })

  const response = await requestJson<{ items?: Array<Record<string, unknown>> }>(`/api/v1/tasks${query.size ? `?${query.toString()}` : ''}`)
  const items = (response.items ?? []).map(mapTaskSummary)

  return {
    items,
    total: items.length,
  }
}

export async function createTask(input: CreateTaskInput): Promise<TaskDetail> {
  const created = await requestJson<{ id?: string; task_id?: string }>('/api/v1/tasks', {
    method: 'POST',
    body: JSON.stringify(input),
  })

  const id = String(created.id ?? created.task_id ?? '')
  if (!id) {
    throw new Error('Task was created but no task id was returned.')
  }

  return getTask(id)
}

export async function getTask(id: string): Promise<TaskDetail> {
  const payload = await requestJson<TaskDetail>(`/api/v1/tasks/${id}`)
  return mapTaskDetail(payload)
}

export async function updateTask(id: string, payload: { description?: string; status?: string; current_stage?: string }) {
  return requestJson<TaskDetail>(`/api/v1/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function getTaskStages(id: string): Promise<TaskStage[]> {
  const response = await requestJson<{ stages?: Array<{ name: string; status: string; retry_count?: number }> }>(`/api/v1/tasks/${id}/stages`)
  return (response.stages ?? []).map((stage) => ({
    key: stage.name.toLowerCase(),
    label: stage.name.replace(/_/g, ' '),
    status: mapStageStatus(stage.status),
    retryCount: Number(stage.retry_count ?? 0),
  }))
}

export async function retryTaskStage(id: string, stage: string): Promise<{ status: string; stage?: string }> {
  return requestJson<{ status: string; stage?: string }>(`/api/v1/tasks/${id}/stages/${stage}/retry`, { method: 'POST' })
}

export async function getTaskEvents(id: string): Promise<RunbookEvent[]> {
  return requestJson<RunbookEvent[]>(`/api/v1/tasks/${id}/attempts/latest/events`)
}

export async function getTaskArtifacts(id: string): Promise<ArtifactItem[]> {
  return requestJson<ArtifactItem[]>(`/api/v1/tasks/${id}/attempts/latest/artifacts`)
}

export async function getTaskDiagnosis(id: string): Promise<DiagnosisItem[]> {
  return requestJson<DiagnosisItem[]>(`/api/v1/tasks/${id}/attempts/latest/diagnosis`)
}

export async function getWorkspaceFiles(id: string): Promise<WorkspaceFileSummary[]> {
  return requestJson<WorkspaceFileSummary[]>(`/api/v1/tasks/${id}/workspace/files`)
}

export async function getWorkspaceFile(id: string, path: string): Promise<WorkspaceFileContent> {
  const query = new URLSearchParams({ path })
  return requestJson<WorkspaceFileContent>(`/api/v1/tasks/${id}/workspace/file?${query.toString()}`)
}

export async function proposeWorkspacePatch(id: string, payload: { instruction: string }): Promise<{ status: string; recommended_next?: string }> {
  return requestJson<{ status: string; recommended_next?: string }>(`/api/v1/tasks/${id}/workspace/propose-patch`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getSignoffStatus(id: string): Promise<SignoffStatus> {
  return requestJson<SignoffStatus>(`/api/v1/tasks/${id}/signoff/status`)
}

export async function submitStageApproval(id: string, stage: string, payload: ApprovalPayload): Promise<{ status: string }> {
  return requestJson<{ status: string }>(`/api/v1/tasks/${id}/approvals/${stage}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function createWaiver(id: string, payload: { title: string; detail: string }): Promise<{ status: string }> {
  return requestJson<{ status: string }>(`/api/v1/tasks/${id}/waivers`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function exportBundle(id: string): Promise<ExportBundleResponse> {
  return requestJson<ExportBundleResponse>(`/api/v1/tasks/${id}/export-bundle`, { method: 'POST' })
}

export function connectTaskEvents(taskId: string, handlers: { onMessage: (event: RunbookEvent) => void; onError?: () => void }) {
  const socket = new WebSocket(getTaskEventsWebSocketUrl(taskId))

  socket.onmessage = (message) => {
    try {
      const payload = JSON.parse(message.data) as RunbookEvent
      handlers.onMessage(payload)
    } catch {
      handlers.onError?.()
    }
  }

  socket.onerror = () => {
    handlers.onError?.()
  }

  return socket
}
