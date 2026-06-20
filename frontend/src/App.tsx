import { Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from '@/auth/AuthProvider'
import { LoadingState } from '@/components/app/shared'
import { ShellLayout } from '@/components/app/ShellLayout'
import { CreateTaskPage } from '@/pages/CreateTaskPage'
import { LoginPage } from '@/pages/LoginPage'
import { OverviewPage } from '@/pages/OverviewPage'
import { TaskDetailPage } from '@/pages/TaskDetailPage'

import './App.css'

function App() {
  const { status } = useAuth()

  if (status === 'checking') {
    return (
      <div className='min-h-screen bg-slate-100 p-4'>
        <LoadingState label='Checking your Orchestrator Service session…' />
      </div>
    )
  }

  if (status === 'unauthenticated') {
    return <LoginPage />
  }

  return (
    <Routes>
      <Route path='/' element={<Navigate to='/overview' replace />} />
      <Route element={<ShellLayout />}>
        <Route path='/overview' element={<OverviewPage />} />
        <Route path='/tasks/new' element={<CreateTaskPage />} />
        <Route path='/tasks/:id' element={<TaskDetailPage tab='runbook' />} />
        <Route path='/tasks/:id/rtl' element={<TaskDetailPage tab='rtl' />} />
        <Route path='/tasks/:id/signoff' element={<TaskDetailPage tab='signoff' />} />
      </Route>
      <Route path='*' element={<Navigate to='/overview' replace />} />
    </Routes>
  )
}

export default App
