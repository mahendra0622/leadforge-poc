import { create } from 'zustand'
import api from '../lib/api'

interface User {
  id: string
  email: string
  name: string
  company_name?: string
  product_description?: string
  key_strengths?: string
  differentiators?: string
  tagline?: string
  tone?: string
  gmail_email?: string
  auth_provider?: string
  products?: string[]
  case_studies?: { customer: string; outcome: string }[]
  integrations?: string[]
}

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  loadUser: () => Promise<void>
  setToken: (token: string) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('fp_token'),
  isLoading: false,

  login: async (email, password) => {
    set({ isLoading: true })
    const resp = await api.post('/api/auth/login', { email, password })
    const { access_token, user } = resp.data
    localStorage.setItem('fp_token', access_token)
    set({ token: access_token, user, isLoading: false })
  },

  logout: () => {
    localStorage.removeItem('fp_token')
    set({ token: null, user: null })
  },

  setToken: (token: string) => {
    localStorage.setItem('fp_token', token)
    set({ token })
  },

  loadUser: async () => {
    const token = localStorage.getItem('fp_token')
    if (!token) return
    try {
      const resp = await api.get('/api/auth/me')
      set({ user: resp.data })
    } catch {
      localStorage.removeItem('fp_token')
      set({ token: null, user: null })
    }
  },
}))
