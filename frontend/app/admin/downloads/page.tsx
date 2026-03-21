'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

export default function AdminDownloads() {
  const { headers } = useAdmin()
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    fetch(`${API_URL}/downloads/admin/stats`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(data => { setStats(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [headers.Authorization])

  const exportCSV = () => {
    window.open(`${API_URL}/downloads/admin/export?token=${localStorage.getItem('refinet_token')}`, '_blank')
  }

  if (loading) return <LoadingState label="Loading download stats..." />
  if (!stats) return (
    <div>
      <PageHeader title="Downloads" subtitle="Product download analytics" />
      <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No download data available.</p>
    </div>
  )

  return (
    <div>
      <PageHeader title="Downloads" subtitle="Product download analytics and lead capture" />

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Downloads', value: stats.total_downloads },
          { label: 'Waitlist Signups', value: stats.total_waitlist },
          { label: 'Total Leads', value: stats.total_downloads + stats.total_waitlist },
          { label: 'Products', value: Object.keys(stats.by_product).length },
        ].map(c => (
          <div key={c.label} className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
            <p className="text-[10px] font-mono uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{c.label}</p>
            <p className="text-2xl font-bold mt-1" style={{ color: 'var(--refi-teal)' }}>{c.value}</p>
          </div>
        ))}
      </div>

      {/* By product */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>By Product</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(stats.by_product).map(([product, count]: [string, any]) => (
            <div key={product} className="card p-3" style={{ border: '1px solid var(--border-subtle)' }}>
              <p className="text-xs font-mono capitalize" style={{ color: 'var(--text-secondary)' }}>{product}</p>
              <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{count}</p>
            </div>
          ))}
        </div>
      </div>

      {/* By platform */}
      {Object.keys(stats.by_platform).length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>By Platform</h3>
          <div className="flex gap-3 flex-wrap">
            {Object.entries(stats.by_platform).map(([platform, count]: [string, any]) => (
              <div key={platform} className="px-3 py-2 rounded-lg text-xs font-mono" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>{platform}: </span>
                <span style={{ color: 'var(--text-primary)' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Leads */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Recent Leads</h3>
          <button onClick={exportCSV} className="px-3 py-1.5 rounded-lg text-[11px] font-mono"
            style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', color: 'var(--refi-teal)', cursor: 'pointer' }}>
            Export CSV
          </button>
        </div>
        <div className="card overflow-x-auto" style={{ border: '1px solid var(--border-subtle)' }}>
          <table className="w-full text-xs font-mono" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg-secondary)' }}>
                {['Name', 'Email', 'Product', 'Platform', 'Type', 'Date'].map(h => (
                  <th key={h} className="px-3 py-2 text-left font-semibold" style={{ color: 'var(--text-tertiary)', borderBottom: '1px solid var(--border-subtle)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stats.recent_leads.map((lead: any) => (
                <tr key={lead.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td className="px-3 py-2" style={{ color: 'var(--text-primary)' }}>{lead.name}</td>
                  <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{lead.email}</td>
                  <td className="px-3 py-2 capitalize" style={{ color: 'var(--refi-teal)' }}>{lead.product}</td>
                  <td className="px-3 py-2" style={{ color: 'var(--text-secondary)' }}>{lead.platform || '-'}</td>
                  <td className="px-3 py-2">
                    <span className="px-1.5 py-0.5 rounded text-[10px]" style={{
                      background: lead.download_type === 'download' ? 'rgba(40,200,64,0.1)' : 'var(--refi-teal-glow)',
                      color: lead.download_type === 'download' ? '#28C840' : 'var(--refi-teal)',
                    }}>{lead.download_type}</span>
                  </td>
                  <td className="px-3 py-2" style={{ color: 'var(--text-tertiary)' }}>{lead.created_at?.split('T')[0] || '-'}</td>
                </tr>
              ))}
              {stats.recent_leads.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-6 text-center" style={{ color: 'var(--text-tertiary)' }}>No leads yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
