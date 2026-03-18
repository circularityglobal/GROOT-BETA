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
  const [tab, setTab] = useState<'stats' | 'users' | 'audit' | 'mcp' | 'secrets'>('stats')
  const [error, setError] = useState('')
  const [roleUserId, setRoleUserId] = useState('')
  const [roleValue, setRoleValue] = useState('operator')

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

  const grantRole = async (userId: string, role: string) => {
    await fetch(`${API_URL}/admin/users/${userId}/role`, {
      method: 'PUT', headers, body: JSON.stringify({ role }),
    })
    loadUsers()
  }

  useEffect(() => {
    if (!token) return
    if (tab === 'users') loadUsers()
    if (tab === 'audit') loadAudit()
    if (tab === 'mcp') loadMcp()
    if (tab === 'secrets') loadSecrets()
  }, [tab, token])

  if (error) {
    return (
      <div className="max-w-2xl mx-auto py-20 px-6 text-center">
        <h1 className="text-2xl font-bold mb-4 text-red-400" style={{ letterSpacing: '-0.02em' }}>Access Denied</h1>
        <p style={{ color: 'var(--text-secondary)' }}>{error}</p>
      </div>
    )
  }

  const tabs = ['stats', 'users', 'audit', 'mcp', 'secrets'] as const

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
            {t.toUpperCase()}
          </button>
        ))}
      </div>

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
    </div>
  )
}
