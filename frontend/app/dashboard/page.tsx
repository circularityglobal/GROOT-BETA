'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

export default function DashboardPage() {
  const [profile, setProfile] = useState<any>(null)
  const [keys, setKeys] = useState<any[]>([])
  const [devices, setDevices] = useState<any[]>([])
  const [activity, setActivity] = useState<any[]>([])
  const [webhookCount, setWebhookCount] = useState(0)
  const [loading, setLoading] = useState(true)

  const loadDashboardData = useCallback((token: string) => {
    const headers = { Authorization: `Bearer ${token}` }
    return Promise.all([
      fetch(`${API_URL}/keys`, { headers }).then(r => r.ok ? r.json() : []).catch(() => []),
      fetch(`${API_URL}/devices`, { headers }).then(r => r.ok ? r.json() : []).catch(() => []),
      fetch(`${API_URL}/keys/activity`, { headers }).then(r => r.ok ? r.json() : []).catch(() => []),
      fetch(`${API_URL}/webhooks`, { headers }).then(r => r.ok ? r.json() : []).catch(() => []),
    ]).then(([k, d, act, wh]) => {
      setKeys(Array.isArray(k) ? k : [])
      setDevices(Array.isArray(d) ? d : [])
      setActivity(Array.isArray(act) ? act : [])
      setWebhookCount(Array.isArray(wh) ? wh.length : 0)
    })
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    if (!token) { window.location.href = '/settings/'; return }

    const headers = { Authorization: `Bearer ${token}` }

    fetch(`${API_URL}/auth/me`, { headers })
      .then((r) => {
        if (r.status === 401) {
          const refreshToken = localStorage.getItem('refinet_refresh')
          if (refreshToken) {
            return fetch(`${API_URL}/auth/token/refresh`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ refresh_token: refreshToken }),
            })
              .then((rr) => { if (!rr.ok) throw new Error('Refresh failed'); return rr.json() })
              .then((tokens) => {
                localStorage.setItem('refinet_token', tokens.access_token)
                localStorage.setItem('refinet_refresh', tokens.refresh_token)
                window.dispatchEvent(new Event('refinet-auth-change'))
                window.location.reload()
                return null
              })
              .catch(() => {
                localStorage.removeItem('refinet_token')
                localStorage.removeItem('refinet_refresh')
                window.location.href = '/settings/'
                return null
              })
          }
          localStorage.removeItem('refinet_token')
          localStorage.removeItem('refinet_refresh')
          window.location.href = '/settings/'
          return null
        }
        if (!r.ok) throw new Error('Profile fetch failed')
        return r.json()
      })
      .then((prof) => {
        if (!prof) return
        setProfile(prof)
        return loadDashboardData(localStorage.getItem('refinet_token')!).then(() => setLoading(false))
      })
      .catch(() => setLoading(false))
  }, [loadDashboardData])

  // Refresh dashboard when keys are created/revoked from Settings modal
  useEffect(() => {
    const onKeysChanged = () => {
      const t = localStorage.getItem('refinet_token')
      if (t) loadDashboardData(t)
    }
    window.addEventListener('refinet-keys-changed', onKeysChanged)
    return () => window.removeEventListener('refinet-keys-changed', onKeysChanged)
  }, [loadDashboardData])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '60vh' }}>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)', fontSize: 13 }} className="animate-pulse">
          Loading...
        </div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '60vh', flexDirection: 'column', gap: 16 }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Connect your wallet to continue.</p>
        <Link href="/settings/" className="btn-primary" style={{ textDecoration: 'none' }}>Sign In</Link>
      </div>
    )
  }

  const greeting = getGreeting()

  return (
    <div style={{ padding: '24px 28px', maxWidth: 1100, margin: '0 auto' }} className="animate-fade-in">
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)', margin: 0 }}>
          {greeting}, {profile.username}
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-tertiary)', marginTop: 4 }}>
          Here&apos;s what&apos;s happening with your infrastructure.
        </p>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 24 }}>
        <MiniStat
          icon={<WalletIconStat />}
          label="Wallet"
          value={profile.eth_address ? `${profile.eth_address.slice(0, 6)}...${profile.eth_address.slice(-4)}` : 'N/A'}
          color="var(--refi-teal)"
        />
        <MiniStat icon={<KeyIconStat />} label="API Keys" value={keys.length.toString()} color="var(--refi-teal)" />
        <MiniStat icon={<DeviceIconStat />} label="Devices" value={devices.length.toString()} color="rgb(96,165,250)" />
        <MiniStat icon={<WebhookIconStat />} label="Webhooks" value={webhookCount.toString()} color="rgb(167,139,250)" />
        <MiniStat icon={<TierIconStat />} label="Tier" value={profile.tier} color="rgb(250,204,21)" />
      </div>

      {/* Two-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }} className="dashboard-two-col">
        {/* API Usage */}
        <Section title="API Usage" action={{ href: '/settings/', label: 'Manage' }}>
          {keys.length > 0 ? keys.map((k: any) => {
            const pct = k.daily_limit > 0 ? Math.min((k.requests_today / k.daily_limit) * 100, 100) : 0
            const color = pct > 90 ? 'var(--error)' : pct > 70 ? 'rgb(250,204,21)' : 'var(--refi-teal)'
            return (
              <div key={k.id} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>{k.prefix}...</span>
                  <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>{k.requests_today}/{k.daily_limit}</span>
                </div>
                <div style={{ width: '100%', height: 6, borderRadius: 3, background: 'var(--bg-tertiary)' }}>
                  <div style={{ width: `${pct}%`, height: '100%', borderRadius: 3, background: color, transition: 'width 0.4s ease' }} />
                </div>
              </div>
            )
          }) : <EmptyState text="No API keys yet" action={{ href: '/settings/', label: 'Create key' }} />}
        </Section>

        {/* Connected Devices */}
        <Section title="Devices" action={{ href: '/devices/', label: 'Manage' }}>
          {devices.length > 0 ? devices.slice(0, 5).map((d: any) => (
            <div key={d.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  width: 7, height: 7, borderRadius: '50%', display: 'inline-block', flexShrink: 0,
                  background: d.status === 'active' ? 'var(--success)' : 'var(--text-tertiary)',
                }} />
                <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{d.name}</span>
                <TypeBadge type={d.device_type} />
              </div>
              <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>
                {d.telemetry_count} events
              </span>
            </div>
          )) : <EmptyState text="No devices registered" action={{ href: '/devices/', label: 'Add device' }} />}
        </Section>
      </div>

      {/* Recent Activity */}
      <Section title="Recent Activity" fullWidth>
        {activity.length > 0 ? activity.slice(0, 8).map((a: any, i: number) => (
          <div key={a.id || i} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0',
            borderBottom: '1px solid var(--border-subtle)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
              <span style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>
                {a.endpoint || '/v1/chat/completions'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>
                {a.tokens_used || 0} tok
              </span>
              <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>
                {a.latency_ms || 0}ms
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                {a.created_at ? timeAgo(a.created_at) : ''}
              </span>
            </div>
          </div>
        )) : <EmptyState text="No activity yet. Make an API call to see usage." />}
      </Section>

      <style jsx>{`
        @media (max-width: 768px) {
          .dashboard-two-col {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  )
}

/* ─── Sub-components ─── */

function MiniStat({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) {
  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 10,
        padding: '14px 16px',
        transition: 'all 0.2s',
        cursor: 'default',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-default)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ color, display: 'flex' }}>{icon}</span>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', lineHeight: 1 }}>
        {value}
      </div>
    </div>
  )
}

function Section({ title, action, children, fullWidth }: {
  title: string; action?: { href: string; label: string }; children: React.ReactNode; fullWidth?: boolean
}) {
  return (
    <div style={{
      background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 10,
      padding: 16, gridColumn: fullWidth ? '1 / -1' : undefined,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>{title}</h3>
        {action && (
          <Link href={action.href} style={{ fontSize: 11, color: 'var(--refi-teal)', textDecoration: 'none', fontFamily: "'JetBrains Mono', monospace" }}
            onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
            onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}>
            {action.label} &rarr;
          </Link>
        )}
      </div>
      {children}
    </div>
  )
}

function EmptyState({ text, action }: { text: string; action?: { href: string; label: string } }) {
  return (
    <div style={{ padding: '12px 0', textAlign: 'center' }}>
      <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: 0 }}>{text}</p>
      {action && (
        <Link href={action.href} style={{ fontSize: 12, color: 'var(--refi-teal)', textDecoration: 'none', marginTop: 6, display: 'inline-block' }}>
          {action.label} &rarr;
        </Link>
      )}
    </div>
  )
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    iot: { bg: 'rgba(92,224,210,0.12)', text: 'var(--refi-teal)' },
    plc: { bg: 'rgba(96,165,250,0.12)', text: 'rgb(96,165,250)' },
    dlt: { bg: 'rgba(167,139,250,0.12)', text: 'rgb(167,139,250)' },
  }
  const c = colors[type?.toLowerCase()] || colors.iot
  return (
    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: c.bg, color: c.text, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em', fontFamily: "'JetBrains Mono', monospace" }}>
      {type}
    </span>
  )
}

/* ─── Helpers ─── */
function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

function timeAgo(dateStr: string) {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diff = Math.floor((now - then) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

/* ─── Stat Icons ─── */
function WalletIconStat() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/></svg> }
function KeyIconStat() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg> }
function DeviceIconStat() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2M9 2v2M15 20v2M9 20v2M2 15h2M2 9h2M20 15h2M20 9h2"/></svg> }
function WebhookIconStat() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 16.98h1.67c1.47 0 2.68-1.2 2.68-2.68V7.35c0-1.47-1.2-2.68-2.68-2.68H4.33C2.87 4.67 1.67 5.87 1.67 7.35v6.95c0 1.47 1.2 2.68 2.68 2.68H6"/><polyline points="12 15 17 20 12 25"/></svg> }
function TierIconStat() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg> }
