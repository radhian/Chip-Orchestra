import { useCallback, useEffect, useMemo, useState } from 'react'
import { NavLink, useParams, useSearchParams } from 'react-router-dom'
import {
  AlertCircle,
  Bot,
  Cpu,
  CheckCircle2,
  Clock3,
  FileCode2,
  ListChecks,
  PackageCheck,
  PlayCircle,
  RefreshCw,
  ShieldCheck,
  Paperclip,
  Wrench,
  XCircle,
} from 'lucide-react'

import {
  connectTaskEvents,
  getSignoffStatus,
  getTask,
  getTaskArtifacts,
  getTaskDiagnosis,
  getTaskEvents,
  getTaskStages,
  getWorkspaceFile,
  getWorkspaceFiles,
  proposeWorkspacePatch,
  retryTaskStage,
  submitStageApproval,
  uploadWorkspaceFile,
  workspaceExportUrl,
  workspaceRawUrl,
} from '@/api/tasks'
import { EmptyState, ErrorState, LoadingState, MetricCard, SummaryRow } from '@/components/app/shared'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import type { ArtifactItem, DiagnosisItem, RunbookEvent, SignoffStatus, TaskDetail, TaskStage, WorkspaceFileSummary } from '@/types/orchestra'

const stageToneClass = {
  running: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  review: 'bg-amber-100 text-amber-700 border-amber-200',
  passed: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  failed: 'bg-rose-100 text-rose-700 border-rose-200',
} as const

const eventToneClass = {
  info: 'bg-sky-100 text-sky-700',
  success: 'bg-emerald-100 text-emerald-700',
  warning: 'bg-amber-100 text-amber-700',
} as const

type DetailTab = 'runbook' | 'rtl' | 'sim' | 'signoff'

const IMAGE_EXT = /\.(png|jpe?g|webp|bmp|gif|svg)$/i
const BINARY_EXT = /\.(gds|gds2|oas|pdf|vcd|fst|zip|gz|tar|bin|lef|def|spef|db|lib)$/i

function isImagePath(path: string): boolean {
  return IMAGE_EXT.test(path)
}

function isBinaryPath(path: string): boolean {
  return BINARY_EXT.test(path)
}

/** Event time in the USER'S timezone (the server's bare "15:04" string is
 *  container-local UTC and read wrong on the wall clock). */
function eventTime(event: RunbookEvent): string {
  if (event.timestamp) {
    const parsed = new Date(event.timestamp)
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  }
  return event.time
}

export function TaskDetailPage({ tab }: { tab: DetailTab }) {
  const { id } = useParams<{ id: string }>()
  const taskId = id ?? ''
  const [searchParams] = useSearchParams()
  const requestedFile = searchParams.get('file') ?? ''
  const [detail, setDetail] = useState<TaskDetail | null>(null)
  const [events, setEvents] = useState<RunbookEvent[]>([])
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([])
  const [diagnoses, setDiagnoses] = useState<DiagnosisItem[]>([])
  const [files, setFiles] = useState<WorkspaceFileSummary[]>([])
  const [selectedFile, setSelectedFile] = useState('')
  const [selectedFileContent, setSelectedFileContent] = useState('')
  const [signoff, setSignoff] = useState<SignoffStatus | null>(null)
  const [showChangeBox, setShowChangeBox] = useState(false)
  const [changeRequest, setChangeRequest] = useState('')
  const [changeFiles, setChangeFiles] = useState<File[]>([])
  const [agentTranscript, setAgentTranscript] = useState('')
  const [agentTranscriptPath, setAgentTranscriptPath] = useState('')
  const [simLog, setSimLog] = useState('')
  const [simReport, setSimReport] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [fileLoading, setFileLoading] = useState(false)
  const [liveConnected, setLiveConnected] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [retryingStage, setRetryingStage] = useState<string | null>(null)

  // Background refreshes (live WebSocket events) must NOT swap the page to a
  // spinner, clear action feedback, or reset the file selection — doing so on
  // every event is what made the whole page flicker during an active run.
  const loadTask = useCallback(async (background = false) => {
    if (!taskId) {
      return
    }

    if (!background) {
      setLoading(true)
      setError(null)
      setActionMessage('')
      setActionError(null)
    }

    try {
      const [task, stageList, taskEvents, taskArtifacts, taskDiagnosis, workspaceFiles, signoffStatus] = await Promise.all([
        getTask(taskId),
        getTaskStages(taskId),
        getTaskEvents(taskId),
        getTaskArtifacts(taskId),
        getTaskDiagnosis(taskId),
        getWorkspaceFiles(taskId),
        getSignoffStatus(taskId),
      ])

      const mergedTask = { ...task, stages: stageList }
      setDetail(mergedTask)
      setEvents(taskEvents)
      setArtifacts(taskArtifacts)
      setDiagnoses(taskDiagnosis)
      setFiles(workspaceFiles)
      setSignoff(signoffStatus)

      // Live activity: the log that explains what the CURRENT stage is doing —
      // deep-agent transcripts for LLM stages, tool logs for EDA stages
      // (librelane/lint/sim/DRC …), so a PNR or LVS failure is readable right
      // in the runbook.
      const stageName = (mergedTask.currentStage || '').toUpperCase()
      const allPaths = workspaceFiles.map((file) => file.path)
      const stageLogCandidates: Record<string, string[]> = {
        SPEC_INGEST: ['context/uploads_digest.md'],
        PLAN: ['logs/plan_deep_agent.md'],
        RTL_GEN: ['logs/rtl_gen_deep_agent.md'],
        RTL_REPAIR: ['logs/rtl_repair_deep_agent.md'],
        TB_GEN: ['logs/tb_gen_deep_agent.md'],
        SIM: ['logs/sim.log'],
        LINT: ['logs/lint.log'],
        SYNTH: ['logs/librelane.log'],
        PNR: ['logs/librelane.log'],
        DRC_LVS: ['logs/librelane.log'],
        STA: ['logs/sta.log', 'logs/librelane.log'],
        GL_SIM: ['logs/gl_sim.log'],
        RENDER: ['logs/render.log'],
        PADRING: ['logs/padring.log', 'padring/padring_gf180.svg'],
        SIGNOFF: ['reports/signoff_summary.md', 'padring/padring_gf180.svg', 'logs/librelane.log'],
        EXPORT: ['exports/final_report.tex', 'logs/librelane.log'],
      }
      const deepAgentLogs = allPaths.filter((path) => path.startsWith('logs/') && path.includes('_deep_agent'))
      const transcriptPath =
        (stageLogCandidates[stageName] ?? []).find((candidate) => allPaths.includes(candidate)) ??
        deepAgentLogs[deepAgentLogs.length - 1] ??
        ''
      setAgentTranscriptPath(transcriptPath)
      if (transcriptPath) {
        try {
          const transcript = await getWorkspaceFile(taskId, transcriptPath)
          const tail = transcript.content.slice(-6000)
          setAgentTranscript((current) => (current === tail ? current : tail))
        } catch {
          // transcript is best-effort
        }
      } else {
        setAgentTranscript('')
      }

      // Simulation evidence: the testbench console (logs/sim.log) and the sim
      // report (reports/sim_report.json) feed the Simulation tab.
      const paths = new Set(workspaceFiles.map((file) => file.path))
      if (paths.has('logs/sim.log')) {
        try {
          const logFile = await getWorkspaceFile(taskId, 'logs/sim.log')
          const tail = logFile.content.slice(-8000)
          setSimLog((current) => (current === tail ? current : tail))
        } catch {
          // best-effort
        }
      }
      if (paths.has('reports/sim_report.json')) {
        try {
          const reportFile = await getWorkspaceFile(taskId, 'reports/sim_report.json')
          setSimReport(JSON.parse(reportFile.content) as Record<string, unknown>)
        } catch {
          // best-effort
        }
      }

      // Keep the user's current file selection across background refreshes;
      // only (re)pick a file on first load or when the selection disappeared.
      const preferredPath = workspaceFiles.some((file) => file.path === requestedFile) ? requestedFile : ''
      let nextPath = ''
      setSelectedFile((current) => {
        const stillExists = current && workspaceFiles.some((file) => file.path === current)
        nextPath = (!background && preferredPath) || (stillExists ? current : '') || preferredPath || (workspaceFiles[0]?.path ?? '')
        return nextPath
      })

      if (nextPath && !isImagePath(nextPath) && !isBinaryPath(nextPath)) {
        if (!background) {
          setFileLoading(true)
        }
        try {
          const content = await getWorkspaceFile(taskId, nextPath)
          // Avoid re-render churn: only update when the content actually changed.
          setSelectedFileContent((current) => (current === content.content ? current : content.content))
        } finally {
          if (!background) {
            setFileLoading(false)
          }
        }
      } else {
        setSelectedFileContent('')
      }
    } catch (err) {
      if (!background) {
        setError(err instanceof Error ? err.message : 'Failed to load task detail')
      }
    } finally {
      if (!background) {
        setLoading(false)
      }
    }
  }, [taskId, requestedFile])

  useEffect(() => {
    void loadTask()
  }, [loadTask, refreshKey])

  useEffect(() => {
    if (!taskId) {
      return
    }

    // Coalesce bursts of live events into ONE background refresh every ~2.5 s —
    // refreshing on every single event hammered the API and flickered the page.
    let refreshTimer: ReturnType<typeof setTimeout> | null = null
    let lastRefresh = 0
    const scheduleRefresh = () => {
      if (refreshTimer) {
        return
      }
      const wait = Math.max(0, 2500 - (Date.now() - lastRefresh))
      refreshTimer = setTimeout(() => {
        refreshTimer = null
        lastRefresh = Date.now()
        void loadTask(true)
      }, wait)
    }

    const socket = connectTaskEvents(taskId, {
      onMessage(event) {
        setLiveConnected(true)
        setEvents((current) => {
          if (current.some((item) => item.id === event.id)) {
            return current
          }
          return [...current, event]
        })
        scheduleRefresh()
      },
      onError() {
        setLiveConnected(false)
      },
    })

    socket.onopen = () => setLiveConnected(true)
    socket.onclose = () => setLiveConnected(false)

    return () => {
      if (refreshTimer) {
        clearTimeout(refreshTimer)
      }
      socket.close()
    }
  }, [loadTask, taskId])

  // The next-action panel adapts to the run's ACTUAL situation instead of a
  // fixed "Approve next action": retry a failed stage, release a review gate,
  // wait while agents work, or — when everything is done — ask the user
  // whether they're happy or want changes.
  const situation = useMemo(() => {
    const stages = detail?.stages ?? []
    const failed = stages.find((stage) => stage.status === 'failed')
    if (failed) return { kind: 'failed' as const, stage: failed }
    const gate = stages.find((stage) => stage.pendingApproval)
    if (gate) return { kind: 'gate' as const, stage: gate }
    const active = stages.find((stage) => stage.status === 'active')
    if (active) return { kind: 'running' as const, stage: active }
    if (stages.length && stages.every((stage) => stage.status === 'done')) {
      return { kind: 'completed' as const, stage: undefined }
    }
    return { kind: 'idle' as const, stage: undefined }
  }, [detail?.stages])

  async function handleRequestChanges() {
    if (!taskId || !changeRequest.trim()) {
      return
    }
    setActionError(null)
    try {
      let instruction = changeRequest.trim()
      if (changeFiles.length) {
        const uploaded: string[] = []
        for (const file of changeFiles) {
          const { path } = await uploadWorkspaceFile(taskId, file)
          uploaded.push(path)
        }
        instruction +=
          `\n\nAttached reference files (already saved in the workspace): ${uploaded.join(', ')} — ` +
          'read them (images are decoded by the vision model) and treat them as the updated spec/input.'
      }
      await proposeWorkspacePatch(taskId, { instruction })
      setActionMessage('Change request sent to the agents — watch the execution log.')
      setChangeRequest('')
      setChangeFiles([])
      setShowChangeBox(false)
      setRefreshKey((value) => value + 1)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Unable to send the change request')
    }
  }

  async function handleApproveGate(stageKey: string) {
    if (!taskId) {
      return
    }
    setActionError(null)
    try {
      await submitStageApproval(taskId, stageKey, {
        decision: 'approve',
        comment: 'Approved from the Chip Orchestra workspace.',
      })
      setActionMessage('Gate approved — the flow continues.')
      setRefreshKey((value) => value + 1)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Unable to approve the gate')
    }
  }

  // Diagnoses accumulate per stage — the LATEST one describes the current
  // state of the run (showing [0] left a stale SPEC_INGEST note on screen).
  const latestDiagnosis = useMemo(() => (diagnoses.length ? diagnoses[diagnoses.length - 1] : undefined), [diagnoses])
  const currentRecommendation = useMemo(
    () => latestDiagnosis?.detail ?? 'No recommendation is available yet.',
    [latestDiagnosis],
  )

  // Group workspace files by their top-level folder (rtl/, tb/, context/, …)
  // so the browser reads like a project tree instead of one flat chip cloud.
  const groupedFiles = useMemo(() => {
    const groups = new Map<string, WorkspaceFileSummary[]>()
    for (const file of files) {
      const slash = file.path.indexOf('/')
      const folder = slash === -1 ? '(root)' : file.path.slice(0, slash)
      const list = groups.get(folder) ?? []
      list.push(file)
      groups.set(folder, list)
    }
    const order = ['rtl', 'tb', 'waves', 'gds', 'reports', 'spec', 'plans', 'context', 'sw', 'logs', 'exports', '(root)']
    return [...groups.entries()].sort(([a], [b]) => {
      const ia = order.indexOf(a) === -1 ? order.length : order.indexOf(a)
      const ib = order.indexOf(b) === -1 ? order.length : order.indexOf(b)
      return ia - ib || a.localeCompare(b)
    })
  }, [files])

  // Simulation-tab evidence derived from the workspace file list.
  // Chip INPUT = the Python-generated stimulus visualization (waves/chip_input*,
  // rtl/*input*); chip OUTPUT = what the RTL computed, rendered from the
  // testbench's $writememh dump (waves/*output*, waves/*.mem → .png).
  const simAssets = useMemo(() => {
    const paths = files.map((file) => file.path)
    const images = paths.filter((path) => IMAGE_EXT.test(path))
    const isWaveform = (path: string) => /waveform/i.test(path)
    const inputImages = images.filter(
      (path) => /input/i.test(path) && !path.startsWith('context/uploads/') && !isWaveform(path),
    )
    // Exactly ONE desired + ONE chip output — the verification pair. Stray
    // debug dumps (dbg_output.png etc.) belong to generatedImages, not here:
    // two "CHIP OUTPUT" cards read as two scenarios.
    const outputImages = images.filter(
      (path) => /(golden|chip)_output\.[a-z]+$/i.test(path) && !isWaveform(path),
    )
    const generatedImages = images.filter(
      (path) =>
        !isWaveform(path) &&
        !inputImages.includes(path) &&
        !outputImages.includes(path) &&
        !path.startsWith('context/uploads/') &&
        !path.startsWith('gds/'),
    )
    return {
      waveImages: images.filter((path) => path.startsWith('waves/') && isWaveform(path)),
      inputImages,
      outputImages,
      generatedImages,
      uploadImages: images.filter((path) => path.startsWith('context/uploads/')),
      vcds: paths.filter((path) => path.startsWith('waves/') && path.endsWith('.vcd')),
      memFiles: paths.filter((path) => path.endsWith('.mem')),
    }
  }, [files])

  const simPassed = useMemo(() => {
    if (/TEST\s+PASSED/i.test(simLog)) return true
    if (/(FAILED|\$fatal|mismatch)/i.test(simLog)) return false
    return null
  }, [simLog])

  const verificationSummary = useMemo(() => {
    const stageList = detail?.stages ?? []
    const completed = stageList.filter((stage) => stage.status === 'done').length
    const failed = stageList.filter((stage) => stage.status === 'failed').length
    const active = stageList.filter((stage) => stage.status === 'active').length

    return [
      { label: 'Completed stages', value: `${completed} / ${stageList.length || 0}`, tone: 'text-emerald-600' },
      { label: 'Active stages', value: String(active), tone: 'text-sky-600' },
      { label: 'Failed stages', value: String(failed), tone: failed ? 'text-rose-600' : 'text-slate-500' },
    ]
  }, [detail?.stages])

  async function handleFileSelect(path: string) {
    if (!taskId) {
      return
    }

    setSelectedFile(path)
    setActionError(null)

    if (isImagePath(path) || isBinaryPath(path)) {
      setSelectedFileContent('')
      return
    }

    setFileLoading(true)
    try {
      const file = await getWorkspaceFile(taskId, path)
      setSelectedFileContent(file.content)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to load file')
    } finally {
      setFileLoading(false)
    }
  }

  async function handleApproveNextAction() {
    if (!taskId) {
      return
    }

    setActionError(null)
    setActionMessage('')

    try {
      const result = await proposeWorkspacePatch(taskId, {
        instruction: currentRecommendation,
      })
      setActionMessage(`Next action queued: ${result.status}`)
      setRefreshKey((value) => value + 1)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Unable to queue the next action')
    }
  }

  async function handleRequestFinalApproval() {
    if (!taskId) {
      return
    }

    setActionError(null)
    setActionMessage('')

    try {
      await submitStageApproval(taskId, 'signoff', {
        decision: 'approve',
        comment: 'Final approval requested from the Chip Orchestra workspace.',
      })

      const updatedSignoff = await getSignoffStatus(taskId)
      setSignoff(updatedSignoff)
      setActionMessage('Signoff approved — the deliverables .zip download is starting.')
      setRefreshKey((value) => value + 1)
    } catch {
      // Approval may already be recorded — exporting is still the user's intent.
      setActionMessage('Deliverables .zip download is starting.')
    }
    window.location.assign(workspaceExportUrl(taskId))
    // The EXPORT stage runs within seconds of the approval — refresh the
    // timeline a few times so its tile turns green without a manual reload.
    for (const delayMs of [3000, 7000, 12000]) {
      window.setTimeout(() => setRefreshKey((value) => value + 1), delayMs)
    }
  }

  async function handleRetryStage(stage: TaskStage) {
    if (!taskId) {
      return
    }

    setRetryingStage(stage.key)
    setActionError(null)
    setActionMessage('')

    try {
      const result = await retryTaskStage(taskId, stage.key)
      setActionMessage(`Retry queued for ${stage.label}: ${result.status}`)
      setRefreshKey((value) => value + 1)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : `Unable to retry ${stage.label}`)
    } finally {
      setRetryingStage(null)
    }
  }

  if (!taskId) return <ErrorState title='Missing task id' detail='No task id was provided in the route.' />
  if (loading) return <LoadingState label='Loading task detail…' />
  if (error || !detail) {
    return <ErrorState title='Unable to load task detail' detail={error ?? 'Task not found'} onRetry={() => setRefreshKey((value) => value + 1)} />
  }

  return (
    <div className='space-y-5'>
      <div className='grid gap-5 xl:grid-cols-2'>
        <Card className='rounded-3xl border-slate-200 shadow-none'>
          <CardHeader>
            <div className='flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between'>
              <div>
                <CardTitle className='text-2xl'>{detail.name}</CardTitle>
                <CardDescription className='mt-2 text-sm leading-6'>{detail.description}</CardDescription>
              </div>
              <Badge className={`rounded-full border px-3 py-1 ${stageToneClass[detail.tone]}`}>{detail.statusLabel}</Badge>
            </div>
          </CardHeader>
          <CardContent className='space-y-5'>
            <div className='grid gap-3 md:grid-cols-5'>
              <MetricCard label='Current stage' value={detail.currentStage} icon={Wrench} />
              <MetricCard label='ETA' value={detail.etaLabel} icon={Clock3} />
              <MetricCard label='Owner' value={detail.ownerName} icon={Bot} />
              <MetricCard label='PDK' value={(detail.pdkLabel || 'N/A').replace('gf180mcu_fd_sc_', '')} icon={Cpu} />
              <MetricCard label='Artifact lineage' value={`${detail.artifactLineageCount} linked outputs`} icon={PackageCheck} />
            </div>

            <div className='rounded-3xl bg-slate-50 p-4'>
              <div className='flex items-center justify-between'>
                <p className='text-sm font-semibold text-slate-900'>Phase timeline</p>
                <Badge variant='secondary' className='rounded-full bg-white text-slate-500'>
                  {liveConnected ? 'Live' : 'Reconnecting'}
                </Badge>
              </div>

              <div className='mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5'>
                {detail.stages.map((stage) => (
                  <div key={stage.key} className='min-w-0 rounded-2xl bg-white p-3 shadow-sm ring-1 ring-slate-100'>
                    <div className='flex items-center justify-between gap-2'>
                      <p className='truncate text-sm font-semibold text-slate-900'>{stage.label}</p>
                      {stage.status === 'done' ? <CheckCircle2 className='h-4 w-4 shrink-0 text-emerald-500' /> : null}
                      {stage.status === 'active' ? <PlayCircle className='h-4 w-4 shrink-0 text-blue-500' /> : null}
                      {stage.status === 'failed' ? <XCircle className='h-4 w-4 shrink-0 text-rose-500' /> : null}
                      {stage.status === 'queued' ? <Clock3 className='h-4 w-4 shrink-0 text-slate-300' /> : null}
                    </div>
                    <div className='mt-3 h-2 rounded-full bg-slate-100'>
                      <div
                        className={`h-2 rounded-full ${
                          stage.status === 'done'
                            ? 'w-full bg-emerald-400'
                            : stage.status === 'active'
                              ? 'w-2/3 bg-blue-500'
                              : stage.status === 'failed'
                                ? 'w-2/3 bg-rose-500'
                                : 'w-1/4 bg-slate-200'
                        }`}
                      />
                    </div>
                    <Button
                      variant='outline'
                      size='sm'
                      className='mt-3 w-full rounded-full border-slate-200 text-xs'
                      disabled={retryingStage === stage.key || stage.status === 'active'}
                      onClick={() => void handleRetryStage(stage)}
                    >
                      <RefreshCw className={`mr-1.5 h-3 w-3 ${retryingStage === stage.key ? 'animate-spin' : ''}`} />
                      Retry{(stage.retryCount ?? 0) > 0 ? ` (${stage.retryCount})` : ''}
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className='rounded-3xl border-slate-200 shadow-none'>
          <CardHeader>
            <CardTitle className='text-xl'>AI diagnosis</CardTitle>
            <CardDescription>Live diagnosis returned by the Orchestrator Service.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            {latestDiagnosis ? (
              <>
                <div className='rounded-2xl border border-amber-200 bg-amber-50 p-4'>
                  <div className='flex items-center gap-2 text-amber-700'>
                    <AlertCircle className='h-4 w-4' />
                    <p className='font-semibold'>{latestDiagnosis.title}</p>
                  </div>
                  <p className='mt-3 text-sm leading-6 text-amber-800/80'>{latestDiagnosis.detail}</p>
                </div>
                <div className='space-y-3 rounded-2xl border border-slate-200 p-4'>
                  <SummaryRow icon={Bot} title='Suggested by' value={latestDiagnosis.suggestedBy} />
                  <SummaryRow icon={FileCode2} title='Primary file' value={latestDiagnosis.primaryFile} />
                  <SummaryRow icon={ListChecks} title='Confidence' value={latestDiagnosis.confidence} />
                </div>
                {situation.kind === 'failed' && situation.stage ? (
                  <div className='space-y-3'>
                    <p className='text-sm leading-6 text-slate-500'>
                      <span className='font-semibold text-rose-600'>{situation.stage.label} failed.</span>{' '}
                      Check the execution log for the reason, then retry — dependent stages reset automatically.
                    </p>
                    <Button
                      onClick={() => void handleRetryStage(situation.stage as TaskStage)}
                      className='h-12 w-full rounded-2xl bg-rose-600 hover:bg-rose-700'
                    >
                      <RefreshCw className='mr-2 h-4 w-4' />
                      Retry {situation.stage.label}
                    </Button>
                  </div>
                ) : situation.kind === 'gate' && situation.stage ? (
                  <div className='space-y-3'>
                    <p className='text-sm leading-6 text-slate-500'>
                      <span className='font-semibold text-amber-600'>{situation.stage.label} is waiting for your review.</span>{' '}
                      Inspect the artifacts and reports, then release the gate.
                    </p>
                    <Button
                      onClick={() => void handleApproveGate((situation.stage as TaskStage).key)}
                      className='h-12 w-full rounded-2xl bg-slate-900 hover:bg-slate-800'
                    >
                      <ShieldCheck className='mr-2 h-4 w-4' />
                      Approve {situation.stage.label} gate
                    </Button>
                  </div>
                ) : situation.kind === 'running' && situation.stage ? (
                  <div className='flex items-center gap-3 rounded-2xl border border-indigo-100 bg-indigo-50 p-4 text-sm leading-6 text-indigo-700'>
                    <Bot className='h-5 w-5 shrink-0 animate-pulse' />
                    <span>
                      Agents are working on <span className='font-semibold'>{situation.stage.label}</span> — follow the
                      execution log and the live agent transcript below. No action needed.
                    </span>
                  </div>
                ) : situation.kind === 'completed' ? (
                  <div className='space-y-3'>
                    <p className='text-sm leading-6 text-slate-500'>
                      The flow finished. Are you happy with the result, or should the agents change something?
                    </p>
                    {showChangeBox ? (
                      <div className='space-y-2'>
                        <Textarea
                          value={changeRequest}
                          onChange={(event) => setChangeRequest(event.target.value)}
                          placeholder='Describe what to change — e.g. "shrink the SRAM to 256B", "redo the testbench with more vectors", "regenerate the report"…'
                          className='min-h-24 rounded-2xl border-slate-200'
                        />
                        <div className='flex items-center gap-2'>
                          <label className='inline-flex h-11 cursor-pointer items-center gap-2 rounded-2xl border border-slate-200 px-4 text-sm text-slate-600 hover:bg-slate-50'>
                            <Paperclip className='h-4 w-4' />
                            Attach image / PDF / file
                            <input
                              type='file'
                              multiple
                              className='hidden'
                              onChange={(event) => {
                                setChangeFiles((current) => [...current, ...Array.from(event.target.files ?? [])])
                                event.target.value = ''
                              }}
                            />
                          </label>
                          {changeFiles.length ? (
                            <span className='text-xs text-slate-500'>
                              {changeFiles.map((file) => file.name).join(', ')}{' '}
                              <button type='button' className='text-rose-500 underline' onClick={() => setChangeFiles([])}>
                                clear
                              </button>
                            </span>
                          ) : null}
                        </div>
                        <div className='flex gap-2'>
                          <Button onClick={() => void handleRequestChanges()} disabled={!changeRequest.trim()} className='h-11 flex-1 rounded-2xl bg-blue-600 hover:bg-blue-700'>
                            Send to agents
                          </Button>
                          <Button variant='outline' onClick={() => setShowChangeBox(false)} className='h-11 rounded-2xl border-slate-200'>
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className='flex gap-2'>
                        <Button
                          onClick={() => {
                            setActionMessage('Result accepted — download the deliverables from Signoff & Delivery.')
                          }}
                          className='h-12 flex-1 rounded-2xl bg-emerald-600 hover:bg-emerald-700'
                        >
                          <CheckCircle2 className='mr-2 h-4 w-4' />
                          Looks good
                        </Button>
                        <Button variant='outline' onClick={() => setShowChangeBox(true)} className='h-12 flex-1 rounded-2xl border-slate-200'>
                          <Wrench className='mr-2 h-4 w-4' />
                          Request changes
                        </Button>
                      </div>
                    )}
                  </div>
                ) : (
                  <Button onClick={() => void handleApproveNextAction()} className='h-12 w-full rounded-2xl bg-slate-900 hover:bg-slate-800'>
                    Approve next action
                  </Button>
                )}
              </>
            ) : (
              <EmptyState title='No diagnosis available' detail='This task has no AI diagnosis yet.' />
            )}
            {actionMessage ? <p className='rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700'>{actionMessage}</p> : null}
            {actionError ? <p className='rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700'>{actionError}</p> : null}
          </CardContent>
        </Card>
      </div>

      <div className='grid h-auto w-full grid-cols-4 rounded-2xl bg-slate-100 p-1'>
        <TabLink to={`/tasks/${taskId}`} label='Runbook' active={tab === 'runbook'} />
        <TabLink to={`/tasks/${taskId}/rtl`} label='RTL Workspace' active={tab === 'rtl'} />
        <TabLink to={`/tasks/${taskId}/sim`} label='Simulation' active={tab === 'sim'} />
        <TabLink to={`/tasks/${taskId}/signoff`} label='Signoff & Delivery' active={tab === 'signoff'} />
      </div>

      {tab === 'runbook' ? (
        <div className='space-y-5'>
          <Card className='rounded-3xl border-slate-200 shadow-none'>
            <CardHeader>
              <CardTitle className='text-xl'>Execution log</CardTitle>
              <CardDescription>What every stage is doing, live — events, images, and stage outcomes.</CardDescription>
            </CardHeader>
            <CardContent>
              {events.length ? (
                <ScrollArea className='h-[30rem] pr-4'>
                  <div className='space-y-4'>
                    {events
                      .filter((event) => Boolean(event.title))
                      .map((event) => (
                      <div key={event.id} className='flex gap-4 rounded-2xl border border-slate-200 p-4'>
                        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${eventToneClass[event.tone] ?? eventToneClass.info}`}>
                          <Clock3 className='h-4 w-4' />
                        </div>
                        <div className='min-w-0'>
                          <div className='flex items-center gap-2 text-sm text-slate-400'>
                            <span>{eventTime(event)}</span>
                            <span>•</span>
                            <span>Orchestrator Service</span>
                          </div>
                          <p className='mt-1 font-semibold text-slate-900'>{event.title}</p>
                          <p className='mt-2 text-sm leading-6 text-slate-500'>{event.detail}</p>
                          {event.image ? (
                            <a href={workspaceRawUrl(taskId, event.image)} target='_blank' rel='noreferrer'>
                              <img
                                src={workspaceRawUrl(taskId, event.image)}
                                alt={event.title}
                                className='mt-3 max-h-56 rounded-xl border border-slate-200 bg-white'
                              />
                            </a>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              ) : (
                <EmptyState title='No execution events yet' detail='The backend has not published any runbook events for this task.' />
              )}
            </CardContent>
          </Card>

          <Card className='rounded-3xl border-slate-200 shadow-none'>
            <CardHeader>
              <CardTitle className='text-xl'>Live activity</CardTitle>
              <CardDescription>
                {agentTranscriptPath
                  ? `What the current stage is doing (${agentTranscriptPath}) — agent thinking/tool calls for LLM stages, tool logs (LibreLane, lint, sim, DRC/LVS, antenna checks) for EDA stages. Refreshed live.`
                  : 'Stage activity (agent transcript or EDA tool log) will appear here once a stage starts.'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {agentTranscript ? (
                <div className='overflow-hidden rounded-3xl border border-slate-200 bg-slate-950'>
                  <ScrollArea className='h-80'>
                    <pre className='whitespace-pre-wrap p-4 text-xs leading-6 text-slate-300'>{agentTranscript}</pre>
                  </ScrollArea>
                </div>
              ) : (
                <EmptyState title='No agent transcript yet' detail='PLAN / RTL_GEN / RTL_REPAIR / TB_GEN write their transcripts to logs/*_deep_agent.md.' />
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {tab === 'rtl' ? (
        <div className='grid gap-5 xl:grid-cols-2'>
          <Card className='rounded-3xl border-slate-200 shadow-none'>
            <CardHeader className='flex flex-row items-start justify-between space-y-0'>
              <div>
                <CardTitle className='text-xl'>RTL editor surface</CardTitle>
                <CardDescription>Workspace files are loaded from the Orchestrator Service on demand.</CardDescription>
              </div>
              <Button asChild variant='outline' className='rounded-full'>
                <a href={workspaceExportUrl(taskId)} download>
                  Export .zip
                </a>
              </Button>
            </CardHeader>
            <CardContent className='space-y-4'>
              <ScrollArea className='max-h-72 overflow-y-auto'>
                <div className='space-y-3 pr-3'>
                  {groupedFiles.map(([folder, groupFiles]) => (
                    <div key={folder}>
                      <p className='mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400'>{folder}</p>
                      <div className='flex flex-wrap gap-2'>
                        {groupFiles.map((file) => (
                          <button
                            key={file.path}
                            onClick={() => void handleFileSelect(file.path)}
                            className={`rounded-full px-3 py-1 text-sm ${
                              selectedFile === file.path ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'
                            }`}
                          >
                            {file.name}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
              <div className='overflow-hidden rounded-3xl border border-slate-200 bg-slate-950 text-slate-200'>
                <div className='flex items-center gap-2 border-b border-slate-800 px-4 py-3 text-sm text-slate-400'>
                  <FileCode2 className='h-4 w-4' />
                  <span className='min-w-0 break-all'>{selectedFile || 'No file selected'}</span>
                </div>
                {isImagePath(selectedFile) ? (
                  <div className='bg-white p-4'>
                    <img
                      src={workspaceRawUrl(taskId, selectedFile)}
                      alt={selectedFile}
                      className='mx-auto max-h-[32rem] rounded-xl border border-slate-200'
                    />
                  </div>
                ) : selectedFile.toLowerCase().endsWith('.pdf') ? (
                  <iframe
                    src={workspaceRawUrl(taskId, selectedFile)}
                    title={selectedFile}
                    className='h-[42rem] w-full bg-white'
                  />
                ) : isBinaryPath(selectedFile) ? (
                  <div className='p-6 text-sm text-slate-300'>
                    Binary file — not rendered as text.{' '}
                    <a className='text-sky-400 underline' href={workspaceRawUrl(taskId, selectedFile, true)}>
                      Download {selectedFile.split('/').pop()}
                    </a>
                  </div>
                ) : (
                  <pre className='overflow-x-auto p-4 text-sm leading-7 text-slate-300'>
                    {fileLoading ? '// Loading file…' : selectedFileContent || '// No file content available'}
                  </pre>
                )}
              </div>
            </CardContent>
          </Card>

          <div className='space-y-5'>
            <Card className='rounded-3xl border-slate-200 shadow-none'>
              <CardHeader>
                <CardTitle className='text-xl'>Verification status</CardTitle>
                <CardDescription>Derived from live stage state instead of placeholder metrics.</CardDescription>
              </CardHeader>
              <CardContent className='space-y-3'>
                {verificationSummary.map((item) => (
                  <div key={item.label} className='flex items-center justify-between rounded-2xl border border-slate-200 p-4'>
                    <p className='text-sm font-medium text-slate-600'>{item.label}</p>
                    <p className={`text-sm font-semibold ${item.tone}`}>{item.value}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className='rounded-3xl border-slate-200 shadow-none'>
              <CardHeader>
                <CardTitle className='text-xl'>Artifacts</CardTitle>
                <CardDescription>Outputs attached to the current task object — Open loads the file in the editor.</CardDescription>
              </CardHeader>
              <CardContent className='space-y-3'>
                {artifacts.length ? (
                  <ScrollArea className='max-h-96 overflow-y-auto'>
                    <div className='space-y-3 pr-3'>
                      {artifacts.map((artifact) => (
                        <div key={artifact.id} className='flex items-center justify-between gap-3 rounded-2xl border border-slate-200 p-4'>
                          <div className='min-w-0'>
                            <p className='truncate font-semibold text-slate-900'>{artifact.name}</p>
                            <p className='mt-1 text-sm text-slate-500'>{artifact.type} · owned by {artifact.owner}</p>
                          </div>
                          <Button
                            variant='outline'
                            className='shrink-0 rounded-full border-slate-200'
                            disabled={!artifact.url && !artifact.path}
                            onClick={() => {
                              if (artifact.path) {
                                void handleFileSelect(artifact.path)
                              } else if (artifact.url) {
                                window.open(artifact.url, '_blank', 'noopener')
                              }
                            }}
                          >
                            {artifact.url || artifact.path ? 'Open' : 'Unavailable'}
                          </Button>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                ) : (
                  <EmptyState title='No artifacts yet' detail='Artifacts will appear here once the current attempt produces them.' />
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}

      {tab === 'sim' ? (
        <div className='space-y-5'>
          <div className='grid gap-5 xl:grid-cols-[1.6fr_1fr]'>
            <Card className='rounded-3xl border-slate-200 shadow-none'>
              <CardHeader>
                <CardTitle className='text-xl'>Waveform</CardTitle>
                <CardDescription>Signals from the testbench run (waves/design.vcd, rendered by the EDA service).</CardDescription>
              </CardHeader>
              <CardContent className='space-y-3'>
                {simAssets.waveImages.length ? (
                  simAssets.waveImages.map((path) => (
                    <a key={path} href={workspaceRawUrl(taskId, path)} target='_blank' rel='noreferrer'>
                      <img src={workspaceRawUrl(taskId, path)} alt={path} className='w-full rounded-2xl border border-slate-200 bg-white' />
                    </a>
                  ))
                ) : (
                  <EmptyState title='No waveform image yet' detail='The SIM stage renders waves/waveform.png once the testbench produces design.vcd.' />
                )}
                {simAssets.vcds.length ? (
                  <div className='flex flex-wrap gap-2'>
                    {simAssets.vcds.map((path) => (
                      <a key={path} href={workspaceRawUrl(taskId, path, true)} className='rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 hover:bg-slate-50'>
                        ⬇ {path.split('/').pop()} (open in GTKWave)
                      </a>
                    ))}
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card className='rounded-3xl border-slate-200 shadow-none'>
              <CardHeader>
                <CardTitle className='text-xl'>Verdict</CardTitle>
                <CardDescription>Result of the self-checking testbench.</CardDescription>
              </CardHeader>
              <CardContent className='space-y-4'>
                <div className={`flex items-center gap-3 rounded-2xl border p-4 ${
                  simPassed === true ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
                  : simPassed === false ? 'border-rose-100 bg-rose-50 text-rose-700'
                  : 'border-slate-200 bg-slate-50 text-slate-500'
                }`}>
                  {simPassed === true ? <CheckCircle2 className='h-6 w-6' /> : simPassed === false ? <XCircle className='h-6 w-6' /> : <Clock3 className='h-6 w-6' />}
                  <div>
                    <p className='font-semibold'>
                      {simPassed === true ? 'TEST PASSED' : simPassed === false ? 'TEST FAILED' : 'No simulation result yet'}
                    </p>
                    <p className='text-sm opacity-80'>{String((simReport as { summary?: string } | null)?.summary ?? 'The SIM stage has not completed for this task.')}</p>
                  </div>
                </div>
                {simReport && typeof simReport.metrics === 'object' && simReport.metrics ? (
                  <div className='overflow-x-auto rounded-2xl border border-slate-200'>
                    <table className='w-full text-left text-sm'>
                      <tbody>
                        {Object.entries(simReport.metrics as Record<string, unknown>).map(([key, value]) => (
                          <tr key={key} className='border-b border-slate-100 last:border-0'>
                            <td className='px-4 py-2.5 font-medium text-slate-700'>{key}</td>
                            <td className='px-4 py-2.5 text-slate-600'>{String(value)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                {simAssets.memFiles.length ? (
                  <div>
                    <p className='text-xs uppercase tracking-widest text-slate-400'>Chip input data (.mem)</p>
                    <div className='mt-2 flex flex-wrap gap-2'>
                      {simAssets.memFiles.map((path) => (
                        <button key={path} onClick={() => void handleFileSelect(path)} className='rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-600'>
                          {path.split('/').pop()}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>

          <Card className='rounded-3xl border-slate-200 shadow-none'>
            <CardHeader>
              <CardTitle className='text-xl'>Testbench console</CardTitle>
              <CardDescription>What the testbench printed while driving the chip (logs/sim.log).</CardDescription>
            </CardHeader>
            <CardContent>
              {simLog ? (
                <div className='overflow-hidden rounded-3xl border border-slate-200 bg-slate-950'>
                  <ScrollArea className='h-72'>
                    <pre className='whitespace-pre-wrap p-4 text-xs leading-6 text-slate-300'>{simLog}</pre>
                  </ScrollArea>
                </div>
              ) : (
                <EmptyState title='No simulation log yet' detail='logs/sim.log appears after the SIM stage runs the testbench.' />
              )}
            </CardContent>
          </Card>

          {simAssets.inputImages.length || simAssets.outputImages.length ? (
            <div className='grid gap-5 xl:grid-cols-2'>
              <Card className='rounded-3xl border-slate-200 shadow-none'>
                <CardHeader>
                  <CardTitle className='text-xl'>Chip input</CardTitle>
                  <CardDescription>Images the user attached — what goes INTO the chip / drives the spec.</CardDescription>
                </CardHeader>
                <CardContent className='space-y-3'>
                  {simAssets.inputImages.length ? (
                    simAssets.inputImages.map((path) => (
                      <a key={path} href={workspaceRawUrl(taskId, path)} target='_blank' rel='noreferrer'>
                        <img src={workspaceRawUrl(taskId, path)} alt={path} className='w-full rounded-2xl border border-slate-200 bg-white' />
                      </a>
                    ))
                  ) : (
                    <EmptyState title='No input images' detail='Attach an image when creating the task to see it here.' />
                  )}
                </CardContent>
              </Card>
              <Card className='rounded-3xl border-slate-200 shadow-none'>
                <CardHeader>
                  <CardTitle className='text-xl'>Desired output vs chip output</CardTitle>
                  <CardDescription>
                    The desired output is what the Python model computed from the input; the chip output is what the
                    RTL actually computed. SIM only passes when they match value-for-value.
                  </CardDescription>
                </CardHeader>
                <CardContent className='space-y-3'>
                  {simAssets.outputImages.length ? (
                    [...simAssets.outputImages]
                      .sort((a, b) => (a.includes('golden') ? -1 : 0) - (b.includes('golden') ? -1 : 0))
                      .map((path) => (
                        <a key={path} href={workspaceRawUrl(taskId, path)} target='_blank' rel='noreferrer'>
                          <div className='rounded-2xl border border-slate-200 bg-white p-3'>
                            <p className='mb-2 text-center text-base font-bold text-slate-800'>
                              {path.includes('golden')
                                ? 'DESIRED OUTPUT — computed by the Python model'
                                : 'CHIP OUTPUT — computed by the RTL (must match the desired output)'}
                            </p>
                            <img src={workspaceRawUrl(taskId, path)} alt={path} className='mx-auto max-h-64 rounded-xl' />
                            <p className='mt-2 text-center text-xs text-slate-400'>{path}</p>
                          </div>
                        </a>
                      ))
                  ) : (
                    <EmptyState title='No output images yet' detail='Images the deep agents or simulation write into the workspace show up here.' />
                  )}
                </CardContent>
              </Card>
            </div>
          ) : null}
        </div>
      ) : null}

      {tab === 'signoff' ? (
        signoff ? (
          <div className='space-y-5'>
            {signoff.gdsImage || (signoff.metrics && Object.keys(signoff.metrics).length) ? (
              <div className='grid gap-5 xl:grid-cols-2'>
                <Card className='rounded-3xl border-slate-200 shadow-none'>
                  <CardHeader>
                    <CardTitle className='text-xl'>GDS render</CardTitle>
                    <CardDescription>Final hardened layout produced by the RENDER stage.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {signoff.gdsImage ? (
                      <a href={workspaceRawUrl(taskId, signoff.gdsImage)} target='_blank' rel='noreferrer'>
                        <img
                          src={workspaceRawUrl(taskId, signoff.gdsImage)}
                          alt='GDS layout render'
                          className='w-full rounded-2xl border border-slate-200 bg-white'
                        />
                      </a>
                    ) : (
                      <EmptyState title='No GDS render yet' detail='The RENDER stage has not produced a layout image for this task.' />
                    )}
                    {signoff.gdsFiles?.length ? (
                      <div className='mt-4 flex flex-wrap gap-2'>
                        {signoff.gdsFiles.map((file) => (
                          <a
                            key={file}
                            href={workspaceRawUrl(taskId, file, true)}
                            className='rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 hover:bg-slate-50'
                          >
                            ⬇ {file.split('/').pop()}
                          </a>
                        ))}
                      </div>
                    ) : null}
                  </CardContent>
                </Card>

                <Card className='rounded-3xl border-slate-200 shadow-none'>
                  <CardHeader>
                    <CardTitle className='text-xl'>Implementation parameters</CardTitle>
                    <CardDescription>Merged metrics from every EDA report (timing, area, power, checks).</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {signoff.metrics && Object.keys(signoff.metrics).length ? (
                      <div className='overflow-x-auto rounded-2xl border border-slate-200'>
                        <table className='w-full text-left text-sm'>
                          <thead>
                            <tr className='border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-400'>
                              <th className='px-4 py-3'>Parameter</th>
                              <th className='px-4 py-3'>Value</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(signoff.metrics)
                              .sort(([a], [b]) => a.localeCompare(b))
                              .map(([key, value]) => (
                                <tr key={key} className='border-b border-slate-100 last:border-0'>
                                  <td className='px-4 py-2.5 font-medium text-slate-700'>{key}</td>
                                  <td className='px-4 py-2.5 text-slate-600'>{value === null ? '—' : String(value)}</td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <EmptyState title='No metrics yet' detail='EDA reports have not published metrics for this task yet.' />
                    )}
                  </CardContent>
                </Card>
              </div>
            ) : null}

            <div className='grid gap-5 xl:grid-cols-2'>
            <Card className='rounded-3xl border-slate-200 shadow-none'>
              <CardHeader>
                <CardTitle className='text-xl'>Tapeout checklist</CardTitle>
                <CardDescription>Live signoff status from GET /api/v1/tasks/:id/signoff/status.</CardDescription>
              </CardHeader>
              <CardContent className='space-y-4'>
                {signoff.checklist.map((item) => (
                  <div key={item.id} className='flex gap-4 rounded-2xl border border-slate-200 p-4'>
                    <div className='mt-0.5'>
                      {item.done || item.status === 'done' ? (
                        <CheckCircle2 className='h-5 w-5 text-emerald-500' />
                      ) : item.status === 'failed' ? (
                        <XCircle className='h-5 w-5 text-rose-500' />
                      ) : (
                        <Clock3 className='h-5 w-5 text-amber-500' />
                      )}
                    </div>
                    <div>
                      <p className='font-semibold text-slate-900'>{item.label}</p>
                      <p className='mt-2 text-sm leading-6 text-slate-500'>{item.detail}</p>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className='rounded-3xl border-slate-200 shadow-none'>
              <CardHeader>
                <CardTitle className='text-xl'>Delivery package</CardTitle>
                <CardDescription>Everything needed for a clean handoff.</CardDescription>
              </CardHeader>
              <CardContent className='space-y-4'>
                <div className='rounded-3xl bg-slate-50 p-4'>
                  <p className='text-xs uppercase tracking-widest text-slate-400'>Package contents</p>
                  <ul className='mt-3 space-y-3 text-sm text-slate-600'>
                    {signoff.packageContents.map((item, index) => {
                      const toneClass = index === 0 ? 'text-emerald-500' : index === 1 ? 'text-blue-500' : 'text-violet-500'
                      const Icon = index === 1 ? FileCode2 : index === 2 ? ShieldCheck : PackageCheck

                      return (
                        <li key={item} className='flex items-center gap-2'>
                          <Icon className={`h-4 w-4 ${toneClass}`} />
                          {item}
                        </li>
                      )
                    })}
                  </ul>
                </div>
                <Separator />
                <div className='rounded-3xl border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-blue-800'>{signoff.message}</div>
                {actionMessage ? <p className='rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700'>{actionMessage}</p> : null}
                {actionError ? <p className='rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700'>{actionError}</p> : null}
                <Button onClick={() => void handleRequestFinalApproval()} className='h-12 w-full rounded-2xl bg-blue-600 text-base hover:bg-blue-700'>
                  Export deliverables (.zip)
                </Button>
              </CardContent>
            </Card>
            </div>
          </div>
        ) : (
          <EmptyState title='No signoff status available' detail='The backend has not returned signoff data for this task yet.' />
        )
      ) : null}
    </div>
  )
}

function TabLink({ to, label, active }: { to: string; label: string; active: boolean }) {
  return (
    <NavLink to={to} className={`rounded-2xl py-3 text-center text-sm font-medium transition ${active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
      {label}
    </NavLink>
  )
}
