import axios from 'axios'
import React, { createContext, useContext, useEffect, useRef, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]   = useState(null)   // { username, role }
  const [token, setToken] = useState(null)   // in-memory only — never written to storage
  const tokenRef = useRef(null)              // always holds the latest token synchronously

  // ── Axios request interceptor: attach Bearer token ──────────────────────
  // Registered once — reads tokenRef so it never has a stale closure.
  // If this used [token] as a dep, the new interceptor would register only after
  // AuthenticatedApp's child effects have already fired, causing a 401 race.
  useEffect(() => {
    const id = axios.interceptors.request.use((config) => {
      if (tokenRef.current) {
        config.headers = config.headers ?? {}
        config.headers.Authorization = `Bearer ${tokenRef.current}`
      }
      return config
    })
    return () => axios.interceptors.request.eject(id)
  }, [])

  // ── Axios response interceptor: auto-logout on 401 ──────────────────────
  useEffect(() => {
    const id = axios.interceptors.response.use(
      (res) => res,
      (err) => {
        if (err.response?.status === 401) {
          tokenRef.current = null
          setToken(null)
          setUser(null)
        }
        return Promise.reject(err)
      }
    )
    return () => axios.interceptors.response.eject(id)
  }, [])

  // ── Auth actions ─────────────────────────────────────────────────────────
  const login = async (username, password) => {
    const res = await axios.post('/api/auth/login', { username, password })
    // Update ref first (synchronous) so the request interceptor has the token
    // immediately — before React re-renders and child effects fire their fetches.
    tokenRef.current = res.data.access_token
    setToken(res.data.access_token)
    setUser({ username: res.data.username, role: res.data.role })
    return res.data
  }

  const logout = async () => {
    if (tokenRef.current) {
      try {
        await axios.post('/api/auth/logout', {})
      } catch {
        // best-effort — clear state regardless
      }
    }
    tokenRef.current = null
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{ user, token, login, logout, isAuthenticated: !!token }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
