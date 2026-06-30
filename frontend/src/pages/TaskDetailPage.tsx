import { useCallback, useEffect, useMemo, useState } from 'react'
import { NavLink, useParams } from 'react-router-dom'
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  Clock3,
  FileCode2,
  ListChecks,
  PackageCheck,
  PlayCircle,
  RefreshCw,
  ShieldCheck,
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
} from '@/api/tasks'
import { EmptyState, ErrorState, LoadingState, MetricCard, SummaryRow } from '@/components/app/shared'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
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

type DetailTab = 'runbook' | 'rtl' | 'signoff'

export function TaskDetailPage({ tab }: { tab: DetailTab }) {
  const { id } = useParams<{ id: string }>()
  const taskId = id ?? ''
  const [detail, setDetail] = useState<TaskDetail | null>(null)
  const [events, setEvents] = useState<RunbookEvent[]>([])
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([])
  const [diagnoses, setDiagnoses] = useState<DiagnosisItem[]>([])
  const [files, setFiles] = useState<WorkspaceFileSummary[]>([])
  const [selectedFile, setSelectedFile] = useState('')
  const [selectedFileContent, setSelectedFileContent] = useState('')
  const [signoff, setSignoff] = useState<SignoffStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [fileLoading, setFileLoading] = useState(false)
  const [liveConnected, setLiveConnected] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [retryingStage, setRetryingStage] = useState<string | null>(null)

  const loadTask = useCallback(async () => {
    if (!taskId) {
      return
    }

    setLoading(true)
    setError(null)
    setActionMessage('')
    setActionError(null)

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

      const firstPath = workspaceFiles[0]?.path ?? ''
      setSelectedFile(firstPath)

      if (firstPath) {
        setFileLoading(true)
        try {
          const content = await getWorkspaceFile(taskId, firstPath)
          setSelectedFileContent(content.content)
        } finally {
          setFileLoading(false)
        }
      } else {
        setSelectedFileContent('')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load task detail')
    } finally {
      setLoading(false)
    }
  }, [taskId])

  useEffect(() => {
    void loadTask()
  }, [loadTask, refreshKey])

  useEffect(() => {
    if (!taskId) {
      return
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
        void loadTask()
      },
      onError() {
        setLiveConnected(false)
      },
    })

    socket.onopen = () => setLiveConnected(true)
    socket.onclose = () => setLiveConnected(false)

    return () => {
      socket.close()
    }
  }, [loadTask, taskId])

  const currentRecommendation = useMemo(() => diagnoses[0]?.detail ?? 'No recommendation is available yet.', [diagnoses])

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
    setFileLoading(true)
    setActionError(null)

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
      setActionMessage('Final approval request recorded.')
      setRefreshKey((value) => value + 1)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Unable to request final approval')
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
            <div className='grid gap-3 md:grid-cols-4'>
              <MetricCard label='Current stage' value={detail.currentStage} icon={Wrench} />
              <MetricCard label='ETA' value={detail.etaLabel} icon={Clock3} />
              <MetricCard label='Owner' value={detail.ownerName} icon={Bot} />
              <MetricCard label='Artifact lineage' value={`${detail.artifactLineageCount} linked outputs`} icon={PackageCheck} />
            </div>

            <div className='rounded-3xl bg-slate-50 p-4'>
              <div className='flex items-center justify-between'>
                <div>
                  <p className='text-sm font-semibold text-slate-900'>Phase timeline</p>
                  <p className='mt-1 text-sm text-slate-500'>GET /api/v1/tasks/:id and GET /api/v1/tasks/:id/stages keep this timeline in sync.</p>
                </div>
                <Badge variant='secondary' className='rounded-full bg-white text-slate-500'>
                  {liveConnected ? 'WebSocket connected' : 'WebSocket reconnecting'}
                </Badge>
              </div>

              <div className='mt-5 grid gap-3 xl:grid-cols-5'>
                {detail.stages.map((stage) => (
                  <div key={stage.key} className='rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100'>
                    <div className='flex items-center justify-between gap-2'>
                      <p className='text-sm font-semibold text-slate-900'>{stage.label}</p>
                      {stage.status === 'done' ? <CheckCircle2 className='h-4 w-4 text-emerald-500' /> : null}
                      {stage.status === 'active' ? <PlayCircle className='h-4 w-4 text-blue-500' /> : null}
                      {stage.status === 'failed' ? <XCircle className='h-4 w-4 text-rose-500' /> : null}
                      {stage.status === 'queued' ? <Clock3 className='h-4 w-4 text-slate-300' /> : null}
                    </div>
                    <div className='mt-4 h-2 rounded-full bg-slate-100'>
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
                    <div className='mt-4 flex items-center justify-between text-xs text-slate-400'>
                      <span>Retries: {stage.retryCount ?? 0}</span>
                      <Button
                        variant='outline'
                        size='sm'
                        className='rounded-full border-slate-200'
                        disabled={retryingStage === stage.key || stage.status === 'active'}
                        onClick={() => void handleRetryStage(stage)}
                      >
                        <RefreshCw className={`mr-2 h-3.5 w-3.5 ${retryingStage === stage.key ? 'animate-spin' : ''}`} />
                        Retry
                      </Button>
                    </div>
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
            {diagnoses[0] ? (
              <>
                <div className='rounded-2xl border border-amber-200 bg-amber-50 p-4'>
                  <div className='flex items-center gap-2 text-amber-700'>
                    <AlertCircle className='h-4 w-4' />
                    <p className='font-semibold'>{diagnoses[0].title}</p>
                  </div>
                  <p className='mt-3 text-sm leading-6 text-amber-800/80'>{diagnoses[0].detail}</p>
                </div>
                <div className='space-y-3 rounded-2xl border border-slate-200 p-4'>
                  <SummaryRow icon={Bot} title='Suggested by' value={diagnoses[0].suggestedBy} />
                  <SummaryRow icon={FileCode2} title='Primary file' value={diagnoses[0].primaryFile} />
                  <SummaryRow icon={ListChecks} title='Confidence' value={diagnoses[0].confidence} />
                </div>
                <Button onClick={() => void handleApproveNextAction()} className='h-12 w-full rounded-2xl bg-slate-900 hover:bg-slate-800'>
                  Approve next action
                </Button>
              </>
            ) : (
              <EmptyState title='No diagnosis available' detail='This task has no AI diagnosis yet.' />
            )}
            {actionMessage ? <p className='rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700'>{actionMessage}</p> : null}
            {actionError ? <p className='rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700'>{actionError}</p> : null}
          </CardContent>
        </Card>
      </div>

      <div className='grid h-auto w-full grid-cols-3 rounded-2xl bg-slate-100 p-1'>
        <TabLink to={`/tasks/${taskId}`} label='Runbook' active={tab === 'runbook'} />
        <TabLink to={`/tasks/${taskId}/rtl`} label='RTL Workspace' active={tab === 'rtl'} />
        <TabLink to={`/tasks/${taskId}/signoff`} label='Signoff & Delivery' active={tab === 'signoff'} />
      </div>

      {tab === 'runbook' ? (
        <div className='grid gap-5 xl:grid-cols-2'>
          <Card className='rounded-3xl border-slate-200 shadow-none'>
            <CardHeader>
              <CardTitle className='text-xl'>Execution log</CardTitle>
              <CardDescription>Chronological events from GET /api/v1/tasks/:id/attempts/latest/events and the live WebSocket stream.</CardDescription>
            </CardHeader>
            <CardContent>
              {events.length ? (
                <ScrollArea className='h-80 pr-4'>
                  <div className='space-y-4'>
                    {events.map((event) => (
                      <div key={event.id} className='flex gap-4 rounded-2xl border border-slate-200 p-4'>
                        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${eventToneClass[event.tone] ?? eventToneClass.info}`}>
                          <Clock3 className='h-4 w-4' />
                        </div>
                        <div>
                          <div className='flex items-center gap-2 text-sm text-slate-400'>
                            <span>{event.time}</span>
                            <span>•</span>
                            <span>Orchestrator Service</span>
                          </div>
                          <p className='mt-1 font-semibold text-slate-900'>{event.title}</p>
                          <p className='mt-2 text-sm leading-6 text-slate-500'>{event.detail}</p>
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

          <div className='space-y-5'>
            <Card className='rounded-3xl border-slate-200 shadow-none'>
              <CardHeader>
                <CardTitle className='text-xl'>Artifacts</CardTitle>
                <CardDescription>Outputs attached to the current task object.</CardDescription>
              </CardHeader>
              <CardContent className='space-y-3'>
                {artifacts.length ? (
                  artifacts.map((artifact) => (
                    <div key={artifact.id} className='flex items-center justify-between rounded-2xl border border-slate-200 p-4'>
                      <div>
                        <p className='font-semibold text-slate-900'>{artifact.name}</p>
                        <p className='mt-1 text-sm text-slate-500'>{artifact.type} · owned by {artifact.owner}</p>
                      </div>
                      <Button variant='outline' className='rounded-full border-slate-200' disabled={!artifact.url && !artifact.path}>
                        {artifact.url || artifact.path ? 'Open' : 'Unavailable'}
                      </Button>
                    </div>
                  ))
                ) : (
                  <EmptyState title='No artifacts yet' detail='Artifacts will appear here once the current attempt produces them.' />
                )}
              </CardContent>
            </Card>

            <Card className='rounded-3xl border-slate-200 shadow-none'>
              <CardHeader>
                <CardTitle className='text-xl'>Current recommendation</CardTitle>
              </CardHeader>
              <CardContent className='rounded-b-3xl bg-slate-50 text-sm leading-6 text-slate-600'>{currentRecommendation}</CardContent>
            </Card>
          </div>
        </div>
      ) : null}

      {tab === 'rtl' ? (
        <div className='grid gap-5 xl:grid-cols-2'>
          <Card className='rounded-3xl border-slate-200 shadow-none'>
            <CardHeader>
              <CardTitle className='text-xl'>RTL editor surface</CardTitle>
              <CardDescription>Workspace files are loaded from the Orchestrator Service on demand.</CardDescription>
            </CardHeader>
            <CardContent className='space-y-4'>
              <div className='flex flex-wrap gap-2'>
                {files.map((file, index) => (
                  <button
                    key={file.path}
                    onClick={() => void handleFileSelect(file.path)}
                    className={`rounded-full px-3 py-1 text-sm ${
                      selectedFile === file.path || (!selectedFile && index === 0) ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {file.name}
                  </button>
                ))}
              </div>
              <div className='overflow-hidden rounded-3xl border border-slate-200 bg-slate-950 text-slate-200'>
                <div className='flex items-center gap-2 border-b border-slate-800 px-4 py-3 text-sm text-slate-400'>
                  <FileCode2 className='h-4 w-4' />
                  {selectedFile || 'No file selected'}
                </div>
                <pre className='overflow-x-auto p-4 text-sm leading-7 text-slate-300'>
                  {fileLoading ? '// Loading file…' : selectedFileContent || '// No file content available'}
                </pre>
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
                <CardTitle className='text-xl'>Open files</CardTitle>
              </CardHeader>
              <CardContent className='space-y-3'>
                {files.length ? (
                  files.map((file) => (
                    <div key={file.path} className='rounded-2xl bg-slate-50 p-4'>
                      <div className='flex items-center justify-between'>
                        <p className='font-semibold text-slate-900'>{file.name}</p>
                        <Badge variant='secondary' className='rounded-full bg-white text-slate-500'>
                          {file.status}
                        </Badge>
                      </div>
                      <p className='mt-2 text-sm leading-6 text-slate-500'>{file.note}</p>
                    </div>
                  ))
                ) : (
                  <EmptyState title='No workspace files' detail='The backend has not exposed any workspace files for this task yet.' />
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}

      {tab === 'signoff' ? (
        signoff ? (
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
                      {item.done ? <CheckCircle2 className='h-5 w-5 text-emerald-500' /> : <XCircle className='h-5 w-5 text-rose-500' />}
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
                  Request final approval
                </Button>
              </CardContent>
            </Card>
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
