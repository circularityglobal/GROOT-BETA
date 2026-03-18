'use client'

import { useState, useEffect } from 'react'
import AuthFlow from '@/components/AuthFlow'

export default function SettingsPage() {
  const [token, setToken] = useState<string | null>(null)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    const t = localStorage.getItem('refinet_token')
    if (t) {
      // Already logged in — settings is now a modal, send to dashboard
      window.location.href = '/dashboard/'
      return
    }
    setToken(null)
    setChecked(true)
  }, [])

  const handleAuthComplete = (newToken: string) => {
    setToken(newToken)
    window.location.href = '/dashboard/'
  }

  if (!checked) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div className="animate-pulse" style={{ color: 'var(--text-tertiary)', fontSize: 13, fontFamily: "'JetBrains Mono', monospace" }}>
          Loading...
        </div>
      </div>
    )
  }

  return (
    <div style={{ paddingTop: 48, paddingBottom: 48 }}>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <h1 style={{ letterSpacing: '-0.02em', fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          Sign In to REFINET Cloud
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: 8 }}>
          Connect your Ethereum wallet to get started.
        </p>
      </div>
      <AuthFlow onComplete={handleAuthComplete} />
    </div>
  )
}
