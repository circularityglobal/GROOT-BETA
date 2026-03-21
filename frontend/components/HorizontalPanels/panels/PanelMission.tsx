'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'
import MatrixRain from '@/components/MatrixRain'

interface PanelMissionProps {
  isActive: boolean
}

const PILLARS = [
  {
    title: 'Sovereign by Design',
    desc: 'Your data never leaves your control. No corporate cloud. No surveillance. Self-hosted infrastructure that you own, operate, and govern.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
    ),
  },
  {
    title: 'Zero Extraction',
    desc: 'No subscription fees. No data harvesting. No vendor lock-in. Every component runs on open-source software at zero recurring cost — forever.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/>
      </svg>
    ),
  },
  {
    title: 'Regenerative Finance',
    desc: 'Built for the people rebuilding the economy. ReFi tools, tokenomics, DAO governance, and multi-chain identity — all from one sovereign platform.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
      </svg>
    ),
  },
  {
    title: 'Community Governed',
    desc: 'Not a product — a commons. Open source, forkable, extensible. The people who build it, govern it. No board of directors. No shareholders.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </svg>
    ),
  },
  {
    title: 'Cryptographic Identity',
    desc: 'Your wallet is your passport. Sign in with Ethereum across 9 ecosystems. ENS resolution. Wallet-to-wallet messaging. No passwords, no middlemen.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
      </svg>
    ),
  },
  {
    title: 'Intelligence for All',
    desc: 'Free AI inference for everyone. BitNet runs on CPU — no GPU required. OpenAI-compatible API. Knowledge bases. Autonomous agents. All sovereign.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 12 18.469a3.374 3.374 0 0 0-1.988-.82l-.548-.547z"/>
      </svg>
    ),
  },
]

export default function PanelMission({ isActive }: PanelMissionProps) {
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
    <div className="w-screen h-full flex-shrink-0 relative overflow-hidden scanlines"
      style={{ background: 'var(--bg-primary)' }}>

      {/* Subtle teal rain */}
      <div className="absolute inset-0 opacity-[0.03]">
        {isActive && <MatrixRain color="#5CE0D2" opacity={0.08} density={12} speed={0.4} />}
      </div>

      {/* Radial glow from center */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: 'radial-gradient(ellipse 50% 50% at 50% 35%, rgba(92,224,210,0.08) 0%, transparent 70%)',
      }} />

      <div className="relative z-10 flex flex-col items-center justify-center h-full px-6 py-10">
        <div className="max-w-5xl w-full">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={animate ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5 }}
            className="text-center mb-10"
          >
            <p className="text-[12px] font-mono uppercase tracking-widest mb-3" style={{ color: 'var(--refi-teal)' }}>
              {'>'} the_mission
            </p>
            <h2 className="text-3xl md:text-5xl font-extrabold tracking-tighter mb-4 text-glow" style={{ letterSpacing: '-0.04em' }}>
              Built by the people.<br />
              <span style={{ color: 'var(--refi-teal)' }}>For the planet.</span>
            </h2>
            <p className="text-base md:text-lg max-w-2xl mx-auto" style={{ color: 'var(--text-secondary)' }}>
              REFINET Cloud is not a startup. It is sovereign infrastructure for a regenerative internet — built by the people who believe technology should serve life, not extract from it.
            </p>
          </motion.div>

          {/* Pillars grid */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={animate ? { opacity: 1 } : {}}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4"
          >
            {PILLARS.map((p, i) => (
              <motion.div
                key={p.title}
                initial={{ opacity: 0, y: 20 }}
                animate={animate ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: 0.3 + i * 0.08, duration: 0.4 }}
                className="card p-5 group hover:border-refi-teal/30 transition-all"
              >
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4 transition-colors"
                  style={{ background: 'var(--refi-teal-glow)', color: 'var(--refi-teal)' }}>
                  {p.icon}
                </div>
                <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                  {p.title}
                </h3>
                <p className="text-[12px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {p.desc}
                </p>
              </motion.div>
            ))}
          </motion.div>

          {/* Bottom manifesto line */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={animate ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 1, duration: 0.5 }}
            className="text-center mt-8"
          >
            <p className="text-[13px] font-mono leading-relaxed max-w-lg mx-auto" style={{ color: 'var(--refi-teal-dim)' }}>
              "The best technology disappears into the world it serves.
              We build so that others can regenerate."
            </p>
            <div className="flex items-center justify-center gap-3 mt-6">
              <Link href="/login/" className="btn-primary !py-2.5 !px-6 font-mono text-sm" prefetch={true}>
                {'>'} Join the Movement
              </Link>
              <Link href="/docs/" className="btn-secondary !py-2.5 !px-6 font-mono text-sm" prefetch={true}>
                {'>'} Read the Docs
              </Link>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
