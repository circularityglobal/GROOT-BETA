'use client'

import { useState, useRef } from 'react'
import { API_URL } from '@/lib/config'

type Step = 'intro' | 'creating' | 'created' | 'secure' | 'ready'

interface WalletOnboardingProps {
  chainId: number
  chainName: string
  onComplete: (token: string) => void
  onCancel: () => void
}

export default function WalletOnboarding({ chainId, chainName, onComplete, onCancel }: WalletOnboardingProps) {
  const [step, setStep] = useState<Step>('intro')
  const [error, setError] = useState('')
  const [walletAddress, setWalletAddress] = useState('')
  const [accessToken, setAccessToken] = useState('')

  // Security setup
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [securityMsg, setSecurityMsg] = useState('')
  const [securityError, setSecurityError] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)
  const [passwordSaved, setPasswordSaved] = useState(false)

  // Animation
  const [addressCopied, setAddressCopied] = useState(false)

  const [progressText, setProgressText] = useState('')
  const progressSteps = useRef([
    'Generating cryptographic keypair...',
    'Splitting private key into 5 shares...',
    'Encrypting shares with AES-256-GCM...',
    'Storing threshold shares (3-of-5)...',
    'Registering wallet identity...',
    'Signing authentication proof...',
    'Verifying signature...',
  ])

  const handleCreate = async () => {
    setStep('creating')
    setError('')

    // Animate progress messages
    let i = 0
    const interval = setInterval(() => {
      if (i < progressSteps.current.length) {
        setProgressText(progressSteps.current[i])
        i++
      }
    }, 600)

    try {
      const resp = await fetch(`${API_URL}/auth/wallet/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chain_id: chainId }),
      })

      clearInterval(interval)

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Wallet creation failed' }))
        throw new Error(err.detail || 'Wallet creation failed')
      }

      const data = await resp.json()

      localStorage.setItem('refinet_token', data.access_token)
      localStorage.setItem('refinet_refresh', data.refresh_token)
      window.dispatchEvent(new Event('refinet-auth-change'))

      setAccessToken(data.access_token)
      setWalletAddress(data.eth_address)
      setProgressText('Wallet secured.')

      // Brief pause to show final message
      setTimeout(() => setStep('created'), 500)
    } catch (e: any) {
      clearInterval(interval)
      setError(e.message)
      setStep('intro')
    }
  }

  const handleSetPassword = async () => {
    setSecurityError('')
    setSecurityMsg('')

    if (!email.trim()) { setSecurityError('Email is required for recovery.'); return }
    if (password.length < 12) { setSecurityError('Password must be at least 12 characters.'); return }
    if (password !== confirmPassword) { setSecurityError('Passwords do not match.'); return }

    setSavingPassword(true)
    try {
      const resp = await fetch(`${API_URL}/auth/settings/password`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Failed' }))
        throw new Error(err.detail)
      }
      setPasswordSaved(true)
      setSecurityMsg('Recovery credentials saved.')
    } catch (e: any) {
      setSecurityError(e.message)
    } finally {
      setSavingPassword(false)
    }
  }

  const copyAddress = () => {
    navigator.clipboard.writeText(walletAddress).then(() => {
      setAddressCopied(true)
      setTimeout(() => setAddressCopied(false), 2000)
    })
  }

  const finish = () => {
    onComplete(accessToken)
  }

  // Escape key to go back on intro, or do nothing on other steps
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && step === 'intro') onCancel()
  }

  const backdropRef = useRef<HTMLDivElement>(null)

  return (
    <div
      ref={backdropRef}
      onKeyDown={handleKeyDown}
      tabIndex={-1}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        className="animate-slide-up"
        style={{
          width: '100%', maxWidth: 480,
          background: 'var(--bg-primary)',
          border: '1px solid var(--border-default)',
          borderRadius: 16,
          overflow: 'hidden',
          boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
        }}
      >
        {/* Progress indicator */}
        <div style={{ display: 'flex', gap: 0, padding: '0 20px', paddingTop: 16 }}>
          {(['intro', 'creating', 'created', 'secure', 'ready'] as Step[]).map((s, i) => (
            <div key={s} style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: stepIndex(step) >= i ? 'var(--refi-teal)' : 'var(--bg-tertiary)',
                transition: 'background 0.3s',
                flexShrink: 0,
              }} />
              {i < 4 && <div style={{ flex: 1, height: 2, background: stepIndex(step) > i ? 'var(--refi-teal)' : 'var(--bg-tertiary)', transition: 'background 0.3s', margin: '0 4px' }} />}
            </div>
          ))}
        </div>

        <div style={{ padding: '20px 24px 24px' }}>
          {/* ── Step: Intro ── */}
          {step === 'intro' && (
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: 8 }}>
                Create Your Wallet
              </h2>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 20 }}>
                We&apos;ll generate a secure Ethereum wallet for you, protected by threshold encryption. No seed phrase to write down.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 20 }}>
                <SecurityPoint icon={<ShieldIcon />} title="Shamir Secret Sharing" description="Your private key is split into 5 encrypted shares. Any 3 can reconstruct it — no single point of failure." />
                <SecurityPoint icon={<LockIcon />} title="AES-256-GCM Encryption" description="Each share is individually encrypted with a unique key derived from your wallet." />
                <SecurityPoint icon={<KeyIcon />} title="Zero Knowledge" description="The full private key exists in memory only during signing, then is securely wiped." />
              </div>

              <div style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', marginBottom: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Network:</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--refi-teal)' }}>{chainName}</span>
                </div>
              </div>

              {error && (
                <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 8, fontSize: 12, background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', color: 'var(--error)' }}>
                  {error}
                </div>
              )}

              <div style={{ display: 'flex', gap: 10 }}>
                <button onClick={onCancel} className="btn-secondary" style={{ flex: 1, fontSize: 13, padding: '10px 0' }}>
                  Back
                </button>
                <button onClick={handleCreate} className="btn-primary" style={{ flex: 2, fontSize: 13, padding: '10px 0' }}>
                  Generate Wallet
                </button>
              </div>
            </div>
          )}

          {/* ── Step: Creating (animated) ── */}
          {step === 'creating' && (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <div className="animate-pulse-glow" style={{
                width: 56, height: 56, borderRadius: '50%', margin: '0 auto 20px',
                background: 'var(--refi-teal-glow)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
              </div>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, letterSpacing: '-0.02em' }}>
                Securing Your Wallet
              </h2>
              <p style={{ fontSize: 12, color: 'var(--refi-teal)', fontFamily: "'JetBrains Mono', monospace", minHeight: 18 }}>
                {progressText}
              </p>
            </div>
          )}

          {/* ── Step: Created ── */}
          {step === 'created' && (
            <div>
              <div style={{ textAlign: 'center', marginBottom: 20 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: '50%', margin: '0 auto 12px',
                  background: 'var(--refi-teal-glow)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </div>
                <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
                  Wallet Created
                </h2>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                  Your wallet is live on {chainName}.
                </p>
              </div>

              <div style={{ padding: '12px 14px', borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Your Address</span>
                  <button onClick={copyAddress} style={{
                    background: 'none', border: 'none', cursor: 'pointer', padding: '2px 6px', borderRadius: 4,
                    fontSize: 10, color: addressCopied ? 'var(--refi-teal)' : 'var(--text-tertiary)',
                    fontFamily: "'JetBrains Mono', monospace", transition: 'color 0.15s',
                  }}>
                    {addressCopied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: 'var(--text-primary)', wordBreak: 'break-all', lineHeight: 1.5, userSelect: 'all' }}>
                  {walletAddress}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 20 }}>
                <Badge label="3-of-5 Threshold" />
                <Badge label="AES-256 Encrypted" />
                <Badge label={chainName} />
              </div>

              <button onClick={() => setStep('secure')} className="btn-primary" style={{ width: '100%', fontSize: 13, padding: '10px 0' }}>
                Set Up Recovery
              </button>
              <button onClick={() => setStep('ready')} style={{
                width: '100%', marginTop: 8, padding: '8px 0', fontSize: 12,
                background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer',
              }}
                onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-secondary)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-tertiary)')}
              >
                Skip for now — you can set this up later in Settings
              </button>
            </div>
          )}

          {/* ── Step: Security Setup ── */}
          {step === 'secure' && (
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: 4 }}>
                Secure Your Account
              </h2>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.5 }}>
                Add email and password as an alternative login method. This lets you recover your account if you lose device access.
              </p>

              {securityMsg && (
                <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 8, fontSize: 12, background: 'rgba(92,224,210,0.1)', border: '1px solid var(--refi-teal)', color: 'var(--refi-teal)' }}>
                  {securityMsg}
                </div>
              )}
              {securityError && (
                <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 8, fontSize: 12, background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', color: 'var(--error)' }}>
                  {securityError}
                </div>
              )}

              {!passwordSaved ? (
                <form onSubmit={e => { e.preventDefault(); handleSetPassword() }} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <input type="email" placeholder="Email address" value={email}
                    onChange={e => setEmail(e.target.value)}
                    className="input-base focus-glow" style={{ fontSize: 13 }} autoFocus />
                  <div>
                    <input type="password" placeholder="Password (12+ characters)" value={password}
                      onChange={e => setPassword(e.target.value)}
                      className="input-base focus-glow" style={{ fontSize: 13 }} />
                    {password.length > 0 && (
                      <div style={{ display: 'flex', gap: 3, marginTop: 6 }}>
                        {[1,2,3,4].map(level => (
                          <div key={level} style={{
                            flex: 1, height: 3, borderRadius: 2,
                            background: password.length >= level * 4 + 8
                              ? (level >= 3 ? 'var(--refi-teal)' : level >= 2 ? 'var(--warning)' : 'var(--error)')
                              : 'var(--bg-tertiary)',
                            transition: 'background 0.2s',
                          }} />
                        ))}
                      </div>
                    )}
                  </div>
                  <input type="password" placeholder="Confirm password" value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    className="input-base focus-glow" style={{ fontSize: 13 }} />

                  <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
                    <button type="button" onClick={() => setStep('ready')} className="btn-secondary" style={{ flex: 1, fontSize: 12, padding: '10px 0' }}>
                      Skip
                    </button>
                    <button type="submit" className="btn-primary" disabled={savingPassword}
                      style={{ flex: 2, fontSize: 12, padding: '10px 0', opacity: savingPassword ? 0.7 : 1 }}>
                      {savingPassword ? 'Saving...' : 'Save Recovery Credentials'}
                    </button>
                  </div>
                </form>
              ) : (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 14px', borderRadius: 10, background: 'rgba(92,224,210,0.08)', border: '1px solid var(--refi-teal)', marginBottom: 16 }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                    <span style={{ fontSize: 12, color: 'var(--refi-teal)', fontWeight: 500 }}>Recovery credentials saved for {email}</span>
                  </div>
                  <button onClick={() => setStep('ready')} className="btn-primary" style={{ width: '100%', fontSize: 13, padding: '10px 0' }}>
                    Continue
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ── Step: Ready ── */}
          {step === 'ready' && (
            <div style={{ textAlign: 'center' }}>
              <div style={{
                width: 56, height: 56, borderRadius: '50%', margin: '0 auto 16px',
                background: 'var(--refi-teal-glow)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
              </div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: 4 }}>
                You&apos;re All Set
              </h2>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>
                Your wallet is secured and ready to use.
              </p>
              <p style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)', marginBottom: 20, wordBreak: 'break-all' }}>
                {walletAddress}
              </p>

              <div style={{ display: 'flex', gap: 6, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
                <Badge label="Wallet Active" />
                {passwordSaved ? <Badge label="Recovery Set" /> : <WarningBadge label="No Recovery" />}
                <Badge label={chainName} />
              </div>

              {!passwordSaved && (
                <button onClick={() => setStep('secure')} style={{
                  width: '100%', marginBottom: 10, padding: '8px 0', fontSize: 11, borderRadius: 8,
                  background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)',
                  color: 'var(--warning)', cursor: 'pointer', transition: 'all 0.15s',
                }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(251,191,36,0.12)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'rgba(251,191,36,0.08)')}
                >
                  Set up recovery before continuing
                </button>
              )}

              <button onClick={finish} className="btn-primary" style={{ width: '100%', fontSize: 14, padding: '12px 0', fontWeight: 600 }}>
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

function SecurityPoint({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div style={{ display: 'flex', gap: 10, padding: '10px 12px', borderRadius: 8, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
      <span style={{ color: 'var(--refi-teal)', flexShrink: 0, marginTop: 1 }}>{icon}</span>
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>{title}</div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>{description}</div>
      </div>
    </div>
  )
}

function Badge({ label }: { label: string }) {
  return (
    <span style={{
      fontSize: 10, padding: '3px 8px', borderRadius: 4,
      background: 'var(--refi-teal-glow)', color: 'var(--refi-teal)',
      fontFamily: "'JetBrains Mono', monospace", fontWeight: 500,
      border: '1px solid rgba(92,224,210,0.2)',
    }}>
      {label}
    </span>
  )
}

function WarningBadge({ label }: { label: string }) {
  return (
    <span style={{
      fontSize: 10, padding: '3px 8px', borderRadius: 4,
      background: 'rgba(251,191,36,0.1)', color: 'var(--warning)',
      fontFamily: "'JetBrains Mono', monospace", fontWeight: 500,
      border: '1px solid rgba(251,191,36,0.2)',
    }}>
      {label}
    </span>
  )
}

function stepIndex(step: Step): number {
  return { intro: 0, creating: 1, created: 2, secure: 3, ready: 4 }[step]
}

/* ─── Icons ─── */
function ShieldIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
}
function LockIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
}
function KeyIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
}
