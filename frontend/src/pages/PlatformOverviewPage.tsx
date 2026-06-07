import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { getWorkflowSteps, listTasks } from '@/api/tasks'
import { PlatformLayout } from '@/components/app/PlatformLayout'
import { PlatformOverviewSection } from '@/components/app/PlatformOverviewSection'
import { ErrorState, LoadingState } from '@/components/app/shared'
import type { TaskFilter, TaskSummary, WorkflowStep } from '@/types/chiporchestra'

const defaultTaskId = 'fft-1024p'

export function PlatformOverviewPage() {
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

  if (loading) {
    return (
      <PlatformLayout activeSection='overview' detailHref={`/tasks/${tasks[0]?.id ?? defaultTaskId}`}>
        <LoadingState label='LoadingChip Orchestra overview…' />
      </PlatformLayout>
    )
  }

  if (error) {
    return (
      <PlatformLayout activeSection='overview' detailHref={`/tasks/${tasks[0]?.id ?? defaultTaskId}`}>
        <ErrorState title='Unable to load overview console' detail={error} />
      </PlatformLayout>
    )
  }

  const selectedTaskId = tasks[0]?.id ?? defaultTaskId

  return (
    <PlatformLayout activeSection='overview' detailHref={`/tasks/${selectedTaskId}`}>
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
