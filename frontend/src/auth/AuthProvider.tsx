import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { SKIP_LOGIN, bootstrapAuth, clearStoredAuth, fetchMe, getStoredToken, getStoredUser, login as loginRequest, persistAuth } from '@/api/auth'
import type { UserProfile } from '@/types/orchestra'

type AuthStatus = 'checking' | 'authenticated' | 'unauthenticated'

interface AuthContextValue {
  status: AuthStatus
  token: string | null
  user: UserProfile | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('checking')
  const [token, setToken] = useState<string | null>(getStoredToken())
  const [user, setUser] = useState<UserProfile | null>(getStoredUser())

  useEffect(() => {
    const storedToken = getStoredToken()
    if (!storedToken && !SKIP_LOGIN) {
      setStatus('unauthenticated')
      setToken(null)
      setUser(null)
      return
    }

    let cancelled = false

    async function bootstrap() {
      try {
        const auth = storedToken
          ? { token: storedToken, user: await fetchMe(storedToken) }
          : await bootstrapAuth()
        if (cancelled) {
          return
        }
        setToken(auth.token)
        setUser(auth.user)
        setStatus('authenticated')
      } catch {
        if (cancelled) {
          return
        }
        clearStoredAuth()
        setToken(null)
        setUser(null)
        setStatus('unauthenticated')
      }
    }

    void bootstrap()

    return () => {
      cancelled = true
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      token,
      user,
      async login(username: string, password: string) {
        const response = await loginRequest(username, password)
        const nextUser = response.user ?? (await fetchMe(response.token))
        persistAuth(response.token, nextUser)
        setToken(response.token)
        setUser(nextUser)
        setStatus('authenticated')
      },
      logout() {
        clearStoredAuth()
        setToken(null)
        setUser(null)
        setStatus('unauthenticated')
      },
      async refreshUser() {
        const currentToken = getStoredToken()
        if (!currentToken) {
          clearStoredAuth()
          setToken(null)
          setUser(null)
          setStatus('unauthenticated')
          return
        }

        const profile = await fetchMe(currentToken)
        setToken(currentToken)
        setUser(profile)
        setStatus('authenticated')
      },
    }),
    [status, token, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
