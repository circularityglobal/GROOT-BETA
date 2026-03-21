'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

export default function AdminOnboarding() {
  const { headers } = useAdmin()
  const [stats, setStats] = useState<any>(null)
  const [leads, setLeads] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [subTab, setSubTab] = useState<'funnel' | 'leads'>('funnel')

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    Promise.all([
      fetch(`${API_URL}/admin/stats/onboarding`, { headers }).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API_URL}/admin/leads`, { headers }).then(r => r.ok ? r.json() : []).catch(() => []),
    ]).then(([s, ld]) => {
      if (s) setStats(s)
      setLeads(Array.isArray(ld) ? ld : [])
      setLoading(false)
    })
  }, [headers.Authorization])

  if (loading) return <LoadingState label="Loading onboarding data..." />

  const s = stats
  const funnel = s?.funnel || {}
  const rates = s?.rates || {}
  const marketing = s?.marketing || {}
  const activity = s?.activity || {}

  return (
    <div>
      <PageHeader title="Onboarding" subtitle="User acquisition funnel and lead management" />

      {/* Sub-tabs */}
      <div className="flex gap-1 mb-6">
        {(['funnel', 'leads'] as const).map(t => (
          <button key={t} onClick={() => setSubTab(t)} className="text-xs px-4 py-2 rounded-lg font-medium transition-colors"
            style={{ background: subTab === t ? 'var(--refi-teal-glow)' : 'var(--bg-tertiary)', color: subTab === t ? 'var(--refi-teal)' : 'var(--text-secondary)', cursor: 'pointer', border: 'none' }}>
            {t === 'funnel' ? 'Onboarding Funnel' : `Leads (${leads.length})`}
          </button>
        ))}
      </div>

      {subTab === 'funnel' && s && (
        <div className="space-y-6">
          {/* Funnel cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[
              { label: 'Wallet Connected', value: funnel.wallet_connected, pct: 100, color: 'var(--refi-teal)' },
              { label: 'Email Captured', value: funnel.email_set, pct: rates.email_capture_pct, color: 'rgb(96,165,250)' },
              { label: 'Password Set', value: funnel.password_set, pct: rates.password_set_pct, color: 'rgb(167,139,250)' },
              { label: 'TOTP Enabled', value: funnel.totp_enabled, pct: rates.totp_enabled_pct, color: 'rgb(250,204,21)' },
              { label: 'Fully Onboarded', value: funnel.fully_onboarded, pct: rates.full_onboarding_pct, color: 'var(--success)' },
            ].map(item => (
              <div key={item.label} className="card p-4" style={{ borderTop: `2px solid ${item.color}`, border: '1px solid var(--border-subtle)' }}>
                <div className="text-[11px] uppercase font-medium mb-1" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>{item.label}</div>
                <div className="text-xl font-bold" style={{ color: item.color, letterSpacing: '-0.02em' }}>{item.value || 0}</div>
                <div className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>{item.pct || 0}%</div>
              </div>
            ))}
          </div>

          {/* Marketing & activity */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
              <div className="text-[11px] uppercase font-medium mb-1" style={{ color: 'var(--text-tertiary)' }}>Marketing Consent</div>
              <div className="text-xl font-bold" style={{ color: 'var(--refi-teal)' }}>{marketing.consented || 0}</div>
              <div className="text-[10px] mt-1 font-mono" style={{ color: 'var(--text-tertiary)' }}>{rates.marketing_consent_pct || 0}% of users</div>
            </div>
            <div className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
              <div className="text-[11px] uppercase font-medium mb-1" style={{ color: 'var(--text-tertiary)' }}>Emails Captured</div>
              <div className="text-xl font-bold" style={{ color: 'rgb(96,165,250)' }}>{marketing.total_with_email || 0}</div>
              <div className="text-[10px] mt-1 font-mono" style={{ color: 'var(--text-tertiary)' }}>{rates.email_capture_pct || 0}% capture rate</div>
            </div>
            <div className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
              <div className="text-[11px] uppercase font-medium mb-1" style={{ color: 'var(--text-tertiary)' }}>Signups (7d)</div>
              <div className="text-xl font-bold" style={{ color: 'var(--success)' }}>{activity.signups_last_7d || 0}</div>
            </div>
            <div className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
              <div className="text-[11px] uppercase font-medium mb-1" style={{ color: 'var(--text-tertiary)' }}>Inactive (30d)</div>
              <div className="text-xl font-bold" style={{ color: activity.inactive_30d > 0 ? 'var(--error)' : 'var(--text-tertiary)' }}>{activity.inactive_30d || 0}</div>
            </div>
          </div>

          {/* Funnel visualization */}
          <div className="card p-5" style={{ border: '1px solid var(--border-subtle)' }}>
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
                    <span className="text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{item.value || 0} ({item.pct || 0}%)</span>
                  </div>
                  <div style={{ width: '100%', height: 6, borderRadius: 3, background: 'var(--bg-tertiary)' }}>
                    <div style={{ width: `${Math.min(item.pct || 0, 100)}%`, height: '100%', borderRadius: 3, background: item.color, transition: 'width 0.6s ease' }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {subTab === 'leads' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
          <div className="px-5 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-xs font-semibold uppercase" style={{ letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>
              Email Leads ({leads.length})
            </span>
            <button onClick={async () => {
              try {
                const resp = await fetch(`${API_URL}/admin/leads?consented_only=true`, { headers })
                if (!resp.ok) return
                const consented = await resp.json()
                const csv = 'email,username,wallet,tier,created_at\n' +
                  consented.map((l: any) => `${l.email},${l.username},${l.eth_address || ''},${l.tier},${l.created_at || ''}`).join('\n')
                const blob = new Blob([csv], { type: 'text/csv' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a'); a.href = url; a.download = 'refinet-consented-leads.csv'; a.click()
                URL.revokeObjectURL(url)
              } catch {}
            }} className="text-[11px] px-3 py-1 rounded-lg"
              style={{ background: 'var(--refi-teal-glow)', color: 'var(--refi-teal)', border: 'none', cursor: 'pointer' }}>
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
                      <td className="px-4 py-3 text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>{l.email}</td>
                      <td className="px-4 py-3 text-[11px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
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
                        {l.marketing_consent
                          ? <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(92,224,210,0.12)', color: 'var(--refi-teal)', fontWeight: 600 }}>OPT-IN</span>
                          : <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>-</span>}
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
