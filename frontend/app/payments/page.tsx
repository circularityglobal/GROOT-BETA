'use client'

import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '@/lib/config'

interface FeeSchedule { service: string; amount: string; currency: string; description: string }
interface Payment { id: string; item_type: string; amount: string; status: string; chain?: string; created_at: string; tx_hash?: string }
interface Subscription { tier: string; status: string; features?: string[]; expires_at?: string; started_at?: string }

const STATUS_COLORS: Record<string, string> = {
  completed: 'var(--success)', active: 'var(--success)', pending: 'rgb(250,204,21)',
  failed: 'var(--error)', cancelled: 'var(--text-tertiary)', expired: 'var(--error)',
}

const TIER_COLORS: Record<string, { bg: string; text: string; accent: string }> = {
  free: { bg: 'rgba(92,224,210,0.08)', text: 'var(--refi-teal)', accent: 'var(--refi-teal)' },
  pro: { bg: 'rgba(96,165,250,0.08)', text: 'rgb(96,165,250)', accent: 'rgb(96,165,250)' },
  enterprise: { bg: 'rgba(167,139,250,0.08)', text: 'rgb(167,139,250)', accent: 'rgb(167,139,250)' },
}

export default function PaymentsPage() {
  const [tab, setTab] = useState<'subscription' | 'fees' | 'history'>('subscription')
  const [fees, setFees] = useState<FeeSchedule[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const headers = useCallback(() => {
    const token = localStorage.getItem('refinet_token')
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    

    Promise.all([
      fetch(`${API_URL}/payments/fee-schedule`, { headers: headers() }).then(r => r.ok ? r.json() : []).catch(() => []),
      fetch(`${API_URL}/payments/history`, { headers: headers() }).then(r => r.ok ? r.json() : []).catch(() => []),
      fetch(`${API_URL}/payments/subscriptions/status`, { headers: headers() }).then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([f, p, s]) => {
      setFees(Array.isArray(f) ? f : f?.fees || [])
      setPayments(Array.isArray(p) ? p : p?.payments || [])
      setSubscription(s)
      setLoading(false)
    })
  }, [headers])

  const tier = subscription?.tier?.toLowerCase() || 'free'
  const tc = TIER_COLORS[tier] || TIER_COLORS.free

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)', fontSize: 13 }}>Loading...</span>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto py-10 px-6 animate-fade-in">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ letterSpacing: '-0.02em' }}>Payments & Subscriptions</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>
          Manage your subscription tier, view fee schedules, and track payment history
        </p>
      </div>

      {/* Messages */}
      {error && <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--error)', border: '1px solid rgba(248,113,113,0.2)' }}>{error}</div>}
      {msg && <div className="mb-4 p-3 rounded-lg text-sm animate-fade-in" style={{ background: 'rgba(92,224,210,0.08)', color: 'var(--refi-teal)', border: '1px solid var(--refi-teal)' }}>{msg}</div>}

      {/* Stats */}
      <div className="grid gap-3 mb-6" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))' }}>
        <StatCard icon={<TierIcon />} label="Current Tier" value={subscription?.tier || 'Free'} color={tc.accent} />
        <StatCard icon={<StatusIcon />} label="Status" value={subscription?.status || 'Active'} color={STATUS_COLORS[subscription?.status || 'active'] || 'var(--success)'} />
        <StatCard icon={<HistoryIcon />} label="Payments" value={payments.length.toString()} color="rgb(167,139,250)" />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6">
        {(['subscription', 'fees', 'history'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className="text-xs px-4 py-2 rounded-lg transition-colors font-medium"
            style={{
              background: tab === t ? 'var(--refi-teal-glow)' : 'var(--bg-tertiary)',
              color: tab === t ? 'var(--refi-teal)' : 'var(--text-secondary)',
            }}>
            {t === 'subscription' ? 'Subscription' : t === 'fees' ? 'Fee Schedule' : 'History'}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'subscription' && (
        <div className="card animate-fade-in" style={{ padding: 0, overflow: 'hidden' }}>
          {/* Tier banner */}
          <div className="p-6" style={{ background: tc.bg, borderBottom: '1px solid var(--border-subtle)' }}>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${tc.accent}20` }}>
                <TierIcon color={tc.accent} />
              </div>
              <div>
                <h2 className="text-lg font-bold" style={{ color: tc.text, letterSpacing: '-0.02em' }}>
                  {subscription?.tier || 'Free'} Tier
                </h2>
                <span className="text-[10px] px-2 py-0.5 rounded uppercase" style={{
                  background: `${STATUS_COLORS[subscription?.status || 'active']}20`,
                  color: STATUS_COLORS[subscription?.status || 'active'],
                  fontFamily: "'JetBrains Mono', monospace", fontWeight: 500,
                }}>{subscription?.status || 'active'}</span>
              </div>
            </div>
          </div>

          <div className="p-6">
            <div className="space-y-1 mb-6">
              {subscription?.expires_at && <InfoRow label="Expires" value={new Date(subscription.expires_at).toLocaleDateString()} />}
              {subscription?.started_at && <InfoRow label="Started" value={new Date(subscription.started_at).toLocaleDateString()} />}
            </div>

            {subscription?.features && subscription.features.length > 0 ? (
              <div>
                <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>Features</span>
                <div className="flex flex-wrap gap-2 mt-2">
                  {subscription.features.map((f, i) => (
                    <span key={i} className="text-xs px-3 py-1 rounded-lg" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>{f}</span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  REFINET Cloud runs entirely on free infrastructure. All platform capabilities are available at zero cost.
                </p>
                <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
                  Oracle Cloud Always Free (4 OCPU, 24GB RAM) + open-source stack = $0/month forever.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'fees' && (
        <div className="card animate-fade-in" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="px-5 py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-xs font-semibold uppercase" style={{ letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>
              Fee Schedule
            </span>
          </div>
          {fees.length === 0 ? (
            <div className="p-8 text-center">
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No fee schedule configured</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>The platform operates at zero cost. All services are free.</p>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  {['Service', 'Amount', 'Currency', 'Description'].map(h => (
                    <th key={h} className="text-left text-[11px] font-semibold uppercase px-5 py-3" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fees.map((f, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-elevated)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                    <td className="px-5 py-3 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{f.service}</td>
                    <td className="px-5 py-3 text-sm" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--refi-teal)' }}>{f.amount}</td>
                    <td className="px-5 py-3 text-sm" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)' }}>{f.currency}</td>
                    <td className="px-5 py-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>{f.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'history' && (
        <div className="card animate-fade-in" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="px-5 py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-xs font-semibold uppercase" style={{ letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>
              Payment History
            </span>
          </div>
          {payments.length === 0 ? (
            <div className="p-8 text-center">
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No payment history</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Transactions will appear here when payments are made.</p>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  {['Date', 'Type', 'Amount', 'Status', 'Chain'].map(h => (
                    <th key={h} className="text-left text-[11px] font-semibold uppercase px-5 py-3" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {payments.map(p => (
                  <tr key={p.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-elevated)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                    <td className="px-5 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>{new Date(p.created_at).toLocaleDateString()}</td>
                    <td className="px-5 py-3 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{p.item_type}</td>
                    <td className="px-5 py-3 text-sm" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--refi-teal)' }}>{p.amount}</td>
                    <td className="px-5 py-3">
                      <span className="text-[10px] px-2 py-0.5 rounded uppercase" style={{
                        background: `${STATUS_COLORS[p.status] || 'var(--text-tertiary)'}20`,
                        color: STATUS_COLORS[p.status] || 'var(--text-tertiary)',
                        fontFamily: "'JetBrains Mono', monospace", fontWeight: 500,
                      }}>{p.status}</span>
                    </td>
                    <td className="px-5 py-3 text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>{p.chain || '-'}</td>
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

/* ─── Sub-components ─── */

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) {
  return (
    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 10, padding: '14px 16px', transition: 'all 0.2s' }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-default)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}>
      <div className="flex items-center gap-2 mb-2">
        <span style={{ color, display: 'flex' }}>{icon}</span>
        <span className="text-[11px] uppercase font-medium" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>{label}</span>
      </div>
      <div className="text-xl font-bold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>{value}</div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <span className="text-xs font-medium w-28 shrink-0" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
      <span className="text-sm" style={{ color: 'var(--text-primary)' }}>{value}</span>
    </div>
  )
}

function TierIcon({ color }: { color?: string }) { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color || 'currentColor'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg> }
function StatusIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> }
function HistoryIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> }
