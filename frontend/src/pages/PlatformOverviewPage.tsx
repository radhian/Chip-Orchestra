import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { getWorkflowSteps, listTasks } from '@/api/tasks'
import { PlatformLayout } from '@/components/app/PlatformLayout'
import { PlatformOverviewSection } from '@/components/app/PlatformOverviewSection'
import { ErrorState, LoadingState } from '@/components/app/shared'
import type { TaskFilter, TaskSummary, WorkflowStep } from '@/types/chiporchestra'

export function PlatformOverviewPage() {
  const navigate = useNavigate()
  const [activeFilter, setActiveFilter] = useState<TaskFilter>('all')
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    async function load(initial: boolean) {
      if (initial) {
        setLoading(true)
        setError(null)
      }

      try {
        const [fetchedTasks, fetchedWorkflow] = await Promise.all([
          listTasks(buildTaskQuery(activeFilter)),
          getWorkflowSteps(),
        ])

        if (!mounted) return
        setTasks(fetchedTasks)
        setWorkflowSteps(fetchedWorkflow)
        setError(null)
      } catch (err) {
        if (!mounted) return
        if (initial) setError(err instanceof Error ? err.message : 'Failed to load overview data')
      } finally {
        if (mounted && initial) setLoading(false)
      }
    }

    void load(true)
    const interval = window.setInterval(() => void load(false), 5000)

    return () => {
      mounted = false
      window.clearInterval(interval)
    }
  }, [activeFilter])

  const detailHref = tasks[0]?.id ? `/tasks/${tasks[0].id}` : '/tasks/new'

  if (loading) {
    return (
      <PlatformLayout activeSection='overview' detailHref={detailHref}>
        <LoadingState label='Loading Chip Orchestra overview…' />
      </PlatformLayout>
    )
  }

  if (error) {
    return (
      <PlatformLayout activeSection='overview' detailHref={detailHref}>
        <ErrorState title='Unable to load overview console' detail={error} />
      </PlatformLayout>
    )
  }

  const selectedTaskId = tasks[0]?.id ?? ''

  return (
    <PlatformLayout activeSection='overview' detailHref={detailHref}>
      <PlatformOverviewSection
        activeFilter={activeFilter}
        selectedTaskId={selectedTaskId}
        tasks={tasks}
        workflowSteps={workflowSteps}
        onFilterChange={setActiveFilter}
        onSelectTask={(taskId) => navigate(`/tasks/${taskId}`)}
      />
    </PlatformLayout>
  )
}

function buildTaskQuery(filter: TaskFilter) {
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
