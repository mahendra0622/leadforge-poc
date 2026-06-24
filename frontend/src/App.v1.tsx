import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom'
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
                <div key={s.id} className={`p-3.5 rounded-xl border text-sm ${
                  s.type === 'operational_gap' ? 'bg-red-50 border-red-100 text-red-700'
                  : s.type === 'pain_point' ? 'bg-amber-50 border-amber-100 text-amber-700'
                  : s.type === 'growth' ? 'bg-green-50 border-green-100 text-green-700'
                  : 'bg-blue-50 border-blue-100 text-blue-700'
                }`}>
                  <div className="font-semibold">{s.label}</div>
                  <div className="text-xs opacity-60 mt-1">{s.type} · severity {s.severity}/100</div>
                </div>
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
          {activeTab === 'outreach' && detail && <AIMessagePanel company={detail} />}
        </div>
      </div>
    </div>
  )
}

// ─── AI Message Panel ───────────────────────────────────────────
function AIMessagePanel({ company }: { company: any }) {
  const [msgType, setMsgType] = useState('email')
  const [message, setMessage] = useState<any>(null)
  const firstContact = company.contacts?.[0]
  const generateMutation = useMutation({
    mutationFn: () => api.post('/api/ai/generate-message', {
      company_id: company.id,
      contact_id: firstContact?.id,
      message_type: msgType,
    }).then(r => r.data),
    onSuccess: setMessage,
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
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
          <div className="flex items-center gap-2 text-blue-600 text-sm">
            <div className="flex gap-1">
              {[0,1,2].map(i => <div key={i} className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />)}
            </div>
            Claude is generating your message...
          </div>
        </div>
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
          <div className="flex gap-2 mt-2">
            <button onClick={() => generateMutation.mutate()} className="text-xs border border-slate-200 text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg bg-white">
              ↺ Regenerate
            </button>
            <button onClick={() => navigator.clipboard.writeText(message.body)} className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold px-3 py-1.5 rounded-lg">
              Copy
            </button>
          </div>
        </div>
      ) : (
        <button onClick={() => generateMutation.mutate()} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-colors text-sm shadow-sm">
          ✦ Generate with Claude AI
        </button>
      )}
    </div>
  )
}

// ─── AI Engine ──────────────────────────────────────────────────
function AIEngine() {
  const [selectedId, setSelectedId] = useState('')
  const [msgType, setMsgType] = useState('email')
  const [message, setMessage] = useState<any>(null)
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
    mutationFn: () => {
      const contact = companyDetail?.contacts?.[0]
      if (!contact) throw new Error('No contact')
      return api.post('/api/ai/generate-message', {
        company_id: selectedId, contact_id: contact.id, message_type: msgType,
      }).then(r => r.data)
    },
    onSuccess: setMessage,
  })
  return (
    <div>
      <PageHeader title="AI Message Engine" sub="Powered by Claude · NCUA signal-driven personalisation" />
      <div className="p-8 grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-5">
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">Select Lead</label>
            <select className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
              value={selectedId} onChange={e => { setSelectedId(e.target.value); setMessage(null) }}>
              <option value="">Choose a credit union...</option>
              {companies?.data?.map((co: any) => (
                <option key={co.id} value={co.id}>{co.name} — Score: {co.opportunity_score}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 flex-wrap">
            {['email', 'linkedin', 'call_script'].map(t => (
              <button key={t} onClick={() => { setMsgType(t); setMessage(null) }}
                className={`text-xs px-4 py-2 rounded-lg border font-semibold transition-colors ${
                  msgType === t ? 'bg-blue-600 border-blue-600 text-white' : 'border-slate-200 text-slate-500 hover:border-blue-300 bg-white'
                }`}>
                {t === 'email' ? '✉ Cold Email' : t === 'linkedin' ? '💼 LinkedIn' : '☎ Call Script'}
              </button>
            ))}
            <button onClick={() => generateMutation.mutate()}
              disabled={!selectedId || generateMutation.isPending}
              className="ml-auto text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold px-5 py-2 rounded-lg transition-colors shadow-sm">
              {generateMutation.isPending ? 'Generating...' : '✦ Generate'}
            </button>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <span className="text-sm font-bold text-slate-700">Generated Message</span>
              {message && (
                <button onClick={() => navigator.clipboard.writeText(message.body)} className="text-xs bg-white hover:bg-slate-50 border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg">
                  Copy
                </button>
              )}
            </div>
            <div className="p-5">
              {generateMutation.isPending ? (
                <div className="flex items-center gap-2 text-blue-500 text-sm py-4">
                  <div className="flex gap-1">
                    {[0,1,2].map(i => <div key={i} className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />)}
                  </div>
                  Claude is personalising with NCUA data...
                </div>
              ) : message ? (
                <div>
                  {message.subject_line && (
                    <div className="text-xs font-semibold text-slate-400 mb-3">
                      SUBJECT: <span className="text-slate-700">{message.subject_line}</span>
                    </div>
                  )}
                  <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">{message.body}</pre>
                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-2">
                    <button onClick={() => generateMutation.mutate()} className="text-xs border border-slate-200 text-slate-400 hover:text-slate-600 px-3 py-1.5 rounded-lg bg-white">
                      ↺ Regenerate
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-slate-300">
                  <div className="text-3xl mb-3">✦</div>
                  <div className="text-sm font-medium text-slate-400">Select a lead and click Generate</div>
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="space-y-4">
          {companyDetail ? (
            <>
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Lead Context</div>
                <h3 className="font-bold text-slate-800 text-sm mb-1">{companyDetail.name}</h3>
                <Badge score={companyDetail.opportunity_score} />
                <div className="mt-3">
                  <StatusSelect value={companyDetail.outreach_status || 'new'} onChange={() => {}} />
                </div>
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
  const [form, setForm] = useState({
    company_name: user?.company_name || '',
    product_description: user?.product_description || '',
    key_strengths: '',
    differentiators: '',
    tone: user?.tone || 'consultative',
  })
  const [saved, setSaved] = useState(false)
  const saveMutation = useMutation({
    mutationFn: () => api.put('/api/auth/profile', form).then(r => r.data),
    onSuccess: () => { setSaved(true); loadUser(); setTimeout(() => setSaved(false), 3000) },
  })
  return (
    <div>
      <PageHeader
        title="Product Profile"
        sub="Powers all AI-generated outreach personalisation"
        action={
          <button onClick={() => saveMutation.mutate()} className="text-sm bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 py-2 rounded-lg transition-colors shadow-sm">
            {saveMutation.isPending ? 'Saving...' : saved ? '✓ Saved!' : 'Save Profile'}
          </button>
        }
      />
      <div className="p-8 max-w-2xl space-y-5">
        {(['company_name', 'product_description', 'key_strengths', 'differentiators'] as const).map(key => (
          <div key={key}>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">
              {key.replace(/_/g, ' ')}
            </label>
            {key === 'company_name' ? (
              <input className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
                value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
            ) : (
              <textarea rows={3} className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none shadow-sm"
                value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
            )}
          </div>
        ))}
        <div>
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Default AI Tone</label>
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
      </Routes>
    </BrowserRouter>
  )
}
