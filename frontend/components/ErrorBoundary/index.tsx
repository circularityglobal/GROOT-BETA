'use client'

import React from 'react'

interface Props {
  children: React.ReactNode
  fallback?: React.ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

/**
 * Global error boundary for REFINET Cloud.
 * Catches render-time crashes and shows a recovery UI instead of a blank page.
 * Provides a "Reload" button that clears stale state and refreshes.
 */
export default class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[REFINET] Uncaught error:', error, errorInfo)
  }

  handleReset = () => {
    // Clear potentially stale state that caused the crash
    try {
      // Clear wagmi cookie state (stale connector references)
      document.cookie.split(';').forEach(c => {
        const name = c.split('=')[0].trim()
        if (name.startsWith('wagmi') || name.startsWith('w3m')) {
          document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
        }
      })
    } catch {}
    this.setState({ hasError: false, error: null })
  }

  handleHardReset = () => {
    try {
      // Clear all wagmi/wallet cookies
      document.cookie.split(';').forEach(c => {
        const name = c.split('=')[0].trim()
        if (name.startsWith('wagmi') || name.startsWith('w3m')) {
          document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
        }
      })
      // Clear wallet-related localStorage but preserve auth tokens
      const keysToRemove: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && (key.startsWith('wagmi') || key.startsWith('w3m') || key.startsWith('wc@'))) {
          keysToRemove.push(key)
        }
      }
      keysToRemove.forEach(k => localStorage.removeItem(k))
    } catch {}
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg-primary, #0a0a0f)',
          color: 'var(--text-primary, #e4e4e7)',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          padding: 24,
        }}>
          <div style={{ maxWidth: 480, textAlign: 'center' }}>
            <img
              src="/refi-logo.png"
              alt="REFINET"
              style={{ width: 48, height: 48, margin: '0 auto 16px', display: 'block' }}
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
            <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
              Something went wrong
            </h1>
            <p style={{
              fontSize: 13,
              color: 'var(--text-secondary, #a1a1aa)',
              marginBottom: 24,
              lineHeight: 1.5,
            }}>
              REFINET Cloud encountered an unexpected error. This can happen after updates
              or when wallet state becomes stale. Try the options below.
            </p>

            {this.state.error && (
              <pre style={{
                fontSize: 10,
                color: 'var(--text-tertiary, #71717a)',
                background: 'var(--bg-secondary, #18181b)',
                padding: 12,
                borderRadius: 8,
                marginBottom: 24,
                textAlign: 'left',
                overflow: 'auto',
                maxHeight: 120,
                border: '1px solid var(--border-subtle, #27272a)',
              }}>
                {this.state.error.message}
              </pre>
            )}

            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
              <button
                onClick={this.handleReset}
                style={{
                  padding: '10px 20px',
                  fontSize: 13,
                  fontWeight: 600,
                  borderRadius: 8,
                  border: 'none',
                  cursor: 'pointer',
                  background: 'var(--refi-teal, #2dd4bf)',
                  color: '#000',
                }}
              >
                Try Again
              </button>
              <button
                onClick={this.handleHardReset}
                style={{
                  padding: '10px 20px',
                  fontSize: 13,
                  fontWeight: 600,
                  borderRadius: 8,
                  border: '1px solid var(--border-default, #3f3f46)',
                  cursor: 'pointer',
                  background: 'transparent',
                  color: 'var(--text-secondary, #a1a1aa)',
                }}
              >
                Clear Wallet State & Reload
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
