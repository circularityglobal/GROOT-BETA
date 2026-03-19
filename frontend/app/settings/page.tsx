'use client'

import { useState, useEffect } from 'react'
import AuthFlow from '@/components/AuthFlow'

export default function SettingsPage() {
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    const t = localStorage.getItem('refinet_token')
    if (t) {
      window.location.href = '/dashboard/'
      return
    }
    setChecked(true)
  }, [])

  const handleAuthComplete = (newToken: string) => {
    window.location.href = '/dashboard/'
  }

  if (!checked) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: 'var(--bg-primary)' }}>
        <div className="auth-spinner-lg" />
      </div>
    )
  }

  return (
    <div className="auth-page">
      {/* Left: Visual Panel */}
      <div className="auth-visual">
        <div className="auth-visual-content">
          {/* Animated background elements */}
          <div className="auth-visual-bg">
            <div className="auth-orb auth-orb-1" />
            <div className="auth-orb auth-orb-2" />
            <div className="auth-orb auth-orb-3" />
          </div>

          {/* Grid overlay */}
          <div className="auth-grid-overlay" />

          {/* Content */}
          <div className="auth-visual-inner">
            <div className="auth-visual-badge">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/>
              </svg>
              Regenerative Finance
            </div>

            <h2 className="auth-visual-title">
              Building the infrastructure for a
              <span className="auth-visual-highlight"> regenerative economy</span>
            </h2>

            <p className="auth-visual-desc">
              REFINET Cloud provides sovereign AI tools, decentralized identity, and smart contract intelligence — all anchored to your wallet.
            </p>

            <div className="auth-visual-stats">
              <div className="auth-stat">
                <span className="auth-stat-value">6</span>
                <span className="auth-stat-label">Networks</span>
              </div>
              <div className="auth-stat-divider" />
              <div className="auth-stat">
                <span className="auth-stat-value">SIWE</span>
                <span className="auth-stat-label">Auth Protocol</span>
              </div>
              <div className="auth-stat-divider" />
              <div className="auth-stat">
                <span className="auth-stat-value">E2E</span>
                <span className="auth-stat-label">Encrypted</span>
              </div>
            </div>

            {/* Decorative illustration: Abstract tree / growth */}
            <div className="auth-visual-illustration">
              <svg viewBox="0 0 400 300" fill="none" xmlns="http://www.w3.org/2000/svg" className="auth-tree-svg">
                {/* Trunk */}
                <path d="M200 280V160" stroke="var(--refi-teal)" strokeWidth="3" strokeLinecap="round" opacity="0.6"/>
                {/* Branches */}
                <path d="M200 200L160 170" stroke="var(--refi-teal)" strokeWidth="2" strokeLinecap="round" opacity="0.5"/>
                <path d="M200 200L240 165" stroke="var(--refi-teal)" strokeWidth="2" strokeLinecap="round" opacity="0.5"/>
                <path d="M200 180L170 145" stroke="var(--refi-teal)" strokeWidth="2" strokeLinecap="round" opacity="0.4"/>
                <path d="M200 180L235 140" stroke="var(--refi-teal)" strokeWidth="2" strokeLinecap="round" opacity="0.4"/>
                <path d="M200 160L150 120" stroke="var(--refi-teal)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3"/>
                <path d="M200 160L250 115" stroke="var(--refi-teal)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3"/>
                {/* Leaves (circles) */}
                <circle cx="160" cy="170" r="8" fill="var(--refi-teal)" opacity="0.15"/>
                <circle cx="240" cy="165" r="10" fill="var(--refi-teal)" opacity="0.12"/>
                <circle cx="170" cy="145" r="6" fill="var(--refi-teal)" opacity="0.18"/>
                <circle cx="235" cy="140" r="7" fill="var(--refi-teal)" opacity="0.14"/>
                <circle cx="150" cy="120" r="12" fill="var(--refi-teal)" opacity="0.1"/>
                <circle cx="250" cy="115" r="9" fill="var(--refi-teal)" opacity="0.13"/>
                <circle cx="200" cy="130" r="14" fill="var(--refi-teal)" opacity="0.08"/>
                {/* Root network */}
                <path d="M200 280L170 300" stroke="var(--refi-teal)" strokeWidth="1.5" strokeLinecap="round" opacity="0.2"/>
                <path d="M200 280L230 295" stroke="var(--refi-teal)" strokeWidth="1.5" strokeLinecap="round" opacity="0.2"/>
                <path d="M200 280L185 300" stroke="var(--refi-teal)" strokeWidth="1" strokeLinecap="round" opacity="0.15"/>
                <path d="M200 280L220 300" stroke="var(--refi-teal)" strokeWidth="1" strokeLinecap="round" opacity="0.15"/>
                {/* Connection dots */}
                <circle cx="160" cy="170" r="3" fill="var(--refi-teal)" opacity="0.6"/>
                <circle cx="240" cy="165" r="3" fill="var(--refi-teal)" opacity="0.6"/>
                <circle cx="170" cy="145" r="2.5" fill="var(--refi-teal)" opacity="0.5"/>
                <circle cx="235" cy="140" r="2.5" fill="var(--refi-teal)" opacity="0.5"/>
                <circle cx="150" cy="120" r="3" fill="var(--refi-teal)" opacity="0.4"/>
                <circle cx="250" cy="115" r="3" fill="var(--refi-teal)" opacity="0.4"/>
                <circle cx="200" cy="160" r="4" fill="var(--refi-teal)" opacity="0.7"/>
              </svg>
            </div>
          </div>

          {/* Bottom attribution */}
          <div className="auth-visual-footer">
            <img src="/refi-logo.png" alt="" className="auth-visual-footer-logo" />
            <span>REFINET Cloud v1.0</span>
          </div>
        </div>
      </div>

      {/* Right: Auth Panel */}
      <div className="auth-panel">
        <AuthFlow onComplete={handleAuthComplete} />
      </div>
    </div>
  )
}
