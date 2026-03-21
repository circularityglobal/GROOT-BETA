'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

interface PanelInfrastructureProps {
  isActive: boolean
}

const AGENTS = [
  { name: 'Platform Ops', desc: 'Self-healing infrastructure — detects failures in 60 seconds', icon: '⚙' },
  { name: 'Knowledge Curator', desc: 'Maintains the intelligence layer — repairs orphans, syncs indexes', icon: '🧠' },
  { name: 'Contract Watcher', desc: 'On-chain security — scans ABIs, decodes events, correlates bridges', icon: '🔗' },
  { name: 'Security Sentinel', desc: 'Autonomous defense — brute force detection, TLS monitoring', icon: '🛡' },
  { name: 'Repo Migrator', desc: 'One-URL import — GitHub to REFINET across 9 blockchain ecosystems', icon: '📦' },
]

const STATS = [
  { value: '$0', label: 'Monthly cost', sub: 'Forever free infrastructure' },
  { value: '317', label: 'API endpoints', sub: 'OpenAI-compatible' },
  { value: '5', label: 'Autonomous agents', sub: 'Self-operating 24/7' },
  { value: '9', label: 'Blockchain ecosystems', sub: 'EVM + Solana + Move + more' },
]

export default function PanelInfrastructure({ isActive }: PanelInfrastructureProps) {
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

      {/* Subtle grid */}
      <div className="absolute inset-0 pointer-events-none dot-grid" style={{
        backgroundImage: 'radial-gradient(circle, var(--border-subtle) 1px, transparent 1px)',
        backgroundSize: '28px 28px',
      }} />

      {/* Radial accent */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: 'radial-gradient(ellipse 50% 50% at 50% 50%, rgba(92,224,210,0.04) 0%, transparent 70%)',
      }} />

      <div className="relative z-10 flex flex-col items-center justify-center h-full px-6 py-10">
        <div className="max-w-5xl w-full">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={animate ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5 }}
            className="text-center mb-8"
          >
            <p className="text-[12px] font-mono uppercase tracking-widest mb-3" style={{ color: 'var(--refi-teal)' }}>
              {'>'} sovereign_infrastructure
            </p>
            <h2 className="text-3xl md:text-5xl font-extrabold tracking-tighter mb-4" style={{ letterSpacing: '-0.04em' }}>
              Infrastructure that<br />
              <span style={{ color: 'var(--refi-teal)' }}>operates itself</span>
            </h2>
            <p className="text-base max-w-lg mx-auto" style={{ color: 'var(--text-secondary)' }}>
              Five autonomous agents keep REFINET Cloud alive, secure, and intelligent — without human intervention. Zero recurring cost. Fully open source.
            </p>
          </motion.div>

          {/* Stats row */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={animate ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8"
          >
            {STATS.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={animate ? { opacity: 1, scale: 1 } : {}}
                transition={{ delay: 0.3 + i * 0.08, duration: 0.4 }}
                className="text-center px-3 py-4 rounded-xl"
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div className="text-2xl md:text-3xl font-extrabold font-mono" style={{ color: 'var(--refi-teal)' }}>
                  {s.value}
                </div>
                <div className="text-[12px] font-semibold mt-1" style={{ color: 'var(--text-primary)' }}>
                  {s.label}
                </div>
                <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                  {s.sub}
                </div>
              </motion.div>
            ))}
          </motion.div>

          {/* Agent cards */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={animate ? { opacity: 1 } : {}}
            transition={{ delay: 0.5, duration: 0.5 }}
            className="space-y-2"
          >
            {AGENTS.map((a, i) => (
              <motion.div
                key={a.name}
                initial={{ opacity: 0, x: -20 }}
                animate={animate ? { opacity: 1, x: 0 } : {}}
                transition={{ delay: 0.6 + i * 0.1, duration: 0.4 }}
                className="flex items-center gap-4 px-4 py-3 rounded-xl transition-all group"
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-lg"
                  style={{ background: 'var(--refi-teal-glow)' }}>
                  {a.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold font-mono" style={{ color: 'var(--text-primary)' }}>
                      {a.name}
                    </h3>
                    <span className="w-1.5 h-1.5 rounded-full animate-pulse flex-shrink-0" style={{ background: 'var(--success)' }} />
                  </div>
                  <p className="text-[11px] leading-relaxed truncate" style={{ color: 'var(--text-secondary)' }}>
                    {a.desc}
                  </p>
                </div>
                <span className="text-[10px] font-mono flex-shrink-0 hidden sm:block" style={{ color: 'var(--text-tertiary)' }}>
                  autonomous
                </span>
              </motion.div>
            ))}
          </motion.div>

          {/* Bottom note */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={animate ? { opacity: 1 } : {}}
            transition={{ delay: 1.2, duration: 0.4 }}
            className="text-center text-[11px] font-mono mt-6"
            style={{ color: 'var(--text-tertiary)' }}
          >
            Runs on Oracle Cloud Always Free — ARM A1 Flex · 4 OCPU · 24GB RAM · BitNet CPU-native inference
          </motion.p>
        </div>
      </div>
    </div>
  )
}
