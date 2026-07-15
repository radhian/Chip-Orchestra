import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, ChevronLeft, ChevronRight, Filter, LayoutGrid, Search, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { deleteTask, listTasks } from '@/api/tasks'
import { useAuth } from '@/auth/AuthProvider'
import { EmptyState, ErrorState, LoadingState } from '@/components/app/shared'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import type { ListTasksParams, TaskFilter, TaskSummary } from '@/types/orchestra'

const filterItems: { key: TaskFilter; label: string }[] = [
  { key: 'all', label: 'All tasks' },
  { key: 'mine', label: 'My tasks' },
  { key: 'review', label: 'Needs review' },
  { key: 'failed', label: 'Failed' },
]

const stageToneClass = {
  running: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  review: 'bg-amber-100 text-amber-700 border-amber-200',
  passed: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  failed: 'bg-rose-100 text-rose-700 border-rose-200',
} as const

const PAGE_SIZE = 8

function buildTaskQuery(filter: TaskFilter, userId?: string): ListTasksParams {
  switch (filter) {
    case 'mine':
      return userId ? { owner: userId } : {}
    case 'review':
      return { status: 'BLOCKED', needs_review: true }
    case 'failed':
      return { status: 'FAILED', failed: true }
    default:
      return {}
  }
}

export function OverviewPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [activeFilter, setActiveFilter] = useState<TaskFilter>('all')
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)

  async function handleDelete(task: TaskSummary) {
    if (!window.confirm(`Delete task "${task.name}"? This cannot be undone.`)) {
      return
    }
    setDeletingId(task.id)
    try {
      await deleteTask(task.id)
      setTasks((current) => current.filter((item) => item.id !== task.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete task')
    } finally {
      setDeletingId(null)
    }
  }

  useEffect(() => {
    let mounted = true

    async function load() {
      setLoading(true)
      setError(null)

      try {
        const response = await listTasks(buildTaskQuery(activeFilter, user?.id))
        if (!mounted) {
          return
        }
        setTasks(response.items)
      } catch (err) {
        if (!mounted) {
          return
        }
        setError(err instanceof Error ? err.message : 'Failed to load overview data')
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    void load()

    return () => {
      mounted = false
    }
  }, [activeFilter, user?.id])

  useEffect(() => {
    setPage(1)
  }, [activeFilter, search])

  const filteredTasks = useMemo(() => {
    const query = search.trim().toLowerCase()

    return tasks.filter((task) => {
      const matchesFilter =
        activeFilter === 'mine'
          ? task.ownerId === user?.id
          : activeFilter === 'review'
            ? task.tone === 'review'
            : activeFilter === 'failed'
              ? task.tone === 'failed'
              : true

      if (!matchesFilter) {
        return false
      }

      if (!query) {
        return true
      }

      const haystack = [task.name, task.description, task.ownerName, task.currentStage, task.repoName].join(' ').toLowerCase()
      return haystack.includes(query)
    })
  }, [activeFilter, search, tasks, user?.id])

  const totalPages = Math.max(1, Math.ceil(filteredTasks.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const pagedTasks = filteredTasks.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  const metrics = useMemo(() => {
    const total = tasks.length
    const running = tasks.filter((task) => task.tone === 'running').length
    const blocked = tasks.filter((task) => task.tone === 'review').length
    const failed = tasks.filter((task) => task.tone === 'failed').length

    return [
      { label: 'Total tasks', value: String(total), tone: 'text-slate-900' },
      { label: 'Running', value: String(running), tone: 'text-indigo-600' },
      { label: 'Needs review', value: String(blocked), tone: 'text-amber-600' },
      { label: 'Failed', value: String(failed), tone: 'text-rose-600' },
    ]
  }, [tasks])

  if (loading) return <LoadingState label='Loading overview console…' />
  if (error) {
    return <ErrorState title='Unable to load Overview Console' detail={error} onRetry={() => window.location.reload()} />
  }

  return (
    <div className='space-y-5'>
      <div className='flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between'>
        <div>
          <h3 className='text-2xl font-semibold text-slate-900'>Task dashboard</h3>
          <p className='mt-1 text-sm text-slate-500'>Live view of Orchestrator Service tasks with filtering, client-side pagination, and direct navigation into task detail.</p>
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
                  active ? 'bg-blue-600 text-white hover:bg-blue-600 hover:text-white' : 'bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                <Filter className='mr-2 h-4 w-4' />
                {filter.label}
              </Button>
            )
          })}
        </div>
      </div>

      <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-4'>
        {metrics.map((metric) => (
          <Card key={metric.label} className='rounded-3xl border-slate-200 shadow-none'>
            <CardContent className='p-5'>
              <p className='text-xs uppercase tracking-widest text-slate-400'>{metric.label}</p>
              <p className={`mt-3 text-3xl font-semibold ${metric.tone}`}>{metric.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className='rounded-3xl border border-slate-200 shadow-none'>
        <CardHeader className='gap-4 lg:flex-row lg:items-center lg:justify-between'>
          <div>
            <CardTitle className='text-xl'>Overview Console</CardTitle>
            <CardDescription>Task list is loaded from GET /api/v1/tasks and filtered locally for quick search.</CardDescription>
          </div>
          <div className='relative w-full lg:max-w-sm'>
            <Search className='pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400' />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder='Search task, repo, owner, or stage'
              className='h-11 rounded-2xl border-slate-200 pl-9'
            />
          </div>
        </CardHeader>
        <CardContent className='space-y-4'>
          {pagedTasks.length === 0 ? (
            <EmptyState
              title='No tasks match the current view'
              detail={search ? 'Try a different search term or clear filters.' : 'Create a task to start the live workflow.'}
            />
          ) : (
            <>
              <div className='overflow-hidden rounded-3xl border border-slate-200'>
                <div className='grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)_2.5rem] gap-3 border-b border-slate-200 bg-slate-50 px-6 py-4 text-xs font-semibold uppercase tracking-widest text-slate-400'>
                  <span>Task</span>
                  <span>Owner</span>
                  <span>Current stage</span>
                  <span>Repository</span>
                  <span>Status</span>
                  <span className='sr-only'>Actions</span>
                </div>

                <div className='divide-y divide-slate-200'>
                  {pagedTasks.map((task) => (
                    <div
                      key={task.id}
                      role='button'
                      tabIndex={0}
                      onClick={() => navigate(`/tasks/${task.id}`)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          navigate(`/tasks/${task.id}`)
                        }
                      }}
                      className='grid w-full cursor-pointer grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)_2.5rem] gap-3 px-6 py-5 text-left transition hover:bg-slate-50'
                    >
                      <div className='min-w-0'>
                        <p className='break-words font-semibold text-slate-900'>{task.name}</p>
                        <p className='mt-1 break-words text-sm text-slate-500'>{task.description}</p>
                      </div>
                      <div className='min-w-0 break-words text-sm text-slate-600'>{task.ownerName}</div>
                      <div className='min-w-0 break-words text-sm text-slate-600'>{task.currentStage}</div>
                      <div className='min-w-0 break-all text-sm text-slate-600'>{task.repoName}</div>
                      <div className='min-w-0'>
                        <Badge className={`rounded-full border px-3 py-1 font-medium ${stageToneClass[task.tone]}`}>{task.statusLabel}</Badge>
                      </div>
                      <div className='flex items-start justify-end'>
                        <Button
                          variant='ghost'
                          size='icon'
                          aria-label={`Delete ${task.name}`}
                          disabled={deletingId === task.id}
                          className='h-9 w-9 rounded-xl text-slate-400 hover:bg-rose-50 hover:text-rose-600'
                          onClick={(event) => {
                            event.stopPropagation()
                            void handleDelete(task)
                          }}
                        >
                          <Trash2 className='h-4 w-4' />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className='flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between'>
                <div className='flex items-center gap-2 text-sm text-slate-500'>
                  <LayoutGrid className='h-4 w-4' />
                  Showing {(currentPage - 1) * PAGE_SIZE + 1}-{Math.min(currentPage * PAGE_SIZE, filteredTasks.length)} of {filteredTasks.length} live tasks
                </div>
                <div className='flex items-center gap-2'>
                  <Button variant='outline' className='rounded-2xl border-slate-200' disabled={currentPage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
                    <ChevronLeft className='mr-2 h-4 w-4' />
                    Previous
                  </Button>
                  <span className='text-sm text-slate-500'>Page {currentPage} / {totalPages}</span>
                  <Button
                    variant='outline'
                    className='rounded-2xl border-slate-200'
                    disabled={currentPage === totalPages}
                    onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                  >
                    Next
                    <ChevronRight className='ml-2 h-4 w-4' />
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card className='rounded-3xl border border-slate-200 shadow-none'>
        <CardHeader>
          <CardTitle className='text-xl'>Operational notes</CardTitle>
          <CardDescription>These cues are derived from live task status returned by the Orchestrator Service.</CardDescription>
        </CardHeader>
        <CardContent className='grid gap-4 xl:grid-cols-3'>
          <div className='rounded-2xl border border-slate-200 p-4'>
            <div className='flex items-center gap-2 text-indigo-600'>
              <AlertCircle className='h-4 w-4' />
              <p className='font-semibold'>Running tasks</p>
            </div>
            <p className='mt-2 text-sm leading-6 text-slate-500'>Tasks with active execution should stream fresh events in the detail view as the backend publishes updates.</p>
          </div>
          <div className='rounded-2xl border border-slate-200 p-4'>
            <div className='flex items-center gap-2 text-amber-600'>
              <AlertCircle className='h-4 w-4' />
              <p className='font-semibold'>Review blockers</p>
            </div>
            <p className='mt-2 text-sm leading-6 text-slate-500'>Blocked tasks can be reopened from the task detail screen where stage approvals and retries are available.</p>
          </div>
          <div className='rounded-2xl border border-slate-200 p-4'>
            <div className='flex items-center gap-2 text-rose-600'>
              <AlertCircle className='h-4 w-4' />
              <p className='font-semibold'>Failed stages</p>
            </div>
            <p className='mt-2 text-sm leading-6 text-slate-500'>Use stage retry actions in the runbook timeline to resubmit failed work without leaving the task page.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
