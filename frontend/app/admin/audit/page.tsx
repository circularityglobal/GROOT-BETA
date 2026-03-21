'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

export default function AdminAudit() {
  const { headers } = useAdmin()
  const [audit, setAudit] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    fetch(`${API_URL}/admin/audit?limit=50`, { headers })
      .then(r => r.ok ? r.json() : [])
      .then(d => { setAudit(Array.isArray(d) ? d : []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [headers.Authorization])

  if (loading) return <LoadingState label="Loading audit log..." />

  return (
    <div>
      <PageHeader title="Audit Log" subtitle="Append-only record of all admin actions" />

      <div className="card overflow-hidden" style={{ border: '1px solid var(--border-subtle)' }}>
        {audit.length === 0 ? (
          <p className="text-sm p-6 text-center" style={{ color: 'var(--text-tertiary)' }}>No audit entries yet.</p>
        ) : (
          <div>
            {audit.map((l: any) => (
              <div key={l.id} className="flex items-center gap-4 px-4 py-2.5 text-xs font-mono" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <span className="w-44 flex-shrink-0" style={{ color: 'var(--text-tertiary)' }}>{l.timestamp}</span>
                <span className="w-24 flex-shrink-0" style={{ color: 'var(--text-primary)' }}>{l.admin_username}</span>
                <span className="w-28 flex-shrink-0" style={{ color: 'var(--refi-teal)' }}>{l.action}</span>
                <span style={{ color: 'var(--text-tertiary)' }}>{l.target_type}:{l.target_id || '-'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
