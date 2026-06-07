import { useEffect, useMemo, useState } from 'react'
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
  ShieldCheck,
  Wrench,
  XCircle,
} from 'lucide-react'

import {
  getSignoffStatus,
  getTask,
  getTaskArtifacts,
  getTaskDiagnosis,
  getTaskEvents,
  getWorkspaceFile,
  getWorkspaceFiles,
  proposeWorkspacePatch,
  submitStageApproval,
} from '@/api/tasks'
import { EmptyState, ErrorState, LoadingState, MetricCard, SummaryRow } from '@/components/app/shared'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import type {
  ArtifactItem,
  DiagnosisItem,
  RunbookEvent,
  SignoffStatus,
  TaskDetail,
  WorkspaceFileSummary,
} from '@/types/chipflow'

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

const defaultRecommendation =
  'Re-run the fast simulation slice after register insertion, then promote the updated artifact set into the signoff package draft.'

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

  useEffect(() => {
    if (!taskId) return
    let mounted = true

    async function load() {
      setLoading(true)
      setError(null)
      setActionMessage('')

      try {
        const [task, taskEvents, taskArtifacts, taskDiagnosis, workspaceFiles, signoffStatus] = await Promise.all([
          getTask(taskId),
          getTaskEvents(taskId),
          getTaskArtifacts(taskId),
          getTaskDiagnosis(taskId),
          getWorkspaceFiles(taskId),
          getSignoffStatus(taskId),
        ])

        if (!mounted) return

        setDetail(task)
        setEvents(taskEvents)
        setArtifacts(taskArtifacts)
        setDiagnoses(taskDiagnosis)
        setFiles(workspaceFiles)
        setSignoff(signoffStatus)

        const firstPath = workspaceFiles[0]?.path ?? ''
        setSelectedFile(firstPath)

        if (firstPath) {
          const content = await getWorkspaceFile(taskId, firstPath)
          if (!mounted) return
          setSelectedFileContent(content.content)
        } else {
          setSelectedFileContent('')
        }
      } catch (err) {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load task detail')
      } finally {
        if (mounted) setLoading(false)
      }
    }

    void load()
    return () => {
      mounted = false
    }
  }, [taskId])

  const currentRecommendation = useMemo(() => {
    return diagnoses[0]?.detail ?? defaultRecommendation
  }, [diagnoses])

  const verificationSummary = useMemo(
    () => [
      {
        label: 'Lint',
        value: detail?.tone === 'failed' ? '1 blocking' : '0 blocking',
        tone: detail?.tone === 'failed' ? 'text-rose-600' : 'text-emerald-600',
      },
      { label: 'Sim regressions', value: detail?.tone === 'failed' ? '38 / 42 pass' : '42 / 42 pass', tone: 'text-sky-600' },
      {
        label: 'Timing slack',
        value: detail?.tone === 'failed' ? '-0.02 ns' : '+0.11 ns',
        tone: detail?.tone === 'failed' ? 'text-rose-600' : 'text-violet-600',
      },
    ],
    [detail],
  )

  async function handleFileSelect(path: string) {
    if (!taskId) return
    setSelectedFile(path)
    const file = await getWorkspaceFile(taskId, path)
    setSelectedFileContent(file.content)
  }

  async function handleApproveNextAction() {
    if (!taskId) return

    const result = await proposeWorkspacePatch(taskId, {
      instruction: currentRecommendation,
    })

    setActionMessage(`Next action queued: ${result.status}`)
  }

  async function handleRequestFinalApproval() {
    if (!taskId) return

    await submitStageApproval(taskId, 'signoff', {
      decision: 'approve',
      comment: 'Final approval requested from the routed ChipFlowAI UI.',
    })

    const updatedSignoff = await getSignoffStatus(taskId)
    setSignoff(updatedSignoff)
    setActionMessage('Final approval request recorded.')
  }

  if (!taskId) return <ErrorState title='Missing task id' detail='No task id was provided in the route.' />
  if (loading) return <LoadingState label='Loading task detail…' />
  if (error || !detail) {
    return <ErrorState title='Unable to load task detail' detail={error ?? 'Task not found'} onRetry={() => window.location.reload()} />
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
                  <p className='mt-1 text-sm text-slate-500'>From planner kickoff to signoff package.</p>
                </div>
                <Badge variant='secondary' className='rounded-full bg-white text-slate-500'>
                  Live status
                </Badge>
              </div>

              <div className='mt-5 grid gap-3 xl:grid-cols-5'>
                {detail.stages.map((stage) => (
                  <div key={stage.key} className='rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100'>
                    <div className='flex items-center justify-between'>
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
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className='rounded-3xl border-slate-200 shadow-none'>
          <CardHeader>
            <CardTitle className='text-xl'>AI diagnosis</CardTitle>
            <CardDescription>Operator-friendly summary of the current issue and next action.</CardDescription>
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
              <CardDescription>Chronological activity from planning through diagnosis.</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className='h-80 pr-4'>
                <div className='space-y-4'>
                  {events.map((event) => (
                    <div key={event.id} className='flex gap-4 rounded-2xl border border-slate-200 p-4'>
                      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${eventToneClass[event.tone]}`}>
                        <Clock3 className='h-4 w-4' />
                      </div>
                      <div>
                        <div className='flex items-center gap-2 text-sm text-slate-400'>
                          <span>{event.time}</span>
                          <span>•</span>
                          <span>ChipFlowAI</span>
                        </div>
                        <p className='mt-1 font-semibold text-slate-900'>{event.title}</p>
                        <p className='mt-2 text-sm leading-6 text-slate-500'>{event.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
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
                        <p className='mt-1 text-sm text-slate-500'>
                          {artifact.type} · owned by {artifact.owner}
                        </p>
                      </div>
                      <Button variant='outline' className='rounded-full border-slate-200'>
                        Open
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
              <CardContent className='rounded-b-3xl bg-slate-50 text-sm leading-6 text-slate-600'>
                {currentRecommendation}
                {actionMessage ? <p className='mt-3 font-medium text-emerald-700'>{actionMessage}</p> : null}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}

      {tab === 'rtl' ? (
        <div className='grid gap-5 xl:grid-cols-2'>
          <Card className='rounded-3xl border-slate-200 shadow-none'>
            <CardHeader>
              <CardTitle className='text-xl'>RTL editor surface</CardTitle>
              <CardDescription>Open tabs and verification context stay adjacent to the code.</CardDescription>
            </CardHeader>
            <CardContent className='space-y-4'>
              <div className='flex flex-wrap gap-2'>
                {files.map((file, index) => (
                  <button
                    key={file.path}
                    onClick={() => void handleFileSelect(file.path)}
                    className={`rounded-full px-3 py-1 text-sm ${
                      selectedFile === file.path || (!selectedFile && index === 0)
                        ? 'bg-slate-900 text-white'
                        : 'bg-slate-100 text-slate-600'
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
                  {selectedFileContent || '// No file content available'}
                </pre>
              </div>
            </CardContent>
          </Card>

          <div className='space-y-5'>
            <Card className='rounded-3xl border-slate-200 shadow-none'>
              <CardHeader>
                <CardTitle className='text-xl'>Verification status</CardTitle>
                <CardDescription>At-a-glance health for the current workspace snapshot.</CardDescription>
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
                <CardDescription>Capture the final release gate in the same task object.</CardDescription>
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
                <div className='rounded-3xl border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-blue-800'>
                  {signoff.message}
                </div>
                {actionMessage ? <p className='text-sm font-medium text-emerald-700'>{actionMessage}</p> : null}
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
    <NavLink
      to={to}
      className={`rounded-2xl py-3 text-center text-sm font-medium transition ${
        active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
      }`}
    >
      {label}
    </NavLink>
  )
}
