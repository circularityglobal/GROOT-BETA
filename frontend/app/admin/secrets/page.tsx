'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

export default function AdminSecrets() {
  const { headers } = useAdmin()
  const [secrets, setSecrets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    fetch(`${API_URL}/admin/secrets`, { headers })
      .then(r => r.ok ? r.json() : [])
      .then(d => { setSecrets(Array.isArray(d) ? d : []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [headers.Authorization])

  if (loading) return <LoadingState label="Loading secrets..." />

  return (
    <div>
      <PageHeader title="Secrets" subtitle="AES-256-GCM encrypted secrets vault. Values are never displayed." />

      <div className="card overflow-hidden overflow-x-auto" style={{ border: '1px solid var(--border-subtle)' }}>
        {secrets.length === 0 ? (
          <p className="text-sm p-6 text-center" style={{ color: 'var(--text-tertiary)' }}>No secrets stored.</p>
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
    </div>
  )
}
