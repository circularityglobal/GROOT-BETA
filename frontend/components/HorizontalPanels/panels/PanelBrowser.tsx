'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import MatrixRain from '@/components/MatrixRain'

interface PanelBrowserProps {
  isActive: boolean
}

const FEATURES = [
  {
    tag: 'SOVEREIGN_DNS',
    title: 'Decentralized Name Resolution',
    desc: 'Navigate the sovereign web with ENS, Handshake, and REFINET\'s own decentralized naming system. No ICANN dependency.',
  },
  {
    tag: 'ENCRYPTED_TRANSIT',
    title: 'End-to-End Encrypted Browsing',
    desc: 'Every connection encrypted by default. No certificate authorities. Peer-to-peer TLS with wallet-based identity verification.',
  },
  {
    tag: 'IPFS_NATIVE',
    title: 'Built-in Decentralized Storage',
    desc: 'Access IPFS, Arweave, and Filecoin content natively. Pin and retrieve content without third-party gateways.',
  },
  {
    tag: 'DID_IDENTITY',
    title: 'Wallet-Based Authentication',
    desc: 'Your Ethereum wallet is your identity. Sign in everywhere with one click. No passwords. No tracking cookies.',
  },
]

export default function PanelBrowser({ isActive }: PanelBrowserProps) {
  const [animate, setAnimate] = useState(false)

  useEffect(() => {
    if (isActive) {
      const t = setTimeout(() => setAnimate(true), 200)
      return () => clearTimeout(t)
    } else {
      setAnimate(false)
    }
  }, [isActive])

  return (
    <div className="w-screen h-full flex-shrink-0 relative overflow-hidden"
      style={{ background: 'var(--bg-primary)' }}>

      {/* Matrix accent - left edge */}
      <div className="absolute left-0 top-0 bottom-0 w-32 overflow-hidden opacity-30">
        {isActive && <MatrixRain color="#00FF41" opacity={0.2} density={16} speed={0.5} />}
      </div>

      <div className="relative z-10 flex flex-col items-center justify-center h-full px-6 py-12">
        <div className="max-w-5xl w-full">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={animate ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5 }}
            className="text-center mb-10"
          >
            <p className="text-[12px] font-mono uppercase tracking-widest mb-3" style={{ color: 'var(--matrix-green)' }}>
              {'>'} refinet_browser
            </p>
            <h2 className="text-3xl md:text-5xl font-extrabold tracking-tighter mb-4" style={{ letterSpacing: '-0.04em' }}>
              A browser for the<br />
              <span className="text-glow-matrix" style={{ color: 'var(--matrix-green)' }}>sovereign internet</span>
            </h2>
            <p className="text-base max-w-lg mx-auto" style={{ color: 'var(--text-secondary)' }}>
              The web was built on openness. REFINET Browser takes it back — decentralized, encrypted, and connected to GROOT.
            </p>
          </motion.div>

          {/* Browser mockup + features */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
            {/* Browser mockup */}
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              animate={animate ? { opacity: 1, x: 0 } : {}}
              transition={{ delay: 0.3, duration: 0.6 }}
              className="rounded-xl overflow-hidden"
              style={{
                background: 'var(--terminal-bg)',
                border: '1px solid var(--terminal-border)',
                boxShadow: '0 8px 40px rgba(0,255,65,0.06)',
              }}
            >
              {/* Browser chrome */}
              <div className="flex items-center gap-2 px-4 py-2.5" style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-subtle)' }}>
                <div className="flex gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#FF5F57' }} />
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#FEBC2E' }} />
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#28C840' }} />
                </div>
                {/* Address bar */}
                <div className="flex-1 ml-3 px-3 py-1 rounded-md text-[11px] font-mono flex items-center gap-2"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border-subtle)' }}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--matrix-green)" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                  </svg>
                  <span style={{ color: 'var(--matrix-green)' }}>refinet://</span>
                  <span style={{ color: 'var(--text-secondary)' }}>sovereign.net</span>
                </div>
              </div>

              {/* Browser content area */}
              <div className="p-6 min-h-[200px] md:min-h-[280px] relative scanlines">
                <div className="font-mono text-[12px] space-y-2">
                  <p style={{ color: 'var(--matrix-green)' }}>
                    ✓ Connected to GROOT Intelligence Network
                  </p>
                  <p style={{ color: 'var(--text-secondary)' }}>
                    ✓ Peer-to-peer encryption active
                  </p>
                  <p style={{ color: 'var(--text-secondary)' }}>
                    ✓ Decentralized DNS resolved
                  </p>
                  <p style={{ color: 'var(--text-secondary)' }}>
                    ✓ IPFS gateway: local node
                  </p>
                  <p style={{ color: 'var(--text-secondary)' }}>
                    ✓ Wallet identity: 0x7a3...9f2c
                  </p>
                  <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                    <p style={{ color: 'var(--text-tertiary)' }}>
                      {'>'} Browsing sovereign web with zero telemetry_<span className="cursor-blink" style={{ color: 'var(--matrix-green)' }}>█</span>
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Feature list */}
            <div className="space-y-4">
              {FEATURES.map((f, i) => (
                <motion.div
                  key={f.tag}
                  initial={{ opacity: 0, x: 30 }}
                  animate={animate ? { opacity: 1, x: 0 } : {}}
                  transition={{ delay: 0.4 + i * 0.12, duration: 0.5 }}
                  className="card p-4"
                >
                  <span className="inline-block text-[10px] font-mono font-semibold px-2 py-0.5 rounded mb-2"
                    style={{
                      color: 'var(--matrix-green)',
                      background: 'var(--matrix-green-dim)',
                      border: '1px solid rgba(0,255,65,0.2)',
                    }}>
                    [{f.tag}]
                  </span>
                  <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
                    {f.title}
                  </h3>
                  <p className="text-[12px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                    {f.desc}
                  </p>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Coming Soon badge */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={animate ? { opacity: 1 } : {}}
            transition={{ delay: 1, duration: 0.4 }}
            className="text-center mt-8"
          >
            <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full font-mono text-[12px]"
              style={{
                border: '1px solid rgba(0,255,65,0.2)',
                color: 'var(--matrix-green)',
                background: 'rgba(0,255,65,0.05)',
              }}>
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--matrix-green)' }} />
              Coming Soon — Join the Waitlist
            </span>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
