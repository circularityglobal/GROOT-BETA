'use client'

import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { API_URL } from '@/lib/config'

interface DownloadModalProps {
  isOpen: boolean
  onClose: () => void
  product: string
  displayName: string
  available: boolean
  downloads: Record<string, string>
}

const PLATFORM_LABELS: Record<string, string> = {
  windows: 'Windows',
  macos: 'macOS',
  linux: 'Linux',
  debian: 'Debian / Ubuntu',
}

const INSTALL_INSTRUCTIONS: Record<string, Record<string, string[]>> = {
  pillars: {
    windows: [
      'Download the installer (.exe)',
      'Run refinet-pillar-setup.exe',
      'Follow the setup wizard',
      'Connect your wallet to start',
    ],
    macos: [
      'Download the disk image (.dmg)',
      'Open and drag to Applications',
      'Launch from Applications folder',
      'Connect your wallet to start',
    ],
    linux: [
      'Download the AppImage',
      'Run: chmod +x refinet-pillar.AppImage',
      'Execute the AppImage',
      'Connect your wallet to start',
    ],
    debian: [
      'Download the .deb package',
      'Run: sudo dpkg -i refinet-pillar.deb',
      'Launch from applications menu',
      'Connect your wallet to start',
    ],
  },
  cluster: {
    linux: [
      'Ensure Oracle Cloud ARM A1 environment',
      'Run the setup script:',
      'curl -sSL https://www.refinet.io/public-downloads/cluster/product/cluster_setup.sh | bash',
      'Your node auto-registers with REFINET Cloud',
    ],
  },
}

function detectPlatform(): string {
  if (typeof navigator === 'undefined') return 'linux'
  const ua = navigator.userAgent.toLowerCase()
  if (ua.includes('win')) return 'windows'
  if (ua.includes('mac')) return 'macos'
  return 'linux'
}

export default function DownloadModal({
  isOpen,
  onClose,
  product,
  displayName,
  available,
  downloads,
}: DownloadModalProps) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [consent, setConsent] = useState(false)
  const [platform, setPlatform] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')
  const [walletAddress, setWalletAddress] = useState<string | null>(null)
  const downloadTimerRef = useRef<ReturnType<typeof setTimeout>>()

  // Detect platform on mount
  useEffect(() => {
    if (isOpen) {
      const detected = detectPlatform()
      const platforms = Object.keys(downloads)
      setPlatform(platforms.includes(detected) ? detected : platforms[0] || '')
      setSuccess(false)
      setError('')
    } else {
      // Clean up download timer when modal closes
      if (downloadTimerRef.current) clearTimeout(downloadTimerRef.current)
    }
  }, [isOpen, downloads])

  // Try to get wallet address from wagmi
  useEffect(() => {
    try {
      // Check if ethereum provider exposes selected address
      const w = (window as any).ethereum
      if (w?.selectedAddress) {
        setWalletAddress(w.selectedAddress)
      }
    } catch {
      // No wallet available
    }
  }, [isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)

    const endpoint = available ? '/downloads/register' : '/downloads/waitlist'

    try {
      const token = typeof localStorage !== 'undefined'
        ? localStorage.getItem('refinet_token')
        : null

      const res = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          name,
          email,
          product,
          platform: available ? platform : undefined,
          eth_address: walletAddress,
          marketing_consent: consent,
          referrer: typeof document !== 'undefined' ? document.referrer : undefined,
        }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Request failed (${res.status})`)
      }

      const data = await res.json()
      setSuccess(true)

      // If download URL returned, trigger download after brief delay
      if (data.download_url) {
        downloadTimerRef.current = setTimeout(() => {
          window.open(data.download_url, '_blank')
        }, 1000)
      }
    } catch (err: any) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const instructions = INSTALL_INSTRUCTIONS[product]?.[platform] || []
  const platforms = Object.keys(downloads)

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
          onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2 }}
            className="w-full max-w-lg rounded-xl overflow-hidden"
            style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-default)',
              boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4"
              style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <div>
                <p className="text-[10px] font-mono uppercase tracking-widest" style={{ color: 'var(--refi-teal)' }}>
                  {available ? '> download' : '> waitlist'}
                </p>
                <h3 className="text-lg font-bold mt-1" style={{ color: 'var(--text-primary)' }}>
                  {displayName}
                </h3>
              </div>
              <button onClick={onClose} className="p-2 rounded-lg hover:opacity-70 transition-opacity"
                style={{ color: 'var(--text-secondary)' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="px-6 py-5 max-h-[70vh] overflow-y-auto">
              {success ? (
                /* Success state */
                <div className="text-center py-8">
                  <div className="text-4xl mb-4">
                    {available ? '↓' : '✓'}
                  </div>
                  <h4 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                    {available ? 'Download Starting...' : "You're on the List!"}
                  </h4>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {available
                      ? 'Your download should begin shortly. Check your downloads folder.'
                      : `We'll notify you at ${email} when ${displayName} is ready.`}
                  </p>
                  <button onClick={onClose} className="mt-6 px-6 py-2 rounded-lg text-sm font-medium"
                    style={{
                      background: 'var(--refi-teal)',
                      color: 'var(--bg-primary)',
                    }}>
                    Close
                  </button>
                </div>
              ) : (
                <>
                  {/* Installation instructions (download mode only) */}
                  {available && instructions.length > 0 && (
                    <div className="mb-5 p-4 rounded-lg" style={{
                      background: 'var(--terminal-bg)',
                      border: '1px solid var(--border-subtle)',
                    }}>
                      <p className="text-[10px] font-mono uppercase tracking-widest mb-3" style={{ color: 'var(--refi-teal)' }}>
                        Installation Steps
                      </p>
                      <ol className="space-y-1.5">
                        {instructions.map((step, i) => (
                          <li key={i} className="text-xs font-mono flex gap-2" style={{ color: 'var(--text-secondary)' }}>
                            <span style={{ color: 'var(--refi-teal)' }}>{i + 1}.</span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {/* Platform selector (download mode only) */}
                  {available && platforms.length > 1 && (
                    <div className="mb-4">
                      <label className="block text-[11px] font-mono uppercase tracking-wider mb-2"
                        style={{ color: 'var(--text-tertiary)' }}>
                        Platform
                      </label>
                      <div className="flex gap-2 flex-wrap">
                        {platforms.map((p) => (
                          <button
                            key={p}
                            onClick={() => setPlatform(p)}
                            className="px-3 py-1.5 rounded-md text-xs font-mono transition-all"
                            style={{
                              background: platform === p ? 'var(--refi-teal-glow)' : 'var(--bg-secondary)',
                              color: platform === p ? 'var(--refi-teal)' : 'var(--text-secondary)',
                              border: `1px solid ${platform === p ? 'rgba(92,224,210,0.3)' : 'var(--border-subtle)'}`,
                            }}
                          >
                            {PLATFORM_LABELS[p] || p}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Lead capture form */}
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                      <label className="block text-[11px] font-mono uppercase tracking-wider mb-1.5"
                        style={{ color: 'var(--text-tertiary)' }}>
                        Name *
                      </label>
                      <input
                        type="text"
                        required
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Your name"
                        className="w-full px-3 py-2 rounded-lg text-sm font-mono"
                        style={{
                          background: 'var(--bg-input)',
                          border: '1px solid var(--border-subtle)',
                          color: 'var(--text-primary)',
                          outline: 'none',
                        }}
                      />
                    </div>

                    <div>
                      <label className="block text-[11px] font-mono uppercase tracking-wider mb-1.5"
                        style={{ color: 'var(--text-tertiary)' }}>
                        Email *
                      </label>
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@example.com"
                        className="w-full px-3 py-2 rounded-lg text-sm font-mono"
                        style={{
                          background: 'var(--bg-input)',
                          border: '1px solid var(--border-subtle)',
                          color: 'var(--text-primary)',
                          outline: 'none',
                        }}
                      />
                    </div>

                    {walletAddress && (
                      <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-mono"
                        style={{
                          background: 'var(--refi-teal-glow)',
                          border: '1px solid rgba(92,224,210,0.2)',
                          color: 'var(--refi-teal)',
                        }}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M20 6L9 17l-5-5" />
                        </svg>
                        Wallet: {walletAddress.slice(0, 6)}...{walletAddress.slice(-4)}
                      </div>
                    )}

                    <label className="flex items-start gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={consent}
                        onChange={(e) => setConsent(e.target.checked)}
                        className="mt-0.5"
                        style={{ accentColor: 'var(--refi-teal)' }}
                      />
                      <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                        I agree to receive product updates and announcements from REFINET
                      </span>
                    </label>

                    {error && (
                      <div className="px-3 py-2 rounded-lg text-xs font-mono"
                        style={{ background: 'rgba(255,95,87,0.1)', color: '#FF5F57', border: '1px solid rgba(255,95,87,0.2)' }}>
                        {error}
                      </div>
                    )}

                    <button
                      type="submit"
                      disabled={submitting || !name || !email}
                      className="w-full py-2.5 rounded-lg text-sm font-semibold transition-all"
                      style={{
                        background: submitting || !name || !email ? 'var(--bg-secondary)' : 'var(--refi-teal)',
                        color: submitting || !name || !email ? 'var(--text-tertiary)' : 'var(--bg-primary)',
                        cursor: submitting || !name || !email ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {submitting
                        ? 'Processing...'
                        : available
                          ? 'Download Now'
                          : 'Join Waitlist'}
                    </button>

                    <p className="text-[10px] text-center" style={{ color: 'var(--text-tertiary)' }}>
                      Your information is stored securely and never shared with third parties.
                    </p>
                  </form>
                </>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
