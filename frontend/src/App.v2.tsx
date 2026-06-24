import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './lib/api'
import { useAuthStore } from './store/authStore'

// ─── Status config ─────────────────────────────────────────────
// Extended pipeline statuses — replaces old new/contacted/replied/qualified
const STATUSES: Record<string, { label: string; color: string; bg: string; border: string }> = {
  pre_sales:       { label: 'Pre-Sales',       color: '#64748B', bg: '#F1F5F9', border: '#CBD5E1' },
  new:             { label: 'New Lead',         color: '#1D4ED8', bg: '#EFF6FF', border: '#BFDBFE' },
  planned_q1:      { label: 'Planned Q1',       color: '#7C3AED', bg: '#F5F3FF', border: '#DDD6FE' },
  planned_q2:      { label: 'Planned Q2',       color: '#7C3AED', bg: '#F5F3FF', border: '#DDD6FE' },
  planned_q3:      { label: 'Planned Q3',       color: '#7C3AED', bg: '#F5F3FF', border: '#DDD6FE' },
  planned_q4:      { label: 'Planned Q4',       color: '#7C3AED', bg: '#F5F3FF', border: '#DDD6FE' },
  contacted:       { label: 'Contacted',        color: '#D97706', bg: '#FFFBEB', border: '#FDE68A' },
  demo_scheduled:  { label: 'Demo Scheduled',   color: '#0891B2', bg: '#ECFEFF', border: '#A5F3FC' },
  in_process:      { label: 'In Process',       color: '#EA580C', bg: '#FFF7ED', border: '#FED7AA' },
  proposal_sent:   { label: 'Proposal Sent',    color: '#0D9488', bg: '#F0FDFA', border: '#99F6E4' },
  negotiating:     { label: 'Negotiating',      color: '#B45309', bg: '#FFFBEB', border: '#FDE68A' },
  replied:         { label: 'Replied',          color: '#059669', bg: '#ECFDF5', border: '#A7F3D0' },
  qualified:       { label: 'Qualified',        color: '#1D4ED8', bg: '#EFF6FF', border: '#93C5FD' },
  completed:       { label: 'Completed',        color: '#166534', bg: '#F0FDF4', border: '#86EFAC' },
  on_hold:         { label: 'On Hold',          color: '#9CA3AF', bg: '#F9FAFB', border: '#E5E7EB' },
  future_action:   { label: 'Future Action',    color: '#6B7280', bg: '#F3F4F6', border: '#D1D5DB' },
}

// ─── Shared UI ─────────────────────────────────────────────────
const Badge = ({ score }: { score: number }) => {
  const cls = score >= 80
    ? 'bg-blue-50 text-blue-700 border-blue-200'
    : score >= 60 ? 'bg-amber-50 text-amber-700 border-amber-200'
    : 'bg-red-50 text-red-600 border-red-200'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border font-semibold ${cls}`}>
      {score} {score >= 80 ? 'HIGH' : score >= 60 ? 'MED' : 'LOW'}
    </span>
  )
}

const StatusPill = ({ status }: { status: string }) => {
  const cfg = STATUSES[status] || STATUSES['new']
  return (
    <span className="inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold border"
      style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}>
      {cfg.label}
    </span>
  )
}

const StatusSelect = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
  <select
    value={value}
    onChange={e => onChange(e.target.value)}
    className="bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
  >
    {Object.entries(STATUSES).map(([k, v]) => (
      <option key={k} value={k}>{v.label}</option>
    ))}
  </select>
)

const Spinner = () => (
  <div className="flex items-center gap-2 text-slate-400 text-sm">
    <div className="w-4 h-4 border-2 border-slate-200 border-t-blue-600 rounded-full animate-spin" />
    Loading...
  </div>
)

const StatCard = ({ label, value, color = 'text-slate-800' }: { label: string; value: string | number; color?: string }) => (
  <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
    <div className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">{label}</div>
    <div className={`text-3xl font-bold tracking-tight ${color}`}>{value}</div>
  </div>
)

// ─── Login ──────────────────────────────────────────────────────
function LoginPage() {
  const [email, setEmail] = useState('demo@fintellipro.com')
  const [password, setPassword] = useState('demo1234')
  const [error, setError] = useState('')
  const { login, token } = useAuthStore()
  if (token) return <Navigate to="/dashboard" replace />

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError('')
    try { await login(email, password) } catch { setError('Invalid credentials') }
  }

  const loginWithGoogle = () => {
    window.location.href = `${import.meta.env.VITE_API_URL || ''}/api/auth/gmail/login`
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-slate-50 p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600 mb-4 shadow-lg">
            <span className="text-white font-black text-xl">LF</span>
          </div>
          <h1 className="text-3xl font-bold text-slate-900">LeadForge</h1>
          <p className="text-slate-500 text-sm mt-1.5">Credit Union Intelligence Platform</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl p-7 shadow-md">

          <button
            onClick={loginWithGoogle}
            className="w-full flex items-center justify-center gap-3 border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold py-2.5 rounded-lg transition-colors text-sm mb-4"
          >
            <svg width="18" height="18" viewBox="0 0 18 18">
              <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84c-.21 1.13-.85 2.08-1.81 2.72v2.26h2.92c1.71-1.57 2.69-3.88 2.69-6.62z"/>
              <path fill="#34A853" d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.71H.96v2.33C2.44 15.98 5.48 18 9 18z"/>
              <path fill="#FBBC05" d="M3.97 10.71c-.18-.54-.28-1.11-.28-1.71s.1-1.17.28-1.71V4.96H.96C.35 6.18 0 7.55 0 9s.35 2.82.96 4.04l3.01-2.33z"/>
              <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59C13.46.89 11.43 0 9 0 5.48 0 2.44 2.02.96 4.96l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"/>
            </svg>
            Continue with Google
          </button>

          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 h-px bg-slate-200" />
            <span className="text-xs text-slate-400">or sign in with email</span>
            <div className="flex-1 h-px bg-slate-200" />
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Email</label>
              <input className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                value={email} onChange={e => setEmail(e.target.value)} type="email" required />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Password</label>
              <input className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                value={password} onChange={e => setPassword(e.target.value)} type="password" required />
            </div>
            {error && <p className="text-red-500 text-xs bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>}
            <button className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg transition-colors text-sm shadow-sm mt-2">
              Sign In →
            </button>
          </form>
          <p className="text-center text-slate-400 text-xs mt-4">Demo: demo@fintellipro.com / demo1234</p>
        </div>
      </div>
    </div>
  )
}

function GoogleAuthCallback() {
  const { setToken, loadUser } = useAuthStore()
  const navigate = useNavigate()
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    if (token) {
      setToken(token)
      loadUser().then(() => navigate('/dashboard'))
    } else {
      navigate('/login')
    }
  }, [])
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-slate-400 text-sm">Signing you in...</div>
    </div>
  )
}

// ─── Sidebar ────────────────────────────────────────────────────
const NAV = [
  { to: '/dashboard', icon: '▦', label: 'Dashboard' },
  { to: '/leads',     icon: '◉', label: 'Leads' },
  { to: '/my-lists',  icon: '☰', label: 'My Lists' },
  { to: '/ai-engine', icon: '✦', label: 'AI Engine' },
  { to: '/campaigns', icon: '✉', label: 'Campaigns' },
  { to: '/pipeline',  icon: '⊞', label: 'Pipeline' },
  { to: '/settings',  icon: '⚙', label: 'Settings' },
]

function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuthStore()
  const location = useLocation()
  return (
    <div className="flex h-screen bg-slate-50">
      <aside className="w-60 bg-white border-r border-slate-200 flex flex-col flex-shrink-0 shadow-sm">
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shadow-sm flex-shrink-0">
              <span className="text-white font-black text-sm">LF</span>
            </div>
            <div>
              <div className="text-sm font-bold text-slate-900">LeadForge</div>
              <div className="text-xs text-slate-400">v2.0 · NCUA Intelligence</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV.map(item => (
            <Link key={item.to} to={item.to}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                location.pathname === item.to
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
              }`}>
              <span className="text-base w-4 text-center">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="px-3 py-3 border-t border-slate-100">
          <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-slate-50 transition-colors">
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
              {user?.name?.charAt(0) || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-slate-800 truncate">{user?.name || 'User'}</div>
              <div className="text-xs text-slate-400 truncate">{user?.email}</div>
            </div>
            <button onClick={logout} className="text-slate-300 hover:text-slate-600 text-sm transition-colors">→</button>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  )
}

const PageHeader = ({ title, sub, action }: { title: string; sub: string; action?: React.ReactNode }) => (
  <div className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-slate-200 px-8 py-4 flex items-center justify-between">
    <div>
      <h1 className="text-lg font-bold text-slate-900">{title}</h1>
      <p className="text-xs text-slate-400 mt-0.5">{sub}</p>
    </div>
    {action}
  </div>
)

// ─── MY LISTS PAGE ──────────────────────────────────────────────
// Lists are private per user — stored with user_id so other users can't see them
function MyLists() {
  const { user } = useAuthStore()
  const qc = useQueryClient()

  // Fetch user's private lists
  const { data: lists } = useQuery({
    queryKey: ['my-lists', user?.id],
    queryFn: () => api.get('/api/lists/').then(r => r.data),
  })

  // Fetch all companies for the "add to list" dropdown
  const { data: companies } = useQuery({
    queryKey: ['companies-all'],
    queryFn: () => api.get('/api/companies/?per_page=200').then(r => r.data),
  })

  const [showNewList, setShowNewList] = useState(false)
  const [newListName, setNewListName] = useState('')
  const [newListColor, setNewListColor] = useState('#1D4ED8')
  const [selectedList, setSelectedList] = useState<any>(null)
  const [addCUId, setAddCUId] = useState('')
  const [addCUTag, setAddCUTag] = useState('')

  const createList = useMutation({
    mutationFn: () => api.post('/api/lists/', {
      name: newListName,
      color: newListColor,
      is_private: true  // always private — only visible to creator
    }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['my-lists'] })
      setShowNewList(false)
      setNewListName('')
    }
  })

  const addToList = useMutation({
    mutationFn: ({ listId, companyId, tag }: any) =>
      api.post(`/api/lists/${listId}/companies`, {
        company_id: companyId,
        tag: tag || null
      }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['my-lists'] })
      setAddCUId('')
      setAddCUTag('')
    }
  })

  const removeFromList = useMutation({
    mutationFn: ({ listId, companyId }: any) =>
      api.delete(`/api/lists/${listId}/companies/${companyId}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['my-lists'] })
  })

  const updateStatus = useMutation({
    mutationFn: ({ companyId, status }: any) =>
      api.patch(`/api/companies/${companyId}`, { outreach_status: status }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['my-lists'] })
  })

  const colors = ['#1D4ED8', '#059669', '#D97706', '#DC2626', '#7C3AED', '#0891B2']

  return (
    <div>
      <PageHeader
        title="My Lists"
        sub="Private lists — only visible to you · Other team members cannot see or edit these"
        action={
          <button onClick={() => setShowNewList(true)}
            className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-lg transition-colors shadow-sm">
            + New List
          </button>
        }
      />

      <div className="p-8">
        {/* New list form */}
        {showNewList && (
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm mb-6">
            <h3 className="text-sm font-bold text-slate-800 mb-4">Create a new private list</h3>
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">List Name</label>
                <input
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. My Q2 targets, California pipeline, Follow-up needed..."
                  value={newListName}
                  onChange={e => setNewListName(e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Colour</label>
                <div className="flex gap-1.5">
                  {colors.map(c => (
                    <button key={c}
                      onClick={() => setNewListColor(c)}
                      className="w-6 h-6 rounded-full border-2 transition-all"
                      style={{ background: c, borderColor: newListColor === c ? '#0F172A' : c }}
                    />
                  ))}
                </div>
              </div>
              <button
                onClick={() => createList.mutate()}
                disabled={!newListName.trim()}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
              >
                Create
              </button>
              <button onClick={() => setShowNewList(false)} className="text-slate-400 hover:text-slate-600 text-sm px-3 py-2">
                Cancel
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-2 flex items-center gap-1">
              <span>🔒</span> This list is private — only you can see and manage it
            </p>
          </div>
        )}

        {/* Lists grid */}
        {!lists?.length ? (
          <div className="text-center py-20 text-slate-300">
            <div className="text-4xl mb-3">☰</div>
            <div className="text-sm font-semibold text-slate-400">No lists yet</div>
            <div className="text-xs mt-1">Create your first private CU list above</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {lists.map((list: any) => (
              <div key={list.id} className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                {/* List header */}
                <div className="px-6 py-4 flex items-center gap-3 border-b border-slate-100"
                  style={{ borderLeftWidth: 4, borderLeftColor: list.color, borderLeftStyle: 'solid' }}>
                  <div>
                    <div className="text-sm font-bold text-slate-800">{list.name}</div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {list.companies?.length || 0} credit unions · Private to you
                    </div>
                  </div>
                  <div className="ml-auto flex items-center gap-2">
                    <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full border border-slate-200 flex items-center gap-1">
                      🔒 Private
                    </span>
                    <button
                      onClick={() => setSelectedList(selectedList?.id === list.id ? null : list)}
                      className="text-xs text-blue-600 hover:text-blue-700 font-medium border border-blue-200 px-3 py-1 rounded-lg bg-blue-50"
                    >
                      {selectedList?.id === list.id ? 'Close' : '+ Add CU'}
                    </button>
                  </div>
                </div>

                {/* Add CU form */}
                {selectedList?.id === list.id && (
                  <div className="px-6 py-4 bg-slate-50 border-b border-slate-100 flex gap-3 items-end">
                    <div className="flex-1">
                      <label className="text-xs font-semibold text-slate-500 block mb-1">Select Credit Union</label>
                      <select
                        value={addCUId}
                        onChange={e => setAddCUId(e.target.value)}
                        className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">Choose a CU...</option>
                        {companies?.data?.map((co: any) => (
                          <option key={co.id} value={co.id}>{co.name} — Score: {co.opportunity_score}</option>
                        ))}
                      </select>
                    </div>
                    <div className="w-44">
                      <label className="text-xs font-semibold text-slate-500 block mb-1">Tag (optional)</label>
                      <input
                        className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="e.g. warm-lead, priority..."
                        value={addCUTag}
                        onChange={e => setAddCUTag(e.target.value)}
                      />
                    </div>
                    <button
                      onClick={() => addToList.mutate({ listId: list.id, companyId: addCUId, tag: addCUTag })}
                      disabled={!addCUId}
                      className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold px-4 py-2 rounded-lg text-sm"
                    >
                      Add
                    </button>
                  </div>
                )}

                {/* CUs in this list */}
                {list.companies?.length > 0 ? (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50">
                        {['Credit Union', 'Score', 'Status', 'Tag', 'Notes', ''].map(h => (
                          <th key={h} className="text-left px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {list.companies.map((item: any) => (
                        <tr key={item.company_id} className="border-b border-slate-50 hover:bg-blue-50/20 transition-colors">
                          <td className="px-6 py-3.5">
                            <div className="font-semibold text-slate-800">{item.company?.name}</div>
                            <div className="text-xs text-slate-400">{item.company?.hq_city}, {item.company?.hq_state}</div>
                          </td>
                          <td className="px-6 py-3.5">
                            <Badge score={item.company?.opportunity_score || 0} />
                          </td>
                          <td className="px-6 py-3.5">
                            <StatusSelect
                              value={item.company?.outreach_status || 'new'}
                              onChange={v => updateStatus.mutate({ companyId: item.company_id, status: v })}
                            />
                          </td>
                          <td className="px-6 py-3.5">
                            {item.tag && (
                              <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium border"
                                style={{ color: list.color, background: `${list.color}18`, borderColor: `${list.color}44` }}>
                                {item.tag}
                              </span>
                            )}
                          </td>
                          <td className="px-6 py-3.5">
                            <input
                              className="text-xs bg-slate-50 border border-slate-200 rounded px-2 py-1 text-slate-600 w-36 focus:outline-none focus:ring-1 focus:ring-blue-400"
                              placeholder="Add note..."
                              defaultValue={item.notes || ''}
                              onBlur={e => api.patch(`/api/lists/${list.id}/companies/${item.company_id}`, { notes: e.target.value })}
                            />
                          </td>
                          <td className="px-6 py-3.5">
                            <button
                              onClick={() => removeFromList.mutate({ listId: list.id, companyId: item.company_id })}
                              className="text-xs text-red-400 hover:text-red-600 transition-colors"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="px-6 py-8 text-center text-slate-400 text-sm">
                    No CUs in this list yet. Click "+ Add CU" above.
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Dashboard ──────────────────────────────────────────────────
function Dashboard() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: () => api.get('/api/dashboard/stats').then(r => r.data),
    refetchInterval: 30_000,
  })
  const { data: companies } = useQuery({
    queryKey: ['companies-top'],
    queryFn: () => api.get('/api/companies/?per_page=5').then(r => r.data),
  })
  return (
    <div>
      <PageHeader
        title="Dashboard"
        sub="Intelligence overview · Real NCUA data"
        action={
          <Link to="/pipeline" className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-lg transition-colors shadow-sm">
            Run Discovery →
          </Link>
        }
      />
      <div className="p-8">
        {stats ? (
          <div className="grid grid-cols-4 gap-4 mb-8">
            <StatCard label="Total Leads" value={stats.total_leads} color="text-blue-600" />
            <StatCard label="Apollo Enriched" value={stats.apollo_enriched} color="text-violet-600" />
            <StatCard label="High Score (80+)" value={stats.high_score_leads} color="text-green-600" />
            <StatCard label="Active Campaigns" value={stats.active_campaigns} color="text-amber-600" />
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-4 mb-8">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-white border border-slate-200 rounded-xl p-5 h-24 animate-pulse" />
            ))}
          </div>
        )}
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-800">Top Opportunities</h2>
            <Link to="/leads" className="text-xs text-blue-600 hover:text-blue-700 font-medium">View all →</Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  {['Company', 'Industry', 'Score', 'Status', 'Contact'].map(h => (
                    <th key={h} className="text-left px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {companies?.data?.map((co: any) => (
                  <tr key={co.id} className="border-b border-slate-50 hover:bg-blue-50/30 transition-colors">
                    <td className="px-6 py-3.5">
                      <div className="font-semibold text-slate-800">{co.name}</div>
                      <div className="text-xs text-slate-400">{co.hq_city}, {co.hq_state}</div>
                    </td>
                    <td className="px-6 py-3.5 text-slate-500 text-xs capitalize">{co.industry?.replace('_', ' ')}</td>
                    <td className="px-6 py-3.5"><Badge score={co.opportunity_score} /></td>
                    <td className="px-6 py-3.5"><StatusPill status={co.outreach_status} /></td>
                    <td className="px-6 py-3.5">
                      {co.top_contact ? (
                        <div>
                          <div className="text-xs font-semibold text-slate-700">{co.top_contact.name}</div>
                          <div className="text-xs text-blue-600">{co.top_contact.title}</div>
                        </div>
                      ) : <span className="text-xs text-slate-300">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Leads ──────────────────────────────────────────────────────
function Leads() {
  const [search, setSearch] = useState('')
  const [industry, setIndustry] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selected, setSelected] = useState<any>(null)
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['companies', search, industry, statusFilter],
    queryFn: () => api.get('/api/companies/', { params: { search, industry, status: statusFilter } }).then(r => r.data),
  })

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: any) => api.patch(`/api/companies/${id}`, { outreach_status: status }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['companies'] })
  })

  return (
    <div>
      <div className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-slate-200 px-8 py-4 flex items-center gap-3 flex-wrap">
        <div className="flex-1">
          <h1 className="text-lg font-bold text-slate-900">Leads & Contacts</h1>
          <p className="text-xs text-slate-400 mt-0.5">NCUA-powered · Sorted by opportunity score</p>
        </div>
        <input
          className="bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 w-44 shadow-sm"
          placeholder="Search companies..."
          value={search} onChange={e => setSearch(e.target.value)}
        />
        <select
          className="bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
          value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
        >
          <option value="">All Statuses</option>
          {Object.entries(STATUSES).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
        <select
          className="bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
          value={industry} onChange={e => setIndustry(e.target.value)}
        >
          <option value="">All Industries</option>
          {['credit_unions', 'insurance', 'lending', 'healthcare', 'utilities'].map(i => (
            <option key={i} value={i}>{i.replace('_', ' ')}</option>
          ))}
        </select>
      </div>
      <div className="p-8">
        {isLoading ? (
          <div className="flex items-center justify-center py-20"><Spinner /></div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  {['Company', 'Score', 'Maturity', 'Status', 'Signals', ''].map(h => (
                    <th key={h} className="text-left px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data?.data?.map((co: any) => (
                  <tr key={co.id} className="border-b border-slate-50 hover:bg-blue-50/20 transition-colors">
                    <td className="px-6 py-3.5">
                      <div className="font-semibold text-slate-800">{co.name}</div>
                      <div className="text-xs text-slate-400">{co.hq_city}, {co.hq_state}</div>
                    </td>
                    <td className="px-6 py-3.5"><Badge score={co.opportunity_score} /></td>
                    <td className="px-6 py-3.5">
                      <div className="flex gap-0.5">
                        {[1,2,3,4,5].map(i => (
                          <div key={i} className={`w-3 h-2 rounded-sm ${i <= (co.digital_maturity||3) ? 'bg-blue-500' : 'bg-slate-200'}`} />
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-3.5">
                      <StatusSelect
                        value={co.outreach_status || 'new'}
                        onChange={v => updateStatus.mutate({ id: co.id, status: v })}
                      />
                    </td>
                    <td className="px-6 py-3.5">
                      <span className="text-xs font-semibold text-slate-500">{co.signal_count}</span>
                      <span className="text-xs text-slate-300 ml-1">signals</span>
                    </td>
                    <td className="px-6 py-3.5">
                      <button onClick={() => setSelected(co)}
                        className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold px-3 py-1.5 rounded-lg transition-colors shadow-sm">
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {selected && <LeadDrawer company={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

// ─── Lead Drawer ────────────────────────────────────────────────
function LeadDrawer({ company, onClose }: { company: any; onClose: () => void }) {
  const { data: detail } = useQuery({
    queryKey: ['company', company.id],
    queryFn: () => api.get(`/api/companies/${company.id}`).then(r => r.data),
  })
  const [activeTab, setActiveTab] = useState('overview')
  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="w-[580px] bg-white border-l border-slate-200 flex flex-col h-full overflow-auto shadow-xl">
        <div className="px-7 py-5 border-b border-slate-100 flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center text-white font-black text-lg flex-shrink-0 shadow-sm">
            {company.name?.charAt(0)}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2.5 mb-1 flex-wrap">
              <h2 className="text-base font-bold text-slate-900">{company.name}</h2>
              <Badge score={company.opportunity_score} />
              <StatusPill status={company.outreach_status} />
            </div>
            <p className="text-sm text-slate-500 capitalize">{company.industry?.replace('_', ' ')} · {company.hq_city}, {company.hq_state}</p>
          </div>
          <button onClick={onClose} className="text-slate-300 hover:text-slate-600 text-xl transition-colors">✕</button>
        </div>
        <div className="flex border-b border-slate-100 px-7 bg-slate-50">
          {['overview', 'signals', 'contacts', 'outreach'].map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`py-3 mr-6 text-xs font-semibold border-b-2 transition-colors capitalize tracking-wide ${
                activeTab === tab ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-400 hover:text-slate-600'
              }`}>
              {tab}
            </button>
          ))}
        </div>
        <div className="p-7 flex-1">
          {activeTab === 'overview' && detail && (
            <div className="space-y-3">
              {[
                ['Total Assets', detail.revenue_est ? `$${(detail.revenue_est / 1_000_000).toFixed(0)}M` : '—'],
                ['Members', detail.regulatory_data?.total_members ? detail.regulatory_data.total_members.toLocaleString() : '—'],
                ['Net Worth Ratio', detail.regulatory_data?.net_worth_ratio ? `${detail.regulatory_data.net_worth_ratio}%` : '—'],
                ['Loan-to-Share', detail.regulatory_data?.loan_to_share_ratio ? `${detail.regulatory_data.loan_to_share_ratio}%` : '—'],
                ['Digital Maturity', `${detail.digital_maturity || '—'} / 5`],
                ['Core Processor', (detail.tech_stack || []).filter(Boolean).join(', ') || '—'],
              ].map(([k, v]) => (
                <div key={k as string} className="flex items-center justify-between py-2.5 border-b border-slate-100">
                  <span className="text-sm text-slate-500">{k}</span>
                  <span className="text-sm text-slate-800 font-semibold">{v}</span>
                </div>
              ))}
            </div>
          )}
          {activeTab === 'signals' && detail && (
            <div className="space-y-2">
              {detail.signals?.map((s: any) => (
                <SignalCard key={s.id} s={s} />
              ))}
            </div>
          )}
          {activeTab === 'contacts' && detail && (
            <div className="space-y-3">
              {detail.contacts?.map((c: any) => (
                <div key={c.id} className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold text-white flex-shrink-0">
                    {c.name.split(' ').map((n: string) => n[0]).join('')}
                  </div>
                  <div className="flex-1">
                    <div className="font-semibold text-slate-800 text-sm">{c.name}</div>
                    <div className="text-xs text-slate-500">{c.title}</div>
                    <div className="text-xs text-blue-600 font-medium mt-0.5">{c.email}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {activeTab === 'outreach' && detail && <OutreachPanel company={detail} />}
        </div>
      </div>
    </div>
  )
}

// ─── Tone dropdown (Regenerate only) ────────────────────────────
const TONE_OPTIONS = [
  { value: 'professional', label: 'Professional', desc: "Default — Claude's natural professional tone" },
  { value: 'friendly',     label: 'Friendly',     desc: 'Warmer, more casual, still credible' },
  { value: 'basic_ai',     label: 'Basic AI',     desc: 'Plain language, no jargon, simple sentences' },
]

function RegenerateWithTone({ onRegenerate }: { onRegenerate: (tone: string) => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen(!open)}
        className="text-xs border border-slate-200 text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg bg-white flex items-center gap-1.5"
      >
        ↺ Regenerate <span className="text-slate-300">▾</span>
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-56 bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden">
          {TONE_OPTIONS.map(t => (
            <button
              key={t.value}
              onClick={() => { onRegenerate(t.value); setOpen(false) }}
              className="w-full text-left px-3.5 py-2.5 hover:bg-blue-50 border-b border-slate-50 last:border-0 transition-colors"
            >
              <div className="text-xs font-semibold text-slate-700">{t.label}</div>
              <div className="text-xs text-slate-400 mt-0.5">{t.desc}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Signal Card ─────────────────────────────────────────────────
function SignalCard({ s }: { s: any }) {
  const colorClass = s.type === 'operational_gap' ? 'bg-red-50 border-red-100 text-red-700'
    : s.type === 'pain_point' ? 'bg-amber-50 border-amber-100 text-amber-700'
    : s.type === 'growth' ? 'bg-green-50 border-green-100 text-green-700'
    : 'bg-blue-50 border-blue-100 text-blue-700'

  return (
    <div className={`p-3.5 rounded-xl border text-sm ${colorClass} flex items-start justify-between gap-2`}>
      <div>
        <div className="font-semibold">{s.label}</div>
        <div className="text-xs opacity-60 mt-1">{s.type} · severity {s.severity}/100</div>
      </div>
      {(s.source_url || s.source_file) && (
        s.source_url ? (
          <a href={s.source_url} target="_blank" rel="noopener noreferrer"
             title={s.source_hover}
             className="flex-shrink-0 text-current opacity-50 hover:opacity-100 transition-opacity">
            🔗
          </a>
        ) : (
          <span title={s.source_hover} className="flex-shrink-0 opacity-50 hover:opacity-100 cursor-help transition-opacity">
            📄
          </span>
        )
      )}
    </div>
  )
}

// ─── Outreach Panel (email history + send) ───────────────────────
function OutreachPanel({ company }: { company: any }) {
  const [showManualLink, setShowManualLink] = useState(false)
  const [manualThreadId, setManualThreadId] = useState('')
  const qc = useQueryClient()

  const { data: threadData, isLoading } = useQuery({
    queryKey: ['email-threads', company.id],
    queryFn: () => api.get(`/api/companies/${company.id}/email-threads`).then(r => r.data),
    retry: false,
  })

  const linkMutation = useMutation({
    mutationFn: () => api.post(`/api/companies/${company.id}/email-threads/link`, {
      thread_id: manualThreadId
    }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['email-threads', company.id] })
      setShowManualLink(false)
      setManualThreadId('')
    }
  })

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Email History</h3>
          <button onClick={() => setShowManualLink(!showManualLink)} className="text-xs text-blue-600 hover:text-blue-700 font-medium">
            {showManualLink ? 'Cancel' : '+ Manually link a thread'}
          </button>
        </div>

        {showManualLink && (
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-3 flex gap-2">
            <input
              className="flex-1 bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Paste Gmail thread ID (from the URL when viewing the email)..."
              value={manualThreadId}
              onChange={e => setManualThreadId(e.target.value)}
            />
            <button onClick={() => linkMutation.mutate()} disabled={!manualThreadId.trim()}
              className="text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold px-3 py-2 rounded-lg">
              Link
            </button>
          </div>
        )}

        {!company.gmail_connected ? (
          <div className="text-center py-8 bg-amber-50 border border-amber-100 rounded-xl">
            <p className="text-xs text-amber-700">Connect Gmail in Settings to see email history</p>
          </div>
        ) : isLoading ? (
          <div className="text-xs text-slate-400 py-4">Loading conversation history...</div>
        ) : threadData?.threads?.length > 0 ? (
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {threadData.threads.map((thread: any) => (
              <div key={thread.thread_id} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                <div className="px-3.5 py-2 bg-slate-50 border-b border-slate-100 text-xs font-semibold text-slate-600">
                  {thread.subject}
                </div>
                <div className="divide-y divide-slate-50">
                  {thread.messages.map((msg: any) => (
                    <div key={msg.id} className="px-3.5 py-2.5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-semibold text-slate-700 truncate">{msg.from}</span>
                        <span className="text-xs text-slate-400 flex-shrink-0 ml-2">{msg.date?.slice(0, 16)}</span>
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-2">{msg.snippet}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-slate-300 text-xs">No email history found for this CU yet</div>
        )}
      </div>

      <div className="border-t border-slate-100 pt-5">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Generate &amp; Send</h3>
        <AIMessagePanel company={company} latestThreadId={threadData?.threads?.[0]?.thread_id} />
      </div>
    </div>
  )
}

// ─── AI Message Panel ───────────────────────────────────────────
function AIMessagePanel({ company, latestThreadId }: { company: any; latestThreadId?: string }) {
  const [msgType, setMsgType] = useState('email')
  const [message, setMessage] = useState<any>(null)
  const [sent, setSent] = useState(false)
  const firstContact = company.contacts?.[0]

  const generateMutation = useMutation({
    mutationFn: ({ tone }: { tone?: string } = {}) => api.post('/api/ai/generate-message', {
      company_id: company.id, contact_id: firstContact?.id,
      message_type: msgType, tone: tone || undefined,
    }).then(r => r.data),
    onSuccess: (data) => { setMessage(data); setSent(false) },
  })

  const sendMutation = useMutation({
    mutationFn: () => api.post('/api/outreach/send-email', {
      company_id: company.id,
      contact_id: firstContact?.id,
      subject: message.subject_line,
      body: message.body,
      thread_id: latestThreadId || undefined,
    }).then(r => r.data),
    onSuccess: () => setSent(true),
  })

  if (!firstContact) return <p className="text-slate-400 text-sm text-center py-10">No contacts found.</p>
  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        {['email', 'linkedin', 'call_script'].map(t => (
          <button key={t} onClick={() => { setMsgType(t); setMessage(null) }}
            className={`text-xs px-3.5 py-1.5 rounded-lg border font-semibold transition-colors ${
              msgType === t ? 'bg-blue-600 border-blue-600 text-white' : 'border-slate-200 text-slate-500 hover:border-blue-300 bg-white'
            }`}>
            {t === 'email' ? '✉ Email' : t === 'linkedin' ? '💼 LinkedIn' : '☎ Call Script'}
          </button>
        ))}
      </div>
      {generateMutation.isPending ? (
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-blue-600 text-sm">Claude is generating your message...</div>
      ) : message ? (
        <div>
          {message.subject_line && (
            <div className="bg-slate-50 border border-slate-200 rounded-t-xl px-4 py-2.5 border-b-0">
              <span className="text-xs font-semibold text-slate-400">SUBJECT: </span>
              <span className="text-sm text-slate-800 font-medium">{message.subject_line}</span>
            </div>
          )}
          <div className={`bg-white border border-slate-200 ${message.subject_line ? 'rounded-b-xl' : 'rounded-xl'} p-4`}>
            <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">{message.body}</pre>
          </div>
          <div className="flex gap-2 mt-2 items-center">
            <RegenerateWithTone onRegenerate={(tone) => generateMutation.mutate({ tone })} />
            <button onClick={() => navigator.clipboard.writeText(message.body)} className="text-xs border border-slate-200 text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg bg-white">
              Copy
            </button>
            {msgType === 'email' && (
              <button
                onClick={() => sendMutation.mutate()}
                disabled={sendMutation.isPending || sent}
                className="ml-auto text-xs bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-semibold px-4 py-1.5 rounded-lg transition-colors"
              >
                {sent ? '✓ Sent' : sendMutation.isPending ? 'Sending...' : '✉ Send from Gmail'}
              </button>
            )}
          </div>
        </div>
      ) : (
        <button onClick={() => generateMutation.mutate({})} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-colors text-sm shadow-sm">
          ✦ Generate with Claude AI
        </button>
      )}
    </div>
  )
}

// ─── AI Engine (Version 2 — RAG + Response Loop) ────────────────
function AIEngine() {
  const [selectedId, setSelectedId] = useState('')
  const [msgType, setMsgType] = useState('email')
  const [message, setMessage] = useState<any>(null)
  // RAG: client response and follow-up
  const [clientResponse, setClientResponse] = useState('')
  const [followUp, setFollowUp] = useState<any>(null)
  const [ragDocs, setRagDocs] = useState<any[]>([])
  const [showRagDocs, setShowRagDocs] = useState(false)

  const { data: companies } = useQuery({
    queryKey: ['companies-list'],
    queryFn: () => api.get('/api/companies/?per_page=50').then(r => r.data),
  })
  const { data: companyDetail } = useQuery({
    queryKey: ['company', selectedId],
    queryFn: () => selectedId ? api.get(`/api/companies/${selectedId}`).then(r => r.data) : null,
    enabled: !!selectedId,
  })

  const generateMutation = useMutation({
    mutationFn: ({ tone }: { tone?: string } = {}) => {
      const contact = companyDetail?.contacts?.[0]
      if (!contact) throw new Error('No contact')
      return api.post('/api/ai/generate-message', {
        company_id: selectedId,
        contact_id: contact.id,
        message_type: msgType,
        use_rag: true,
        tone: tone || undefined,
      }).then(r => r.data)
    },
    onSuccess: (data) => {
      setMessage(data)
      setFollowUp(null)
      setClientResponse('')
      if (data.rag_chunks_used) setRagDocs(data.rag_chunks_used)
    },
  })

  // Generate follow-up based on client's actual response
  const followUpMutation = useMutation({
    mutationFn: () => api.post('/api/ai/generate-followup', {
      company_id: selectedId,
      original_message: message?.body,
      client_response: clientResponse,
      use_rag: true,  // ← RAG retrieves fresh context for the follow-up too
    }).then(r => r.data),
    onSuccess: (data) => {
      setFollowUp(data)
      if (data.rag_chunks_used) setRagDocs(data.rag_chunks_used)
    },
  })

  return (
    <div>
      <PageHeader
        title="AI Message Engine"
        sub="Powered by Claude + RAG · NCUA data + case studies + past email threads"
        action={
          <span className="text-xs bg-purple-50 text-purple-700 border border-purple-200 px-3 py-1.5 rounded-full font-semibold">
            RAG Enabled
          </span>
        }
      />

      <div className="p-8 grid grid-cols-3 gap-6">
        {/* ── Left: controls + output ── */}
        <div className="col-span-2 space-y-5">

          {/* Select lead + type */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">Select Lead</label>
              <select className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
                value={selectedId} onChange={e => { setSelectedId(e.target.value); setMessage(null); setFollowUp(null); setClientResponse('') }}>
                <option value="">Choose a credit union...</option>
                {companies?.data?.map((co: any) => (
                  <option key={co.id} value={co.id}>{co.name} — Score: {co.opportunity_score}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">Message Type</label>
              <div className="flex gap-2">
                {['email', 'linkedin', 'call_script'].map(t => (
                  <button key={t} onClick={() => { setMsgType(t); setMessage(null); setFollowUp(null) }}
                    className={`flex-1 text-xs py-2.5 rounded-lg border font-semibold transition-colors ${
                      msgType === t ? 'bg-blue-600 border-blue-600 text-white' : 'border-slate-200 text-slate-500 bg-white hover:border-blue-300'
                    }`}>
                    {t === 'email' ? 'Email' : t === 'linkedin' ? 'LinkedIn' : 'Call'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <button onClick={() => generateMutation.mutate({})}
            disabled={!selectedId || generateMutation.isPending}
            className="w-full text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold px-5 py-3 rounded-xl transition-colors shadow-sm flex items-center justify-center gap-2">
            {generateMutation.isPending
              ? <><div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" /> Generating with RAG...</>
              : '✦ Generate Initial Email'}
          </button>

          {/* Generated email */}
          {message && (
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
              <div className="px-5 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-slate-700">Initial Email</span>
                  {ragDocs.length > 0 && (
                    <button onClick={() => setShowRagDocs(!showRagDocs)}
                      className="text-xs text-purple-600 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded-full font-medium">
                      {ragDocs.length} RAG sources used
                    </button>
                  )}
                </div>
                <button onClick={() => navigator.clipboard.writeText(message.body)}
                  className="text-xs bg-white hover:bg-slate-50 border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg">
                  Copy
                </button>
              </div>

              {/* RAG sources panel */}
              {showRagDocs && ragDocs.length > 0 && (
                <div className="px-5 py-3 bg-purple-50 border-b border-purple-100">
                  <div className="text-xs font-semibold text-purple-700 mb-2">Context retrieved from knowledge base:</div>
                  <div className="space-y-1.5">
                    {ragDocs.map((doc: any, i: number) => (
                      <div key={i} className="flex items-start gap-2 text-xs text-purple-700">
                        <span className="bg-purple-100 border border-purple-200 px-1.5 py-0.5 rounded font-mono font-medium flex-shrink-0">
                          {(doc.score * 100).toFixed(0)}%
                        </span>
                        <span className="capitalize">{doc.type.replace(/_/g, ' ')}</span>
                        <span className="text-purple-400">·</span>
                        <span className="text-purple-500 truncate">{doc.source}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="p-5">
                {message.subject_line && (
                  <div className="text-xs font-semibold text-slate-400 mb-3">
                    SUBJECT: <span className="text-slate-700">{message.subject_line}</span>
                  </div>
                )}
                <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">{message.body}</pre>
                <div className="mt-3 pt-3 border-t border-slate-100 flex gap-2">
                  <RegenerateWithTone onRegenerate={(tone) => generateMutation.mutate({ tone })} />
                </div>
              </div>
            </div>
          )}

          {/* ── CLIENT RESPONSE BOX ── */}
          {message && (
            <div className="bg-white border-2 border-blue-200 rounded-xl overflow-hidden shadow-sm">
              <div className="px-5 py-3 bg-blue-50 border-b border-blue-100 flex items-center gap-2">
                <span className="text-sm font-bold text-blue-700">Client Response</span>
                <span className="text-xs text-blue-500">Paste their actual reply here → we generate a follow-up email using RAG</span>
              </div>
              <div className="p-5">
                <textarea
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none leading-relaxed placeholder-slate-400"
                  rows={5}
                  placeholder={`Paste the client's actual email reply here...

Example:
"Thanks for reaching out. We are evaluating FedNow options for Q3. Our main constraint is we don't want a core replacement project. Happy to chat if you have a middleware approach."`}
                  value={clientResponse}
                  onChange={e => { setClientResponse(e.target.value); setFollowUp(null) }}
                />

                {clientResponse.trim().length > 20 && (
                  <div className="mt-3">
                    {/* Quick signal detection */}
                    <div className="flex gap-2 flex-wrap mb-3">
                      {clientResponse.toLowerCase().includes('interest') && (
                        <span className="text-xs bg-green-50 text-green-700 border border-green-200 px-2 py-0.5 rounded-full">Showing interest</span>
                      )}
                      {clientResponse.toLowerCase().includes('q3') && (
                        <span className="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full">Q3 timeline mentioned</span>
                      )}
                      {clientResponse.toLowerCase().includes('budget') && (
                        <span className="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full">Budget context</span>
                      )}
                      {(clientResponse.toLowerCase().includes("not right now") || clientResponse.toLowerCase().includes("not interested")) && (
                        <span className="text-xs bg-red-50 text-red-700 border border-red-200 px-2 py-0.5 rounded-full">Objection detected</span>
                      )}
                      {clientResponse.toLowerCase().includes('call') && (
                        <span className="text-xs bg-purple-50 text-purple-700 border border-purple-200 px-2 py-0.5 rounded-full">Open to a call</span>
                      )}
                    </div>

                    <button
                      onClick={() => followUpMutation.mutate()}
                      disabled={followUpMutation.isPending}
                      className="w-full text-sm bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:opacity-40 text-white font-semibold px-5 py-3 rounded-xl transition-all shadow-sm flex items-center justify-center gap-2">
                      {followUpMutation.isPending
                        ? <><div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" /> Generating follow-up with RAG...</>
                        : '✦ Generate Follow-up Email (RAG-powered)'}
                    </button>
                    <p className="text-xs text-center text-slate-400 mt-2">
                      Claude reads their response + retrieves relevant case studies + past threads from your knowledge base
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Follow-up email output ── */}
          {followUp && (
            <div className="bg-white border border-green-200 rounded-xl overflow-hidden shadow-sm">
              <div className="px-5 py-3 bg-green-50 border-b border-green-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-green-700">Follow-up Email</span>
                  <span className="text-xs text-green-600 bg-green-100 border border-green-200 px-2 py-0.5 rounded-full">
                    Informed by their response
                  </span>
                  {followUp.rag_chunks_used?.length > 0 && (
                    <span className="text-xs text-purple-600 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded-full">
                      {followUp.rag_chunks_used.length} RAG sources
                    </span>
                  )}
                </div>
                <button onClick={() => navigator.clipboard.writeText(followUp.body)}
                  className="text-xs bg-white hover:bg-slate-50 border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg">
                  Copy
                </button>
              </div>
              <div className="p-5">
                {followUp.subject_line && (
                  <div className="text-xs font-semibold text-slate-400 mb-3">
                    SUBJECT: <span className="text-slate-700">{followUp.subject_line}</span>
                  </div>
                )}
                <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">{followUp.body}</pre>
                <div className="mt-3 pt-3 border-t border-slate-100 flex gap-2">
                  <RegenerateWithTone onRegenerate={() => followUpMutation.mutate()} />
                  <button
                    onClick={() => { setClientResponse(''); setFollowUp(null) }}
                    className="text-xs border border-blue-200 text-blue-500 hover:text-blue-700 px-3 py-1.5 rounded-lg bg-blue-50">
                    + Log another response
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Right: context panel ── */}
        <div className="space-y-4">
          {companyDetail ? (
            <>
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Lead Context</div>
                <div className="flex items-center gap-2 mb-3">
                  <h3 className="font-bold text-slate-800 text-sm">{companyDetail.name}</h3>
                  <Badge score={companyDetail.opportunity_score} />
                </div>
                <div className="mb-3">
                  <StatusSelect value={companyDetail.outreach_status || 'new'} onChange={() => {}} />
                </div>
                {[
                  ['Assets', companyDetail.revenue_est ? `$${(companyDetail.revenue_est/1e6).toFixed(0)}M` : '—'],
                  ['Members', companyDetail.regulatory_data?.total_members?.toLocaleString() || '—'],
                  ['LTS', companyDetail.regulatory_data?.loan_to_share_ratio ? `${companyDetail.regulatory_data.loan_to_share_ratio}%` : '—'],
                  ['Maturity', `${companyDetail.digital_maturity}/5`],
                ].map(([k, v]) => (
                  <div key={k as string} className="flex justify-between py-1.5 border-b border-slate-50 last:border-0 text-xs">
                    <span className="text-slate-400">{k}</span>
                    <span className="text-slate-700 font-semibold">{v}</span>
                  </div>
                ))}
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Top Signals</div>
                <div className="space-y-1.5">
                  {companyDetail.signals?.slice(0, 4).map((s: any) => (
                    <div key={s.id} className={`text-xs px-3 py-2 rounded-lg font-medium ${
                      s.type === 'operational_gap' ? 'bg-red-50 text-red-600'
                      : s.type === 'pain_point' ? 'bg-amber-50 text-amber-600'
                      : 'bg-green-50 text-green-600'
                    }`}>{s.label}</div>
                  ))}
                </div>
              </div>

              {/* RAG knowledge base hint */}
              <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
                <div className="text-xs font-semibold text-purple-700 mb-2">RAG Knowledge Base</div>
                <div className="text-xs text-purple-600 space-y-1.5">
                  <div>• Case studies matching this CU</div>
                  <div>• Past email threads with {companyDetail.name}</div>
                  <div>• News articles (last 90 days)</div>
                  <div>• CUNA conference notes</div>
                </div>
                <div className="text-xs text-purple-400 mt-2">Retrieved automatically at generation time</div>
              </div>

              {companyDetail.contacts?.[0] && (
                <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Target Contact</div>
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
                      {companyDetail.contacts[0].name.split(' ').map((n: string) => n[0]).join('')}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-800">{companyDetail.contacts[0].name}</div>
                      <div className="text-xs text-slate-500">{companyDetail.contacts[0].title}</div>
                      <div className="text-xs text-blue-600 font-medium">{companyDetail.contacts[0].email}</div>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl p-6 text-center shadow-sm">
              <div className="text-slate-300 text-sm">Select a lead to see context</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Pipeline ───────────────────────────────────────────────────
function Pipeline() {
  const qc = useQueryClient()
  const { data: status } = useQuery({
    queryKey: ['pipeline-status'],
    queryFn: () => api.get('/api/pipeline/status').then(r => r.data),
    refetchInterval: 5_000,
  })
  const runMutation = useMutation({
    mutationFn: (industry: string) => api.post('/api/pipeline/run', { industry }).then(r => r.data),
    onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ['pipeline-status'] }), 3000),
  })
  const industries = [
    { id: 'credit_unions', icon: '🏦', label: 'Credit Unions' },
    { id: 'insurance', icon: '🛡️', label: 'Insurance' },
    { id: 'lending', icon: '💳', label: 'Lending' },
    { id: 'healthcare', icon: '🏥', label: 'Healthcare' },
    { id: 'utilities', icon: '⚡', label: 'Utilities' },
  ]
  return (
    <div>
      <PageHeader title="Data Pipeline" sub="NCUA → Apollo → AI Scoring · Pull companies by industry" />
      <div className="p-8 space-y-6">
        {status && (
          <div className="grid grid-cols-5 gap-4">
            {[
              { label: 'Total Companies', value: status.companies_total },
              { label: 'Apollo Enriched', value: status.apollo_enriched },
              { label: 'Regulatory Data', value: status.regulatory_enriched },
              { label: 'Scored', value: status.opportunity_scored },
              { label: 'Total Signals', value: status.total_signals },
            ].map(s => (
              <div key={s.label} className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
                <div className="text-2xl font-bold text-slate-800 mb-1">{s.value}</div>
                <div className="text-xs font-semibold text-slate-400">{s.label}</div>
              </div>
            ))}
          </div>
        )}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <h2 className="text-sm font-bold text-slate-800 mb-4">Run Discovery by Industry</h2>
          <div className="grid grid-cols-5 gap-3">
            {industries.map(ind => (
              <button key={ind.id} onClick={() => runMutation.mutate(ind.id)} disabled={runMutation.isPending}
                className="bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-200 disabled:opacity-40 rounded-xl p-4 text-center transition-colors">
                <div className="text-2xl mb-2">{ind.icon}</div>
                <div className="text-xs font-semibold text-slate-700">{ind.label}</div>
              </button>
            ))}
          </div>
          {runMutation.data && (
            <div className="mt-4 bg-green-50 border border-green-100 text-green-700 text-sm px-4 py-3 rounded-lg">
              ✓ {runMutation.data.message}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Campaigns ──────────────────────────────────────────────────
function Campaigns() {
  const { data: campaigns } = useQuery({
    queryKey: ['campaigns'],
    queryFn: () => api.get('/api/campaigns/').then(r => r.data),
  })
  return (
    <div>
      <PageHeader title="Campaigns" sub="Multi-channel outreach management" />
      <div className="p-8">
        {campaigns?.length > 0 ? (
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  {['Name', 'Sent', 'Opens', 'Replies', 'Status'].map(h => (
                    <th key={h} className="text-left px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c: any) => (
                  <tr key={c.id} className="border-b border-slate-50 hover:bg-blue-50/20 transition-colors">
                    <td className="px-6 py-3.5 font-semibold text-slate-800">{c.name}</td>
                    <td className="px-6 py-3.5">{c.total_sent}</td>
                    <td className="px-6 py-3.5 text-green-600">{c.total_opens}</td>
                    <td className="px-6 py-3.5 text-blue-600">{c.total_replies}</td>
                    <td className="px-6 py-3.5"><StatusPill status={c.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-20 text-slate-300">
            <div className="text-4xl mb-3">✉</div>
            <div className="text-sm font-semibold text-slate-400">No campaigns yet</div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Settings ───────────────────────────────────────────────────
function Settings() {
  const { user, loadUser } = useAuthStore()
  const [companyUrl, setCompanyUrl] = useState('')
  const [scraping, setScraping] = useState(false)
  const [scrapeError, setScrapeError] = useState('')
  const [form, setForm] = useState({
    company_name:        user?.company_name || '',
    tagline:             '',
    product_description: user?.product_description || '',
    key_strengths:       '',
    differentiators:     '',
    products:            [] as string[],
    case_studies:        [] as { customer: string; outcome: string }[],
    integrations:        [] as string[],
    tone: user?.tone || 'consultative',
  })
  const [saved, setSaved] = useState(false)

  const scrapeMutation = useMutation({
    mutationFn: () => api.post('/api/settings/scrape-company', { url: companyUrl }).then(r => r.data),
    onMutate: () => { setScraping(true); setScrapeError('') },
    onSuccess: (data) => {
      setScraping(false)
      setForm(f => ({
        ...f,
        company_name:        data.company_name || f.company_name,
        tagline:             data.tagline || '',
        product_description: data.product_description || '',
        key_strengths:       data.key_strengths || '',
        differentiators:     data.differentiators || '',
        products:            data.products || [],
        case_studies:        data.case_studies || [],
        integrations:        data.integrations || [],
      }))
    },
    onError: (err: any) => {
      setScraping(false)
      setScrapeError(err?.response?.data?.detail || 'Could not scrape this URL. Fill fields manually below.')
    },
  })

  const saveMutation = useMutation({
    mutationFn: () => api.put('/api/auth/profile', form).then(r => r.data),
    onSuccess: () => { setSaved(true); loadUser(); setTimeout(() => setSaved(false), 3000) },
  })

  const connectGmail = async () => {
    const { data } = await api.get('/api/auth/gmail/connect')
    window.location.href = data.auth_url
  }

  return (
    <div>
      <PageHeader
        title="Company Profile"
        sub="Powers all AI-generated outreach personalisation"
        action={
          <button onClick={() => saveMutation.mutate()} className="text-sm bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 py-2 rounded-lg transition-colors shadow-sm">
            {saveMutation.isPending ? 'Saving...' : saved ? '✓ Saved!' : 'Save Profile'}
          </button>
        }
      />
      <div className="p-8 max-w-3xl space-y-6">

        {/* Gmail connection status */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-sm font-bold text-slate-800 mb-1">Gmail Integration</div>
            {user?.gmail_email ? (
              <div className="text-xs text-green-600 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" /> Connected as {user.gmail_email}
              </div>
            ) : (
              <div className="text-xs text-slate-400">Not connected — enables email history sync and sending from Outreach</div>
            )}
          </div>
          {!user?.gmail_email && (
            <button onClick={connectGmail} className="text-xs bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold px-4 py-2 rounded-lg">
              Connect Gmail
            </button>
          )}
        </div>

        {/* Company URL scraper */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
          <div className="text-sm font-bold text-slate-800 mb-1">Auto-fill from your website</div>
          <p className="text-xs text-slate-400 mb-3">We'll crawl your site and auto-fill the fields below. Anything we can't extract is left blank for you to fill in.</p>
          <div className="flex gap-2">
            <input
              className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="https://www.yourcompany.com"
              value={companyUrl}
              onChange={e => setCompanyUrl(e.target.value)}
            />
            <button
              onClick={() => scrapeMutation.mutate()}
              disabled={!companyUrl.trim() || scraping}
              className="text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold px-5 py-2.5 rounded-lg transition-colors shadow-sm flex items-center gap-2"
            >
              {scraping ? <><div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" /> Scraping...</> : 'Scrape & Auto-fill'}
            </button>
          </div>
          {scrapeError && <p className="text-xs text-amber-600 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 mt-2">{scrapeError}</p>}
          {scrapeMutation.isSuccess && <p className="text-xs text-green-600 bg-green-50 border border-green-100 rounded-lg px-3 py-2 mt-2">✓ Fields auto-filled below — review and edit before saving.</p>}
        </div>

        {/* Core text fields */}
        {(['company_name', 'tagline', 'product_description', 'key_strengths', 'differentiators'] as const).map(key => (
          <div key={key}>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">
              {key.replace(/_/g, ' ')}
            </label>
            {key === 'company_name' || key === 'tagline' ? (
              <input className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
                value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
            ) : (
              <textarea rows={3} className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none shadow-sm"
                value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
            )}
          </div>
        ))}

        {/* Products */}
        <div>
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Products</label>
          <div className="flex flex-wrap gap-2 mb-2">
            {form.products.map((p, i) => (
              <span key={i} className="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-full flex items-center gap-1.5">
                {p}
                <button onClick={() => setForm(f => ({ ...f, products: f.products.filter((_, idx) => idx !== i) }))} className="text-blue-400 hover:text-blue-600">×</button>
              </span>
            ))}
          </div>
          <input
            className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Type a product name and press Enter..."
            onKeyDown={e => {
              if (e.key === 'Enter' && e.currentTarget.value.trim()) {
                setForm(f => ({ ...f, products: [...f.products, e.currentTarget.value.trim()] }))
                e.currentTarget.value = ''
              }
            }}
          />
        </div>

        {/* Case studies */}
        {form.case_studies.length > 0 && (
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Case Studies (from your site)</label>
            <div className="space-y-2">
              {form.case_studies.map((cs, i) => (
                <div key={i} className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold text-slate-700">{cs.customer}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{cs.outcome}</div>
                  </div>
                  <button onClick={() => setForm(f => ({ ...f, case_studies: f.case_studies.filter((_, idx) => idx !== i) }))} className="text-slate-300 hover:text-red-400 text-sm flex-shrink-0">×</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Integrations */}
        {form.integrations.length > 0 && (
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Integrations / Partners</label>
            <div className="flex flex-wrap gap-2">
              {form.integrations.map((p, i) => (
                <span key={i} className="text-xs bg-slate-100 text-slate-600 border border-slate-200 px-2.5 py-1 rounded-full">{p}</span>
              ))}
            </div>
          </div>
        )}

        {/* Default AI tone */}
        <div>
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Default AI Tone (used on first generation)</label>
          <select className="bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
            value={form.tone} onChange={e => setForm(f => ({ ...f, tone: e.target.value }))}>
            {['consultative', 'formal', 'friendly', 'data_driven'].map(t => (
              <option key={t} value={t}>{t.replace('_', ' ')}</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  )
}

// ─── Auth guard ─────────────────────────────────────────────────
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

// ─── App root ────────────────────────────────────────────────────
export default function App() {
  const { loadUser } = useAuthStore()
  useEffect(() => { loadUser() }, [])
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<RequireAuth><Layout><Dashboard /></Layout></RequireAuth>} />
        <Route path="/leads"     element={<RequireAuth><Layout><Leads /></Layout></RequireAuth>} />
        <Route path="/my-lists"  element={<RequireAuth><Layout><MyLists /></Layout></RequireAuth>} />
        <Route path="/ai-engine" element={<RequireAuth><Layout><AIEngine /></Layout></RequireAuth>} />
        <Route path="/campaigns" element={<RequireAuth><Layout><Campaigns /></Layout></RequireAuth>} />
        <Route path="/pipeline"  element={<RequireAuth><Layout><Pipeline /></Layout></RequireAuth>} />
        <Route path="/settings"  element={<RequireAuth><Layout><Settings /></Layout></RequireAuth>} />
        <Route path="/auth/callback" element={<GoogleAuthCallback />} />
      </Routes>
    </BrowserRouter>
  )
}
