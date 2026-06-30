import type { UserProfile } from '@/types/orchestra'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080').replace(/\/$/, '')
const AUTH_STORAGE_KEY = import.meta.env.VITE_AUTH_STORAGE_KEY ?? 'chip-orchestra.auth'

interface StoredAuth {
  token: string
  user: UserProfile | null
}

interface LoginResponse {
  access_token: string
  user: {
    id: string
    username: string
    full_name: string
    roles?: string[]
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { error?: string; message?: string }
    return payload.error ?? payload.message ?? `${response.status} ${response.statusText}`
  } catch {
    return `${response.status} ${response.statusText}`
  }
}

function normalizeUser(user: LoginResponse['user'] | null | undefined): UserProfile | null {
  if (!user) {
    return null
  }

  return {
    id: user.id,
    username: user.username,
    fullName: user.full_name,
    roles: user.roles ?? [],
  }
}

function readStoredAuth(): StoredAuth | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as StoredAuth
  } catch {
    window.localStorage.removeItem(AUTH_STORAGE_KEY)
    return null
  }
}

function writeStoredAuth(auth: StoredAuth | null) {
  if (typeof window === 'undefined') {
    return
  }

  if (!auth) {
    window.localStorage.removeItem(AUTH_STORAGE_KEY)
    return
  }

  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth))
}

export function getApiBaseUrl() {
  return API_BASE_URL
}

export function getStoredToken() {
  return readStoredAuth()?.token ?? null
}

export function getStoredUser() {
  return readStoredAuth()?.user ?? null
}

export function persistAuth(token: string, user: UserProfile | null) {
  writeStoredAuth({ token, user })
}

export function clearStoredAuth() {
  writeStoredAuth(null)
}

export async function login(username: string, password: string): Promise<{ token: string; user: UserProfile | null }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  if (!response.ok) {
    throw new Error(await parseError(response))
  }

  const payload = (await response.json()) as LoginResponse
  const user = normalizeUser(payload.user)
  persistAuth(payload.access_token, user)

  return { token: payload.access_token, user }
}

export async function fetchMe(token = getStoredToken()): Promise<UserProfile> {
  if (!token) {
    throw new Error('Missing authentication token')
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    if (response.status === 401) {
      clearStoredAuth()
    }
    throw new Error(await parseError(response))
  }

  const payload = (await response.json()) as {
    id: string
    username: string
    full_name: string
    roles?: string[]
  }

  const user = normalizeUser(payload)
  if (!user) {
    throw new Error('Unable to read current user profile')
  }

  persistAuth(token, user)
  return user
}

export function getTaskEventsWebSocketUrl(taskId: string, token = getStoredToken()) {
  const wsBase = API_BASE_URL.replace(/^http/i, 'ws')
  const url = new URL(`${wsBase}/ws/tasks/${taskId}/events`)
  if (token) {
    url.searchParams.set('token', token)
  }
  return url.toString()
}
