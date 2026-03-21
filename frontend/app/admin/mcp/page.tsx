'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

export default function AdminMcp() {
  const { headers } = useAdmin()
  const [mcpServers, setMcpServers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    fetch(`${API_URL}/admin/mcp`, { headers })
      .then(r => r.ok ? r.json() : [])
      .then(d => { setMcpServers(Array.isArray(d) ? d : []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [headers.Authorization])

  if (loading) return <LoadingState label="Loading MCP servers..." />

  return (
    <div>
      <PageHeader title="MCP Servers" subtitle="Registered Model Context Protocol servers" />

      <div className="card overflow-hidden overflow-x-auto" style={{ border: '1px solid var(--border-subtle)' }}>
        {mcpServers.length === 0 ? (
          <p className="text-sm p-6 text-center" style={{ color: 'var(--text-tertiary)' }}>No MCP servers registered. Use admin API to register.</p>
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
    </div>
  )
}
