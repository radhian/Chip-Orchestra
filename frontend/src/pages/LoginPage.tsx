import { useState, type FormEvent } from 'react'
import { Cpu, KeyRound, LogIn, User } from 'lucide-react'

import { useAuth } from '@/auth/AuthProvider'
import { ErrorState } from '@/components/app/shared'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

export function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      await login(username.trim(), password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className='flex min-h-screen items-center justify-center bg-slate-100 px-4 py-8'>
      <div className='w-full max-w-md space-y-4'>
        <div className='text-center'>
          <div className='mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-br from-blue-500 to-cyan-400 text-white shadow-lg'>
            <Cpu className='h-7 w-7' />
          </div>
          <h1 className='mt-4 text-3xl font-semibold text-slate-900'>Chip Orchestra</h1>
          <p className='mt-2 text-sm leading-6 text-slate-500'>
            Sign in with your Orchestrator Service account to load live tasks, task details, and WebSocket status updates.
          </p>
        </div>

        {error ? <ErrorState title='Login failed' detail={error} /> : null}

        <Card className='rounded-3xl border-slate-200 shadow-xl'>
          <CardHeader>
            <CardTitle>Orchestrator Service login</CardTitle>
            <CardDescription>JWT is stored in localStorage and attached to every REST and WebSocket request.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className='space-y-4' onSubmit={handleSubmit}>
              <label className='block space-y-2'>
                <span className='text-sm font-medium text-slate-700'>Username</span>
                <div className='relative'>
                  <User className='pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400' />
                  <Input
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    placeholder='radhian.armansyah'
                    autoComplete='username'
                    className='h-11 rounded-2xl border-slate-200 pl-9'
                    required
                  />
                </div>
              </label>

              <label className='block space-y-2'>
                <span className='text-sm font-medium text-slate-700'>Password</span>
                <div className='relative'>
                  <KeyRound className='pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400' />
                  <Input
                    type='password'
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder='Enter your password'
                    autoComplete='current-password'
                    className='h-11 rounded-2xl border-slate-200 pl-9'
                    required
                  />
                </div>
              </label>

              <Button type='submit' disabled={submitting} className='h-11 w-full rounded-2xl bg-blue-600 hover:bg-blue-700'>
                <LogIn className='mr-2 h-4 w-4' />
                {submitting ? 'Signing in…' : 'Sign in'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
