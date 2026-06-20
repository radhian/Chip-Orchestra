import { NavLink, Outlet, useLocation, useParams } from 'react-router-dom'

import {
  Bot,
  ChevronRight,
  Cog,
  Cpu,
  Cuboid,
  FileCode2,
  LayoutGrid,
  LogOut,
  PackageCheck,
  PlusCircle,
  ShieldCheck,
  Sparkles,
  Waypoints,
} from 'lucide-react'

import { useAuth } from '@/auth/AuthProvider'
import { getApiBaseUrl } from '@/api/auth'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const navItems: {
  key: 'overview' | 'create' | 'detail'
  label: string
  icon: typeof LayoutGrid
  sectionIcon: typeof LayoutGrid
  to: string
  isActive: (pathname: string) => boolean
}[] = [
  {
    key: 'overview',
    label: 'Overview Console',
    icon: LayoutGrid,
    sectionIcon: LayoutGrid,
    to: '/overview',
    isActive: (pathname) => pathname === '/overview',
  },
  {
    key: 'create',
    label: 'Create Design Task',
    icon: Sparkles,
    sectionIcon: PlusCircle,
    to: '/tasks/new',
    isActive: (pathname) => pathname === '/tasks/new',
  },
  {
    key: 'detail',
    label: 'Task Detail & Runbook',
    icon: Waypoints,
    sectionIcon: Cog,
    to: '/overview',
    isActive: (pathname) => pathname.startsWith('/tasks/') && pathname !== '/tasks/new',
  },
]

function getDetailTarget(pathname: string) {
  if (!pathname.startsWith('/tasks/') || pathname === '/tasks/new') {
    return '/overview'
  }

  const [, , taskId] = pathname.split('/')
  return taskId ? `/tasks/${taskId}` : '/overview'
}

function RouteTaskHint() {
  const { id } = useParams<{ id: string }>()

  return (
    <div className='mt-4 grid grid-cols-2 gap-3 text-sm'>
      <div>
        <p className='text-xs uppercase tracking-wide text-slate-400'>Current task</p>
        <p className='mt-1 font-medium'>{id ?? 'Select a task from Overview'}</p>
      </div>
      <div>
        <p className='text-xs uppercase tracking-wide text-slate-400'>API host</p>
        <p className='mt-1 font-medium'>{getApiBaseUrl()}</p>
      </div>
      <div>
        <p className='text-xs uppercase tracking-wide text-slate-400'>Runtime</p>
        <p className='mt-1 font-medium'>REST + WebSocket</p>
      </div>
      <div>
        <p className='text-xs uppercase tracking-wide text-slate-400'>Auth</p>
        <p className='mt-1 font-medium'>JWT from localStorage</p>
      </div>
    </div>
  )
}

export function ShellLayout() {
  const { pathname } = useLocation()
  const { user, logout } = useAuth()

  return (
    <div className='min-h-screen bg-slate-100 text-slate-800'>
      <div className='mx-auto flex min-h-screen max-w-screen-2xl gap-3 p-2 sm:gap-4 sm:p-3 lg:p-4'>
        <aside className='hidden w-72 shrink-0 rounded-3xl bg-white p-4 shadow-xl lg:flex lg:flex-col'>
          <div className='rounded-3xl bg-slate-50 p-4'>
            <div className='flex items-start justify-between gap-3'>
              <div>
                <p className='text-xs font-semibold uppercase tracking-widest text-slate-400'>AI-native chip design</p>
                <h1 className='mt-2 text-3xl font-semibold tracking-tight text-blue-600'>Chip Orchestra</h1>
              </div>
              <div className='flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-400 text-white shadow-lg'>
                <Cpu className='h-6 w-6' />
              </div>
            </div>

            <div className='mt-4 rounded-3xl bg-gradient-to-br from-blue-600 via-sky-500 to-cyan-400 p-4 text-white shadow-xl'>
              <p className='text-xs font-medium uppercase tracking-widest text-blue-100'>Live Orchestrator Service</p>
              <h2 className='mt-3 text-2xl font-semibold leading-8'>Task-first workflow for design execution, diagnosis, and signoff.</h2>
              <p className='mt-4 text-sm leading-6 text-blue-50'>
                Live tasks, live stage status, and live event streaming are all surfaced from the Orchestrator Service.
              </p>
            </div>
          </div>

          <div className='mt-4 rounded-3xl bg-slate-50 p-3'>
            {navItems.map((item) => {
              const Icon = item.icon
              const SectionIcon = item.sectionIcon
              const active = item.isActive(pathname)
              const target = item.key === 'detail' ? getDetailTarget(pathname) : item.to

              return (
                <NavLink
                  key={item.key}
                  to={target}
                  className={`mb-2 flex w-full items-center justify-between rounded-2xl px-3 py-3 text-left transition-all ${
                    active
                      ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200'
                      : 'text-slate-500 hover:bg-white/80 hover:text-slate-800'
                  }`}
                >
                  <div className='flex items-center gap-3'>
                    <div
                      className={`flex h-9 w-9 items-center justify-center rounded-xl ${
                        active ? 'bg-blue-50 text-blue-600' : 'bg-slate-200 text-slate-500'
                      }`}
                    >
                      <Icon className='h-4 w-4' />
                    </div>
                    <div>
                      <div className='mb-1 flex items-center text-slate-400'>
                        <SectionIcon className='h-3.5 w-3.5' />
                      </div>
                      <div className='text-sm font-semibold'>{item.label}</div>
                    </div>
                  </div>
                  <ChevronRight className={`h-4 w-4 ${active ? 'text-blue-500' : 'text-slate-300'}`} />
                </NavLink>
              )
            })}
          </div>

          <div className='mt-auto space-y-4'>
            <div className='rounded-3xl border-0 bg-slate-50 p-4 shadow-none'>
              <div className='flex items-center justify-between'>
                <div>
                  <p className='text-sm font-semibold text-slate-500'>Session context</p>
                  <p className='text-xs text-slate-400'>Connected to the live backend</p>
                </div>
                <Badge className='bg-emerald-100 text-emerald-700 hover:bg-emerald-100'>Online</Badge>
              </div>
              <RouteTaskHint />
            </div>

            <div className='rounded-3xl border-0 bg-slate-50 p-4 shadow-none'>
              <div className='flex items-center justify-between gap-3'>
                <div>
                  <h3 className='text-sm font-semibold text-slate-700'>{user?.fullName ?? 'Authenticated user'}</h3>
                  <p className='text-sm text-slate-500'>{user?.username ?? 'Unknown user'}</p>
                </div>
                <Button variant='outline' onClick={logout} className='rounded-2xl border-slate-200'>
                  <LogOut className='mr-2 h-4 w-4' />
                  Sign out
                </Button>
              </div>
            </div>

            <div className='rounded-3xl border-0 bg-slate-50 p-4 shadow-none'>
              <h3 className='mb-3 text-sm font-semibold text-slate-700'>Primary UX principles</h3>
              <div className='space-y-3 text-sm text-slate-600'>
                <div className='flex gap-2'>
                  <Bot className='mt-0.5 h-4 w-4 text-blue-500' />
                  <p>Task-first orchestration, not tool-first navigation.</p>
                </div>
                <div className='flex gap-2'>
                  <ShieldCheck className='mt-0.5 h-4 w-4 text-emerald-500' />
                  <p>Every suggestion stays inspectable, rerunnable, and auditable.</p>
                </div>
                <div className='flex gap-2'>
                  <PackageCheck className='mt-0.5 h-4 w-4 text-violet-500' />
                  <p>Every step emits artifacts, metrics, and clear next actions.</p>
                </div>
              </div>
            </div>
          </div>
        </aside>

        <main className='flex-1 space-y-4'>
          <section className='rounded-3xl bg-white px-5 py-5 shadow-xl sm:px-6'>
            <div className='flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between'>
              <div className='max-w-3xl'>
                <p className='text-sm font-medium text-slate-400'>Live task operations console</p>
                <h2 className='mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl'>Chip Orchestra digital IC platform</h2>
                <p className='mt-3 max-w-3xl text-sm leading-6 text-slate-500 sm:text-base'>
                  Use the Orchestrator Service to create tasks, inspect stages, review generated artifacts, and follow live execution updates.
                </p>
              </div>
              <div className='flex flex-wrap items-center gap-2 xl:justify-end'>
                <Badge className='rounded-full bg-emerald-100 px-3 py-1 text-emerald-700 hover:bg-emerald-100'>
                  <Bot className='mr-1.5 h-3.5 w-3.5' />
                  Agentic pipeline
                </Badge>
                <Badge className='rounded-full bg-indigo-100 px-3 py-1 text-indigo-700 hover:bg-indigo-100'>
                  <Cuboid className='mr-1.5 h-3.5 w-3.5' />
                  Browser-native
                </Badge>
                <Badge className='rounded-full bg-amber-100 px-3 py-1 text-amber-700 hover:bg-amber-100'>
                  <FileCode2 className='mr-1.5 h-3.5 w-3.5' />
                  Live data only
                </Badge>
              </div>
            </div>
          </section>

          <section className='rounded-3xl bg-white p-4 shadow-xl sm:p-5'>
            <Outlet />
          </section>
        </main>
      </div>
    </div>
  )
}
