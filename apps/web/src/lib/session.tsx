import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authApi, type User } from './api/endpoints'
import { setBearerToken, setUnauthorizedHandler } from './api/client'

interface Session {
  user: User | null
  checking: boolean
  signIn: (email: string, password: string) => Promise<void>
  register: (input: { email: string; password: string; display_name: string; persona?: User['persona'] }) => Promise<void>
  signOut: () => Promise<void>
}

const SessionContext = createContext<Session | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    authApi.me().then(setUser, () => setUser(null)).finally(() => setChecking(false))
  }, [])

  const startSession = useCallback((session: { user: User; token: string }) => {
    setBearerToken(session.token)
    setUser(session.user)
  }, [])

  const value = useMemo<Session>(
    () => ({
      user,
      checking,
      signIn: async (email, password) => startSession(await authApi.login({ email, password })),
      register: async (input) =>
        startSession(await authApi.register(input as Parameters<typeof authApi.register>[0])),
      signOut: async () => {
        await authApi.logout().catch(() => undefined)
        setBearerToken(null)
        setUser(null)
      },
    }),
    [user, checking, startSession],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): Session {
  const session = useContext(SessionContext)
  if (!session) throw new Error('useSession must be used inside SessionProvider')
  return session
}
