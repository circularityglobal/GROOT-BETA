'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'

interface FeeSchedule { service: string; amount: string; currency: string; description: string }
interface Payment { id: string; item_type: string; amount: string; status: string; chain?: string; created_at: string }
interface Subscription { tier: string; status: string; features: string[]; expires_at?: string }

export default function PaymentsPage() {
  const [tab, setTab] = useState<'subscription' | 'fees' | 'history'>('subscription')
  const [fees, setFees] = useState<FeeSchedule[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const headers = () => {
    const token = localStorage.getItem('refinet_token')
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  }

  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/payments/fee-schedule`, { headers: headers() }).then(r => r.json()).catch(() => []),
      fetch(`${API_URL}/payments/history`, { headers: headers() }).then(r => r.json()).catch(() => []),
      fetch(`${API_URL}/payments/subscriptions/status`, { headers: headers() }).then(r => r.json()).catch(() => null),
    ]).then(([f, p, s]) => {
      setFees(Array.isArray(f) ? f : f.fees || [])
      setPayments(Array.isArray(p) ? p : p.payments || [])
      setSubscription(s)
      setLoading(false)
    })
  }, [])

  const statusColor = (s: string) => {
    if (s === 'completed' || s === 'active') return '#22c55e'
    if (s === 'pending') return '#f59e0b'
    if (s === 'failed' || s === 'cancelled') return '#ef4444'
    return '#6b7280'
  }

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>Payments & Subscriptions</h1>

      {error && <div style={{ padding: 12, background: '#dc2626', color: '#fff', borderRadius: 6, marginBottom: 16 }}>{error}</div>}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {(['subscription', 'fees', 'history'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
              background: tab === t ? '#3b82f6' : 'var(--bg-secondary)', color: tab === t ? '#fff' : 'inherit', fontWeight: 600 }}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>Loading...</div>
      ) : (
        <>
          {tab === 'subscription' && (
            <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 24 }}>
              <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Current Subscription</h2>
              {subscription ? (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '12px 20px' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Tier:</span>
                    <span style={{ fontWeight: 700, fontSize: 16 }}>{subscription.tier}</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Status:</span>
                    <span style={{ color: statusColor(subscription.status) }}>{subscription.status}</span>
                    {subscription.expires_at && (
                      <><span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Expires:</span>
                      <span>{new Date(subscription.expires_at).toLocaleDateString()}</span></>
                    )}
                  </div>
                  {subscription.features && subscription.features.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <span style={{ fontWeight: 600, color: 'var(--text-secondary)', fontSize: 13 }}>Features:</span>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                        {subscription.features.map((f, i) => (
                          <span key={i} style={{ padding: '3px 10px', background: 'var(--bg-secondary)', borderRadius: 12, fontSize: 12 }}>{f}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ color: 'var(--text-secondary)' }}>
                  <p>You are on the <strong>Free</strong> tier. All platform capabilities are available at zero cost.</p>
                  <p style={{ marginTop: 8, fontSize: 13 }}>REFINET Cloud runs entirely on free infrastructure. No premium tiers exist yet.</p>
                </div>
              )}
            </div>
          )}

          {tab === 'fees' && (
            <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-secondary)' }}>
                    <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600 }}>Service</th>
                    <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600 }}>Amount</th>
                    <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600 }}>Currency</th>
                    <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600 }}>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {fees.length === 0 ? (
                    <tr><td colSpan={4} style={{ padding: 20, textAlign: 'center', color: 'var(--text-secondary)' }}>No fee schedule configured. Platform is free.</td></tr>
                  ) : (
                    fees.map((f, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '10px 16px', fontSize: 13, fontWeight: 500 }}>{f.service}</td>
                        <td style={{ padding: '10px 16px', fontSize: 13 }}>{f.amount}</td>
                        <td style={{ padding: '10px 16px', fontSize: 13 }}>{f.currency}</td>
                        <td style={{ padding: '10px 16px', fontSize: 13, color: 'var(--text-secondary)' }}>{f.description}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {tab === 'history' && (
            <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-secondary)' }}>
                    <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600 }}>Date</th>
                    <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600 }}>Type</th>
                    <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600 }}>Amount</th>
                    <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600 }}>Status</th>
                    <th style={{ padding: '10px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600 }}>Chain</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.length === 0 ? (
                    <tr><td colSpan={5} style={{ padding: 20, textAlign: 'center', color: 'var(--text-secondary)' }}>No payment history</td></tr>
                  ) : (
                    payments.map(p => (
                      <tr key={p.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '10px 16px', fontSize: 13 }}>{new Date(p.created_at).toLocaleDateString()}</td>
                        <td style={{ padding: '10px 16px', fontSize: 13 }}>{p.item_type}</td>
                        <td style={{ padding: '10px 16px', fontSize: 13 }}>{p.amount}</td>
                        <td style={{ padding: '10px 16px', fontSize: 13 }}><span style={{ color: statusColor(p.status) }}>{p.status}</span></td>
                        <td style={{ padding: '10px 16px', fontSize: 13 }}>{p.chain || '-'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
