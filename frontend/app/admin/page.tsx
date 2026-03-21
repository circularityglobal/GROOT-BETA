'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from './layout'
import { PageHeader, LoadingState } from './shared'

export default function AdminOverview() {
  const { headers } = useAdmin()
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    fetch(`${API_URL}/admin/stats`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { setStats(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [headers.Authorization])

  if (loading) return <LoadingState label="Loading platform stats..." />

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Platform overview and key metrics" />

      {stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(stats).map(([k, v]) => (
            <div key={k} className="card p-5" style={{ border: '1px solid var(--border-subtle)' }}>
              <div className="text-[10px] font-mono uppercase mb-2" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>
                {k.replace(/_/g, ' ')}
              </div>
              <div className="text-2xl font-bold" style={{ color: 'var(--refi-teal)', letterSpacing: '-0.02em' }}>
                {String(v)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card p-8 text-center" style={{ border: '1px solid var(--border-subtle)' }}>
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Could not load stats. Is the backend running?</p>
        </div>
      )}
    </div>
  )
}
