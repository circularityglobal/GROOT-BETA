'use client'

import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '@/lib/config'

interface OnboardingWizardProps {
  onComplete: () => void
}

type Step = 'welcome' | 'profile' | 'security' | 'apikey' | 'done'

const STEPS: { id: Step; label: string }[] = [
  { id: 'welcome', label: 'Welcome' },
  { id: 'profile', label: 'Profile' },
  { id: 'security', label: 'Security' },
  { id: 'apikey', label: 'API Key' },
  { id: 'done', label: 'Done' },
]

export default function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const [step, setStep] = useState<Step>('welcome')
  const [profile, setProfile] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  // Profile fields
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [marketingConsent, setMarketingConsent] = useState(false)

  // Security fields
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [totpData, setTotpData] = useState<{ qr_code_base64: string; manual_entry_key: string } | null>(null)
  const [totpCode, setTotpCode] = useState('')
  const [passwordSet, setPasswordSet] = useState(false)
  const [totpEnabled, setTotpEnabled] = useState(false)

  // API Key fields
  const [keyName, setKeyName] = useState('My First Key')
  const [newApiKey, setNewApiKey] = useState('')
  const [keyCopied, setKeyCopied] = useState(false)

  // Status
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [saving, setSaving] = useState(false)

  const getToken = () => localStorage.getItem('refinet_token')
  const authHeaders = useCallback(() => {
    const t = getToken()
    return { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' }
  }, [])

  // Load profile on mount
  useEffect(() => {
    const t = getToken()
    if (!t) { setLoading(false); return }
    fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${t}` } })
      .then(r => r.ok ? r.json() : null)
      .then(prof => {
        if (prof) {
          setProfile(prof)
          setUsername(prof.username || '')
          setEmail(prof.email || '')
          setPasswordSet(!!prof.password_enabled)
          setTotpEnabled(!!prof.totp_enabled)
        }
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const reloadProfile = useCallback(() => {
    const t = getToken()
    if (!t) return
    fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${t}` } })
      .then(r => r.ok ? r.json() : null)
      .then(prof => {
        if (prof) {
          setProfile(prof)
          setPasswordSet(!!prof.password_enabled)
          setTotpEnabled(!!prof.totp_enabled)
        }
      })
      .catch(() => {})
  }, [])

  const handleSaveProfile = async () => {
    setSaving(true); setError(''); setMsg('')
    try {
      const body: any = {}
      if (username.trim() && username !== profile?.username) body.username = username.trim()
      if (email.trim() && email !== profile?.email) body.email = email.trim()
      body.marketing_consent = marketingConsent
      const resp = await fetch(`${API_URL}/auth/me`, { method: 'PUT', headers: authHeaders(), body: JSON.stringify(body) })
      if (!resp.ok) { const d = await resp.json().catch(() => ({})); setError(d.detail || 'Failed to update profile'); setSaving(false); return }
      setMsg('Profile updated')
      reloadProfile()
      setTimeout(() => { setMsg(''); setStep('security') }, 800)
    } catch (e: any) { setError(e.message) }
    setSaving(false)
  }

  const handleSetPassword = async () => {
    setSaving(true); setError(''); setMsg('')
    if (!email.trim()) { setError('Enter your email first in the Profile step'); setSaving(false); return }
    if (password.length < 12) { setError('Password must be at least 12 characters'); setSaving(false); return }
    if (password !== confirmPassword) { setError('Passwords do not match'); setSaving(false); return }
    try {
      const resp = await fetch(`${API_URL}/auth/settings/password`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ email, password }),
      })
      if (!resp.ok) { const d = await resp.json().catch(() => ({})); setError(d.detail || 'Failed'); setSaving(false); return }
      setPasswordSet(true)
      setMsg('Password set successfully')
      setPassword(''); setConfirmPassword('')
      reloadProfile()
      setTimeout(() => setMsg(''), 2000)
    } catch (e: any) { setError(e.message) }
    setSaving(false)
  }

  const handleTotpSetup = async () => {
    setSaving(true); setError('')
    try {
      const resp = await fetch(`${API_URL}/auth/settings/totp/setup`, { method: 'POST', headers: authHeaders() })
      if (!resp.ok) { const d = await resp.json().catch(() => ({})); setError(d.detail || 'Failed'); setSaving(false); return }
      const data = await resp.json()
      setTotpData(data)
    } catch (e: any) { setError(e.message) }
    setSaving(false)
  }

  const handleTotpVerify = async () => {
    setSaving(true); setError(''); setMsg('')
    try {
      const resp = await fetch(`${API_URL}/auth/settings/totp/verify`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ code: totpCode }),
      })
      if (!resp.ok) { const d = await resp.json().catch(() => ({})); setError(d.detail || 'Invalid code'); setSaving(false); return }
      setTotpEnabled(true)
      setTotpData(null)
      setTotpCode('')
      setMsg('2FA enabled!')
      reloadProfile()
      setTimeout(() => setMsg(''), 2000)
    } catch (e: any) { setError(e.message) }
    setSaving(false)
  }

  const handleCreateKey = async () => {
    setSaving(true); setError('')
    try {
      const resp = await fetch(`${API_URL}/keys`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ name: keyName, scopes: 'inference:read', daily_limit: 250 }),
      })
      const data = await resp.json()
      if (!resp.ok) { setError(data.detail || 'Failed to create key'); setSaving(false); return }
      setNewApiKey(data.key)
      window.dispatchEvent(new Event('refinet-keys-changed'))
    } catch (e: any) { setError(e.message) }
    setSaving(false)
  }

  const handleFinish = () => {
    localStorage.setItem('refinet_onboarding_complete', 'true')
    window.dispatchEvent(new Event('refinet-keys-changed'))
    onComplete()
  }

  const handleSkip = () => {
    localStorage.setItem('refinet_onboarding_complete', 'true')
    onComplete()
  }

  const currentIndex = STEPS.findIndex(s => s.id === step)
  const passwordStrength = password.length === 0 ? 0 : password.length < 8 ? 1 : password.length < 12 ? 2 : password.length < 16 ? 3 : 4
  const strengthColors = ['var(--bg-tertiary)', 'var(--error)', 'rgb(250,204,21)', 'var(--refi-teal)', 'var(--success)']

  const securityComplete = passwordSet && totpEnabled
  const allSecurityDone = passwordSet && totpEnabled

  if (loading) {
    return (
      <div style={{ position: 'fixed', inset: 0, zIndex: 200, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)', fontSize: 13 }}>Loading...</div>
      </div>
    )
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div className="animate-slide-up" style={{ width: '100%', maxWidth: 560, maxHeight: 'calc(100vh - 60px)', background: 'var(--bg-primary)', border: '1px solid var(--border-default)', borderRadius: 14, display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 24px 64px rgba(0,0,0,0.5)' }}>

        {/* Header */}
        <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.02em' }}>
              {step === 'welcome' ? 'Welcome to REFINET Cloud' :
               step === 'profile' ? 'Set Up Your Profile' :
               step === 'security' ? 'Secure Your Account' :
               step === 'apikey' ? 'Get Your API Key' :
               'You\'re All Set'}
            </h2>
            <p style={{ fontSize: 11, color: 'var(--text-tertiary)', margin: '2px 0 0', fontFamily: "'JetBrains Mono', monospace" }}>
              Step {currentIndex + 1} of {STEPS.length}
            </p>
          </div>
          <button onClick={handleSkip} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace", padding: '4px 8px', borderRadius: 6 }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-secondary)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-tertiary)')}>
            Skip for now
          </button>
        </div>

        {/* Progress bar */}
        <div style={{ display: 'flex', gap: 3, padding: '0 24px', paddingTop: 12, flexShrink: 0 }}>
          {STEPS.map((s, i) => (
            <div key={s.id} style={{ flex: 1, height: 3, borderRadius: 2, background: i <= currentIndex ? 'var(--refi-teal)' : 'var(--bg-tertiary)', transition: 'background 0.3s' }} />
          ))}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
          {/* Messages */}
          {error && <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 8, fontSize: 12, background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', color: 'var(--error)' }}>{error}</div>}
          {msg && <div className="animate-fade-in" style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 8, fontSize: 12, background: 'rgba(92,224,210,0.1)', border: '1px solid var(--refi-teal)', color: 'var(--refi-teal)' }}>{msg}</div>}

          {/* ── Welcome ── */}
          {step === 'welcome' && (
            <div className="animate-fade-in">
              <div style={{ textAlign: 'center', marginBottom: 24 }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>{'\uD83C\uDF31'}</div>
                <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: 400, margin: '0 auto' }}>
                  Let&apos;s get you set up in under 3 minutes. We&apos;ll customize your profile, lock down your account with enterprise-grade security, and generate your first API key.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  { icon: '\uD83D\uDC64', title: 'Profile', desc: 'Set your username and email', time: '30 sec' },
                  { icon: '\uD83D\uDD12', title: 'Security', desc: 'Password + Two-Factor Authentication', time: '90 sec' },
                  { icon: '\uD83D\uDD11', title: 'API Key', desc: 'Generate your first inference key', time: '30 sec' },
                ].map(item => (
                  <div key={item.title} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                    <span style={{ fontSize: 20, width: 32, textAlign: 'center' }}>{item.icon}</span>
                    <div style={{ flex: 1 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{item.title}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 8 }}>{item.desc}</span>
                    </div>
                    <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>~{item.time}</span>
                  </div>
                ))}
              </div>

              <button onClick={() => { setError(''); setStep('profile') }} className="btn-primary" style={{ width: '100%', marginTop: 20, padding: '12px 0', fontSize: 14, fontWeight: 600 }}>
                Let&apos;s Go
              </button>
            </div>
          )}

          {/* ── Profile ── */}
          {step === 'profile' && (
            <div className="animate-fade-in">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20, padding: '12px 14px', borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--refi-teal-glow)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0 }}>{'\uD83D\uDC64'}</span>
                <div>
                  <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>Wallet Connected</p>
                  <p style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: 'var(--refi-teal)' }}>
                    {profile?.eth_address ? `${profile.eth_address.slice(0, 8)}...${profile.eth_address.slice(-6)}` : 'Unknown'}
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>Username</label>
                  <input className="input-base focus-glow" style={{ width: '100%', fontSize: 14 }} value={username} onChange={e => setUsername(e.target.value)} placeholder="Choose a username" />
                  <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>Visible on your public profile and registry projects</p>
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>Email</label>
                  <input className="input-base focus-glow" type="email" style={{ width: '100%', fontSize: 14 }} value={email} onChange={e => setEmail(e.target.value)} placeholder="your@email.com" />
                  <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>Required for password recovery and admin alerts</p>
                </div>
              </div>

              {/* Marketing consent */}
              <div style={{ marginTop: 16, padding: '14px 16px', borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer' }}>
                  <div onClick={() => setMarketingConsent(!marketingConsent)} style={{
                    width: 18, height: 18, borderRadius: 4, flexShrink: 0, marginTop: 1,
                    border: `2px solid ${marketingConsent ? 'var(--refi-teal)' : 'var(--border-default)'}`,
                    background: marketingConsent ? 'var(--refi-teal)' : 'transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', transition: 'all 0.15s',
                  }}>
                    {marketingConsent && (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-inverse)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </div>
                  <div>
                    <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                      Keep me updated on REFINET Cloud
                    </span>
                    <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 3, lineHeight: 1.5 }}>
                      Receive platform updates, new features, community events, and ecosystem news.
                      No spam &mdash; unsubscribe anytime. We never share your data with third parties.
                    </p>
                  </div>
                </label>
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 20 }}>
                <button onClick={() => setStep('welcome')} className="btn-secondary" style={{ padding: '10px 20px' }}>Back</button>
                <button onClick={handleSaveProfile} className="btn-primary" disabled={saving} style={{ flex: 1, padding: '10px 0' }}>
                  {saving ? 'Saving...' : 'Continue'}
                </button>
              </div>
            </div>
          )}

          {/* ── Security ── */}
          {step === 'security' && (
            <div className="animate-fade-in">
              {/* Security checklist */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                <SecurityBadge label="Wallet (SIWE)" done={true} />
                <SecurityBadge label="Password" done={passwordSet} />
                <SecurityBadge label="2FA (TOTP)" done={totpEnabled} />
              </div>

              {!allSecurityDone && (
                <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(250,204,21,0.08)', border: '1px solid rgba(250,204,21,0.2)', marginBottom: 16 }}>
                  <p style={{ fontSize: 12, color: 'rgb(250,204,21)' }}>
                    Complete all 3 layers to unlock API key management and AI provider connections.
                  </p>
                </div>
              )}

              {/* Password section */}
              {!passwordSet ? (
                <div style={{ padding: 16, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', marginBottom: 12 }}>
                  <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>Set Password</h3>
                  <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 12 }}>Enables email login and unlocks full security features</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <input type="password" className="input-base focus-glow" style={{ fontSize: 13 }} placeholder="Password (12+ characters)" value={password} onChange={e => setPassword(e.target.value)} />
                    {password.length > 0 && (
                      <div style={{ display: 'flex', gap: 3 }}>
                        {[1,2,3,4].map(i => (
                          <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, background: i <= passwordStrength ? strengthColors[passwordStrength] : 'var(--bg-tertiary)', transition: 'background 0.2s' }} />
                        ))}
                      </div>
                    )}
                    <input type="password" className="input-base focus-glow" style={{ fontSize: 13 }} placeholder="Confirm password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} />
                    <button onClick={handleSetPassword} className="btn-primary" disabled={saving || password.length < 12} style={{ fontSize: 12, padding: '8px 16px', width: 'fit-content' }}>
                      {saving ? 'Setting...' : 'Set Password'}
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ padding: '12px 16px', borderRadius: 10, background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.2)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span>{'\u2705'}</span>
                  <span style={{ fontSize: 13, color: 'var(--success)', fontWeight: 500 }}>Password set for {email || profile?.email}</span>
                </div>
              )}

              {/* TOTP section */}
              {!totpEnabled ? (
                <div style={{ padding: 16, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                  <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>Two-Factor Authentication</h3>
                  <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 12 }}>Use Google Authenticator or Authy for a second layer of protection</p>

                  {!totpData ? (
                    <button onClick={handleTotpSetup} className="btn-secondary" disabled={saving || !passwordSet} style={{ fontSize: 12, padding: '8px 16px' }}>
                      {!passwordSet ? 'Set password first' : saving ? 'Loading...' : 'Enable 2FA'}
                    </button>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Scan this QR code with your authenticator app:</p>
                      <div style={{ display: 'flex', justifyContent: 'center', padding: 12, background: '#fff', borderRadius: 10 }}>
                        <img src={`data:image/png;base64,${totpData.qr_code_base64}`} alt="TOTP QR" style={{ width: 160, height: 160 }} />
                      </div>
                      <div style={{ padding: '8px 10px', borderRadius: 8, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)' }}>
                        <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>Manual key: </span>
                        <span style={{ fontSize: 11, color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace", userSelect: 'all' }}>{totpData.manual_entry_key}</span>
                      </div>
                      <input type="text" className="input-base focus-glow" placeholder="Enter 6-digit code" value={totpCode} onChange={e => setTotpCode(e.target.value)} maxLength={6}
                        style={{ fontSize: 16, textAlign: 'center', letterSpacing: '0.3em', fontFamily: "'JetBrains Mono', monospace" }} />
                      <button onClick={handleTotpVerify} className="btn-primary" disabled={saving || totpCode.length !== 6} style={{ fontSize: 12, padding: '8px 16px' }}>
                        {saving ? 'Verifying...' : 'Verify & Enable'}
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ padding: '12px 16px', borderRadius: 10, background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.2)', display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span>{'\u2705'}</span>
                  <span style={{ fontSize: 13, color: 'var(--success)', fontWeight: 500 }}>Two-Factor Authentication enabled</span>
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, marginTop: 20 }}>
                <button onClick={() => setStep('profile')} className="btn-secondary" style={{ padding: '10px 20px' }}>Back</button>
                <button onClick={() => { setError(''); setStep('apikey') }} className="btn-primary" style={{ flex: 1, padding: '10px 0' }}>
                  {allSecurityDone ? 'Continue' : 'Skip for now'}
                </button>
              </div>
            </div>
          )}

          {/* ── API Key ── */}
          {step === 'apikey' && (
            <div className="animate-fade-in">
              {!allSecurityDone && (
                <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(250,204,21,0.08)', border: '1px solid rgba(250,204,21,0.2)', marginBottom: 16 }}>
                  <p style={{ fontSize: 12, color: 'rgb(250,204,21)' }}>
                    API key creation requires all 3 security layers (Wallet + Password + 2FA).
                    <button onClick={() => setStep('security')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--refi-teal)', marginLeft: 4, fontSize: 12, textDecoration: 'underline' }}>
                      Go back to set up security
                    </button>
                  </p>
                </div>
              )}

              {!newApiKey ? (
                <div style={{ padding: 16, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                  <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>Create Your First API Key</h3>
                  <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 14 }}>
                    Use this key to access the OpenAI-compatible inference API at <code style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--refi-teal)', fontSize: 10 }}>/v1/chat/completions</code>
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div>
                      <label style={{ fontSize: 11, color: 'var(--text-tertiary)', display: 'block', marginBottom: 4 }}>Key Name</label>
                      <input className="input-base focus-glow" style={{ width: '100%', fontSize: 13 }} value={keyName} onChange={e => setKeyName(e.target.value)} placeholder="e.g. Production, CLI, Mobile" />
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <InfoPill label="Scope" value="inference:read" />
                      <InfoPill label="Daily Limit" value="250 requests" />
                      <InfoPill label="Model" value="bitnet-b1.58-2b (free)" />
                    </div>
                    <button onClick={handleCreateKey} className="btn-primary" disabled={saving || !keyName.trim() || !allSecurityDone}
                      style={{ fontSize: 12, padding: '10px 20px', width: 'fit-content' }}>
                      {saving ? 'Creating...' : !allSecurityDone ? 'Complete security first' : 'Create Key'}
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ padding: 16, borderRadius: 10, background: 'rgba(92,224,210,0.08)', border: '1px solid var(--refi-teal)', marginBottom: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--refi-teal)' }}>{'\uD83D\uDD11'} API Key Created</span>
                    </div>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 10 }}>
                      Copy this key now. It cannot be retrieved after you leave this screen.
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 6, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)' }}>
                      <code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', userSelect: 'all' }}>{newApiKey}</code>
                      <button onClick={() => { navigator.clipboard.writeText(newApiKey); setKeyCopied(true); setTimeout(() => setKeyCopied(false), 2500) }}
                        className="btn-primary" style={{ fontSize: 11, padding: '4px 14px', flexShrink: 0 }}>
                        {keyCopied ? '\u2705 Copied!' : 'Copy'}
                      </button>
                    </div>
                  </div>

                  <div style={{ padding: 14, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                    <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>Quick test:</p>
                    <code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-all', display: 'block' }}>
{`curl ${API_URL}/v1/chat/completions \\
  -H "Authorization: Bearer ${newApiKey.slice(0, 16)}..." \\
  -H "Content-Type: application/json" \\
  -d '{"model":"groot","messages":[{"role":"user","content":"hello"}]}'`}
                    </code>
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, marginTop: 20 }}>
                <button onClick={() => setStep('security')} className="btn-secondary" style={{ padding: '10px 20px' }}>Back</button>
                <button onClick={() => { setError(''); setStep('done') }} className="btn-primary" style={{ flex: 1, padding: '10px 0' }}>
                  {newApiKey ? 'Continue' : 'Skip for now'}
                </button>
              </div>
            </div>
          )}

          {/* ── Done ── */}
          {step === 'done' && (
            <div className="animate-fade-in" style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>{'\uD83D\uDE80'}</div>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, letterSpacing: '-0.02em' }}>
                You&apos;re Ready
              </h3>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24, maxWidth: 380, margin: '0 auto 24px' }}>
                Your REFINET Cloud account is set up. Here&apos;s what you can do now:
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 24, textAlign: 'left' }}>
                <CompletionRow label="Profile" done={!!(username || profile?.username)} detail={username || profile?.username || 'Not set'} />
                <CompletionRow label="Password" done={passwordSet} detail={passwordSet ? 'Enabled' : 'Not set'} />
                <CompletionRow label="2FA" done={totpEnabled} detail={totpEnabled ? 'Enabled' : 'Not set'} />
                <CompletionRow label="API Key" done={!!newApiKey} detail={newApiKey ? `${newApiKey.slice(0, 12)}...` : 'Not created'} />
              </div>

              <button onClick={handleFinish} className="btn-primary" style={{ width: '100%', padding: '12px 0', fontSize: 14, fontWeight: 600 }}>
                Go to Dashboard
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Sub-components ─── */

function SecurityBadge({ label, done }: { label: string; done: boolean }) {
  return (
    <div style={{
      flex: 1, padding: '8px 10px', borderRadius: 8, textAlign: 'center',
      background: done ? 'rgba(74,222,128,0.06)' : 'var(--bg-secondary)',
      border: `1px solid ${done ? 'rgba(74,222,128,0.2)' : 'var(--border-subtle)'}`,
    }}>
      <div style={{ fontSize: 14, marginBottom: 2 }}>{done ? '\u2705' : '\u26A0\uFE0F'}</div>
      <div style={{ fontSize: 10, fontWeight: 600, color: done ? 'var(--success)' : 'var(--text-tertiary)' }}>{label}</div>
    </div>
  )
}

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <span style={{ fontSize: 10, padding: '4px 10px', borderRadius: 6, background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)' }}>
      <span style={{ color: 'var(--text-tertiary)' }}>{label}: </span>
      <span style={{ color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>{value}</span>
    </span>
  )
}

function CompletionRow({ label, done, detail }: { label: string; done: boolean; detail: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderRadius: 8, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 12 }}>{done ? '\u2705' : '\u26A0\uFE0F'}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</span>
      </div>
      <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: done ? 'var(--refi-teal)' : 'var(--text-tertiary)' }}>{detail}</span>
    </div>
  )
}
