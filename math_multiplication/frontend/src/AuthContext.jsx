import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { supabase } from './supabaseClient'

const API_URL = import.meta.env.VITE_API_URL || ''

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [authLoading, setAuthLoading] = useState(true)
  const [session, setSession] = useState(null)
  const [profileLoading, setProfileLoading] = useState(false)
  const [profileError, setProfileError] = useState(null)
  const [profile, setProfile] = useState(null) // { display_name }

  const isAuthConfigured = Boolean(supabase)

  const accessToken = session?.access_token || null
  const user = session?.user || null

  useEffect(() => {
    let isMounted = true

    async function init() {
      if (!supabase) {
        if (isMounted) setAuthLoading(false)
        return
      }

      const { data, error } = await supabase.auth.getSession()
      if (!isMounted) return
      if (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to get session:', error)
      }
      setSession(data?.session ?? null)
      setAuthLoading(false)
    }

    init()

    if (!supabase) return () => {}

    const { data: sub } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession ?? null)
    })

    return () => {
      isMounted = false
      sub?.subscription?.unsubscribe()
    }
  }, [])

  const refreshProfile = async () => {
    if (!accessToken) {
      setProfile(null)
      setProfileError(null)
      return null
    }

    try {
      setProfileLoading(true)
      setProfileError(null)
      const res = await fetch(`${API_URL}/api/profile`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.error || `Failed to load profile (${res.status})`)
      }

      const data = await res.json()
      setProfile(data?.profile ?? null)
      return data?.profile ?? null
    } catch (e) {
      setProfile(null)
      setProfileError(e?.message || String(e))
      return null
    } finally {
      setProfileLoading(false)
    }
  }

  useEffect(() => {
    // Keep profile in sync with session.
    refreshProfile()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken])

  const signInWithGoogle = async () => {
    if (!supabase) throw new Error('Supabase is not configured')
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        // Works for both Netlify and local.
        redirectTo: window.location.origin,
      },
    })
    if (error) throw error
  }

  const signOut = async () => {
    if (!supabase) return
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }

  const updateDisplayName = async (displayName) => {
    if (!accessToken) throw new Error('Not authenticated')
    const res = await fetch(`${API_URL}/api/profile`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ display_name: displayName }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(data?.error || `Failed to update profile (${res.status})`)
    }
    setProfile(data?.profile ?? null)
    return data?.profile ?? null
  }

  const value = useMemo(
    () => ({
      isAuthConfigured,
      authLoading,
      session,
      user,
      accessToken,
      profileLoading,
      profileError,
      profile,
      signInWithGoogle,
      signOut,
      refreshProfile,
      updateDisplayName,
    }),
    [isAuthConfigured, authLoading, session, user, accessToken, profileLoading, profileError, profile]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

