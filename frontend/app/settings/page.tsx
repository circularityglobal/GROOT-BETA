'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { API_URL } from '@/lib/config'

type Section = 'identity' | 'api-keys' | 'providers' | 'mcp' | 'security' | 'account' | 'support'

const NAV: { id: Section; label: string; icon: string }[] = [
  { id: 'identity', label: 'Identity', icon: '\uD83D\uDEE1\uFE0F' },
  { id: 'api-keys', label: 'API Keys', icon: '\uD83D\uDD11' },
  { id: 'providers', label: 'AI Providers', icon: '\u26A1' },
  { id: 'mcp', label: 'MCP Servers', icon: '\uD83D\uDD0C' },
  { id: 'security', label: 'Security', icon: '\uD83D\uDD12' },
  { id: 'account', label: 'Account', icon: '\uD83D\uDC64' },
  { id: 'support', label: 'Help & Support', icon: '\uD83C\uDFA7' },
]

const PROVIDER_COLORS: Record<string, string> = {
  openai: '#10A37F', anthropic: '#D97706', gemini: '#4285F4', openrouter: '#F97316',
  replicate: '#3B82F6', stability: '#A78BFA', together: '#06B6D4', groq: '#F43F5E',
  mistral: '#FF7000', perplexity: '#22D3EE', ollama: '#84CC16', lmstudio: '#A78BFA', custom: '#6B7280',
}

export default function SettingsPage() {
  const router = useRouter()
  const [token, setToken] = useState('')
  const [section, setSection] = useState<Section>('identity')
  const [profile, setProfile] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const t = localStorage.getItem('refinet_token')
    if (!t) { router.replace('/login/'); return }
    setToken(t)
    fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${t}` } })
      .then(r => { if (!r.ok) throw new Error(); return r.json() })
      .then(p => { setProfile(p); setLoading(false) })
      .catch(() => { router.replace('/login/'); setLoading(false) })
  }, [router])

  const reloadProfile = useCallback(() => {
    const t = localStorage.getItem('refinet_token')
    if (!t) return
    fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${t}` } })
      .then(r => r.ok ? r.json() : null)
      .then(p => { if (p) setProfile(p) })
      .catch(() => {})
  }, [])

  const authHeaders = useCallback((): Record<string, string> => {
    const t = localStorage.getItem('refinet_token') || ''
    return { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' }
  }, [])

  if (loading) {
    return <div style={{ minHeight: '80vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="animate-pulse" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>Loading settings...</div>
    </div>
  }

  if (!profile) return null

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 28px' }} className="animate-fade-in">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Link href="/dashboard" style={{ fontSize: 11, color: 'var(--text-tertiary)', textDecoration: 'none', fontFamily: "'JetBrains Mono', monospace" }}>Dashboard</Link>
            <span style={{ color: 'var(--text-tertiary)', fontSize: 10 }}>/</span>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>Settings</span>
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)', margin: 0 }}>
            Settings &amp; Connections
          </h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {profile.cifi_verified && (
            <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 8, background: 'rgba(74,222,128,0.1)', color: 'var(--success)', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
              @{profile.cifi_username}
            </span>
          )}
          <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 8, background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
            {profile.tier}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 24 }}>
        {/* Sidebar Navigation */}
        <nav style={{ width: 200, flexShrink: 0 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, position: 'sticky', top: 80 }}>
            {NAV.map(n => (
              <button key={n.id} onClick={() => { setSection(n.id); setMsg(''); setError('') }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderRadius: 8,
                  background: section === n.id ? 'var(--bg-tertiary)' : 'transparent',
                  border: section === n.id ? '1px solid var(--border-default)' : '1px solid transparent',
                  cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s', width: '100%',
                }}
                onMouseEnter={e => { if (section !== n.id) e.currentTarget.style.background = 'var(--bg-secondary)' }}
                onMouseLeave={e => { if (section !== n.id) e.currentTarget.style.background = 'transparent' }}
              >
                <span style={{ fontSize: 14 }}>{n.icon}</span>
                <span style={{ fontSize: 12, fontWeight: section === n.id ? 600 : 400, color: section === n.id ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                  {n.label}
                </span>
              </button>
            ))}
          </div>
        </nav>

        {/* Main Content */}
        <main style={{ flex: 1, minWidth: 0 }}>
          {msg && <div style={{ marginBottom: 14, padding: '10px 14px', borderRadius: 8, fontSize: 12, background: 'rgba(92,224,210,0.1)', border: '1px solid var(--refi-teal)', color: 'var(--refi-teal)' }}>{msg}</div>}
          {error && <div style={{ marginBottom: 14, padding: '10px 14px', borderRadius: 8, fontSize: 12, background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', color: 'var(--error)' }}>{error}</div>}

          {section === 'identity' && <IdentitySection profile={profile} authHeaders={authHeaders} reloadProfile={reloadProfile} setMsg={setMsg} setError={setError} />}
          {section === 'api-keys' && <ApiKeysSection authHeaders={authHeaders} profile={profile} />}
          {section === 'providers' && <ProvidersSection authHeaders={authHeaders} profile={profile} />}
          {section === 'mcp' && <McpSection authHeaders={authHeaders} />}
          {section === 'security' && <SecuritySection authHeaders={authHeaders} profile={profile} reloadProfile={reloadProfile} setMsg={setMsg} setError={setError} />}
          {section === 'account' && <AccountSection profile={profile} />}
          {section === 'support' && <SupportSection authHeaders={authHeaders} />}
        </main>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   SECTION: CIFI IDENTITY
   ═══════════════════════════════════════════════════════════════════ */

function IdentitySection({ profile, authHeaders, reloadProfile, setMsg, setError }: any) {
  const [checking, setChecking] = useState(false)
  const [registering, setRegistering] = useState(false)
  const [regUsername, setRegUsername] = useState('')
  const [saving, setSaving] = useState(false)

  const handleVerify = async () => {
    setChecking(true); setError(''); setMsg('')
    try {
      const resp = await fetch(`${API_URL}/auth/cifi/verify`, { method: 'POST', headers: authHeaders() })
      const data = await resp.json()
      if (resp.ok && data.verified) {
        setMsg(`Identity verified as @${data.cifi_username}`)
        reloadProfile()
      } else {
        setError('No CIFI identity found for this wallet. Register below or at cifi.global.')
      }
    } catch { setError('Unable to reach CIFI identity service.') }
    setChecking(false)
  }

  const handleRegister = async () => {
    setSaving(true); setError(''); setMsg('')
    try {
      const resp = await fetch(`${API_URL}/auth/cifi/register`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ username: regUsername }),
      })
      const data = await resp.json()
      if (!resp.ok) { setError(data.detail || 'Registration failed'); setSaving(false); return }
      if (data.verified) {
        setMsg(`Registered and verified as @${data.cifi_username}`)
        setRegistering(false); setRegUsername('')
        reloadProfile()
      }
    } catch { setError('Unable to reach CIFI identity service.') }
    setSaving(false)
  }

  const handleDisconnect = async () => {
    if (!confirm('Disconnect your CIFI identity? You will lose your @username on this platform.')) return
    setError(''); setMsg('')
    try {
      const resp = await fetch(`${API_URL}/auth/cifi/verify`, { method: 'DELETE', headers: authHeaders() })
      if (resp.ok) { setMsg('CIFI identity disconnected. Reverted to pseudonymous wallet display.'); reloadProfile() }
      else { const d = await resp.json(); setError(d.detail || 'Failed to disconnect') }
    } catch { setError('Network error') }
  }

  const handleReverify = async () => {
    setChecking(true); setError(''); setMsg('')
    try {
      const resp = await fetch(`${API_URL}/auth/cifi/reverify`, { method: 'POST', headers: authHeaders() })
      const data = await resp.json()
      if (data.verified) { setMsg('Identity re-verified successfully.'); reloadProfile() }
      else { setError('CIFI identity is no longer valid. It has been disconnected.'); reloadProfile() }
    } catch { setError('Unable to reach CIFI identity service.') }
    setChecking(false)
  }

  return (
    <div>
      <SectionHeader title="CIFI Federated Identity" description="Your @username and KYC verification from CIFI.GLOBAL. Required for App Store submissions." />

      {profile.cifi_verified ? (
        <div>
          {/* Verified Identity Card */}
          <div style={{ padding: 20, borderRadius: 12, background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.25)', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'linear-gradient(135deg, var(--refi-teal), var(--refi-teal-dim))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 700, color: 'var(--bg-primary)', flexShrink: 0 }}>
                {profile.cifi_username?.[0]?.toUpperCase()}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>@{profile.cifi_username}</span>
                  <span style={{ fontSize: 9, padding: '2px 8px', borderRadius: 6, background: 'rgba(74,222,128,0.15)', color: 'var(--success)', fontWeight: 700, letterSpacing: '0.05em' }}>VERIFIED</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2, fontFamily: "'JetBrains Mono', monospace" }}>
                  {profile.cifi_display_name && <span>{profile.cifi_display_name} &middot; </span>}
                  {profile.cifi_kyc_level && <span>KYC: {profile.cifi_kyc_level} &middot; </span>}
                  <span>Verified {profile.cifi_verified_at ? new Date(profile.cifi_verified_at).toLocaleDateString() : ''}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleReverify} disabled={checking} className="btn-secondary" style={{ fontSize: 12, padding: '8px 16px' }}>
              {checking ? 'Checking...' : 'Re-verify'}
            </button>
            <button onClick={handleDisconnect} style={{ fontSize: 12, padding: '8px 16px', borderRadius: 8, background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', color: 'var(--error)', cursor: 'pointer' }}>
              Disconnect
            </button>
          </div>

          {/* What CIFI enables */}
          <div style={{ marginTop: 20, padding: 14, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>Your verified identity enables:</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {[
                'Submit apps to the REFINET App Store',
                'Display @username on your public profile',
                'KYC-verified status visible to other users',
                'Cross-platform identity with CIFI ecosystem',
              ].map(item => (
                <div key={item} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--success)', fontSize: 10 }}>{'\u2713'}</span> {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div>
          {/* Not Verified */}
          <div style={{ padding: 20, borderRadius: 12, background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'var(--bg-tertiary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, color: 'var(--text-tertiary)', flexShrink: 0, fontFamily: "'JetBrains Mono', monospace" }}>
                {profile.eth_address ? profile.eth_address.slice(2, 4) : '?'}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {profile.eth_address ? `${profile.eth_address.slice(0, 6)}...${profile.eth_address.slice(-4)}` : 'No wallet'}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>
                  Pseudonymous &middot; No @username &middot; App Store submissions blocked
                </div>
              </div>
            </div>
          </div>

          {/* Verify or Register */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button onClick={handleVerify} disabled={checking} className="btn-primary" style={{ fontSize: 12, padding: '10px 20px' }}>
              {checking ? 'Checking...' : 'Check CIFI Identity'}
            </button>
            <button onClick={() => setRegistering(!registering)} className="btn-secondary" style={{ fontSize: 12, padding: '10px 20px' }}>
              {registering ? 'Cancel' : 'Register New Identity'}
            </button>
          </div>

          {registering && (
            <div style={{ padding: 16, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', marginBottom: 16 }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>Register on CIFI.GLOBAL</h3>
              <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 12 }}>Choose your @username (5-15 chars, lowercase, letters/numbers/underscore/hyphen)</p>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 14, color: 'var(--text-tertiary)' }}>@</span>
                <input className="input-base focus-glow" style={{ flex: 1, fontSize: 14 }}
                  value={regUsername}
                  onChange={e => setRegUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
                  placeholder="your_username" maxLength={15} />
                <button onClick={handleRegister} className="btn-primary"
                  disabled={saving || regUsername.length < 5 || regUsername.length > 15}
                  style={{ fontSize: 12, padding: '8px 16px' }}>
                  {saving ? 'Registering...' : 'Register'}
                </button>
              </div>
              {regUsername && (regUsername.length < 5) && (
                <p style={{ fontSize: 10, color: 'var(--error)', marginTop: 6 }}>Username must be at least 5 characters</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   SECTION: API KEYS
   ═══════════════════════════════════════════════════════════════════ */

function ApiKeysSection({ authHeaders, profile }: any) {
  const [keys, setKeys] = useState<any[]>([])
  const [activity, setActivity] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [keyScopes, setKeyScopes] = useState('inference:read')
  const [keyLimit, setKeyLimit] = useState(250)
  const [newKey, setNewKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [msg, setMsg] = useState('')

  const load = useCallback(() => {
    const h = authHeaders()
    Promise.all([
      fetch(`${API_URL}/keys`, { headers: h }).then(r => r.ok ? r.json() : []),
      fetch(`${API_URL}/keys/activity`, { headers: h }).then(r => r.ok ? r.json() : []),
    ]).then(([k, a]) => {
      setKeys(Array.isArray(k) ? k : [])
      setActivity(Array.isArray(a) ? a : [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [authHeaders])

  useEffect(() => { load() }, [load])

  const allSecure = profile?.password_enabled && profile?.totp_enabled

  const handleCreate = async () => {
    if (!keyName.trim()) return
    setMsg('')
    const resp = await fetch(`${API_URL}/keys`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ name: keyName, scopes: keyScopes, daily_limit: keyLimit }),
    })
    const data = await resp.json()
    if (data.key) {
      setNewKey(data.key); setCopied(false); setKeyName(''); setShowCreate(false)
      load(); window.dispatchEvent(new Event('refinet-keys-changed'))
    } else {
      setMsg(data.detail || 'Failed to create key')
    }
  }

  const handleRevoke = async (id: string) => {
    if (!confirm('Revoke this API key? This cannot be undone.')) return
    await fetch(`${API_URL}/keys/${id}`, { method: 'DELETE', headers: authHeaders() })
    load(); window.dispatchEvent(new Event('refinet-keys-changed'))
  }

  const SCOPES = ['inference:read', 'devices:write', 'webhooks:write', 'registry:read', 'registry:write']

  if (!allSecure) return <SecurityGateInline />

  return (
    <div>
      <SectionHeader title="API Keys" description="Manage your REFINET Cloud API keys. Use these to access the OpenAI-compatible inference API." />

      {/* New key created banner */}
      {newKey && (
        <div style={{ marginBottom: 16, padding: 16, borderRadius: 10, background: 'rgba(92,224,210,0.08)', border: '1px solid var(--refi-teal)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--refi-teal)' }}>Key Created</span>
            <button onClick={() => setNewKey(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: 2 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8 }}>Copy this key now. It cannot be retrieved after you close this.</p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 6, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)' }}>
            <code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', userSelect: 'all' }}>{newKey}</code>
            <button onClick={() => { navigator.clipboard.writeText(newKey); setCopied(true); setTimeout(() => setCopied(false), 2500) }}
              className="btn-primary" style={{ fontSize: 11, padding: '4px 12px', flexShrink: 0 }}>{copied ? 'Copied!' : 'Copy'}</button>
          </div>
          <div style={{ marginTop: 10, padding: '8px 10px', borderRadius: 6, background: 'var(--bg-secondary)' }}>
            <code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'var(--text-tertiary)', whiteSpace: 'pre-wrap', wordBreak: 'break-all', lineHeight: 1.7 }}>
{`curl ${API_URL}/v1/chat/completions \\
  -H "Authorization: Bearer ${newKey.slice(0, 20)}..." \\
  -H "Content-Type: application/json" \\
  -d '{"model":"groot","messages":[{"role":"user","content":"hello"}]}'`}
            </code>
          </div>
        </div>
      )}

      {/* Header bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{keys.length} key{keys.length !== 1 ? 's' : ''} active</span>
        <button onClick={() => { setShowCreate(!showCreate); setNewKey(null) }} className="btn-primary" style={{ fontSize: 11, padding: '6px 14px' }}>
          {showCreate ? 'Cancel' : '+ New Key'}
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div style={{ marginBottom: 16, padding: 16, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <input className="input-base focus-glow" placeholder="Key name (e.g. Production, CLI)" value={keyName}
            onChange={e => setKeyName(e.target.value)} style={{ fontSize: 13 }} autoFocus />
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-tertiary)', display: 'block', marginBottom: 4 }}>Scopes</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {SCOPES.map(scope => {
                const active = keyScopes.includes(scope)
                return (
                  <button key={scope} onClick={() => {
                    const s = keyScopes.split(' ').filter(Boolean)
                    setKeyScopes(active ? s.filter(x => x !== scope).join(' ') : [...s, scope].join(' '))
                  }} style={{
                    fontSize: 10, padding: '3px 8px', borderRadius: 6, cursor: 'pointer',
                    background: active ? 'var(--refi-teal-glow)' : 'var(--bg-tertiary)',
                    border: `1px solid ${active ? 'var(--refi-teal)' : 'var(--border-subtle)'}`,
                    color: active ? 'var(--refi-teal)' : 'var(--text-tertiary)',
                    fontFamily: "'JetBrains Mono', monospace",
                  }}>{scope}</button>
                )
              })}
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-tertiary)', display: 'block', marginBottom: 4 }}>Daily Limit</label>
            <input type="number" value={keyLimit} onChange={e => setKeyLimit(Math.min(250, Math.max(1, parseInt(e.target.value) || 1)))}
              className="input-base focus-glow" style={{ width: 120, fontSize: 13 }} min={1} max={250} />
            <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>Maximum: 250 requests per day</p>
          </div>
          <button onClick={handleCreate} className="btn-primary" disabled={!keyName.trim()} style={{ fontSize: 12, padding: '8px 20px', alignSelf: 'flex-start' }}>
            Create Key
          </button>
          {msg && <span style={{ fontSize: 11, color: 'var(--error)' }}>{msg}</span>}
        </div>
      )}

      {/* Key list */}
      {loading ? (
        <div className="animate-pulse" style={{ padding: 20, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>Loading keys...</div>
      ) : keys.length === 0 ? (
        <div style={{ padding: 24, textAlign: 'center', borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
          <p style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 4 }}>No API keys yet.</p>
          <p style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Create one to start using the inference API.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {keys.map((k: any) => (
            <div key={k.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{k.name}</span>
                  <code style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>{k.prefix}...</code>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--text-tertiary)' }}>
                  <span>{k.requests_today}/{k.daily_limit} today</span>
                  <span>{k.scopes || 'inference:read'}</span>
                  {k.last_used_at && <span>Last used {formatDate(k.last_used_at)}</span>}
                </div>
                {/* Usage bar */}
                <div style={{ marginTop: 6, height: 3, borderRadius: 2, background: 'var(--bg-tertiary)', overflow: 'hidden' }}>
                  <div style={{ height: '100%', borderRadius: 2, background: k.requests_today >= k.daily_limit ? 'var(--error)' : 'var(--refi-teal)', width: `${Math.min(100, (k.requests_today / k.daily_limit) * 100)}%`, transition: 'width 0.3s' }} />
                </div>
              </div>
              <button onClick={() => handleRevoke(k.id)} style={{ fontSize: 10, padding: '4px 10px', borderRadius: 6, background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', color: 'var(--error)', cursor: 'pointer', flexShrink: 0 }}>
                Revoke
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Recent Activity */}
      {activity.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <h3 style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>Recent Activity</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {activity.map((a: any) => (
              <div key={a.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', fontSize: 11 }}>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)' }}>{a.endpoint}</span>
                <div style={{ display: 'flex', gap: 12, color: 'var(--text-tertiary)' }}>
                  <span>{a.model}</span>
                  <span>{a.prompt_tokens + a.completion_tokens} tok</span>
                  <span>{a.latency_ms}ms</span>
                  <span>{formatDate(a.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   SECTION: AI PROVIDERS (BYOK)
   ═══════════════════════════════════════════════════════════════════ */

function ProvidersSection({ authHeaders, profile }: any) {
  const [catalog, setCatalog] = useState<any[]>([])
  const [userKeys, setUserKeys] = useState<any[]>([])
  const [adding, setAdding] = useState<string | null>(null)
  const [keyInput, setKeyInput] = useState('')
  const [urlInput, setUrlInput] = useState('')
  const [nameInput, setNameInput] = useState('')
  const [msg, setMsg] = useState('')
  const [testing, setTesting] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<Record<string, any>>({})

  const allSecure = profile?.password_enabled && profile?.totp_enabled

  const load = useCallback(() => {
    const h = authHeaders()
    fetch(`${API_URL}/provider-keys/catalog`).then(r => r.json()).then(setCatalog).catch(() => {})
    fetch(`${API_URL}/provider-keys`, { headers: h }).then(r => r.ok ? r.json() : []).then(setUserKeys).catch(() => {})
  }, [authHeaders])

  useEffect(() => { load() }, [load])

  const saveKey = async (providerType: string) => {
    setMsg('')
    try {
      const body: any = { provider_type: providerType, display_name: nameInput || `My ${providerType} key`, api_key: keyInput }
      if (urlInput) body.base_url = urlInput
      const r = await fetch(`${API_URL}/provider-keys`, { method: 'POST', headers: authHeaders(), body: JSON.stringify(body) })
      const d = await r.json()
      if (!r.ok) { setMsg(d.detail || 'Error saving key'); return }
      setMsg(d.updated ? 'Key updated' : 'Key saved')
      setAdding(null); setKeyInput(''); setUrlInput(''); setNameInput('')
      load()
    } catch { setMsg('Network error') }
  }

  const deleteKey = async (id: string) => {
    if (!confirm('Remove this provider key?')) return
    await fetch(`${API_URL}/provider-keys/${id}`, { method: 'DELETE', headers: authHeaders() })
    load()
  }

  const testKey = async (id: string) => {
    setTesting(id)
    try {
      const r = await fetch(`${API_URL}/provider-keys/${id}/test`, { method: 'POST', headers: authHeaders() })
      const d = await r.json()
      setTestResult(prev => ({ ...prev, [id]: d }))
    } catch { setTestResult(prev => ({ ...prev, [id]: { status: 'error', message: 'Network error' } })) }
    setTesting(null)
  }

  if (!allSecure) return <SecurityGateInline />

  const connectedTypes = new Set(userKeys.map((k: any) => k.provider_type))

  return (
    <div>
      <SectionHeader title="AI Service Providers" description="Bring your own API keys (BYOK) to use any AI provider through GROOT. All keys are encrypted with AES-256-GCM." />

      {/* Connected keys */}
      {userKeys.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>Connected ({userKeys.length})</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {userKeys.map((k: any) => {
              const color = PROVIDER_COLORS[k.provider_type] || '#888'
              const tr = testResult[k.id]
              return (
                <div key={k.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 8, background: 'var(--bg-secondary)', border: `1px solid ${color}30` }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{k.display_name}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
                      {k.provider_type} &middot; {k.key_preview} &middot; {k.usage_count} uses
                    </div>
                  </div>
                  <button onClick={() => testKey(k.id)} disabled={testing === k.id}
                    style={{ fontSize: 10, padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border-subtle)', background: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                    {testing === k.id ? '...' : 'Test'}
                  </button>
                  {tr && <span style={{ fontSize: 9, color: tr.status === 'ok' ? 'var(--success)' : 'var(--error)', minWidth: 36 }}>{tr.status === 'ok' ? `${tr.latency_ms}ms` : 'Fail'}</span>}
                  <button onClick={() => deleteKey(k.id)}
                    style={{ fontSize: 10, padding: '4px 10px', borderRadius: 6, background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', color: 'var(--error)', cursor: 'pointer' }}>
                    Remove
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Provider Catalog */}
      <h3 style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>Available Providers</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8, marginBottom: 16 }}>
        {catalog.map((p: any) => {
          const color = PROVIDER_COLORS[p.type] || '#888'
          const connected = connectedTypes.has(p.type)
          return (
            <button key={p.type} onClick={() => { setAdding(p.type); setNameInput(`My ${p.name} key`); setUrlInput(p.base_url || ''); setKeyInput(''); setMsg('') }}
              style={{
                padding: '10px 12px', borderRadius: 8, textAlign: 'left', cursor: 'pointer',
                background: adding === p.type ? `${color}15` : 'var(--bg-secondary)',
                border: `1px solid ${connected ? color + '50' : adding === p.type ? color + '40' : 'var(--border-subtle)'}`,
                transition: 'all 0.15s',
              }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: color }} />
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{p.name}</span>
                {connected && <span style={{ fontSize: 8, background: `${color}20`, color, padding: '1px 5px', borderRadius: 4, fontWeight: 600 }}>CONNECTED</span>}
                {p.free_tier && !connected && <span style={{ fontSize: 8, background: 'rgba(92,224,210,0.15)', color: '#5CE0D2', padding: '1px 5px', borderRadius: 4 }}>FREE</span>}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.4 }}>{p.description}</div>
              <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                {(p.capabilities || []).map((c: string) => (
                  <span key={c} style={{ fontSize: 8, padding: '1px 5px', borderRadius: 3, background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>{c}</span>
                ))}
              </div>
            </button>
          )
        })}
      </div>

      {/* Add key form */}
      {adding && (() => {
        const entry = catalog.find((p: any) => p.type === adding)
        if (!entry) return null
        const color = PROVIDER_COLORS[adding] || '#888'
        return (
          <div style={{ padding: 16, borderRadius: 10, background: 'var(--bg-secondary)', border: `1px solid ${color}40` }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, color, marginBottom: 10 }}>Connect {entry.name}</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div>
                <label style={{ fontSize: 10, color: 'var(--text-tertiary)', display: 'block', marginBottom: 3 }}>Display Name</label>
                <input value={nameInput} onChange={e => setNameInput(e.target.value)} className="input-base focus-glow" style={{ width: '100%', fontSize: 12 }} />
              </div>
              {entry.auth_type !== 'url_only' && (
                <div>
                  <label style={{ fontSize: 10, color: 'var(--text-tertiary)', display: 'block', marginBottom: 3 }}>
                    API Key {entry.key_url && <a href={entry.key_url} target="_blank" rel="noopener noreferrer" style={{ color, textDecoration: 'underline', marginLeft: 4 }}>Get key</a>}
                  </label>
                  <input type="password" value={keyInput} onChange={e => setKeyInput(e.target.value)} placeholder="sk-... / key-..."
                    className="input-base focus-glow" style={{ width: '100%', fontSize: 12, fontFamily: "'JetBrains Mono', monospace" }} />
                </div>
              )}
              {(entry.auth_type === 'url_only' || entry.auth_type === 'api_key_and_url' || entry.type === 'custom') && (
                <div>
                  <label style={{ fontSize: 10, color: 'var(--text-tertiary)', display: 'block', marginBottom: 3 }}>Base URL</label>
                  <input value={urlInput} onChange={e => setUrlInput(e.target.value)} placeholder={entry.base_url || 'https://...'}
                    className="input-base focus-glow" style={{ width: '100%', fontSize: 12, fontFamily: "'JetBrains Mono', monospace" }} />
                </div>
              )}
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 4 }}>
                <button onClick={() => saveKey(adding)} style={{ padding: '7px 18px', fontSize: 12, fontWeight: 600, borderRadius: 6, background: color, color: '#fff', border: 'none', cursor: 'pointer' }}>Save Key</button>
                <button onClick={() => { setAdding(null); setMsg('') }} className="btn-secondary" style={{ fontSize: 12, padding: '7px 18px' }}>Cancel</button>
                {msg && <span style={{ fontSize: 11, color: msg.toLowerCase().includes('error') ? 'var(--error)' : 'var(--success)' }}>{msg}</span>}
              </div>
            </div>
          </div>
        )
      })()}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   SECTION: MCP SERVERS
   ═══════════════════════════════════════════════════════════════════ */

function McpSection({ authHeaders }: any) {
  const [servers, setServers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedServer, setSelectedServer] = useState<string | null>(null)
  const [tools, setTools] = useState<string[]>([])
  const [toolsLoading, setToolsLoading] = useState(false)
  const [callTool, setCallTool] = useState<string | null>(null)
  const [callArgs, setCallArgs] = useState('{}')
  const [callResult, setCallResult] = useState<any>(null)
  const [calling, setCalling] = useState(false)

  useEffect(() => {
    fetch(`${API_URL}/mcp/servers`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : [])
      .then(d => { setServers(Array.isArray(d) ? d : []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [authHeaders])

  const loadTools = async (name: string) => {
    setSelectedServer(name); setToolsLoading(true); setTools([]); setCallTool(null); setCallResult(null)
    try {
      const r = await fetch(`${API_URL}/mcp/servers/${name}/tools`, { headers: authHeaders() })
      const d = await r.json()
      setTools(d.tools || [])
    } catch {}
    setToolsLoading(false)
  }

  const executeTool = async () => {
    if (!selectedServer || !callTool) return
    setCalling(true); setCallResult(null)
    try {
      let args = {}
      try { args = JSON.parse(callArgs) } catch {}
      const r = await fetch(`${API_URL}/mcp/call`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ server: selectedServer, tool: callTool, arguments: args }),
      })
      setCallResult(await r.json())
    } catch (e: any) { setCallResult({ error: e.message }) }
    setCalling(false)
  }

  return (
    <div>
      <SectionHeader title="MCP Servers" description="Model Context Protocol servers connected to GROOT. These provide tools and capabilities for the AI agent." />

      {loading ? (
        <div className="animate-pulse" style={{ padding: 20, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>Loading MCP servers...</div>
      ) : servers.length === 0 ? (
        <div style={{ padding: 24, textAlign: 'center', borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
          <p style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 4 }}>No MCP servers configured.</p>
          <p style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>MCP servers are managed by the platform administrator.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {servers.map((s: any) => {
            const isSelected = selectedServer === s.name
            return (
              <div key={s.id || s.name}>
                <button onClick={() => isSelected ? setSelectedServer(null) : loadTools(s.name)}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', borderRadius: 10,
                    background: isSelected ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
                    border: `1px solid ${isSelected ? 'var(--refi-teal)' : 'var(--border-subtle)'}`,
                    cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s',
                  }}>
                  <span style={{
                    width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
                    background: s.is_healthy ? 'var(--success)' : s.status === 'active' ? 'rgb(250,204,21)' : 'var(--error)',
                  }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{s.name}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
                      {s.transport} &middot; {s.status} &middot; {(s.capabilities ? JSON.parse(s.capabilities) : []).length} tools
                    </div>
                  </div>
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{isSelected ? '\u25B2' : '\u25BC'}</span>
                </button>

                {/* Tools panel */}
                {isSelected && (
                  <div style={{ margin: '4px 0 0 0', padding: 14, borderRadius: '0 0 10px 10px', background: 'var(--bg-secondary)', borderLeft: '2px solid var(--refi-teal)' }}>
                    {toolsLoading ? (
                      <div className="animate-pulse" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Loading tools...</div>
                    ) : tools.length === 0 ? (
                      <p style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>No tools exposed by this server.</p>
                    ) : (
                      <div>
                        <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>{tools.length} tool{tools.length !== 1 ? 's' : ''} available:</p>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                          {tools.map(t => (
                            <button key={t} onClick={() => { setCallTool(callTool === t ? null : t); setCallResult(null); setCallArgs('{}') }}
                              style={{
                                fontSize: 10, padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
                                background: callTool === t ? 'var(--refi-teal-glow)' : 'var(--bg-tertiary)',
                                border: `1px solid ${callTool === t ? 'var(--refi-teal)' : 'var(--border-subtle)'}`,
                                color: callTool === t ? 'var(--refi-teal)' : 'var(--text-secondary)',
                                fontFamily: "'JetBrains Mono', monospace",
                              }}>{t}</button>
                          ))}
                        </div>

                        {/* Tool call form */}
                        {callTool && (
                          <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)' }}>
                            <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--refi-teal)', marginBottom: 6 }}>
                              {selectedServer}.{callTool}()
                            </p>
                            <div style={{ marginBottom: 8 }}>
                              <label style={{ fontSize: 10, color: 'var(--text-tertiary)', display: 'block', marginBottom: 3 }}>Arguments (JSON)</label>
                              <textarea value={callArgs} onChange={e => setCallArgs(e.target.value)}
                                style={{
                                  width: '100%', height: 60, padding: '6px 10px', fontSize: 11,
                                  fontFamily: "'JetBrains Mono', monospace", borderRadius: 6,
                                  border: '1px solid var(--border-default)', background: 'var(--bg-secondary)',
                                  color: 'var(--text-primary)', resize: 'vertical', outline: 'none',
                                }} />
                            </div>
                            <button onClick={executeTool} disabled={calling} className="btn-primary" style={{ fontSize: 11, padding: '6px 14px' }}>
                              {calling ? 'Executing...' : 'Execute'}
                            </button>
                            {callResult && (
                              <pre style={{
                                marginTop: 10, padding: 10, borderRadius: 6, background: 'var(--bg-tertiary)',
                                border: '1px solid var(--border-subtle)', fontSize: 10,
                                fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)',
                                overflow: 'auto', maxHeight: 200, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                              }}>
                                {JSON.stringify(callResult, null, 2)}
                              </pre>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   SECTION: SECURITY
   ═══════════════════════════════════════════════════════════════════ */

function SecuritySection({ authHeaders, profile, reloadProfile, setMsg, setError }: any) {
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [showTotpSetup, setShowTotpSetup] = useState(false)
  const [totpData, setTotpData] = useState<any>(null)
  const [passwordForm, setPasswordForm] = useState({ email: '', password: '', confirmPassword: '' })
  const [totpCode, setTotpCode] = useState('')

  const handleSetPassword = async () => {
    setMsg(''); setError('')
    if (passwordForm.password !== passwordForm.confirmPassword) { setError('Passwords do not match'); return }
    if (passwordForm.password.length < 12) { setError('Password must be at least 12 characters'); return }
    try {
      const resp = await fetch(`${API_URL}/auth/settings/password`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ email: passwordForm.email, password: passwordForm.password }),
      })
      if (!resp.ok) { const err = await resp.json().catch(() => ({ detail: 'Failed' })); throw new Error(err.detail) }
      setMsg('Password set successfully.')
      setShowPasswordForm(false); setPasswordForm({ email: '', password: '', confirmPassword: '' })
      reloadProfile()
    } catch (e: any) { setError(e.message) }
  }

  const handleTotpSetup = async () => {
    setMsg(''); setError('')
    try {
      const resp = await fetch(`${API_URL}/auth/settings/totp/setup`, { method: 'POST', headers: authHeaders() })
      if (!resp.ok) { const err = await resp.json().catch(() => ({ detail: 'Failed' })); throw new Error(err.detail) }
      setTotpData(await resp.json()); setShowTotpSetup(true)
    } catch (e: any) { setError(e.message) }
  }

  const handleTotpVerify = async () => {
    setMsg(''); setError('')
    try {
      const resp = await fetch(`${API_URL}/auth/settings/totp/verify`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ code: totpCode }),
      })
      if (!resp.ok) { const err = await resp.json().catch(() => ({ detail: 'Invalid code' })); throw new Error(err.detail) }
      setMsg('Two-factor authentication enabled.'); setShowTotpSetup(false); setTotpData(null); setTotpCode('')
      reloadProfile()
    } catch (e: any) { setError(e.message) }
  }

  const layers = [
    { name: 'Wallet Auth (SIWE)', done: true, desc: 'Connected via Ethereum wallet' },
    { name: 'Email + Password', done: !!profile?.password_enabled, desc: profile?.email || 'Not configured' },
    { name: 'Two-Factor Auth (TOTP)', done: !!profile?.totp_enabled, desc: profile?.totp_enabled ? 'Enabled' : 'Not configured' },
  ]
  const allComplete = layers.every(l => l.done)

  return (
    <div>
      <SectionHeader title="Security" description="Manage your authentication layers. All three are required for API key management and AI provider connections." />

      {/* Security layers overview */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20 }}>
        {layers.map((l, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', borderRadius: 10,
            background: l.done ? 'rgba(74,222,128,0.06)' : 'var(--bg-secondary)',
            border: `1px solid ${l.done ? 'rgba(74,222,128,0.2)' : 'rgba(250,204,21,0.2)'}`,
          }}>
            <span style={{ fontSize: 16 }}>{l.done ? '\u2705' : '\u26A0\uFE0F'}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: l.done ? 'var(--success)' : 'var(--text-primary)' }}>{l.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{l.desc}</div>
            </div>
            {l.done && <span style={{ fontSize: 9, color: 'var(--success)', fontWeight: 700 }}>COMPLETE</span>}
          </div>
        ))}
      </div>

      {allComplete && (
        <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(92,224,210,0.08)', border: '1px solid var(--refi-teal)', marginBottom: 20, fontSize: 12, color: 'var(--refi-teal)' }}>
          All security layers complete. API key and provider management is unlocked.
        </div>
      )}

      {/* Password setup */}
      <div style={{ padding: 14, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', marginBottom: 12 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>Email &amp; Password</h3>
        <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 10 }}>{profile?.password_enabled ? `Enabled for ${profile.email}` : 'Add email/password as an alternative login method.'}</p>
        {!showPasswordForm ? (
          <button onClick={() => setShowPasswordForm(true)} className="btn-secondary" style={{ fontSize: 12, padding: '8px 16px' }}>
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
      </div>

      {/* TOTP setup */}
      <div style={{ padding: 14, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>Two-Factor Authentication</h3>
        <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 10 }}>{profile?.totp_enabled ? 'TOTP 2FA is active.' : 'Use Google Authenticator or Authy for an extra layer of protection.'}</p>
        {profile?.totp_enabled ? (
          <span style={{ fontSize: 12, color: 'var(--refi-teal)', fontWeight: 600 }}>Enabled</span>
        ) : !showTotpSetup ? (
          <button onClick={handleTotpSetup} className="btn-secondary" disabled={!profile?.password_enabled} style={{ fontSize: 12, padding: '8px 16px' }}>
            {!profile?.password_enabled ? 'Set password first' : 'Enable 2FA'}
          </button>
        ) : totpData && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Scan with your authenticator app:</p>
            <div style={{ display: 'flex', justifyContent: 'center', padding: 12, background: '#fff', borderRadius: 10 }}>
              <img src={`data:image/png;base64,${totpData.qr_code_base64}`} alt="TOTP QR" style={{ width: 160, height: 160 }} />
            </div>
            <div style={{ padding: '8px 10px', borderRadius: 8, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>Manual key: </span>
              <span style={{ fontSize: 11, color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace", userSelect: 'all' }}>{totpData.manual_entry_key}</span>
            </div>
            <input type="text" placeholder="Enter 6-digit code" value={totpCode}
              onChange={e => setTotpCode(e.target.value)} maxLength={6}
              className="input-base focus-glow" style={{ fontSize: 16, textAlign: 'center', letterSpacing: '0.3em', fontFamily: "'JetBrains Mono', monospace" }} />
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleTotpVerify} className="btn-primary" style={{ fontSize: 12, padding: '8px 16px' }}>Verify &amp; Enable</button>
              <button onClick={() => { setShowTotpSetup(false); setTotpData(null); setError('') }} className="btn-secondary" style={{ fontSize: 12, padding: '8px 16px' }}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   SECTION: ACCOUNT
   ═══════════════════════════════════════════════════════════════════ */

function AccountSection({ profile }: any) {
  const rows = [
    { label: 'Wallet', value: profile.eth_address || 'Not linked', mono: true },
    { label: 'Username', value: profile.cifi_verified ? `@${profile.cifi_username}` : profile.username || 'Not set' },
    { label: 'Email', value: profile.email || 'Not set' },
    { label: 'Tier', value: profile.tier || 'free', accent: true },
    { label: 'CIFI Identity', value: profile.cifi_verified ? `Verified (${profile.cifi_kyc_level || 'standard'})` : 'Not verified' },
    { label: 'Password', value: profile.password_enabled ? 'Enabled' : 'Not set' },
    { label: '2FA (TOTP)', value: profile.totp_enabled ? 'Enabled' : 'Not set' },
    { label: 'Member Since', value: profile.created_at ? new Date(profile.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : 'Unknown' },
    { label: 'Last Login', value: profile.last_login_at ? formatDate(profile.last_login_at) : 'Never' },
  ]

  return (
    <div>
      <SectionHeader title="Account" description="Your REFINET Cloud account information." />
      <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
        {rows.map((r, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '11px 16px',
            background: i % 2 === 0 ? 'var(--bg-secondary)' : 'var(--bg-primary)',
            borderBottom: i < rows.length - 1 ? '1px solid var(--border-subtle)' : 'none',
          }}>
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{r.label}</span>
            <span style={{
              fontSize: 12,
              fontFamily: r.mono ? "'JetBrains Mono', monospace" : 'inherit',
              color: r.accent ? 'var(--refi-teal)' : 'var(--text-primary)',
              fontWeight: r.accent ? 600 : 400,
              maxWidth: '60%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>{r.value}</span>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 20 }}>
        <button onClick={() => {
          localStorage.removeItem('refinet_token')
          localStorage.removeItem('refinet_refresh')
          window.dispatchEvent(new Event('refinet-auth-change'))
          window.location.href = '/'
        }} style={{
          fontSize: 12, padding: '10px 20px', borderRadius: 8,
          background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)',
          color: 'var(--error)', cursor: 'pointer',
        }}>
          Sign Out
        </button>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   SHARED COMPONENTS
   ═══════════════════════════════════════════════════════════════════ */

function SectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.02em' }}>{title}</h2>
      <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>{description}</p>
    </div>
  )
}

function SecurityGateInline() {
  return (
    <div style={{ padding: 24, borderRadius: 12, background: 'var(--bg-secondary)', border: '1px solid rgba(250,204,21,0.3)', textAlign: 'center' }}>
      <div style={{ fontSize: 32, marginBottom: 8 }}>{'\uD83D\uDD12'}</div>
      <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>Security Layers Required</h3>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16 }}>
        Complete all three security layers (Wallet + Password + 2FA) to manage API keys and AI provider connections.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxWidth: 320, margin: '0 auto', textAlign: 'left' }}>
        {[
          { icon: '\uD83D\uDD10', name: 'Wallet Auth (SIWE)', desc: 'Sign in with your wallet' },
          { icon: '\uD83D\uDCE7', name: 'Email + Password', desc: 'Go to Security tab to set up' },
          { icon: '\uD83D\uDEE1\uFE0F', name: '2FA (TOTP)', desc: 'Go to Security tab to enable' },
        ].map(l => (
          <div key={l.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderRadius: 8, background: 'var(--bg-tertiary)', border: '1px solid rgba(250,204,21,0.15)' }}>
            <span>{l.icon}</span>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{l.name}</div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{l.desc}</div>
            </div>
          </div>
        ))}
      </div>
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

/* ═══════════════════════════════════════════════════════════════════
   SECTION: HELP & SUPPORT
   ═══════════════════════════════════════════════════════════════════ */

function SupportSection({ authHeaders }: { authHeaders: () => Record<string, string> }) {
  const [subject, setSubject] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('general')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState('')
  const [error, setError] = useState('')

  const CATS = [
    { id: 'general', label: 'General Question' },
    { id: 'bug', label: 'Bug Report' },
    { id: 'billing', label: 'Billing & Payments' },
    { id: 'security', label: 'Security Concern' },
    { id: 'feature', label: 'Feature Request' },
    { id: 'account', label: 'Account Issue' },
  ]

  const handleSubmit = async () => {
    if (!subject.trim() || !description.trim()) { setError('Subject and description are required'); return }
    setSubmitting(true); setError(''); setResult('')
    try {
      const r = await fetch(`${API_URL}/support/tickets`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ subject: subject.trim(), description: description.trim(), category }),
      })
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || 'Failed') }
      const t = await r.json()
      setResult(`Ticket #${t.ticket_number} created. View it in the Help Desk.`)
      setSubject(''); setDescription(''); setCategory('general')
    } catch (e: any) { setError(e.message) }
    finally { setSubmitting(false) }
  }

  return (
    <div>
      <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 4px 0' }}>Help & Support</h2>
      <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: '0 0 20px 0' }}>Contact our team or browse common questions.</p>

      {/* Quick ticket form */}
      <div className="card" style={{ padding: 20, marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 14px 0' }}>Quick Support Ticket</h3>

        {error && <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 6, fontSize: 12, background: 'rgba(248,113,113,0.1)', color: 'var(--error)' }}>{error}</div>}
        {result && <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 6, fontSize: 12, background: 'rgba(34,197,94,0.1)', color: '#22C55E' }}>{result}</div>}

        <div style={{ marginBottom: 12 }}>
          <input value={subject} onChange={e => setSubject(e.target.value)} placeholder="Subject"
            className="input-base" style={{ width: '100%', padding: '8px 12px', fontSize: 13, borderRadius: 6 }} />
        </div>
        <div style={{ marginBottom: 12 }}>
          <select value={category} onChange={e => setCategory(e.target.value)}
            className="input-base" style={{ width: '100%', padding: '8px 12px', fontSize: 13, borderRadius: 6 }}>
            {CATS.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </div>
        <div style={{ marginBottom: 14 }}>
          <textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe your issue..."
            className="input-base" rows={4} style={{ width: '100%', padding: '8px 12px', fontSize: 13, borderRadius: 6, resize: 'vertical' }} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <a href="/help/" style={{ fontSize: 12, color: 'var(--refi-teal)', textDecoration: 'none' }}>View all tickets in Help Desk &rarr;</a>
          <button onClick={handleSubmit} disabled={submitting} className="btn-primary"
            style={{ padding: '8px 16px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', fontWeight: 600, opacity: submitting ? 0.6 : 1 }}>
            {submitting ? 'Sending...' : 'Submit'}
          </button>
        </div>
      </div>

      {/* FAQ */}
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 14px 0' }}>Frequently Asked Questions</h3>
        {[
          { q: 'How do I connect my wallet?', a: 'Click "Connect Wallet" on the homepage. We support MetaMask, WalletConnect, Coinbase Wallet, and more via EIP-6963.' },
          { q: 'How do I deploy a smart contract?', a: 'Navigate to the Wizard (Pipeline) page, upload your contract, and GROOT will handle compilation, testing, and deployment.' },
          { q: 'Are my messages encrypted?', a: 'When XMTP is enabled on your wallet, all messages use end-to-end encryption via X3DH key exchange and Double Ratchet protocol.' },
          { q: 'How do I generate an API key?', a: 'Go to Settings > API Keys and click "Create Key". You can set scopes and rate limits per key.' },
          { q: 'Who has access to my data?', a: 'Your private data is stored in your account only. Source code is never exposed. GROOT only reads public SDK definitions you explicitly make public.' },
        ].map((faq, i) => (
          <details key={i} style={{ marginBottom: 8, padding: '10px 14px', borderRadius: 8, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
            <summary style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', cursor: 'pointer' }}>{faq.q}</summary>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8, lineHeight: 1.6 }}>{faq.a}</p>
          </details>
        ))}
      </div>
    </div>
  )
}
