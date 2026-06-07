import { Navigate, Route, Routes } from 'react-router-dom'

import { PlatformCreateTaskPage } from '@/pages/PlatformCreateTaskPage'
import { PlatformOverviewPage } from '@/pages/PlatformOverviewPage'
import { PlatformTaskDetailPage } from '@/pages/PlatformTaskDetailPage'

import './App.css'

function App() {
  return (
    <Routes>
      <Route path='/' element={<Navigate to='/overview' replace />} />
      <Route path='/overview' element={<PlatformOverviewPage />} />
      <Route path='/tasks/new' element={<PlatformCreateTaskPage />} />
      <Route path='/tasks/:id' element={<PlatformTaskDetailPage tab='runbook' />} />
      <Route path='/tasks/:id/rtl' element={<PlatformTaskDetailPage tab='rtl' />} />
      <Route path='/tasks/:id/signoff' element={<PlatformTaskDetailPage tab='signoff' />} />
      <Route path='*' element={<Navigate to='/overview' replace />} />
    </Routes>
  )
}

export default App
