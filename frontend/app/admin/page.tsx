'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'

export default function AdminPage() {
  const [token, setToken] = useState('')
  const [stats, setStats] = useState<any>(null)
  const [users, setUsers] = useState<any[]>([])
  const [audit, setAudit] = useState<any[]>([])
  const [mcpServers, setMcpServers] = useState<any[]>([])
  const [secrets, setSecrets] = useState<any[]>([])
  const [storeApps, setStoreApps] = useState<any[]>([])
  const [storeStats, setStoreStats] = useState<any>(null)
  const [tab, setTab] = useState<'stats' | 'users' | 'audit' | 'mcp' | 'secrets' | 'store' | 'reviews' | 'wallets' | 'networks' | 'providers' | 'onboarding'>('stats')
  const [onboardingStats, setOnboardingStats] = useState<any>(null)
  const [leads, setLeads] = useState<any[]>([])
  const [error, setError] = useState('')
  const [reviewSubs, setReviewSubs] = useState<any[]>([])
  const [reviewStats, setReviewStats] = useState<any>(null)
  const [selectedReview, setSelectedReview] = useState<any>(null)
  const [reviewNote, setReviewNote] = useState('')
  const [reviewMsg, setReviewMsg] = useState('')
  const [roleUserId, setRoleUserId] = useState('')
  const [roleValue, setRoleValue] = useState('operator')
  // Publish form state
  const [showPublish, setShowPublish] = useState(false)
  const [publishForm, setPublishForm] = useState({
    name: '', description: '', category: 'dapp', chain: '', version: '1.0.0',
    readme: '', icon_url: '', price_type: 'free', price_amount: '0',
    price_token: '', license_type: 'open', download_url: '', external_url: '',
    tags: '',
  })
  const [publishMsg, setPublishMsg] = useState('')

  useEffect(() => {
    const t = localStorage.getItem('refinet_token') || ''
    setToken(t)
  }, [])

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }

  const loadStats = async () => {
    try {
      const resp = await fetch(`${API_URL}/admin/stats`, { headers })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      setStats(await resp.json())
      setError('')
    } catch (e: any) {
      setError(e.message === 'HTTP 403' ? 'Admin role required' : e.message)
    }
  }

  const loadUsers = async () => {
    const resp = await fetch(`${API_URL}/admin/users`, { headers })
    if (resp.ok) setUsers(await resp.json())
  }

  const loadAudit = async () => {
    const resp = await fetch(`${API_URL}/admin/audit?limit=50`, { headers })
    if (resp.ok) setAudit(await resp.json())
  }

  useEffect(() => {
    if (!token) return
    loadStats()
  }, [token])

  const loadMcp = async () => {
    const resp = await fetch(`${API_URL}/admin/mcp`, { headers })
    if (resp.ok) setMcpServers(await resp.json())
  }

  const loadSecrets = async () => {
    const resp = await fetch(`${API_URL}/admin/secrets`, { headers })
    if (resp.ok) setSecrets(await resp.json())
  }

  const loadStoreApps = async () => {
    const resp = await fetch(`${API_URL}/admin/apps?include_inactive=true&page_size=50`, { headers })
    if (resp.ok) {
      const data = await resp.json()
      setStoreApps(data.apps || [])
    }
  }

  const loadStoreStats = async () => {
    const resp = await fetch(`${API_URL}/admin/apps/stats`, { headers })
    if (resp.ok) setStoreStats(await resp.json())
  }

  const grantRole = async (userId: string, role: string) => {
    await fetch(`${API_URL}/admin/users/${userId}/role`, {
      method: 'PUT', headers, body: JSON.stringify({ role, action: 'grant' }),
    })
    loadUsers()
  }

  const verifyApp = async (appId: string, verified: boolean) => {
    await fetch(`${API_URL}/admin/apps/${appId}/verify`, {
      method: 'PUT', headers, body: JSON.stringify({ verified }),
    })
    loadStoreApps()
  }

  const featureApp = async (appId: string, featured: boolean) => {
    await fetch(`${API_URL}/admin/apps/${appId}/feature`, {
      method: 'PUT', headers, body: JSON.stringify({ featured }),
    })
    loadStoreApps()
  }

  const setAppStatus = async (appId: string, active: boolean) => {
    await fetch(`${API_URL}/admin/apps/${appId}/status`, {
      method: 'PUT', headers, body: JSON.stringify({ active }),
    })
    loadStoreApps()
  }

  const publishProduct = async () => {
    setPublishMsg('')
    const body: any = {
      name: publishForm.name,
      description: publishForm.description,
      category: publishForm.category,
      version: publishForm.version,
      price_type: publishForm.price_type,
      price_amount: parseFloat(publishForm.price_amount) || 0,
      license_type: publishForm.license_type,
    }
    if (publishForm.chain) body.chain = publishForm.chain
    if (publishForm.readme) body.readme = publishForm.readme
    if (publishForm.icon_url) body.icon_url = publishForm.icon_url
    if (publishForm.price_token) body.price_token = publishForm.price_token
    if (publishForm.download_url) body.download_url = publishForm.download_url
    if (publishForm.external_url) body.external_url = publishForm.external_url
    if (publishForm.tags) body.tags = publishForm.tags.split(',').map((t: string) => t.trim()).filter(Boolean)

    try {
      const resp = await fetch(`${API_URL}/admin/apps/publish`, { method: 'POST', headers, body: JSON.stringify(body) })
      const data = await resp.json()
      if (resp.ok) {
        setPublishMsg(`Published: ${data.slug}`)
        setShowPublish(false)
        setPublishForm({ name: '', description: '', category: 'dapp', chain: '', version: '1.0.0', readme: '', icon_url: '', price_type: 'free', price_amount: '0', price_token: '', license_type: 'open', download_url: '', external_url: '', tags: '' })
        loadStoreApps()
        loadStoreStats()
      } else {
        setPublishMsg(data.detail || 'Publish failed')
      }
    } catch {
      setPublishMsg('Publish failed')
    }
  }

  const loadReviewSubs = async (statusFilter?: string) => {
    const params = statusFilter ? `?status=${statusFilter}` : '?page_size=50'
    const resp = await fetch(`${API_URL}/admin/submissions${params}`, { headers })
    if (resp.ok) { const data = await resp.json(); setReviewSubs(data.submissions || []) }
  }
  const loadReviewStats = async () => {
    const resp = await fetch(`${API_URL}/admin/submissions/stats`, { headers })
    if (resp.ok) setReviewStats(await resp.json())
  }
  const loadReviewDetail = async (id: string) => {
    const resp = await fetch(`${API_URL}/admin/submissions/${id}`, { headers })
    if (resp.ok) setSelectedReview(await resp.json())
  }
  const claimReview = async (id: string) => {
    setReviewMsg('')
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/claim`, { method: 'PUT', headers })
    const d = await resp.json(); setReviewMsg(d.message || d.detail || ''); loadReviewDetail(id); loadReviewSubs()
  }
  const approveReview = async (id: string) => {
    setReviewMsg('')
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/approve`, { method: 'PUT', headers, body: JSON.stringify({ note: reviewNote }) })
    const d = await resp.json(); setReviewMsg(d.message || d.detail || ''); if (resp.ok) { setSelectedReview(null); loadReviewSubs(); loadReviewStats() }
  }
  const rejectReview = async (id: string) => {
    if (!reviewNote) { setReviewMsg('Rejection reason required'); return }
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/reject`, { method: 'PUT', headers, body: JSON.stringify({ reason: reviewNote }) })
    const d = await resp.json(); setReviewMsg(d.message || d.detail || ''); if (resp.ok) { setSelectedReview(null); loadReviewSubs(); loadReviewStats() }
  }
  const requestChanges = async (id: string) => {
    if (!reviewNote) { setReviewMsg('Reason required'); return }
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/request-changes`, { method: 'PUT', headers, body: JSON.stringify({ reason: reviewNote }) })
    const d = await resp.json(); setReviewMsg(d.message || d.detail || ''); if (resp.ok) loadReviewDetail(id)
  }
  const provisionSandbox = async (id: string) => {
    setReviewMsg('')
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/sandbox`, { method: 'POST', headers, body: '{}' })
    const d = await resp.json(); setReviewMsg(d.access_url ? `Sandbox running at ${d.access_url}` : d.detail || d.error || 'Sandbox provisioned'); loadReviewDetail(id)
  }
  const destroySandbox = async (id: string) => {
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/sandbox`, { method: 'DELETE', headers })
    const d = await resp.json(); setReviewMsg(d.message || d.detail || ''); loadReviewDetail(id)
  }
  const addAdminNote = async (id: string) => {
    if (!reviewNote) return
    await fetch(`${API_URL}/admin/submissions/${id}/notes`, { method: 'POST', headers, body: JSON.stringify({ content: reviewNote, note_type: 'comment' }) })
    setReviewNote(''); loadReviewDetail(id)
  }

  useEffect(() => {
    if (!token) return
    if (tab === 'users') loadUsers()
    if (tab === 'audit') loadAudit()
    if (tab === 'mcp') loadMcp()
    if (tab === 'secrets') loadSecrets()
    if (tab === 'store') { loadStoreApps(); loadStoreStats() }
    if (tab === 'reviews') { loadReviewSubs(); loadReviewStats(); setSelectedReview(null) }
  }, [tab, token])

  if (error) {
    return (
      <div className="max-w-2xl mx-auto py-20 px-6 text-center">
        <h1 className="text-2xl font-bold mb-4 text-red-400" style={{ letterSpacing: '-0.02em' }}>Access Denied</h1>
        <p style={{ color: 'var(--text-secondary)' }}>{error}</p>
      </div>
    )
  }

  const tabs = ['stats', 'onboarding', 'users', 'reviews', 'store', 'providers', 'wallets', 'networks', 'audit', 'mcp', 'secrets'] as const

  return (
    <div className="max-w-6xl mx-auto py-10 px-6">
      <h1 className="text-2xl font-bold mb-6" style={{ letterSpacing: '-0.02em' }}>Admin Panel</h1>

      {/* Tabs */}
      <div className="flex gap-1 mb-8 overflow-x-auto" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-4 py-2 text-xs font-mono transition-colors whitespace-nowrap"
            style={{
              color: tab === t ? 'var(--refi-teal)' : 'var(--text-tertiary)',
              borderBottom: tab === t ? '2px solid var(--refi-teal)' : '2px solid transparent',
            }}
          >
            {t === 'store' ? 'APP STORE' : t === 'reviews' ? 'REVIEWS' : t === 'wallets' ? 'WALLETS' : t === 'networks' ? 'NETWORKS' : t === 'providers' ? 'AI PROVIDERS' : t === 'onboarding' ? 'ONBOARDING' : t.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Onboarding Funnel & Leads */}
      {tab === 'onboarding' && <OnboardingPanel headers={headers} onboardingStats={onboardingStats} setOnboardingStats={setOnboardingStats} leads={leads} setLeads={setLeads} />}

      {/* Stats */}
      {tab === 'stats' && stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(stats).map(([k, v]) => (
            <div key={k} className="card p-4">
              <div className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{k.replace(/_/g, ' ')}</div>
              <div className="text-xl font-bold" style={{ color: 'var(--refi-teal)' }}>{String(v)}</div>
            </div>
          ))}
        </div>
      )}

      {/* Users */}
      {tab === 'users' && (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]">
            <thead style={{ background: 'var(--bg-elevated)' }}>
              <tr>
                {['Username', 'Email', 'Tier', 'Wallet', 'Roles'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u: any) => (
                <tr key={u.id} className="transition-colors" style={{ borderTop: '1px solid var(--border-subtle)' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <td className="px-4 py-3 font-mono">{u.username}</td>
                  <td className="px-4 py-3">{u.email}</td>
                  <td className="px-4 py-3">{u.tier}</td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {u.eth_address ? `${u.eth_address.slice(0, 6)}...` : '-'}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    <div className="flex items-center gap-2">
                      <span>{(u.roles || []).join(', ') || '-'}</span>
                      <select className="text-[10px] px-1 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)' }}
                        value="" onChange={e => { if (e.target.value) grantRole(u.id, e.target.value); e.target.value = '' }}>
                        <option value="">+ role</option>
                        <option value="admin">admin</option>
                        <option value="operator">operator</option>
                        <option value="readonly">readonly</option>
                      </select>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Audit */}
      {tab === 'audit' && (
        <div className="space-y-1">
          {audit.map((l: any) => (
            <div key={l.id} className="flex items-center gap-4 px-4 py-2 text-xs font-mono" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <span className="w-44" style={{ color: 'var(--text-tertiary)' }}>{l.timestamp}</span>
              <span className="w-24" style={{ color: 'var(--text-primary)' }}>{l.admin_username}</span>
              <span className="w-28" style={{ color: 'var(--refi-teal)' }}>{l.action}</span>
              <span style={{ color: 'var(--text-tertiary)' }}>{l.target_type}:{l.target_id || '-'}</span>
            </div>
          ))}
          {audit.length === 0 && <p className="text-sm p-4" style={{ color: 'var(--text-tertiary)' }}>No audit entries yet.</p>}
        </div>
      )}

      {/* MCP Servers */}
      {tab === 'mcp' && (
        <div className="card overflow-hidden overflow-x-auto">
          {mcpServers.length === 0 ? (
            <p className="text-sm p-6" style={{ color: 'var(--text-tertiary)' }}>No MCP servers registered. Use admin API to register.</p>
          ) : (
            <table className="w-full text-sm min-w-[500px]">
              <thead style={{ background: 'var(--bg-elevated)' }}>
                <tr>
                  {['Name', 'URL', 'Transport', 'Status', 'Last Check'].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {mcpServers.map((s: any) => (
                  <tr key={s.id} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                    <td className="px-4 py-3 font-mono">{s.name}</td>
                    <td className="px-4 py-3 text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>{s.url}</td>
                    <td className="px-4 py-3 text-xs">{s.transport}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-2 py-0.5 rounded" style={{ background: s.is_healthy ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)', color: s.is_healthy ? 'var(--success)' : 'var(--error)' }}>
                        {s.is_healthy ? 'healthy' : 'unhealthy'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>{s.last_health_check_at ? new Date(s.last_health_check_at).toLocaleString() : 'never'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Secrets */}
      {tab === 'secrets' && (
        <div className="card overflow-hidden overflow-x-auto">
          <p className="text-xs px-4 pt-3 pb-2" style={{ color: 'var(--text-tertiary)' }}>Secrets are AES-256-GCM encrypted at rest. Values are never displayed.</p>
          {secrets.length === 0 ? (
            <p className="text-sm p-6" style={{ color: 'var(--text-tertiary)' }}>No secrets stored.</p>
          ) : (
            <table className="w-full text-sm min-w-[400px]">
              <thead style={{ background: 'var(--bg-elevated)' }}>
                <tr>
                  {['Name', 'Description', 'Created By', 'Created'].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {secrets.map((s: any) => (
                  <tr key={s.id || s.name} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                    <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--refi-teal)' }}>{s.name}</td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-secondary)' }}>{s.description || '-'}</td>
                    <td className="px-4 py-3 text-xs">{s.created_by}</td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>{s.created_at ? new Date(s.created_at).toLocaleDateString() : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Submission Reviews */}
      {tab === 'reviews' && (
        <div>
          {/* Review Stats */}
          {reviewStats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                { label: 'Pending Review', value: reviewStats.pending_review, color: '#60a5fa' },
                { label: 'In Review', value: reviewStats.in_review, color: '#a855f7' },
                { label: 'Approved', value: reviewStats.approved, color: '#4ade80' },
                { label: 'Rejected', value: reviewStats.rejected, color: '#f87171' },
              ].map(s => (
                <div key={s.label} className="card p-3">
                  <div className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{s.label}</div>
                  <div className="text-lg font-bold" style={{ color: s.color }}>{s.value}</div>
                </div>
              ))}
            </div>
          )}

          {reviewMsg && <div className="mb-4 px-3 py-2 rounded text-xs" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>{reviewMsg}</div>}

          {/* Filter buttons */}
          <div className="flex gap-2 mb-4 flex-wrap">
            {['all', 'submitted', 'in_review', 'changes_requested', 'approved', 'rejected'].map(f => (
              <button key={f} onClick={() => loadReviewSubs(f === 'all' ? undefined : f)}
                className="text-[10px] px-2 py-1 rounded font-mono" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>
                {f.replace(/_/g, ' ')}
              </button>
            ))}
          </div>

          {!selectedReview ? (
            /* Submissions List */
            <div className="card overflow-hidden overflow-x-auto">
              {reviewSubs.length === 0 ? (
                <p className="text-sm p-6" style={{ color: 'var(--text-tertiary)' }}>No submissions found.</p>
              ) : (
                <table className="w-full text-sm min-w-[700px]">
                  <thead style={{ background: 'var(--bg-elevated)' }}>
                    <tr>
                      {['App', 'Category', 'Submitter', 'Status', 'Scan', 'Submitted', 'Actions'].map(h => (
                        <th key={h} className="text-left px-3 py-2.5 text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {reviewSubs.map((s: any) => {
                      const sc: any = { draft: '#94a3b8', submitted: '#60a5fa', automated_review: '#fbbf24', in_review: '#a855f7', changes_requested: '#fb923c', approved: '#4ade80', rejected: '#f87171', published: '#4ade80' }
                      return (
                        <tr key={s.id} style={{ borderTop: '1px solid var(--border-subtle)' }}
                          onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                          onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                          <td className="px-3 py-2.5">
                            <div className="font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{s.name}</div>
                            <div className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>v{s.version} · {s.submission_type}</div>
                          </td>
                          <td className="px-3 py-2.5 text-xs">{s.category}</td>
                          <td className="px-3 py-2.5 text-xs" style={{ color: 'var(--text-secondary)' }}>@{s.submitter_username || '?'}</td>
                          <td className="px-3 py-2.5">
                            <span className="text-[9px] px-1.5 py-0.5 rounded font-mono" style={{ color: sc[s.status] || '#94a3b8' }}>
                              {s.status.replace(/_/g, ' ')}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-[10px]">
                            {s.automated_scan_status === 'passed' ? <span style={{ color: '#4ade80' }}>passed</span>
                              : s.automated_scan_status === 'failed' ? <span style={{ color: '#f87171' }}>failed</span>
                              : <span style={{ color: 'var(--text-tertiary)' }}>{s.automated_scan_status || '-'}</span>}
                          </td>
                          <td className="px-3 py-2.5 text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                            {s.submitted_at ? new Date(s.submitted_at).toLocaleDateString() : '-'}
                          </td>
                          <td className="px-3 py-2.5">
                            <button onClick={() => loadReviewDetail(s.id)} className="text-[10px] px-2 py-0.5 rounded"
                              style={{ background: 'var(--refi-teal)', color: '#000', border: 'none', cursor: 'pointer' }}>
                              Review
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          ) : (
            /* Review Detail */
            <div>
              <button onClick={() => setSelectedReview(null)} className="text-xs mb-4" style={{ color: 'var(--refi-teal)', background: 'none', border: 'none', cursor: 'pointer' }}>
                Back to list
              </button>

              <div className="card p-5 mb-4" style={{ border: '1px solid var(--border-default)' }}>
                <div className="flex items-center gap-3 mb-3">
                  <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{selectedReview.name}</h2>
                  <span className="text-[10px] px-2 py-0.5 rounded font-mono" style={{ color: ({ submitted: '#60a5fa', in_review: '#a855f7', changes_requested: '#fb923c', approved: '#4ade80', rejected: '#f87171' } as any)[selectedReview.status] || '#94a3b8' }}>
                    {selectedReview.status.replace(/_/g, ' ')}
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
                  {[['Submitter', `@${selectedReview.submitter_username}`], ['Category', selectedReview.category], ['Version', selectedReview.version], ['Price', selectedReview.price_type === 'free' ? 'Free' : `$${selectedReview.price_amount}`]].map(([k, v]) => (
                    <div key={k as string}><span style={{ color: 'var(--text-tertiary)' }}>{k}: </span><span style={{ color: 'var(--text-primary)' }}>{v}</span></div>
                  ))}
                </div>

                {selectedReview.description && <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>{selectedReview.description}</p>}

                {selectedReview.artifact_filename && (
                  <div className="text-xs mb-3 font-mono" style={{ color: 'var(--text-secondary)' }}>
                    Artifact: <span style={{ color: 'var(--refi-teal)' }}>{selectedReview.artifact_filename}</span>
                    ({selectedReview.artifact_size_bytes ? `${(selectedReview.artifact_size_bytes / 1024).toFixed(0)} KB` : '?'})
                    {selectedReview.artifact_hash && <span className="text-[9px] ml-1" style={{ color: 'var(--text-tertiary)' }}>SHA256: {selectedReview.artifact_hash.slice(0, 16)}...</span>}
                  </div>
                )}

                {/* Scan Results */}
                {selectedReview.automated_scan_result && (
                  <div className="p-3 mb-3 rounded text-xs" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                    <div className="font-mono mb-1" style={{ color: 'var(--text-tertiary)' }}>AUTOMATED SCAN: <span style={{ color: selectedReview.automated_scan_status === 'passed' ? '#4ade80' : '#f87171' }}>{selectedReview.automated_scan_status}</span></div>
                    <div style={{ color: 'var(--text-tertiary)' }}>{selectedReview.automated_scan_result.file_count} files · {selectedReview.automated_scan_result.critical_count} critical · {selectedReview.automated_scan_result.warning_count} warnings</div>
                    {selectedReview.automated_scan_result.findings?.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {selectedReview.automated_scan_result.findings.slice(0, 10).map((f: any, i: number) => (
                          <div key={i} className="flex gap-2" style={{ color: f.severity === 'critical' ? '#f87171' : f.severity === 'warning' ? '#fbbf24' : 'var(--text-tertiary)' }}>
                            <span className="font-mono w-12">[{f.severity}]</span>
                            <span className="font-mono">{f.file}</span>
                            <span>{f.issue}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Admin Actions */}
                <div className="flex gap-2 flex-wrap mb-3">
                  {selectedReview.status === 'submitted' && (
                    <button onClick={() => claimReview(selectedReview.id)} className="px-3 py-1.5 text-xs rounded font-semibold"
                      style={{ background: 'var(--refi-teal)', color: '#000', cursor: 'pointer' }}>Claim for Review</button>
                  )}
                  {selectedReview.status === 'in_review' && (
                    <>
                      <button onClick={() => provisionSandbox(selectedReview.id)} className="px-3 py-1.5 text-xs rounded"
                        style={{ background: 'rgba(168,85,247,0.15)', color: '#a855f7', border: 'none', cursor: 'pointer' }}>Launch Sandbox</button>
                      <button onClick={() => destroySandbox(selectedReview.id)} className="px-3 py-1.5 text-xs rounded"
                        style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>Destroy Sandbox</button>
                      <button onClick={() => approveReview(selectedReview.id)} className="px-3 py-1.5 text-xs rounded font-semibold"
                        style={{ background: 'rgba(74,222,128,0.15)', color: '#4ade80', border: 'none', cursor: 'pointer' }}>Approve & Publish</button>
                      <button onClick={() => requestChanges(selectedReview.id)} className="px-3 py-1.5 text-xs rounded"
                        style={{ background: 'rgba(251,146,60,0.15)', color: '#fb923c', border: 'none', cursor: 'pointer' }}>Request Changes</button>
                      <button onClick={() => rejectReview(selectedReview.id)} className="px-3 py-1.5 text-xs rounded"
                        style={{ background: 'rgba(248,113,113,0.15)', color: '#f87171', border: 'none', cursor: 'pointer' }}>Reject</button>
                    </>
                  )}
                </div>

                {/* Review Note Input */}
                {['in_review', 'submitted'].includes(selectedReview.status) && (
                  <div className="flex gap-2">
                    <input value={reviewNote} onChange={e => setReviewNote(e.target.value)} placeholder="Add review note / reason..."
                      className="flex-1 px-2 py-1.5 text-xs rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }} />
                    <button onClick={() => addAdminNote(selectedReview.id)} className="px-3 py-1.5 text-xs rounded"
                      style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>Add Note</button>
                  </div>
                )}
              </div>

              {/* Review Thread */}
              {selectedReview.notes?.length > 0 && (
                <div>
                  <h3 className="text-xs font-mono mb-2 uppercase" style={{ color: 'var(--text-tertiary)' }}>Review Thread</h3>
                  <div className="space-y-2">
                    {selectedReview.notes.map((n: any) => (
                      <div key={n.id} className="card p-3" style={{ border: '1px solid var(--border-subtle)', borderLeft: n.note_type === 'request_changes' ? '3px solid #fb923c' : n.note_type === 'rejection' ? '3px solid #f87171' : n.note_type === 'approval' ? '3px solid #4ade80' : '3px solid var(--border-subtle)' }}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{n.author_username || 'System'}</span>
                          <span className="text-[9px] px-1 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>{n.note_type}</span>
                          <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{n.created_at ? new Date(n.created_at).toLocaleString() : ''}</span>
                        </div>
                        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{n.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* AI Model Providers */}
      {tab === 'providers' && <ModelProviderPanel headers={headers} />}

      {/* GROOT Wallet + Pending Actions + Wallet Provider Management */}
      {tab === 'wallets' && (
        <div className="space-y-6">
          <GrootWalletPanel />
          <PendingActionsPanel />
          <WalletProviderPanel />
        </div>
      )}

      {/* Network Management */}
      {tab === 'networks' && <NetworksPanel />}

      {/* App Store Management */}
      {tab === 'store' && (
        <div>
          {/* Store Stats */}
          {storeStats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                { label: 'Total Apps', value: storeStats.total_apps },
                { label: 'Published', value: storeStats.published_apps },
                { label: 'Verified', value: storeStats.verified_apps },
                { label: 'Featured', value: storeStats.featured_apps },
                { label: 'Total Installs', value: storeStats.total_installs },
                { label: 'Total Reviews', value: storeStats.total_reviews },
                { label: 'Total Downloads', value: storeStats.total_downloads },
              ].map(s => (
                <div key={s.label} className="card p-3">
                  <div className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{s.label}</div>
                  <div className="text-lg font-bold" style={{ color: 'var(--refi-teal)' }}>{s.value}</div>
                </div>
              ))}
              {/* Category breakdown */}
              {storeStats.categories && Object.keys(storeStats.categories).length > 0 && (
                <div className="card p-3">
                  <div className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>By Category</div>
                  <div className="text-[10px] space-y-0.5">
                    {Object.entries(storeStats.categories).map(([cat, count]) => (
                      <div key={cat} className="flex justify-between" style={{ color: 'var(--text-secondary)' }}>
                        <span>{cat}</span><span className="font-mono">{String(count)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Publish Button */}
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={() => setShowPublish(!showPublish)}
              className="px-4 py-2 text-xs font-semibold rounded-lg"
              style={{ background: 'var(--refi-teal)', color: '#000', cursor: 'pointer' }}
            >
              {showPublish ? 'Cancel' : 'Publish Product'}
            </button>
            {publishMsg && <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{publishMsg}</span>}
          </div>

          {/* Publish Form */}
          {showPublish && (
            <div className="card p-4 mb-6" style={{ border: '1px solid var(--border-default)' }}>
              <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>List Product in App Store</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {[
                  { key: 'name', label: 'Name *', type: 'text' },
                  { key: 'version', label: 'Version', type: 'text' },
                  { key: 'icon_url', label: 'Icon URL', type: 'text' },
                  { key: 'chain', label: 'Chain', type: 'text' },
                  { key: 'price_amount', label: 'Price (USD)', type: 'number' },
                  { key: 'price_token', label: 'Token Symbol', type: 'text' },
                  { key: 'download_url', label: 'Download URL', type: 'text' },
                  { key: 'external_url', label: 'External URL', type: 'text' },
                  { key: 'tags', label: 'Tags (comma-separated)', type: 'text' },
                ].map(f => (
                  <div key={f.key}>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>{f.label}</label>
                    <input
                      type={f.type}
                      value={(publishForm as any)[f.key]}
                      onChange={e => setPublishForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                      className="w-full px-2 py-1.5 text-xs rounded"
                      style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }}
                    />
                  </div>
                ))}
                <div>
                  <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Category *</label>
                  <select value={publishForm.category} onChange={e => setPublishForm(prev => ({ ...prev, category: e.target.value }))}
                    className="w-full px-2 py-1.5 text-xs rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
                    {['dapp', 'agent', 'tool', 'template', 'dataset', 'api-service', 'digital-asset'].map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Price Type</label>
                  <select value={publishForm.price_type} onChange={e => setPublishForm(prev => ({ ...prev, price_type: e.target.value }))}
                    className="w-full px-2 py-1.5 text-xs rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
                    {['free', 'one-time', 'subscription'].map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>License</label>
                  <select value={publishForm.license_type} onChange={e => setPublishForm(prev => ({ ...prev, license_type: e.target.value }))}
                    className="w-full px-2 py-1.5 text-xs rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
                    {['open', 'single-use', 'multi-use', 'enterprise'].map(l => <option key={l} value={l}>{l}</option>)}
                  </select>
                </div>
              </div>
              <div className="mt-3">
                <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Description</label>
                <textarea value={publishForm.description} onChange={e => setPublishForm(prev => ({ ...prev, description: e.target.value }))}
                  rows={2} className="w-full px-2 py-1.5 text-xs rounded"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none', resize: 'vertical' }} />
              </div>
              <div className="mt-3">
                <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>README (Markdown)</label>
                <textarea value={publishForm.readme} onChange={e => setPublishForm(prev => ({ ...prev, readme: e.target.value }))}
                  rows={4} className="w-full px-2 py-1.5 text-xs rounded font-mono"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none', resize: 'vertical' }} />
              </div>
              <button onClick={publishProduct} className="mt-3 px-4 py-2 text-xs font-semibold rounded-lg"
                style={{ background: 'var(--refi-teal)', color: '#000', cursor: 'pointer' }}>
                Publish to Store
              </button>
            </div>
          )}

          {/* Apps Table */}
          <div className="card overflow-hidden overflow-x-auto">
            {storeApps.length === 0 ? (
              <p className="text-sm p-6" style={{ color: 'var(--text-tertiary)' }}>No apps in the store yet. Publish your first product above.</p>
            ) : (
              <table className="w-full text-sm min-w-[800px]">
                <thead style={{ background: 'var(--bg-elevated)' }}>
                  <tr>
                    {['Name', 'Category', 'Owner', 'Price', 'Installs', 'Rating', 'Status', 'Actions'].map(h => (
                      <th key={h} className="text-left px-3 py-2.5 text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {storeApps.map((app: any) => (
                    <tr key={app.id} style={{ borderTop: '1px solid var(--border-subtle)' }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                      <td className="px-3 py-2.5">
                        <div className="font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{app.name}</div>
                        <div className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{app.slug}</div>
                      </td>
                      <td className="px-3 py-2.5 text-xs">{app.category}</td>
                      <td className="px-3 py-2.5 text-xs" style={{ color: 'var(--text-secondary)' }}>{app.owner_username || 'platform'}</td>
                      <td className="px-3 py-2.5 text-xs font-mono">
                        {app.price_type === 'free' ? (
                          <span style={{ color: 'var(--success)' }}>FREE</span>
                        ) : (
                          <span>${app.price_amount}</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-xs font-mono">{app.install_count}</td>
                      <td className="px-3 py-2.5 text-xs">
                        {app.rating_count > 0 ? `${app.rating_avg.toFixed(1)} (${app.rating_count})` : '-'}
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-1.5">
                          {app.is_verified && <span className="text-[9px] px-1 py-0.5 rounded" style={{ background: 'rgba(74,222,128,0.15)', color: 'var(--success)' }}>verified</span>}
                          {app.is_featured && <span className="text-[9px] px-1 py-0.5 rounded" style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}>featured</span>}
                          {app.listed_by_admin && <span className="text-[9px] px-1 py-0.5 rounded" style={{ background: 'rgba(96,165,250,0.15)', color: '#60a5fa' }}>platform</span>}
                          {!app.is_published && <span className="text-[9px] px-1 py-0.5 rounded" style={{ background: 'rgba(248,113,113,0.15)', color: 'var(--error)' }}>unpublished</span>}
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex gap-1">
                          <button onClick={() => verifyApp(app.id, !app.is_verified)} className="text-[9px] px-1.5 py-0.5 rounded"
                            style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>
                            {app.is_verified ? 'Unverify' : 'Verify'}
                          </button>
                          <button onClick={() => featureApp(app.id, !app.is_featured)} className="text-[9px] px-1.5 py-0.5 rounded"
                            style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>
                            {app.is_featured ? 'Unfeature' : 'Feature'}
                          </button>
                          <button onClick={() => setAppStatus(app.id, !app.is_active)} className="text-[9px] px-1.5 py-0.5 rounded"
                            style={{ background: app.is_active ? 'rgba(248,113,113,0.15)' : 'rgba(74,222,128,0.15)', color: app.is_active ? 'var(--error)' : 'var(--success)', border: 'none', cursor: 'pointer' }}>
                            {app.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  )
}


/* ─── Wallet Provider Configuration Panel ─── */
function NetworksPanel() {
  const [chains, setChains] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [importId, setImportId] = useState('')
  const [importing, setImporting] = useState(false)
  const [msg, setMsg] = useState('')

  const headers: any = { 'Content-Type': 'application/json' }
  const token = typeof window !== 'undefined' ? localStorage.getItem('refinet_token') : null
  if (token) headers.Authorization = `Bearer ${token}`

  const fetchChains = async () => {
    try {
      const resp = await fetch(`${API_URL}/admin/chains`, { headers })
      if (resp.ok) setChains(await resp.json())
    } catch {}
    setLoading(false)
  }

  useEffect(() => { fetchChains() }, [])

  const importFromChainlist = async () => {
    const chainId = parseInt(importId)
    if (!chainId || isNaN(chainId)) { setMsg('Enter a valid chain ID (number)'); return }
    setImporting(true); setMsg('')
    try {
      const resp = await fetch(`${API_URL}/admin/chains/import`, {
        method: 'POST', headers, body: JSON.stringify({ chain_id: chainId })
      })
      const data = await resp.json()
      if (!resp.ok) { setMsg(data.detail || 'Import failed'); setImporting(false); return }
      setMsg(`Imported: ${data.name} (${data.short_name})`)
      setImportId('')
      fetchChains()
    } catch (e: any) { setMsg(e.message) }
    setImporting(false)
  }

  const toggleChain = async (chainId: number, active: boolean) => {
    await fetch(`${API_URL}/admin/chains/${chainId}`, {
      method: 'PUT', headers, body: JSON.stringify({ is_active: active })
    })
    fetchChains()
  }

  return (
    <div className="card p-6" style={{ border: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontWeight: 700, fontSize: 16 }}>EVM Networks ({chains.length})</h3>
        <button onClick={() => setShowAdd(!showAdd)}
          style={{ background: '#FF6B00', color: 'white', border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
          + Add Network
        </button>
      </div>

      {showAdd && (
        <div style={{ marginBottom: 16, padding: 16, border: '1px solid var(--border-subtle)', borderRadius: 8 }}>
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Import from Chainlist.org</h4>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
            Enter a chain ID to auto-import network config (RPC, explorer, currency).
            Find chain IDs at <a href="https://chainlist.org" target="_blank" rel="noopener noreferrer" style={{ color: '#FF6B00' }}>chainlist.org</a>
          </p>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input value={importId} onChange={e => setImportId(e.target.value)} placeholder="Chain ID (e.g., 43114 for Avalanche)"
              style={{ flex: 1, background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', fontSize: 12 }} />
            <button onClick={importFromChainlist} disabled={importing}
              style={{ background: '#FF6B00', color: 'white', border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: importing ? 0.5 : 1 }}>
              {importing ? 'Importing...' : 'Import'}
            </button>
          </div>
          {msg && <p style={{ fontSize: 11, color: msg.includes('Imported') ? '#10B981' : '#EF4444', marginTop: 6 }}>{msg}</p>}
        </div>
      )}

      {loading && <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading...</p>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {chains.map((c: any) => (
          <div key={c.chain_id} style={{
            padding: 12, borderRadius: 8, border: '1px solid var(--border-subtle)',
            opacity: c.is_active ? 1 : 0.5,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                {c.name}
                {c.is_testnet && <span style={{ fontSize: 10, color: '#F59E0B', marginLeft: 6 }}>TESTNET</span>}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                ID: {c.chain_id} | {c.short_name} | {c.currency}
              </div>
            </div>
            <button onClick={() => toggleChain(c.chain_id, !c.is_active)}
              style={{
                fontSize: 10, padding: '3px 8px', borderRadius: 4, border: 'none', cursor: 'pointer',
                background: c.is_active ? '#10B98120' : '#EF444420',
                color: c.is_active ? '#10B981' : '#EF4444',
                fontWeight: 600,
              }}>
              {c.is_active ? 'Active' : 'Inactive'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

function GrootWalletPanel() {
  const [wallet, setWallet] = useState<any>(null)
  const [balances, setBalances] = useState<Record<string, any>>({})
  const [transactions, setTransactions] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [balanceChain, setBalanceChain] = useState('base')

  const headers: any = { 'Content-Type': 'application/json' }
  const token = typeof window !== 'undefined' ? localStorage.getItem('refinet_token') : null
  if (token) headers.Authorization = `Bearer ${token}`

  useEffect(() => {
    const fetchWallet = async () => {
      try {
        const resp = await fetch(`${API_URL}/admin/wallet`, { headers })
        if (resp.ok) setWallet(await resp.json())
      } catch {}
      setLoading(false)
    }
    fetchWallet()
  }, [])

  const fetchBalance = async (chain: string) => {
    try {
      const resp = await fetch(`${API_URL}/admin/wallet/balance/${chain}`, { headers })
      if (resp.ok) {
        const data = await resp.json()
        setBalances(prev => ({ ...prev, [chain]: data }))
      }
    } catch {}
  }

  const fetchTransactions = async () => {
    try {
      const resp = await fetch(`${API_URL}/admin/wallet/transactions?limit=20`, { headers })
      if (resp.ok) setTransactions(await resp.json())
    } catch {}
  }

  if (loading) return <div className="card p-6"><p style={{ color: 'var(--text-muted)' }}>Loading GROOT wallet...</p></div>
  if (!wallet) return (
    <div className="card p-6" style={{ border: '1px solid var(--border-subtle)' }}>
      <h3 style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>GROOT Wallet</h3>
      <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
        GROOT wallet not initialized. Run <code style={{ background: 'var(--bg-subtle)', padding: '2px 6px', borderRadius: 4 }}>python scripts/init_groot_wallet.py</code> to create it.
      </p>
    </div>
  )

  return (
    <div className="card p-6" style={{ border: '1px solid var(--border-subtle)' }}>
      <h3 style={{ fontWeight: 700, fontSize: 16, marginBottom: 12 }}>GROOT Wallet (The Wizard)</h3>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13 }}>
        <div><span style={{ color: 'var(--text-muted)' }}>Address:</span> <code style={{ color: '#FF6B00' }}>{wallet.address}</code></div>
        <div><span style={{ color: 'var(--text-muted)' }}>Chain ID:</span> {wallet.chain_id}</div>
        <div><span style={{ color: 'var(--text-muted)' }}>Threshold:</span> {wallet.threshold}-of-{wallet.share_count} SSS</div>
        <div><span style={{ color: 'var(--text-muted)' }}>Created:</span> {wallet.created_at?.slice(0, 10)}</div>
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
        <select value={balanceChain} onChange={e => setBalanceChain(e.target.value)}
          style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px', fontSize: 12 }}>
          {['base', 'ethereum', 'sepolia', 'polygon', 'arbitrum', 'optimism'].map(c =>
            <option key={c} value={c}>{c}</option>
          )}
        </select>
        <button onClick={() => fetchBalance(balanceChain)}
          style={{ background: '#FF6B00', color: 'white', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer' }}>
          Check Balance
        </button>
        <button onClick={fetchTransactions}
          style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer' }}>
          Load Transactions
        </button>
      </div>

      {Object.entries(balances).map(([chain, bal]: [string, any]) => (
        <div key={chain} style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
          {chain}: <span style={{ color: '#4ade80', fontWeight: 600 }}>{bal.balance_eth} ETH</span>
        </div>
      ))}

      {transactions && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
            Deployments: {transactions.deployments?.length || 0} | Pending Actions: {transactions.pending_actions?.length || 0}
          </p>
          {transactions.deployments?.slice(0, 5).map((d: any) => (
            <div key={d.id} style={{ fontSize: 11, color: 'var(--text-muted)', padding: '2px 0' }}>
              {d.chain} | {d.contract_address?.slice(0, 14)}... | {d.ownership_status} | {d.created_at?.slice(0, 10)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function PendingActionsPanel() {
  const [actions, setActions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [note, setNote] = useState('')

  const headers: any = { 'Content-Type': 'application/json' }
  const token = typeof window !== 'undefined' ? localStorage.getItem('refinet_token') : null
  if (token) headers.Authorization = `Bearer ${token}`

  const fetchActions = async () => {
    try {
      const resp = await fetch(`${API_URL}/pipeline/admin/pending-actions?status=pending`, { headers })
      if (resp.ok) setActions(await resp.json())
    } catch {}
    setLoading(false)
  }

  useEffect(() => { fetchActions() }, [])

  const approve = async (id: string) => {
    await fetch(`${API_URL}/pipeline/admin/pending-actions/${id}/approve`, {
      method: 'POST', headers, body: JSON.stringify({ note })
    })
    setNote(''); fetchActions()
  }

  const reject = async (id: string) => {
    await fetch(`${API_URL}/pipeline/admin/pending-actions/${id}/reject`, {
      method: 'POST', headers, body: JSON.stringify({ note: note || 'Rejected by admin' })
    })
    setNote(''); fetchActions()
  }

  return (
    <div className="card p-6" style={{ border: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ fontWeight: 700, fontSize: 16 }}>Pending Actions (Tier 2 Approvals)</h3>
        <button onClick={fetchActions}
          style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer' }}>
          Refresh
        </button>
      </div>

      {loading && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading...</p>}
      {!loading && actions.length === 0 && (
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No pending actions. GROOT is idle.</p>
      )}

      {actions.map((a: any) => (
        <div key={a.id} style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12, marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontWeight: 600, fontSize: 13 }}>{a.action_type}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>{a.target_chain}</span>
              {a.target_address && (
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>{a.target_address?.slice(0, 14)}...</span>
              )}
            </div>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{a.created_at?.slice(0, 16)}</span>
          </div>

          {a.payload && (
            <details style={{ marginTop: 6 }}>
              <summary style={{ fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer' }}>Payload</summary>
              <pre style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, background: 'var(--bg-subtle)', padding: 8, borderRadius: 4, overflow: 'auto' }}>
                {JSON.stringify(a.payload, null, 2)}
              </pre>
            </details>
          )}

          <div style={{ marginTop: 8, display: 'flex', gap: 6, alignItems: 'center' }}>
            <input value={note} onChange={e => setNote(e.target.value)} placeholder="Note (optional)"
              style={{ flex: 1, background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px', fontSize: 11 }} />
            <button onClick={() => approve(a.id)}
              style={{ background: '#22c55e', color: 'white', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
              Approve
            </button>
            <button onClick={() => reject(a.id)}
              style={{ background: '#ef4444', color: 'white', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

function WalletProviderPanel() {
  const [config, setConfig] = useState({
    injected: true,
    coinbaseWallet: true,
    walletConnect: true,
    walletConnectProjectId: '',
  })
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    try {
      const stored = localStorage.getItem('refinet_wallet_providers')
      if (stored) {
        const parsed = JSON.parse(stored)
        setConfig(prev => ({ ...prev, ...parsed }))
      }
    } catch {}
  }, [])

  const handleSave = () => {
    localStorage.setItem('refinet_wallet_providers', JSON.stringify(config))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const providers = [
    {
      key: 'injected' as const,
      name: 'Browser Wallets (Injected)',
      desc: 'MetaMask, Brave Wallet, Phantom, and all EIP-6963 compatible browser extensions',
      icon: '🦊',
      alwaysOn: true,
    },
    {
      key: 'coinbaseWallet' as const,
      name: 'Coinbase Wallet',
      desc: 'Coinbase Wallet browser extension and mobile app via direct SDK',
      icon: '🔵',
      alwaysOn: false,
    },
    {
      key: 'walletConnect' as const,
      name: 'WalletConnect v2',
      desc: 'Mobile wallets (Trust, Rainbow, Argent), hardware wallets (DCENT, Trezor, Ledger), and 300+ wallets via QR code scanning',
      icon: '🔗',
      alwaysOn: false,
      requiresConfig: true,
    },
  ]

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-bold mb-1" style={{ color: 'var(--text-primary)' }}>Wallet Providers</h2>
        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
          Configure which wallet connection methods are available to users on the login page.
          Changes take effect on next page load.
        </p>
      </div>

      <div className="space-y-3 mb-6">
        {providers.map(p => (
          <div key={p.key} className="card p-4" style={{ border: `1px solid ${config[p.key] ? 'var(--refi-teal)' : 'var(--border-subtle)'}`, opacity: config[p.key] ? 1 : 0.7 }}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <span className="text-xl mt-0.5">{p.icon}</span>
                <div>
                  <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{p.name}</div>
                  <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{p.desc}</div>
                  {p.key === 'walletConnect' && (
                    <div className="text-[10px] mt-1 px-2 py-0.5 rounded inline-block" style={{ background: 'rgba(59,153,252,0.1)', color: '#3B99FC' }}>
                      Supports: DCENT, Trezor, Ledger, Trust Wallet, Rainbow, Argent, Safe, and more
                    </div>
                  )}
                </div>
              </div>
              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={config[p.key]}
                  disabled={p.alwaysOn}
                  onChange={e => setConfig(prev => ({ ...prev, [p.key]: e.target.checked }))}
                  className="sr-only"
                />
                <div
                  className="w-10 h-5 rounded-full transition-colors relative"
                  style={{ background: config[p.key] ? 'var(--refi-teal)' : 'var(--bg-tertiary)' }}
                >
                  <div
                    className="absolute top-0.5 w-4 h-4 rounded-full transition-transform"
                    style={{
                      background: 'white',
                      transform: config[p.key] ? 'translateX(22px)' : 'translateX(2px)',
                    }}
                  />
                </div>
              </label>
            </div>

            {/* WalletConnect Project ID */}
            {p.requiresConfig && config.walletConnect && (
              <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                <label className="text-[10px] block mb-1 font-mono" style={{ color: 'var(--text-tertiary)' }}>
                  WALLETCONNECT PROJECT ID
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={config.walletConnectProjectId}
                    onChange={e => setConfig(prev => ({ ...prev, walletConnectProjectId: e.target.value }))}
                    placeholder="Get from cloud.walletconnect.com"
                    className="flex-1 px-2 py-1.5 text-xs rounded font-mono"
                    style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }}
                  />
                </div>
                <p className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
                  Required for WalletConnect. Get a free project ID at{' '}
                  <span style={{ color: 'var(--refi-teal)' }}>cloud.walletconnect.com</span>
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Hardware Wallets Info */}
      <div className="card p-4 mb-6" style={{ border: '1px solid var(--border-subtle)' }}>
        <h3 className="text-xs font-mono mb-2 uppercase" style={{ color: 'var(--text-tertiary)' }}>Hardware Wallet Support</h3>
        <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
          Hardware wallets connect through WalletConnect or browser extensions. Enable WalletConnect above to support:
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {[
            { name: "D'CENT", method: 'WalletConnect QR', color: '#00D4AA' },
            { name: 'Trezor', method: 'WalletConnect QR', color: '#14854F' },
            { name: 'Ledger', method: 'WalletConnect QR', color: '#000000' },
            { name: 'Keystone', method: 'WalletConnect QR', color: '#2C6CFF' },
          ].map(hw => (
            <div key={hw.name} className="p-2 rounded text-center" style={{ background: 'var(--bg-secondary)' }}>
              <div className="text-xs font-semibold" style={{ color: hw.color }}>{hw.name}</div>
              <div className="text-[9px]" style={{ color: 'var(--text-tertiary)' }}>{hw.method}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Native Wallet Info */}
      <div className="card p-4 mb-6" style={{ border: '1px solid var(--border-subtle)' }}>
        <h3 className="text-xs font-mono mb-2 uppercase" style={{ color: 'var(--text-tertiary)' }}>Native Wallet Generation</h3>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          Users can also create a sovereign cloud wallet directly on the login page. This uses Shamir Secret Sharing (3-of-5 threshold)
          with AES-256-GCM encryption — no browser extension required. This feature is always available regardless of provider settings.
        </p>
      </div>

      {/* Save Button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          className="px-4 py-2 text-xs font-semibold rounded-lg"
          style={{ background: 'var(--refi-teal)', color: '#000', cursor: 'pointer' }}
        >
          Save Configuration
        </button>
        {saved && <span className="text-xs" style={{ color: 'var(--success)' }}>Saved — reload the login page to apply changes</span>}
        {config.walletConnect && !config.walletConnectProjectId && (
          <span className="text-xs" style={{ color: '#fbbf24' }}>WalletConnect requires a project ID to function</span>
        )}
      </div>
    </div>
  )
}


/* ─── AI Model Provider Management Panel ─── */
function ModelProviderPanel({ headers }: { headers: Record<string, string> }) {
  const [data, setData] = useState<any>(null)
  const [usageData, setUsageData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [healthLoading, setHealthLoading] = useState(false)

  const ADMIN_WALLET = '0xE302932D42C751404AeD466C8929F1704BA89D5A'

  const load = () => {
    setLoading(true)
    fetch(`${API_URL}/admin/providers`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))

    fetch(`${API_URL}/admin/providers/usage?period=day`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(setUsageData)
      .catch(() => {})
  }

  useEffect(() => { if (headers.Authorization !== 'Bearer ') load() }, [headers.Authorization])

  const runHealthCheck = async () => {
    setHealthLoading(true)
    try {
      const r = await fetch(`${API_URL}/admin/providers/health`, { headers })
      if (r.ok) load()
    } catch {}
    setHealthLoading(false)
  }

  const PROVIDER_COLORS: Record<string, string> = {
    bitnet: '#5CE0D2', gemini: '#4285F4', ollama: '#84CC16',
    lmstudio: '#A78BFA', openrouter: '#F97316',
  }

  const PROVIDER_ICONS: Record<string, string> = {
    bitnet: '1', gemini: 'G', ollama: 'O', lmstudio: 'L', openrouter: 'R',
  }

  if (loading && !data) return <div className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading providers...</div>

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>AI Model Providers</h2>
          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
            Configure which AI backends GROOT can use for inference. BitNet is sovereign and always active.
          </p>
        </div>
        <button onClick={runHealthCheck} disabled={healthLoading}
          className="px-3 py-1.5 text-xs font-semibold rounded-lg"
          style={{
            background: healthLoading ? 'var(--bg-tertiary)' : 'var(--refi-teal)',
            color: healthLoading ? 'var(--text-tertiary)' : '#000',
            cursor: healthLoading ? 'not-allowed' : 'pointer',
          }}>
          {healthLoading ? 'Checking...' : 'Run Health Check'}
        </button>
      </div>

      {/* Admin Wallet */}
      <div className="card p-3 mb-4" style={{ border: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>Platform Admin Wallet</div>
            <div className="text-xs font-mono" style={{ color: 'var(--refi-teal)' }}>{ADMIN_WALLET}</div>
          </div>
          <div className="text-[9px] px-2 py-0.5 rounded" style={{ background: 'rgba(92,224,210,0.15)', color: '#5CE0D2' }}>OWNER</div>
        </div>
      </div>

      {/* Fallback Chain */}
      {data && (
        <div className="card p-3 mb-4" style={{ border: '1px solid var(--border-subtle)' }}>
          <div className="text-[10px] font-mono uppercase mb-2" style={{ color: 'var(--text-tertiary)' }}>Fallback Chain (priority order)</div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {data.fallback_chain.map((p: string, i: number) => (
              <span key={p} className="flex items-center gap-1">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded"
                  style={{ background: `${PROVIDER_COLORS[p] || '#888'}15`, color: PROVIDER_COLORS[p] || '#888', border: `1px solid ${PROVIDER_COLORS[p] || '#888'}30` }}>
                  {p}
                </span>
                {i < data.fallback_chain.length - 1 && <span style={{ color: 'var(--text-tertiary)', fontSize: '10px' }}>→</span>}
              </span>
            ))}
          </div>
          <div className="text-[10px] mt-2" style={{ color: 'var(--text-tertiary)' }}>
            Default model: <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>{data.default_model}</span>
          </div>
        </div>
      )}

      {/* Provider Cards */}
      {data && (
        <div className="space-y-3 mb-6">
          {data.providers.map((p: any) => {
            const color = PROVIDER_COLORS[p.type] || '#888'
            const icon = PROVIDER_ICONS[p.type] || '?'
            const isHealthy = p.healthy === true
            const isUnknown = p.healthy === null
            const usageRow = usageData?.by_provider?.find((u: any) => u.provider === p.type)

            return (
              <div key={p.type} className="card p-4"
                style={{ border: `1px solid ${p.enabled ? color + '40' : 'var(--border-subtle)'}`, opacity: p.enabled ? 1 : 0.6 }}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold flex-shrink-0"
                      style={{ background: `${color}20`, color }}>{icon}</div>
                    <div>
                      <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{p.name}</div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{p.description}</div>
                      {p.models.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {p.models.slice(0, 8).map((m: string) => (
                            <span key={m} className="text-[9px] font-mono px-1.5 py-0.5 rounded"
                              style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>{m}</span>
                          ))}
                          {p.models.length > 8 && (
                            <span className="text-[9px] px-1.5 py-0.5" style={{ color: 'var(--text-tertiary)' }}>+{p.models.length - 8} more</span>
                          )}
                        </div>
                      )}
                      {usageRow && (
                        <div className="flex gap-3 mt-2 text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                          <span>{usageRow.calls} calls today</span>
                          <span>{(usageRow.prompt_tokens + usageRow.completion_tokens).toLocaleString()} tokens</span>
                          <span>{usageRow.avg_latency_ms}ms avg</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                    <div className="flex items-center gap-1.5">
                      {p.enabled ? (
                        <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(74,222,128,0.15)', color: 'var(--success)' }}>ENABLED</span>
                      ) : (
                        <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--text-tertiary)' }}>DISABLED</span>
                      )}
                      {p.registered && (
                        isHealthy ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(74,222,128,0.15)', color: 'var(--success)' }}>HEALTHY</span>
                        ) : isUnknown ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}>PENDING</span>
                        ) : (
                          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(248,113,113,0.15)', color: 'var(--error)' }}>UNHEALTHY</span>
                        )
                      )}
                    </div>
                    {p.latency_ms !== null && (
                      <span className="text-[9px] font-mono" style={{ color: 'var(--text-tertiary)' }}>{p.latency_ms}ms</span>
                    )}
                    {p.error && (
                      <span className="text-[9px] max-w-[200px] truncate" style={{ color: 'var(--error)' }}>{p.error}</span>
                    )}
                  </div>
                </div>
                <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>{p.config_key}</span>
                    <span className="text-[10px] font-mono" style={{ color: p.config_value ? 'var(--text-secondary)' : 'var(--error)' }}>
                      {p.config_value || '(not set)'}
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Setup Guide */}
      <div className="card p-4 mb-4" style={{ border: '1px solid var(--border-subtle)' }}>
        <h3 className="text-xs font-mono mb-3 uppercase" style={{ color: 'var(--text-tertiary)' }}>Enable Providers (.env)</h3>
        <pre className="text-[11px] font-mono p-3 rounded overflow-x-auto" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
{`# Set the ones you want (empty = disabled)
GEMINI_API_KEY=your-google-api-key
OLLAMA_HOST=http://127.0.0.1:11434
LMSTUDIO_HOST=http://127.0.0.1:1234
OPENROUTER_API_KEY=your-openrouter-key

# Defaults
DEFAULT_MODEL=bitnet-b1.58-2b
PROVIDER_FALLBACK_CHAIN=bitnet,gemini,ollama,lmstudio,openrouter`}
        </pre>
      </div>

      {/* Add New Provider Guide */}
      <div className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
        <h3 className="text-xs font-mono mb-3 uppercase" style={{ color: 'var(--text-tertiary)' }}>Adding a Future Provider (e.g., Anthropic)</h3>
        <div className="space-y-2">
          {[
            { step: '1', text: 'Create api/services/providers/anthropic.py implementing BaseProvider' },
            { step: '2', text: 'Add ANTHROPIC_API_KEY to api/config.py' },
            { step: '3', text: 'Register in gateway.py initialize() — done. No route changes needed.' },
          ].map(s => (
            <div key={s.step} className="flex items-start gap-2">
              <span className="text-[10px] font-mono w-5 h-5 rounded flex items-center justify-center flex-shrink-0"
                style={{ background: 'var(--refi-teal-glow)', color: 'var(--refi-teal)' }}>{s.step}</span>
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{s.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}


/* ─── Onboarding Panel ─── */

function OnboardingPanel({ headers, onboardingStats, setOnboardingStats, leads, setLeads }: {
  headers: any; onboardingStats: any; setOnboardingStats: (s: any) => void; leads: any[]; setLeads: (l: any[]) => void
}) {
  const [loading, setLoading] = useState(!onboardingStats)
  const [subTab, setSubTab] = useState<'funnel' | 'leads'>('funnel')

  useEffect(() => {
    if (onboardingStats) { setLoading(false); return }
    Promise.all([
      fetch(`${API_URL}/admin/stats/onboarding`, { headers }).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API_URL}/admin/leads`, { headers }).then(r => r.ok ? r.json() : []).catch(() => []),
    ]).then(([stats, ld]) => {
      if (stats) setOnboardingStats(stats)
      setLeads(Array.isArray(ld) ? ld : [])
      setLoading(false)
    })
  }, [])

  if (loading) return <div className="animate-pulse" style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>Loading onboarding data...</div>

  const s = onboardingStats
  const funnel = s?.funnel || {}
  const rates = s?.rates || {}
  const marketing = s?.marketing || {}
  const activity = s?.activity || {}

  return (
    <div className="space-y-6">
      {/* Sub-tabs */}
      <div className="flex gap-1">
        {(['funnel', 'leads'] as const).map(t => (
          <button key={t} onClick={() => setSubTab(t)} className="text-xs px-4 py-2 rounded-lg font-medium transition-colors"
            style={{ background: subTab === t ? 'var(--refi-teal-glow)' : 'var(--bg-tertiary)', color: subTab === t ? 'var(--refi-teal)' : 'var(--text-secondary)' }}>
            {t === 'funnel' ? 'Onboarding Funnel' : `Leads (${leads.length})`}
          </button>
        ))}
      </div>

      {subTab === 'funnel' && s && (
        <>
          {/* Funnel stats cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <FunnelCard label="Wallet Connected" value={funnel.wallet_connected} pct={100} color="var(--refi-teal)" />
            <FunnelCard label="Email Captured" value={funnel.email_set} pct={rates.email_capture_pct} color="rgb(96,165,250)" />
            <FunnelCard label="Password Set" value={funnel.password_set} pct={rates.password_set_pct} color="rgb(167,139,250)" />
            <FunnelCard label="TOTP Enabled" value={funnel.totp_enabled} pct={rates.totp_enabled_pct} color="rgb(250,204,21)" />
            <FunnelCard label="Fully Onboarded" value={funnel.fully_onboarded} pct={rates.full_onboarding_pct} color="var(--success)" />
          </div>

          {/* Marketing & activity */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="card p-4">
              <div className="text-[11px] uppercase font-medium mb-1" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>Marketing Consent</div>
              <div className="text-xl font-bold" style={{ color: 'var(--refi-teal)' }}>{marketing.consented || 0}</div>
              <div className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>{rates.marketing_consent_pct || 0}% of users</div>
            </div>
            <div className="card p-4">
              <div className="text-[11px] uppercase font-medium mb-1" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>Emails Captured</div>
              <div className="text-xl font-bold" style={{ color: 'rgb(96,165,250)' }}>{marketing.total_with_email || 0}</div>
              <div className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>{rates.email_capture_pct || 0}% capture rate</div>
            </div>
            <div className="card p-4">
              <div className="text-[11px] uppercase font-medium mb-1" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>Signups (7d)</div>
              <div className="text-xl font-bold" style={{ color: 'var(--success)' }}>{activity.signups_last_7d || 0}</div>
            </div>
            <div className="card p-4">
              <div className="text-[11px] uppercase font-medium mb-1" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>Inactive (30d)</div>
              <div className="text-xl font-bold" style={{ color: activity.inactive_30d > 0 ? 'var(--error)' : 'var(--text-tertiary)' }}>{activity.inactive_30d || 0}</div>
            </div>
          </div>

          {/* Funnel visualization */}
          <div className="card p-5">
            <h3 className="font-bold text-sm mb-4" style={{ letterSpacing: '-0.02em' }}>Conversion Funnel</h3>
            <div className="space-y-3">
              {[
                { label: 'Wallet Connected (SIWE)', value: funnel.wallet_connected, pct: 100, color: 'var(--refi-teal)' },
                { label: 'Email Captured', value: funnel.email_set, pct: rates.email_capture_pct, color: 'rgb(96,165,250)' },
                { label: 'Password Set (Layer 1)', value: funnel.password_set, pct: rates.password_set_pct, color: 'rgb(167,139,250)' },
                { label: 'TOTP Enabled (Layer 2)', value: funnel.totp_enabled, pct: rates.totp_enabled_pct, color: 'rgb(250,204,21)' },
                { label: 'Fully Onboarded (3/3)', value: funnel.fully_onboarded, pct: rates.full_onboarding_pct, color: 'var(--success)' },
              ].map(item => (
                <div key={item.label}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{item.label}</span>
                    <span className="text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>{item.value || 0} ({item.pct || 0}%)</span>
                  </div>
                  <div style={{ width: '100%', height: 6, borderRadius: 3, background: 'var(--bg-tertiary)' }}>
                    <div style={{ width: `${Math.min(item.pct || 0, 100)}%`, height: '100%', borderRadius: 3, background: item.color, transition: 'width 0.6s ease' }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {subTab === 'leads' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="px-5 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-xs font-semibold uppercase" style={{ letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>
              Email Leads ({leads.length})
            </span>
            <button onClick={() => {
              const consented = leads.filter(l => l.marketing_consent)
              const csv = 'email,username,wallet,tier,marketing_consent,fully_onboarded,created_at\n' +
                consented.map(l => `${l.email},${l.username},${l.eth_address || ''},${l.tier},${l.marketing_consent},${l.fully_onboarded},${l.created_at || ''}`).join('\n')
              const blob = new Blob([csv], { type: 'text/csv' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a'); a.href = url; a.download = 'refinet-consented-leads.csv'; a.click()
              URL.revokeObjectURL(url)
            }} className="text-[11px] px-3 py-1 rounded-lg transition-colors"
              style={{ background: 'var(--refi-teal-glow)', color: 'var(--refi-teal)' }}>
              Export Consented CSV
            </button>
          </div>
          {leads.length === 0 ? (
            <div className="p-8 text-center" style={{ color: 'var(--text-tertiary)' }}>
              <p className="text-sm">No leads captured yet</p>
              <p className="text-xs mt-1">Leads appear when users enter their email during onboarding</p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    {['User', 'Email', 'Wallet', 'Security', 'Consent', 'Joined'].map(h => (
                      <th key={h} className="text-left text-[11px] font-semibold uppercase px-4 py-3" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {leads.map(l => (
                    <tr key={l.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-elevated)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                      <td className="px-4 py-3 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{l.username}</td>
                      <td className="px-4 py-3 text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)' }}>{l.email}</td>
                      <td className="px-4 py-3 text-[11px]" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>
                        {l.eth_address ? `${l.eth_address.slice(0, 8)}...${l.eth_address.slice(-4)}` : '-'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: l.wallet_connected ? 'rgba(74,222,128,0.1)' : 'var(--bg-tertiary)', color: l.wallet_connected ? 'var(--success)' : 'var(--text-tertiary)' }}>W</span>
                          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: l.password_set ? 'rgba(74,222,128,0.1)' : 'var(--bg-tertiary)', color: l.password_set ? 'var(--success)' : 'var(--text-tertiary)' }}>P</span>
                          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: l.totp_enabled ? 'rgba(74,222,128,0.1)' : 'var(--bg-tertiary)', color: l.totp_enabled ? 'var(--success)' : 'var(--text-tertiary)' }}>2FA</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {l.marketing_consent ? (
                          <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(92,224,210,0.12)', color: 'var(--refi-teal)', fontWeight: 600 }}>OPT-IN</span>
                        ) : (
                          <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                        {l.created_at ? new Date(l.created_at).toLocaleDateString() : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function FunnelCard({ label, value, pct, color }: { label: string; value: number; pct: number; color: string }) {
  return (
    <div className="card p-4" style={{ borderTop: `2px solid ${color}` }}>
      <div className="text-[11px] uppercase font-medium mb-1" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>{label}</div>
      <div className="text-xl font-bold" style={{ color, letterSpacing: '-0.02em' }}>{value || 0}</div>
      <div className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>{pct || 0}%</div>
    </div>
  )
}
