import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from './lib/api'
import { useAuthStore } from './store/authStore'

// ─── Design tokens ─────────────────────────────────────────────
// Primary: Blue #1D4ED8  Surface: White  Border: #E2E8F0
// Text primary: #0F172A  Text muted: #64748B  Accent: #3B82F6

// ─── Shared UI components ──────────────────────────────────────
const Badge = ({ score }: { score: number }) => {
  const cls = score >= 80
    ? 'bg-blue-50 text-blue-700 border-blue-200'
    : score >= 60
    ? 'bg-amber-50 text-amber-700 border-amber-200'
    : 'bg-red-50 text-red-600 border-red-200'
  const label = score >= 80 ? 'HIGH' : score >= 60 ? 'MED' : 'LOW'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border font-semibold ${cls}`}>
      {score} {label}
    </span>
  )
}

const StatusPill = ({ status }: { status: string }) => {
  const map: Record<string, string> = {
    new:       'bg-slate-100 text-slate-600 border-slate-200',
    contacted: 'bg-amber-50 text-amber-700 border-amber-200',
    replied:   'bg-green-50 text-green-700 border-green-200',
    qualified: 'bg-blue-50 text-blue-700 border-blue-200',
  }
  return (
    <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold border ${map[status] || 'bg-slate-100 text-slate-500 border-slate-200'}`}>
      {status}
    </span>
  )
}

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

// ─── Login page ────────────────────────────────────────────────
function LoginPage() {
  const [email, setEmail] = useState('demo@fintellipro.com')
  const [password, setPassword] = useState('demo1234')
  const [error, setError] = useState('')
  const { login, token } = useAuthStore()

  if (token) return <Navigate to="/dashboard" replace />

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await login(email, password)
    } catch {
      setError('Invalid credentials. Use demo@fintellipro.com / demo1234')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-slate-50 p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600 mb-4 shadow-lg">
            <span className="text-white font-black text-xl">LF</span>
          </div>
          <h1 className="text-3xl font-bold text-slate-900">LeadForge</h1>
          <p className="text-slate-500 text-sm mt-1.5">Credit Union Intelligence Platform</p>
        </div>

        {/* Card */}
        <div className="bg-white border border-slate-200 rounded-2xl p-7 shadow-md">
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Email</label>
              <input
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                value={email} onChange={e => setEmail(e.target.value)} type="email" required
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Password</label>
              <input
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                value={password} onChange={e => setPassword(e.target.value)} type="password" required
              />
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

// ─── Sidebar nav ───────────────────────────────────────────────
const NAV = [
  { to: '/dashboard', icon: '▦', label: 'Dashboard' },
  { to: '/leads',     icon: '◉', label: 'Leads' },
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
      {/* Sidebar */}
      <aside className="w-60 bg-white border-r border-slate-200 flex flex-col flex-shrink-0 shadow-sm">
        {/* Brand */}
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shadow-sm flex-shrink-0">
              <span className="text-white font-black text-sm">LF</span>
            </div>
            <div>
              <div className="text-sm font-bold text-slate-900">LeadForge</div>
              <div className="text-xs text-slate-400">v1.0 · NCUA Intelligence</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV.map(item => (
            <Link
              key={item.to}
              to={item.to}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                location.pathname === item.to
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
              }`}
            >
              <span className="text-base w-4 text-center">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>

        {/* User */}
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

      {/* Main */}
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  )
}

// ─── Page header component ─────────────────────────────────────
const PageHeader = ({ title, sub, action }: { title: string; sub: string; action?: React.ReactNode }) => (
  <div className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-slate-200 px-8 py-4 flex items-center justify-between">
    <div>
      <h1 className="text-lg font-bold text-slate-900">{title}</h1>
      <p className="text-xs text-slate-400 mt-0.5">{sub}</p>
    </div>
    {action}
  </div>
)

// ─── Dashboard ─────────────────────────────────────────────────
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
                    <td className="px-6 py-3.5 text-slate-500 text-xs capitalize">{co.industry?.replace('_',' ')}</td>
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

// ─── Leads page ────────────────────────────────────────────────
function Leads() {
  const [search, setSearch] = useState('')
  const [industry, setIndustry] = useState('')
  const [selected, setSelected] = useState<any>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['companies', search, industry],
    queryFn: () => api.get('/api/companies/', { params: { search, industry } }).then(r => r.data),
  })

  return (
    <div>
      <div className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-slate-200 px-8 py-4 flex items-center gap-4">
        <div className="flex-1">
          <h1 className="text-lg font-bold text-slate-900">Leads & Contacts</h1>
          <p className="text-xs text-slate-400 mt-0.5">NCUA-powered · Sorted by opportunity score</p>
        </div>
        <input
          className="bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 w-52 shadow-sm"
          placeholder="Search companies..."
          value={search} onChange={e => setSearch(e.target.value)}
        />
        <select
          className="bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
          value={industry} onChange={e => setIndustry(e.target.value)}
        >
          <option value="">All Industries</option>
          {['credit_unions','insurance','lending','healthcare','utilities','logistics','retail','wealth','government'].map(i => (
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
                  {['Company', 'Industry', 'Score', 'Maturity', 'Signals', 'Status', ''].map(h => (
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
                    <td className="px-6 py-3.5 text-xs text-slate-500 capitalize">{co.industry?.replace('_',' ')}</td>
                    <td className="px-6 py-3.5"><Badge score={co.opportunity_score} /></td>
                    <td className="px-6 py-3.5">
                      <div className="flex gap-0.5">
                        {[1,2,3,4,5].map(i => (
                          <div key={i} className={`w-3 h-2 rounded-sm ${i <= (co.digital_maturity||3) ? 'bg-blue-500' : 'bg-slate-200'}`} />
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-3.5">
                      <span className="text-xs font-semibold text-slate-500">{co.signal_count}</span>
                      <span className="text-xs text-slate-300 ml-1">signals</span>
                    </td>
                    <td className="px-6 py-3.5"><StatusPill status={co.outreach_status} /></td>
                    <td className="px-6 py-3.5">
                      <button
                        onClick={() => setSelected(co)}
                        className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold px-3 py-1.5 rounded-lg transition-colors shadow-sm"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(!data?.data || data.data.length === 0) && (
              <div className="text-center py-16 text-slate-400">
                <div className="text-4xl mb-3">◉</div>
                <div className="text-sm font-semibold text-slate-500">No leads yet</div>
                <div className="text-xs mt-1">Run the pipeline to pull credit unions</div>
                <Link to="/pipeline" className="inline-block mt-4 text-xs bg-blue-600 text-white font-semibold px-4 py-2 rounded-lg shadow-sm">
                  Run Discovery
                </Link>
              </div>
            )}
          </div>
        )}
      </div>

      {selected && <LeadDrawer company={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

// ─── Lead Drawer ───────────────────────────────────────────────
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
        {/* Header */}
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
            <p className="text-sm text-slate-500 capitalize">{company.industry?.replace('_',' ')} · {company.hq_city}, {company.hq_state}</p>
          </div>
          <button onClick={onClose} className="text-slate-300 hover:text-slate-600 text-xl transition-colors flex-shrink-0">✕</button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-100 px-7 bg-slate-50">
          {['overview', 'signals', 'contacts', 'outreach'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-3 mr-6 text-xs font-semibold border-b-2 transition-colors capitalize tracking-wide ${
                activeTab === tab ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-400 hover:text-slate-600'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="p-7 flex-1">
          {activeTab === 'overview' && detail && (
            <div className="space-y-3">
              {[
                ['Total Assets', detail.revenue_est ? `$${(detail.revenue_est / 1_000_000).toFixed(0)}M` : '—'],
                ['Employees', detail.employee_count || '—'],
                ['Tech Stack', (detail.tech_stack || []).filter(Boolean).join(', ') || '—'],
                ['Regulatory Source', detail.regulatory_src || '—'],
                ['Charter Number', detail.regulatory_data?.charter_number || '—'],
                ['Total Members', detail.regulatory_data?.total_members ? detail.regulatory_data.total_members.toLocaleString() : '—'],
                ['Net Worth Ratio', detail.regulatory_data?.net_worth_ratio ? `${detail.regulatory_data.net_worth_ratio}%` : '—'],
                ['Loan-to-Share', detail.regulatory_data?.loan_to_share_ratio ? `${detail.regulatory_data.loan_to_share_ratio}%` : '—'],
                ['Digital Maturity', `${detail.digital_maturity || '—'} / 5`],
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
                  : s.type === 'pain_point'    ? 'bg-amber-50 border-amber-100 text-amber-700'
                  : s.type === 'growth'         ? 'bg-green-50 border-green-100 text-green-700'
                  : 'bg-blue-50 border-blue-100 text-blue-700'
                }`}>
                  <div className="font-semibold">{s.label}</div>
                  <div className="text-xs opacity-60 mt-1 font-medium">{s.type} · severity {s.severity}/100 · {s.source}</div>
                </div>
              ))}
              {(!detail.signals || detail.signals.length === 0) && (
                <p className="text-slate-400 text-sm text-center py-10">No signals yet.</p>
              )}
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
                  {c.is_decision_maker && (
                    <span className="text-xs bg-blue-100 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full font-semibold">DM</span>
                  )}
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

// ─── AI Message Panel ──────────────────────────────────────────
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
    onSuccess: (data) => setMessage(data),
  })

  if (!firstContact) return <p className="text-slate-400 text-sm text-center py-10">No contacts found.</p>

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        {['email', 'linkedin', 'call_script'].map(t => (
          <button
            key={t}
            onClick={() => { setMsgType(t); setMessage(null) }}
            className={`text-xs px-3.5 py-1.5 rounded-lg border font-semibold transition-colors ${
              msgType === t ? 'bg-blue-600 border-blue-600 text-white' : 'border-slate-200 text-slate-500 hover:border-blue-300 hover:text-blue-600 bg-white'
            }`}
          >
            {t === 'email' ? '✉ Email' : t === 'linkedin' ? '💼 LinkedIn' : '☎ Call Script'}
          </button>
        ))}
      </div>

      <p className="text-xs text-slate-400">For: <span className="font-semibold text-slate-600">{firstContact.name}</span> · {firstContact.title}</p>

      {generateMutation.isPending ? (
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
          <div className="flex items-center gap-2 text-blue-600 text-sm">
            <div className="flex gap-1">
              {[0,1,2].map(i => <div key={i} className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />)}
            </div>
            Claude is generating your personalised message...
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
            <button onClick={() => generateMutation.mutate()} className="text-xs border border-slate-200 text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg transition-colors bg-white">
              ↺ Regenerate
            </button>
            <button onClick={() => navigator.clipboard.writeText(message.body)} className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold px-3 py-1.5 rounded-lg transition-colors">
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

// ─── AI Engine page ────────────────────────────────────────────
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
        {/* Controls */}
        <div className="col-span-2 space-y-5">
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">Select Lead</label>
            <select
              className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
              value={selectedId} onChange={e => { setSelectedId(e.target.value); setMessage(null) }}
            >
              <option value="">Choose a credit union...</option>
              {companies?.data?.map((co: any) => (
                <option key={co.id} value={co.id}>{co.name} — Score: {co.opportunity_score}</option>
              ))}
            </select>
          </div>

          <div className="flex gap-2 flex-wrap">
            {['email', 'linkedin', 'call_script'].map(t => (
              <button
                key={t}
                onClick={() => { setMsgType(t); setMessage(null) }}
                className={`text-xs px-4 py-2 rounded-lg border font-semibold transition-colors ${
                  msgType === t ? 'bg-blue-600 border-blue-600 text-white' : 'border-slate-200 text-slate-500 hover:border-blue-300 bg-white'
                }`}
              >
                {t === 'email' ? '✉ Cold Email' : t === 'linkedin' ? '💼 LinkedIn' : '☎ Call Script'}
              </button>
            ))}
            <button
              onClick={() => generateMutation.mutate()}
              disabled={!selectedId || generateMutation.isPending}
              className="ml-auto text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold px-5 py-2 rounded-lg transition-colors shadow-sm"
            >
              {generateMutation.isPending ? 'Generating...' : '✦ Generate'}
            </button>
          </div>

          {/* Output */}
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <span className="text-sm font-bold text-slate-700">
                {msgType === 'email' ? 'Cold Email' : msgType === 'linkedin' ? 'LinkedIn Message' : 'Call Script'}
              </span>
              {message && (
                <button onClick={() => navigator.clipboard.writeText(message.body)} className="text-xs bg-white hover:bg-slate-50 border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg transition-colors">
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
                  Claude is personalising your message using NCUA data...
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
                    <span className="text-xs text-slate-300 ml-auto">
                      {message.tokens_used ? `${message.tokens_used} tokens` : 'template mode'}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-slate-300">
                  <div className="text-3xl mb-3">✦</div>
                  <div className="text-sm font-medium text-slate-400">Ready to generate</div>
                  <div className="text-xs mt-1 text-slate-300">Select a lead and click Generate</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Context panel */}
        <div className="space-y-4">
          {companyDetail ? (
            <>
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Lead Context</div>
                <div className="flex items-center gap-2 mb-3">
                  <h3 className="font-bold text-slate-800 text-sm">{companyDetail.name}</h3>
                  <Badge score={companyDetail.opportunity_score} />
                </div>
                {[
                  ['Assets', companyDetail.revenue_est ? `$${(companyDetail.revenue_est/1e6).toFixed(0)}M` : '—'],
                  ['Members', companyDetail.regulatory_data?.total_members?.toLocaleString() || '—'],
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
                      : s.type === 'pain_point'   ? 'bg-amber-50 text-amber-600'
                      : 'bg-green-50 text-green-600'
                    }`}>
                      {s.label}
                    </div>
                  ))}
                </div>
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

// ─── Pipeline page ─────────────────────────────────────────────
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
              <button
                key={ind.id}
                onClick={() => runMutation.mutate(ind.id)}
                disabled={runMutation.isPending}
                className="bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-200 disabled:opacity-40 rounded-xl p-4 text-center transition-colors"
              >
                <div className="text-2xl mb-2">{ind.icon}</div>
                <div className="text-xs font-semibold text-slate-700">{ind.label}</div>
                <div className="text-xs text-slate-400 mt-1">Click to pull</div>
              </button>
            ))}
          </div>
          {runMutation.data && (
            <div className="mt-4 bg-green-50 border border-green-100 text-green-700 text-sm px-4 py-3 rounded-lg">
              ✓ {runMutation.data.message}
            </div>
          )}
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <h2 className="text-sm font-bold text-slate-800 mb-4">Pipeline Flow</h2>
          <div className="flex items-center gap-2 overflow-x-auto pb-2">
            {[
              { icon: '⊕', label: 'Apollo.ai', sub: 'Contacts' },
              { icon: '🏛️', label: 'NCUA', sub: '5300 Data' },
              { icon: '🌐', label: 'Web Scraper', sub: 'Core processor' },
              { icon: '📰', label: 'News', sub: 'RSS signals' },
              { icon: '✦', label: 'Claude AI', sub: 'Gap detection' },
              { icon: '◈', label: 'Scoring', sub: '0-100 score' },
              { icon: '🗄️', label: 'Database', sub: 'PostgreSQL' },
            ].map((node, i, arr) => (
              <div key={node.label} className="flex items-center gap-2 flex-shrink-0">
                <div className="border border-blue-100 bg-blue-50 rounded-xl p-3 text-center min-w-[110px]">
                  <div className="text-lg mb-1">{node.icon}</div>
                  <div className="text-xs font-semibold text-slate-700">{node.label}</div>
                  <div className="text-xs text-slate-400">{node.sub}</div>
                </div>
                {i < arr.length - 1 && <div className="text-slate-300 text-lg">→</div>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Campaigns ─────────────────────────────────────────────────
function Campaigns() {
  const { data: campaigns } = useQuery({
    queryKey: ['campaigns'],
    queryFn: () => api.get('/api/campaigns/').then(r => r.data),
  })

  return (
    <div>
      <PageHeader title="Campaigns" sub="Multi-channel outreach management" />

      <div className="p-8">
        {campaigns && campaigns.length > 0 ? (
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  {['Name', 'Industry', 'Sent', 'Opens', 'Replies', 'Status'].map(h => (
                    <th key={h} className="text-left px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c: any) => (
                  <tr key={c.id} className="border-b border-slate-50 hover:bg-blue-50/20 transition-colors">
                    <td className="px-6 py-3.5 font-semibold text-slate-800">{c.name}</td>
                    <td className="px-6 py-3.5 text-xs text-slate-500 capitalize">{c.industry?.replace('_',' ') || '—'}</td>
                    <td className="px-6 py-3.5 font-semibold text-slate-700">{c.total_sent}</td>
                    <td className="px-6 py-3.5 text-green-600 font-semibold">{c.total_opens} <span className="text-xs text-slate-400">({c.open_rate}%)</span></td>
                    <td className="px-6 py-3.5 text-blue-600 font-semibold">{c.total_replies} <span className="text-xs text-slate-400">({c.reply_rate}%)</span></td>
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
            <div className="text-xs mt-1 text-slate-300">Campaigns appear after you generate and send outreach</div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Settings ──────────────────────────────────────────────────
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

  const field = (label: string, key: keyof typeof form, multiline = false) => (
    <div key={key}>
      <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">{label}</label>
      {multiline ? (
        <textarea rows={3}
          className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none shadow-sm"
          value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        />
      ) : (
        <input
          className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
          value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        />
      )}
    </div>
  )

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
        {field('Your Company Name', 'company_name')}
        {field('Product / Platform Description', 'product_description', true)}
        {field('Key Strengths', 'key_strengths', true)}
        {field('Differentiators vs Competitors', 'differentiators', true)}
        <div>
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Default AI Tone</label>
          <select
            className="bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
            value={form.tone} onChange={e => setForm(f => ({ ...f, tone: e.target.value }))}
          >
            {['consultative', 'formal', 'friendly', 'data_driven'].map(t => (
              <option key={t} value={t}>{t.replace('_', ' ')}</option>
            ))}
          </select>
        </div>
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-sm text-blue-600">
          ℹ Add your Anthropic API key to .env to use live Claude AI for message generation.
        </div>
      </div>
    </div>
  )
}

// ─── Auth guard ────────────────────────────────────────────────
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

// ─── App root ──────────────────────────────────────────────────
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
        <Route path="/ai-engine" element={<RequireAuth><Layout><AIEngine /></Layout></RequireAuth>} />
        <Route path="/campaigns" element={<RequireAuth><Layout><Campaigns /></Layout></RequireAuth>} />
        <Route path="/pipeline"  element={<RequireAuth><Layout><Pipeline /></Layout></RequireAuth>} />
        <Route path="/settings"  element={<RequireAuth><Layout><Settings /></Layout></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  )
}
