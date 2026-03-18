'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

type SettingsTab = 'account' | 'security' | 'api-keys' | 'admin'

interface SettingsModalProps {
  open: boolean
  onClose: () => void
}

export default function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [tab, setTab] = useState<SettingsTab>('account')
  const [profile, setProfile] = useState<any>(null)
  const [apiKeys, setApiKeys] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  // API Key creation
  const [newApiKey, setNewApiKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [keyScopes, setKeyScopes] = useState('inference:read')
  const [keyLimit, setKeyLimit] = useState(250)
  const [showCreateKey, setShowCreateKey] = useState(false)

  // Security
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [showTotpSetup, setShowTotpSetup] = useState(false)
  const [totpData, setTotpData] = useState<{ qr_code_base64: string; manual_entry_key: string } | null>(null)
  const [passwordForm, setPasswordForm] = useState({ email: '', password: '', confirmPassword: '' })
  const [totpCode, setTotpCode] = useState('')

  // Messages
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  const backdropRef = useRef<HTMLDivElement>(null)

  const getToken = () => localStorage.getItem('refinet_token')
  const authHeaders = (t: string) => ({ Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' })

  const loadData = useCallback(() => {
    const t = getToken()
    if (!t) return
    setLoading(true)
    Promise.all([
      fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${t}` } }).then(r => r.ok ? r.json() : null),
      fetch(`${API_URL}/keys`, { headers: { Authorization: `Bearer ${t}` } }).then(r => r.ok ? r.json() : []),
    ]).then(([prof, keys]) => {
      setProfile(prof)
      setApiKeys(Array.isArray(keys) ? keys : [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (open) {
      loadData()
      setMsg('')
      setError('')
      setNewApiKey(null)
      setCopied(false)
      setShowCreateKey(false)
      setShowPasswordForm(false)
      setShowTotpSetup(false)
    }
  }, [open, loadData])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const isAdmin = profile?.tier === 'admin' || profile?.tier === 'sovereign'

  const handleLogout = () => {
    localStorage.removeItem('refinet_token')
    localStorage.removeItem('refinet_refresh')
    window.dispatchEvent(new Event('refinet-auth-change'))
    onClose()
    window.location.href = '/'
  }

  const handleCreateKey = async () => {
    const t = getToken()
    if (!t || !keyName.trim()) return
    const resp = await fetch(`${API_URL}/keys`, {
      method: 'POST', headers: authHeaders(t),
      body: JSON.stringify({ name: keyName, scopes: keyScopes, daily_limit: keyLimit }),
    })
    const data = await resp.json()
    if (data.key) {
      setNewApiKey(data.key)
      setCopied(false)
      setKeyName('')
      setShowCreateKey(false)
      loadData()
      window.dispatchEvent(new Event('refinet-keys-changed'))
    }
  }

  const handleRevokeKey = async (keyId: string) => {
    const t = getToken()
    if (!t || !confirm('Revoke this API key? This cannot be undone.')) return
    await fetch(`${API_URL}/keys/${keyId}`, { method: 'DELETE', headers: authHeaders(t) })
    loadData()
    window.dispatchEvent(new Event('refinet-keys-changed'))
  }

  const handleCopyKey = () => {
    if (!newApiKey) return
    navigator.clipboard.writeText(newApiKey).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    })
  }

  const handleSetPassword = async () => {
    const t = getToken()
    if (!t) return
    setMsg(''); setError('')
    if (passwordForm.password !== passwordForm.confirmPassword) { setError('Passwords do not match'); return }
    if (passwordForm.password.length < 12) { setError('Password must be at least 12 characters'); return }
    try {
      const resp = await fetch(`${API_URL}/auth/settings/password`, {
        method: 'POST', headers: authHeaders(t),
        body: JSON.stringify({ email: passwordForm.email, password: passwordForm.password }),
      })
      if (!resp.ok) { const err = await resp.json().catch(() => ({ detail: 'Failed' })); throw new Error(err.detail) }
      setMsg('Password set successfully.')
      setShowPasswordForm(false)
      setPasswordForm({ email: '', password: '', confirmPassword: '' })
      loadData()
    } catch (e: any) { setError(e.message) }
  }

  const handleTotpSetup = async () => {
    const t = getToken()
    if (!t) return
    setMsg(''); setError('')
    try {
      const resp = await fetch(`${API_URL}/auth/settings/totp/setup`, { method: 'POST', headers: authHeaders(t) })
      if (!resp.ok) { const err = await resp.json().catch(() => ({ detail: 'Failed' })); throw new Error(err.detail) }
      const data = await resp.json()
      setTotpData(data)
      setShowTotpSetup(true)
    } catch (e: any) { setError(e.message) }
  }

  const handleTotpVerify = async () => {
    const t = getToken()
    if (!t) return
    setMsg(''); setError('')
    try {
      const resp = await fetch(`${API_URL}/auth/settings/totp/verify`, {
        method: 'POST', headers: authHeaders(t),
        body: JSON.stringify({ code: totpCode }),
      })
      if (!resp.ok) { const err = await resp.json().catch(() => ({ detail: 'Invalid code' })); throw new Error(err.detail) }
      setMsg('TOTP enabled.')
      setShowTotpSetup(false)
      setTotpData(null)
      setTotpCode('')
      loadData()
    } catch (e: any) { setError(e.message) }
  }

  const tabs: { id: SettingsTab; label: string; show: boolean }[] = [
    { id: 'account', label: 'Account', show: true },
    { id: 'security', label: 'Security', show: true },
    { id: 'api-keys', label: 'API Keys', show: true },
    { id: 'admin', label: 'Admin', show: !!isAdmin },
  ]

  return (
    <div
      ref={backdropRef}
      onClick={e => { if (e.target === backdropRef.current) onClose() }}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(0,0,0,0.6)',
        backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        className="animate-slide-up"
        style={{
          width: '100%', maxWidth: 640, maxHeight: 'calc(100vh - 80px)',
          background: 'var(--bg-primary)',
          border: '1px solid var(--border-default)',
          borderRadius: 14,
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 24px 64px rgba(0,0,0,0.4)',
        }}
      >
        {/* Modal Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          flexShrink: 0,
        }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.02em' }}>
            Settings
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={handleLogout}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: 'var(--error)', fontFamily: "'JetBrains Mono', monospace", padding: '4px 8px', borderRadius: 6 }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(248,113,113,0.1)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              Sign out
            </button>
            <button
              onClick={onClose}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: 4, borderRadius: 6, display: 'flex' }}
              onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)' }}
              onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-tertiary)'; e.currentTarget.style.background = 'transparent' }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>
        </div>

        {/* Tab Bar */}
        <div style={{
          display: 'flex', gap: 0,
          borderBottom: '1px solid var(--border-subtle)',
          paddingLeft: 20, paddingRight: 20,
          flexShrink: 0,
          overflowX: 'auto',
        }}>
          {tabs.filter(t => t.show).map(t => (
            <button
              key={t.id}
              onClick={() => { setTab(t.id); setMsg(''); setError('') }}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                padding: '10px 14px',
                fontSize: 12, fontWeight: tab === t.id ? 600 : 400,
                color: tab === t.id ? 'var(--refi-teal)' : 'var(--text-tertiary)',
                borderBottom: tab === t.id ? '2px solid var(--refi-teal)' : '2px solid transparent',
                transition: 'all 0.15s',
                whiteSpace: 'nowrap',
              }}
              onMouseEnter={e => { if (tab !== t.id) e.currentTarget.style.color = 'var(--text-secondary)' }}
              onMouseLeave={e => { if (tab !== t.id) e.currentTarget.style.color = 'var(--text-tertiary)' }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
          {/* Status Messages */}
          {msg && (
            <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 8, fontSize: 12, background: 'rgba(92,224,210,0.1)', border: '1px solid var(--refi-teal)', color: 'var(--refi-teal)' }}>
              {msg}
            </div>
          )}
          {error && (
            <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 8, fontSize: 12, background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', color: 'var(--error)' }}>
              {error}
            </div>
          )}

          {loading ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)', fontSize: 13 }} className="animate-pulse">Loading...</div>
          ) : (
            <>
              {/* ── Account Tab ── */}
              {tab === 'account' && profile && (
                <div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                    <Row label="Wallet" value={profile.eth_address || 'Not linked'} mono />
                    <Row label="Username" value={profile.username} />
                    <Row label="Email" value={profile.email || 'Not set'} />
                    <Row label="Tier" value={profile.tier} accent />
                    <Row label="Password" value={profile.password_enabled ? 'Enabled' : 'Not set'} />
                    <Row label="2FA (TOTP)" value={profile.totp_enabled ? 'Enabled' : 'Not set'} />
                  </div>
                </div>
              )}

              {/* ── Security Tab ── */}
              {tab === 'security' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {/* Password */}
                  <SectionBlock title="Email & Password" description={profile?.password_enabled ? `Enabled for ${profile.email}` : 'Add email/password as an alternative login method.'}>
                    {!showPasswordForm ? (
                      <button
                        onClick={() => { setShowPasswordForm(true); setMsg(''); setError('') }}
                        className="btn-secondary"
                        style={{ fontSize: 12, padding: '8px 16px' }}
                      >
                        {profile?.password_enabled ? 'Change Password' : 'Set Up Password'}
                      </button>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <input type="email" placeholder="Email address" value={passwordForm.email}
                          onChange={e => setPasswordForm({ ...passwordForm, email: e.target.value })}
                          className="input-base focus-glow" style={{ fontSize: 13 }} />
                        <input type="password" placeholder="Password (12+ characters)" value={passwordForm.password}
                          onChange={e => setPasswordForm({ ...passwordForm, password: e.target.value })}
                          className="input-base focus-glow" style={{ fontSize: 13 }} />
                        <input type="password" placeholder="Confirm password" value={passwordForm.confirmPassword}
                          onChange={e => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                          className="input-base focus-glow" style={{ fontSize: 13 }} />
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button onClick={handleSetPassword} className="btn-primary" style={{ fontSize: 12, padding: '8px 16px' }}>Save</button>
                          <button onClick={() => { setShowPasswordForm(false); setError('') }} className="btn-secondary" style={{ fontSize: 12, padding: '8px 16px' }}>Cancel</button>
                        </div>
                      </div>
                    )}
                  </SectionBlock>

                  {/* TOTP */}
                  <SectionBlock title="Two-Factor Authentication" description={profile?.totp_enabled ? 'TOTP 2FA is active.' : 'Add TOTP for additional login security.'}>
                    {profile?.totp_enabled ? (
                      <span style={{ fontSize: 12, color: 'var(--refi-teal)' }}>Enabled</span>
                    ) : !showTotpSetup ? (
                      <button onClick={handleTotpSetup} className="btn-secondary" style={{ fontSize: 12, padding: '8px 16px' }}>
                        Enable 2FA
                      </button>
                    ) : totpData && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Scan with Google Authenticator or Authy:</p>
                        <div style={{ display: 'flex', justifyContent: 'center', padding: 12, background: '#fff', borderRadius: 10 }}>
                          <img src={`data:image/png;base64,${totpData.qr_code_base64}`} alt="TOTP QR" style={{ width: 160, height: 160 }} />
                        </div>
                        <div style={{ padding: '8px 10px', borderRadius: 8, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>Manual key: </span>
                          <span style={{ fontSize: 11, color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace", userSelect: 'all' }}>{totpData.manual_entry_key}</span>
                        </div>
                        <input type="text" placeholder="Enter 6-digit code" value={totpCode}
                          onChange={e => setTotpCode(e.target.value)} maxLength={6}
                          className="input-base focus-glow" style={{ fontSize: 13, textAlign: 'center', letterSpacing: '0.3em', fontFamily: "'JetBrains Mono', monospace" }} />
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button onClick={handleTotpVerify} className="btn-primary" style={{ fontSize: 12, padding: '8px 16px' }}>Verify & Enable</button>
                          <button onClick={() => { setShowTotpSetup(false); setTotpData(null); setError('') }} className="btn-secondary" style={{ fontSize: 12, padding: '8px 16px' }}>Cancel</button>
                        </div>
                      </div>
                    )}
                  </SectionBlock>
                </div>
              )}

              {/* ── API Keys Tab ── */}
              {tab === 'api-keys' && (
                <div>
                  {/* New key banner — stays visible until user closes it */}
                  {newApiKey && (
                    <div style={{ marginBottom: 14, padding: 14, borderRadius: 10, background: 'rgba(92,224,210,0.08)', border: '1px solid var(--refi-teal)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--refi-teal)' }}>Key Created</span>
                        <button onClick={() => setNewApiKey(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: 2 }}>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                        </button>
                      </div>
                      <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8 }}>
                        Copy this key now. It cannot be retrieved after you close this.
                      </p>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '8px 10px', borderRadius: 6,
                        background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)',
                      }}>
                        <code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', userSelect: 'all' }}>{newApiKey}</code>
                        <button onClick={handleCopyKey} className="btn-primary" style={{ fontSize: 11, padding: '4px 12px', flexShrink: 0 }}>{copied ? 'Copied!' : 'Copy'}</button>
                      </div>
                      <div style={{ marginTop: 10, padding: '8px 10px', borderRadius: 6, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                        <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>Quick test:</p>
                        <code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
{`curl ${API_URL}/v1/chat/completions \\
  -H "Authorization: Bearer ${newApiKey.slice(0, 20)}..." \\
  -H "Content-Type: application/json" \\
  -d '{"model":"groot","messages":[{"role":"user","content":"hello"}]}'`}
                        </code>
                      </div>
                    </div>
                  )}

                  {/* Header + create button */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                      {apiKeys.length} key{apiKeys.length !== 1 ? 's' : ''} active
                    </span>
                    <button
                      onClick={() => { setShowCreateKey(!showCreateKey); setNewApiKey(null) }}
                      className="btn-primary"
                      style={{ fontSize: 11, padding: '6px 14px', letterSpacing: '0.04em' }}
                    >
                      {showCreateKey ? 'Cancel' : '+ New Key'}
                    </button>
                  </div>

                  {/* Create key form */}
                  {showCreateKey && (
                    <div style={{ marginBottom: 16, padding: 14, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <input className="input-base focus-glow" placeholder="Key name (e.g. Production, CLI, Mobile)" value={keyName}
                        onChange={e => setKeyName(e.target.value)} style={{ fontSize: 13 }} autoFocus />
                      <div>
                        <label style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4, display: 'block' }}>Scopes</label>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {['inference:read', 'devices:write', 'webhooks:write', 'registry:read', 'registry:write'].map(scope => (
                            <button key={scope} onClick={() => {
                              const s = keyScopes.split(' ').filter(Boolean)
                              setKeyScopes(s.includes(scope) ? s.filter(x => x !== scope).join(' ') : [...s, scope].join(' '))
                            }}
                              style={{
                                fontSize: 10, padding: '3px 8px', borderRadius: 4, cursor: 'pointer', border: '1px solid',
                                fontFamily: "'JetBrains Mono', monospace",
                                background: keyScopes.includes(scope) ? 'var(--refi-teal)' : 'var(--bg-tertiary)',
                                color: keyScopes.includes(scope) ? 'var(--text-inverse)' : 'var(--text-secondary)',
                                borderColor: keyScopes.includes(scope) ? 'var(--refi-teal)' : 'var(--border-default)',
                                transition: 'all 0.15s',
                              }}>
                              {scope}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <label style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Daily limit</label>
                        <input type="number" className="input-base focus-glow" style={{ width: 100, fontSize: 13 }}
                          value={keyLimit} onChange={e => setKeyLimit(Number(e.target.value))} min={1} max={10000} />
                      </div>
                      <button className="btn-primary" onClick={handleCreateKey} disabled={!keyName.trim()}
                        style={{ fontSize: 12, padding: '8px 16px', width: 'fit-content' }}>Create Key</button>
                    </div>
                  )}

                  {/* Key list */}
                  {apiKeys.length === 0 && !newApiKey ? (
                    <div style={{ textAlign: 'center', padding: '24px 16px' }}>
                      <div style={{ fontSize: 28, marginBottom: 8 }}>
                        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ margin: '0 auto', display: 'block' }}>
                          <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
                        </svg>
                      </div>
                      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>No API keys yet</p>
                      <p style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Create a key to use the REFINET API programmatically.</p>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {apiKeys.map((k: any) => {
                        const pct = k.daily_limit > 0 ? Math.min((k.requests_today / k.daily_limit) * 100, 100) : 0
                        const barColor = pct > 90 ? 'var(--error)' : pct > 70 ? 'rgb(250,204,21)' : 'var(--refi-teal)'
                        return (
                          <div key={k.id} style={{
                            padding: '10px 12px', borderRadius: 8,
                            background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <code style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>{k.prefix}...</code>
                                <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 500 }}>{k.name}</span>
                              </div>
                              <button onClick={() => handleRevokeKey(k.id)}
                                style={{
                                  fontSize: 10, padding: '3px 8px', borderRadius: 5, cursor: 'pointer',
                                  background: 'rgba(248,113,113,0.08)', color: 'var(--error)',
                                  border: '1px solid rgba(248,113,113,0.15)', transition: 'all 0.15s',
                                }}
                                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(248,113,113,0.15)')}
                                onMouseLeave={e => (e.currentTarget.style.background = 'rgba(248,113,113,0.08)')}
                              >
                                Revoke
                              </button>
                            </div>
                            {/* Usage bar */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                              <div style={{ flex: 1, height: 4, borderRadius: 2, background: 'var(--bg-tertiary)', overflow: 'hidden' }}>
                                <div style={{ width: `${pct}%`, height: '100%', borderRadius: 2, background: barColor, transition: 'width 0.4s' }} />
                              </div>
                              <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)', flexShrink: 0 }}>{k.requests_today}/{k.daily_limit} today</span>
                            </div>
                            {/* Meta row */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                              <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                                Scopes: <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{k.scopes || 'none'}</span>
                              </span>
                              <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                                Created {k.created_at ? formatDate(k.created_at) : 'unknown'}
                              </span>
                              {k.last_used_at && (
                                <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                                  Last used {formatDate(k.last_used_at)}
                                </span>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* ── Admin Tab ── */}
              {tab === 'admin' && isAdmin && (
                <div>
                  <Link href="/admin/" onClick={onClose} style={{ color: 'var(--refi-teal)', fontSize: 13, textDecoration: 'underline', textUnderlineOffset: 2 }}>
                    Open Admin Panel
                  </Link>
                  <div style={{ marginTop: 12 }}>
                    <Link href="/knowledge/" onClick={onClose} style={{ color: 'var(--refi-teal)', fontSize: 13, textDecoration: 'underline', textUnderlineOffset: 2 }}>
                      Knowledge Base Management
                    </Link>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Sub-components ─── */

function Row({ label, value, mono, accent }: { label: string; value: string; mono?: boolean; accent?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '9px 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{label}</span>
      <span style={{
        fontSize: 13,
        fontFamily: mono ? "'JetBrains Mono', monospace" : 'inherit',
        color: accent ? 'var(--refi-teal)' : 'var(--text-primary)',
        fontWeight: accent ? 600 : 400,
      }}>{value}</span>
    </div>
  )
}

function SectionBlock({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div style={{ padding: 14, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>{title}</h3>
      <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 12 }}>{description}</p>
      {children}
    </div>
  )
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  const now = Date.now()
  const diff = Math.floor((now - d.getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
