import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { getSignoffStatus, getTask, getTaskArtifacts, getTaskDiagnosis, getTaskEvents, getWorkspaceFile, getWorkspaceFiles } from '@/api/tasks'
import { PlatformLayout } from '@/components/app/PlatformLayout'
import { PlatformTaskSections } from '@/components/app/PlatformTaskSections'
import { ErrorState, LoadingState } from '@/components/app/shared'
import type { ArtifactItem, DiagnosisItem, RunbookEvent, SignoffStatus, TaskDetail, WorkspaceFileSummary } from '@/types/chipflow'

type DetailTab = 'runbook' | 'rtl' | 'signoff'

export function PlatformTaskDetailPage({ tab }: { tab: DetailTab }) {
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

  useEffect(() => {
    if (!taskId) return

    let mounted = true

    async function load() {
      setLoading(true)
      setError(null)

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
          const file = await getWorkspaceFile(taskId, firstPath)
          if (!mounted) return
          setSelectedFileContent(file.content)
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

  async function handleSelectFile(path: string) {
    if (!taskId) return
    setSelectedFile(path)
    const file = await getWorkspaceFile(taskId, path)
    setSelectedFileContent(file.content)
  }

  if (!taskId) {
    return (
      <PlatformLayout activeSection='detail' detailHref='/tasks/fft-1024p'>
        <ErrorState title='Missing task id' detail='No task id was provided in the route.' />
      </PlatformLayout>
    )
  }

  if (loading) {
    return (
      <PlatformLayout activeSection='detail' detailHref={`/tasks/${taskId}`}>
        <LoadingState label='Loading task detail…' />
      </PlatformLayout>
    )
  }

  if (error || !detail) {
    return (
      <PlatformLayout activeSection='detail' detailHref={`/tasks/${taskId}`}>
        <ErrorState title='Unable to load task detail' detail={error ?? 'Task not found'} />
      </PlatformLayout>
    )
  }

  return (
    <PlatformLayout activeSection='detail' detailHref={`/tasks/${taskId}`}>
      <PlatformTaskSections
        task={detail}
        artifacts={artifacts}
        diagnoses={diagnoses}
        events={events}
        files={files}
        selectedFile={selectedFile}
        selectedFileContent={selectedFileContent}
        signoff={signoff}
        activeTab={tab}
        onSelectFile={(path) => void handleSelectFile(path)}
      />
    </PlatformLayout>
  )
}
