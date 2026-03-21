'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

export default function AdminUsers() {
  const { headers } = useAdmin()
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const loadUsers = async () => {
    const resp = await fetch(`${API_URL}/admin/users`, { headers })
    if (resp.ok) setUsers(await resp.json())
    setLoading(false)
  }

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    loadUsers()
  }, [headers.Authorization])

  const grantRole = async (userId: string, role: string) => {
    await fetch(`${API_URL}/admin/users/${userId}/role`, {
      method: 'PUT', headers, body: JSON.stringify({ role, action: 'grant' }),
    })
    loadUsers()
  }

  if (loading) return <LoadingState label="Loading users..." />

  return (
    <div>
      <PageHeader title="Users" subtitle={`${users.length} registered users`} />

      <div className="card overflow-hidden overflow-x-auto" style={{ border: '1px solid var(--border-subtle)' }}>
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
                  {u.eth_address ? `${u.eth_address.slice(0, 6)}...${u.eth_address.slice(-4)}` : '-'}
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
        {users.length === 0 && <p className="text-sm p-6 text-center" style={{ color: 'var(--text-tertiary)' }}>No users found.</p>}
      </div>
    </div>
  )
}
