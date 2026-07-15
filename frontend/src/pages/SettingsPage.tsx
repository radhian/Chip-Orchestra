import { LogOut, Moon, Sun } from 'lucide-react'

import { getApiBaseUrl } from '@/api/auth'
import { useAuth } from '@/auth/AuthProvider'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

function useThemeSetting(): [boolean, () => void] {
  const dark = document.documentElement.classList.contains('dark')
  return [
    dark,
    () => {
      const next = !document.documentElement.classList.contains('dark')
      document.documentElement.classList.toggle('dark', next)
      localStorage.setItem('co-theme', next ? 'dark' : 'light')
      // force a re-render via a storage event listener-free hack: navigation state
      window.dispatchEvent(new Event('co-theme-changed'))
    },
  ]
}

export function SettingsPage() {
  const { user, logout } = useAuth()
  const [dark, toggleDark] = useThemeSetting()
  const lastTask = localStorage.getItem('co-last-task') ?? ''

  const rows: { label: string; value: string }[] = [
    { label: 'API host', value: getApiBaseUrl() },
    { label: 'Runtime', value: 'REST + WebSocket' },
    { label: 'Auth', value: 'JWT from localStorage' },
    { label: 'Signed in as', value: `${user?.fullName ?? '—'} (${user?.username ?? '—'})` },
    { label: 'Last opened task', value: lastTask || '—' },
  ]

  return (
    <div className='space-y-6'>
      <div>
        <h3 className='text-2xl font-semibold text-slate-900'>Settings</h3>
        <p className='mt-1 text-sm text-slate-500'>Session context, appearance, and platform principles.</p>
      </div>

      <div className='grid gap-5 xl:grid-cols-2'>
        <Card className='rounded-3xl border-slate-200 shadow-none'>
          <CardHeader>
            <div className='flex items-center justify-between'>
              <div>
                <CardTitle className='text-xl'>Session context</CardTitle>
                <CardDescription>Connected to the live backend.</CardDescription>
              </div>
              <Badge className='bg-emerald-100 text-emerald-700 hover:bg-emerald-100'>Online</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className='overflow-hidden rounded-2xl border border-slate-200'>
              <table className='w-full text-left text-sm'>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.label} className='border-b border-slate-100 last:border-0'>
                      <td className='px-4 py-2.5 font-medium text-slate-700'>{row.label}</td>
                      <td className='min-w-0 break-all px-4 py-2.5 text-slate-600'>{row.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <div className='space-y-5'>
          <Card className='rounded-3xl border-slate-200 shadow-none'>
            <CardHeader>
              <CardTitle className='text-xl'>Appearance</CardTitle>
              <CardDescription>Theme preference is stored in this browser.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant='outline' onClick={toggleDark} className='rounded-2xl border-slate-200'>
                {dark ? <Sun className='mr-2 h-4 w-4' /> : <Moon className='mr-2 h-4 w-4' />}
                Switch to {dark ? 'light' : 'dark'} mode
              </Button>
            </CardContent>
          </Card>

          <Card className='rounded-3xl border-slate-200 shadow-none'>
            <CardHeader>
              <CardTitle className='text-xl'>Account</CardTitle>
              <CardDescription>
                Signed in as {user?.fullName ?? '—'} ({user?.username ?? '—'}).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant='outline' onClick={logout} className='rounded-2xl border-slate-200'>
                <LogOut className='mr-2 h-4 w-4' />
                Sign out
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
