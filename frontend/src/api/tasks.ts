import {
  applyMockApproval,
  applyMockWaiver,
  createMockExportBundle,
  createMockTask,
  filterMockTasks,
  loadMockSnapshot,
} from '@/mocks/chiporchestra'
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
  WaiverPayload,
  WorkflowStep,
  WorkspaceFileContent,
  WorkspaceFileSummary,
} from '@/types/chiporchestra'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '')
const SHOULD_USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false'

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error('Missing VITE_API_BASE_URL')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

async function withFallback<T>(remote: () => Promise<T>, mock: () => T | Promise<T>): Promise<T> {
  if (!API_BASE_URL && SHOULD_USE_MOCKS) {
    return mock()
  }

  try {
    return await remote()
  } catch (error) {
    if (SHOULD_USE_MOCKS) {
      console.warn('Chip Orchestra API unavailable, falling back to mock data.', error)
      return mock()
    }

    throw error
  }
}

function getSnapshot() {
  return loadMockSnapshot()
}

export async function getWorkflowSteps(): Promise<WorkflowStep[]> {
  return withFallback(
    () => Promise.resolve(getSnapshot().workflowSteps),
    () => getSnapshot().workflowSteps,
  )
}

export async function listTasks(params: ListTasksParams = {}): Promise<TaskSummary[]> {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      query.set(key, String(value))
    }
  })

  return withFallback(
    async () => requestJson<TaskSummary[]>(`/api/tasks${query.size ? `?${query.toString()}` : ''}`),
    () => filterMockTasks(getSnapshot().tasks, params),
  )
}

export async function createTask(input: CreateTaskInput): Promise<TaskDetail> {
  return withFallback(
    () => requestJson<TaskDetail>('/api/tasks', { method: 'POST', body: JSON.stringify(input) }),
    () => createMockTask(input),
  )
}

export async function getTask(id: string): Promise<TaskDetail> {
  return withFallback(
    () => requestJson<TaskDetail>(`/api/tasks/${id}`),
    () => {
      const detail = getSnapshot().taskDetails[id]
      if (!detail) {
        throw new Error(`Task ${id} not found`)
      }
      return detail
    },
  )
}

export async function getTaskStages(id: string): Promise<TaskStage[]> {
  return withFallback(
    () => requestJson<TaskStage[]>(`/api/tasks/${id}/stages`),
    async () => (await getTask(id)).stages,
  )
}

export async function retryTask(id: string): Promise<{ status: string }> {
  return withFallback(
    () => requestJson<{ status: string }>(`/api/tasks/${id}/retry`, { method: 'POST' }),
    () => ({ status: 'queued' }),
  )
}

export async function getTaskEvents(id: string): Promise<RunbookEvent[]> {
  return withFallback(
    () => requestJson<RunbookEvent[]>(`/api/tasks/${id}/attempts/latest/events`),
    () => getSnapshot().events[id] ?? [],
  )
}

export async function getTaskArtifacts(id: string): Promise<ArtifactItem[]> {
  return withFallback(
    () => requestJson<ArtifactItem[]>(`/api/tasks/${id}/attempts/latest/artifacts`),
    () => getSnapshot().artifacts[id] ?? [],
  )
}

export async function getTaskDiagnosis(id: string): Promise<DiagnosisItem[]> {
  return withFallback(
    () => requestJson<DiagnosisItem[]>(`/api/tasks/${id}/attempts/latest/diagnosis`),
    () => getSnapshot().diagnoses[id] ?? [],
  )
}

export async function getWorkspaceFiles(id: string): Promise<WorkspaceFileSummary[]> {
  return withFallback(
    () => requestJson<WorkspaceFileSummary[]>(`/api/tasks/${id}/workspace/files`),
    () => getSnapshot().workspaceFiles[id] ?? [],
  )
}

export async function getWorkspaceFile(id: string, path: string): Promise<WorkspaceFileContent> {
  const query = new URLSearchParams({ path })

  return withFallback(
    () => requestJson<WorkspaceFileContent>(`/api/tasks/${id}/workspace/file?${query.toString()}`),
    () => ({ path, content: getSnapshot().workspaceContent[id]?.[path] ?? '// File not found in mock workspace' }),
  )
}

export async function proposeWorkspacePatch(
  id: string,
  payload: { instruction: string },
): Promise<{ status: string }> {
  return withFallback(
    () =>
      requestJson<{ status: string }>(`/api/tasks/${id}/workspace/propose-patch`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    () => ({ status: 'queued' }),
  )
}

export async function getSignoffStatus(id: string): Promise<SignoffStatus> {
  return withFallback(
    () => requestJson<SignoffStatus>(`/api/tasks/${id}/signoff/status`),
    () => {
      const signoff = getSnapshot().signoff[id]
      if (!signoff) {
        throw new Error(`Signoff status for task ${id} not found`)
      }
      return signoff
    },
  )
}

export async function submitStageApproval(
  id: string,
  stage: string,
  payload: ApprovalPayload,
): Promise<{ status: string }> {
  return withFallback(
    () =>
      requestJson<{ status: string }>(`/api/tasks/${id}/approvals/${stage}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    () => {
      applyMockApproval(id, stage, payload)
      return { status: 'recorded' }
    },
  )
}

export async function createWaiver(id: string, payload: WaiverPayload): Promise<{ status: string }> {
  return withFallback(
    () => requestJson<{ status: string }>(`/api/tasks/${id}/waivers`, { method: 'POST', body: JSON.stringify(payload) }),
    () => {
      applyMockWaiver(id, payload)
      return { status: 'queued' }
    },
  )
}

export async function exportBundle(id: string): Promise<ExportBundleResponse> {
  return withFallback(
    () => requestJson<ExportBundleResponse>(`/api/tasks/${id}/export-bundle`, { method: 'POST' }),
    () => createMockExportBundle(id),
  )
}
