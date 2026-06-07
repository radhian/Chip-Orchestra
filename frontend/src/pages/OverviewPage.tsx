import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { getWorkflowSteps, listTasks } from '@/api/tasks'
import { EmptyState, ErrorState, LoadingState } from '@/components/app/shared'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { ListTasksParams, TaskFilter, TaskSummary, WorkflowStep } from '@/types/chipflow'

const filterItems: { key: TaskFilter; label: string }[] = [
  { key: 'all', label: 'All repos' },
  { key: 'mine', label: 'My tasks' },
  { key: 'review', label: 'Needs review' },
  { key: 'failed', label: 'Failed' },
]

function MaterialIcon({ name, className = '' }: { name: string; className?: string }) {
  return <span className={`material-symbols-rounded ${className}`.trim()} aria-hidden='true'>{name}</span>
}

function buildTaskQuery(filter: TaskFilter): ListTasksParams {
  switch (filter) {
    case 'mine':
      return { owner: 'me' }
    case 'review':
      return { needs_review: true }
    case 'failed':
      return { failed: true }
    default:
      return {}
  }
}

export function OverviewPage() {
  const navigate = useNavigate()
  const [activeFilter, setActiveFilter] = useState<TaskFilter>('all')
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    async function load() {
      setLoading(true)
      setError(null)

      try {
        const [fetchedTasks, fetchedWorkflow] = await Promise.all([
          listTasks(buildTaskQuery(activeFilter)),
          getWorkflowSteps(),
        ])

        if (!mounted) return
        setTasks(fetchedTasks)
        setWorkflowSteps(fetchedWorkflow)
      } catch (err) {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load overview data')
      } finally {
        if (mounted) setLoading(false)
      }
    }

    void load()
    return () => {
      mounted = false
    }
  }, [activeFilter])

  if (loading) return <LoadingState label='Loading overview console…' />
  if (error) {
    return <ErrorState title='Unable to load Overview Console' detail={error} onRetry={() => window.location.reload()} />
  }

  return (
    <div className='space-y-5'>
      <div className='flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between'>
        <div>
          <h3 className='text-2xl font-semibold text-slate-900'>Task dashboard</h3>
          <p className='mt-1 text-sm text-slate-500'>
            A lean MVP home focused on active design tasks, status, and the path from RTL to GDS.
          </p>
        </div>
        <div className='flex flex-wrap gap-2'>
          {filterItems.map((filter) => {
            const active = filter.key === activeFilter
            return (
              <Button
                key={filter.key}
                variant='outline'
                onClick={() => setActiveFilter(filter.key)}
                className={`rounded-full border-slate-200 px-4 ${
                  active
                    ? 'bg-blue-600 text-white hover:bg-blue-600 hover:text-white'
                    : 'bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                {filter.label}
              </Button>
            )
          })}
        </div>
      </div>

      {tasks.length === 0 ? (
        <EmptyState title='No tasks match the current filter' detail='Try another filter or create a new design task.' />
      ) : (
        <Card className='overflow-hidden rounded-3xl border border-slate-200 bg-slate-50 shadow-none'>
          <CardContent className='p-0'>
            <div className='grid grid-cols-[2.4fr_1fr_1.2fr_.8fr] gap-3 border-b border-slate-200 px-6 py-4 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400'>
              <span>Task</span>
              <span>Owner</span>
              <span>Current stage</span>
              <span>ETA</span>
            </div>

            <div className='divide-y divide-slate-200'>
              {tasks.map((task) => (
                <button
                  key={task.id}
                  onClick={() => navigate(`/tasks/${task.id}`)}
                  className={`grid w-full grid-cols-[2.4fr_1fr_1.2fr_.8fr] gap-3 px-6 py-4 text-left transition hover:bg-white ${
                    task.id === 'fft-1024p' ? 'bg-violet-50/70' : 'bg-transparent'
                  }`}
                >
                  <div>
                    <p className='font-semibold text-slate-900'>{task.name}</p>
                  </div>
                  <div className='text-sm text-slate-600'>{task.ownerName}</div>
                  <div className='text-sm text-slate-600'>{task.currentStage}</div>
                  <div className='text-sm text-slate-600'>{task.etaLabel}</div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card className='rounded-3xl border border-slate-200 shadow-none'>
        <CardHeader className='flex flex-row items-start justify-between gap-3'>
          <div>
            <CardTitle className='text-xl'>RTL-to-GDS workflow</CardTitle>
            <CardDescription>
              A simple stage map for the MVP flow, from specification input to signoff packaging.
            </CardDescription>
          </div>
          <Badge variant='secondary' className='rounded-full bg-slate-100 text-slate-500'>
            MVP flow
          </Badge>
        </CardHeader>
        <CardContent>
          <div className='grid gap-4 lg:grid-cols-2'>
            {workflowSteps.map((step) => (
              <Card key={step.title} className='rounded-2xl border-slate-200 shadow-none'>
                <CardHeader className='pb-3'>
                  <div className={`mb-1 inline-flex h-9 w-9 items-center justify-center rounded-full ${
                    step.tone === 'violet'
                      ? 'bg-violet-100 text-violet-600'
                      : step.tone === 'mint'
                        ? 'bg-emerald-100 text-emerald-600'
                        : step.tone === 'sky'
                          ? 'bg-cyan-100 text-cyan-600'
                          : step.tone === 'amber'
                            ? 'bg-amber-100 text-amber-600'
                            : 'bg-rose-100 text-rose-600'
                  }`}>
                    <MaterialIcon name={step.label} className='text-[16px]' />
                  </div>
                  <CardTitle className='text-lg'>{step.title}</CardTitle>
                </CardHeader>
                <CardContent className='pt-0 text-sm leading-6 text-slate-500'>{step.detail}</CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
