'use client'

import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'
import MatrixRain from '@/components/MatrixRain'
import DownloadModal from '@/components/DownloadModal'

/* ─── useInView hook ─── */
function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setInView(true) },
      { threshold },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])

  return { ref, inView }
}

/* ─── Animated terminal typing ─── */
function AnimatedTerminal() {
  const lines = [
    { text: 'Connected to GROOT Intelligence Network', color: 'var(--refi-teal)' },
    { text: 'Peer-to-peer encryption active', color: 'var(--text-secondary)' },
    { text: 'Decentralized DNS resolved', color: 'var(--text-secondary)' },
    { text: 'IPFS gateway: local node', color: 'var(--text-secondary)' },
    { text: 'Wallet identity: 0x7a3...9f2c', color: 'var(--text-secondary)' },
  ]

  const [visibleCount, setVisibleCount] = useState(0)

  useEffect(() => {
    if (visibleCount >= lines.length) return
    const t = setTimeout(() => setVisibleCount((c) => c + 1), 700 + visibleCount * 200)
    return () => clearTimeout(t)
  }, [visibleCount, lines.length])

  return (
    <div className="font-mono text-[12px] md:text-[13px] space-y-2.5 p-6 md:p-8 min-h-[240px]">
      {lines.slice(0, visibleCount).map((line, i) => (
        <motion.p
          key={i}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3 }}
          style={{ color: line.color }}
        >
          <span style={{ color: 'var(--refi-teal)', opacity: 0.6 }}>{'>'}</span> {line.text}
        </motion.p>
      ))}
      {visibleCount >= lines.length && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-4 pt-4"
          style={{ borderTop: '1px solid var(--border-subtle)' }}
        >
          <p style={{ color: 'var(--text-tertiary)' }}>
            <span style={{ color: 'var(--refi-teal)', opacity: 0.6 }}>{'>'}</span>{' '}
            Browsing sovereign web with zero telemetry_
            <span className="animate-pulse" style={{ color: 'var(--refi-teal)' }}>|</span>
          </p>
        </motion.div>
      )}
    </div>
  )
}

/* ─── Feature data ─── */
const FEATURES = [
  {
    num: '01',
    tag: 'SOVEREIGN DNS',
    title: 'Decentralized Name Resolution',
    desc: 'Navigate the sovereign web with ENS, Handshake, and REFINET\'s own decentralized naming system. No ICANN dependency. No DNS hijacking. Your addresses, your rules.',
    terminal: 'resolve sovereign.eth \u2192 0x7a3...9f2c [OK]',
  },
  {
    num: '02',
    tag: 'ENCRYPTED TRANSIT',
    title: 'End-to-End Encrypted Browsing',
    desc: 'Every connection encrypted by default with peer-to-peer TLS. No certificate authorities controlling your trust chain. Wallet-based identity verification replaces the broken CA model.',
    terminal: 'tunnel established: AES-256-GCM [OK]',
  },
  {
    num: '03',
    tag: 'IPFS NATIVE',
    title: 'Built-in Decentralized Storage',
    desc: 'Pin and retrieve content from IPFS, Arweave, and Filecoin natively. No third-party gateways. Your browser is your node. Content-addressed permanence, built in.',
    terminal: 'ipfs://QmX7... \u2192 cached locally [OK]',
  },
  {
    num: '04',
    tag: 'WALLET IDENTITY',
    title: 'One-Click Authentication Everywhere',
    desc: 'Your Ethereum wallet is your universal identity. Sign in with a single click using SIWE. No passwords to remember. No tracking cookies to delete. Just cryptographic proof.',
    terminal: 'SIWE verified: 0x7a3...9f2c [OK]',
  },
  {
    num: '05',
    tag: 'GROOT SIDEBAR',
    title: 'AI Intelligence at Your Fingertips',
    desc: 'GROOT AI is built into the browser sidebar. Highlight any contract address for instant security analysis. Import repos directly from GitHub. Get risk assessments in seconds.',
    terminal: 'analyzing 0xUniswap... 4 risks found',
  },
]

/* ─── Comparison data ─── */
const COMPARE_ROWS = [
  { label: 'Telemetry', chrome: false, brave: 'partial', refinet: true },
  { label: 'Decentralized DNS', chrome: false, brave: false, refinet: true },
  { label: 'Wallet Identity', chrome: false, brave: 'partial', refinet: true },
  { label: 'Decentralized Storage', chrome: false, brave: 'partial', refinet: true },
  { label: 'AI Assistant', chrome: false, brave: false, refinet: true },
]

/* ─── Steps data ─── */
const STEPS = [
  {
    num: '01',
    title: 'Install',
    desc: 'Download REFINET Browser for your platform. One binary, zero dependencies.',
    terminal: '$ curl -sSL refinet.io/install | sh\n[OK] Browser installed',
  },
  {
    num: '02',
    title: 'Connect Wallet',
    desc: 'Link your Ethereum wallet for sovereign identity. No account creation needed.',
    terminal: '> wallet connected: 0x7a3...9f2c\n[OK] Identity verified',
  },
  {
    num: '03',
    title: 'Browse Sovereign Web',
    desc: 'Access the decentralized web with zero telemetry and full encryption.',
    terminal: '> navigating sovereign.eth\n[OK] Zero telemetry active',
  },
]

/* ─── Feature row component ─── */
function FeatureRow({ feature, index }: { feature: typeof FEATURES[0]; index: number }) {
  const { ref, inView } = useInView(0.2)
  const isEven = index % 2 === 1

  return (
    <div ref={ref} className={`flex flex-col ${isEven ? 'md:flex-row-reverse' : 'md:flex-row'} gap-8 md:gap-16 items-center py-16 md:py-24`}>
      {/* Text side */}
      <div
        className="flex-1"
        style={{
          opacity: inView ? 1 : 0,
          transform: inView ? 'translateY(0)' : 'translateY(40px)',
          transition: 'all 0.7s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <div className="flex items-baseline gap-4 mb-4">
          <span
            className="text-5xl md:text-7xl font-mono font-black"
            style={{ color: 'var(--refi-teal)', opacity: 0.3 }}
          >
            {feature.num}
          </span>
          <span
            className="text-[10px] font-mono tracking-[0.3em] uppercase"
            style={{ color: 'var(--refi-teal)' }}
          >
            {feature.tag}
          </span>
        </div>
        <h3
          className="text-xl md:text-2xl font-bold mb-4"
          style={{ color: 'var(--text-primary)', letterSpacing: '-0.02em' }}
        >
          {feature.title}
        </h3>
        <p
          className="text-sm md:text-base leading-relaxed max-w-lg"
          style={{ color: 'var(--text-secondary)' }}
        >
          {feature.desc}
        </p>
      </div>

      {/* Terminal visual side */}
      <div
        className="flex-1 w-full max-w-md"
        style={{
          opacity: inView ? 1 : 0,
          transform: inView ? 'translateY(0)' : 'translateY(40px)',
          transition: 'all 0.7s cubic-bezier(0.16, 1, 0.3, 1) 0.15s',
        }}
      >
        <div
          className="rounded-xl overflow-hidden"
          style={{
            background: 'var(--terminal-bg)',
            border: '1px solid var(--border-default)',
            boxShadow: '0 8px 32px rgba(92,224,210,0.06)',
          }}
        >
          <div
            className="flex items-center gap-1.5 px-4 py-2"
            style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-subtle)' }}
          >
            <span className="w-2 h-2 rounded-full" style={{ background: '#FF5F57' }} />
            <span className="w-2 h-2 rounded-full" style={{ background: '#FEBC2E' }} />
            <span className="w-2 h-2 rounded-full" style={{ background: '#28C840' }} />
            <span className="ml-3 text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
              terminal
            </span>
          </div>
          <div className="p-5 font-mono text-[12px] md:text-[13px]">
            <p style={{ color: 'var(--text-tertiary)' }}>
              <span style={{ color: 'var(--refi-teal)' }}>$</span> {feature.terminal.split('[')[0]}
              <span style={{ color: 'var(--success)' }}>[{feature.terminal.split('[')[1]}</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─── Main page ─── */
export default function BrowserProductPage() {
  const [modalOpen, setModalOpen] = useState(false)

  const comparisonSection = useInView(0.15)
  const howSection = useInView(0.15)
  const ctaSection = useInView(0.15)

  return (
    <div style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>

      {/* ═══════════════════ SECTION 1: HERO ═══════════════════ */}
      <section className="relative min-h-screen flex flex-col justify-center overflow-hidden scanlines">
        {/* Matrix rain background */}
        <MatrixRain color="#5CE0D2" opacity={0.05} density={18} speed={0.5} />

        {/* Radial glow */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse 60% 50% at 50% 40%, rgba(92,224,210,0.08) 0%, transparent 70%)',
          }}
        />

        <div className="relative z-10 max-w-6xl mx-auto px-6 md:px-12 py-32">
          {/* Breadcrumb */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6 }}
            className="mb-10"
          >
            <Link
              href="/products/"
              className="text-[11px] font-mono hover:underline"
              style={{ color: 'var(--text-tertiary)', textDecoration: 'none' }}
            >
              Products
            </Link>
            <span className="mx-2 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>/</span>
            <span className="text-[11px] font-mono" style={{ color: 'var(--refi-teal)' }}>Browser</span>
          </motion.div>

          {/* Coming Soon badge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
            className="mb-8"
          >
            <span
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-mono font-semibold tracking-wider uppercase"
              style={{
                background: 'var(--refi-teal-glow)',
                color: 'var(--refi-teal)',
                border: '1px solid rgba(92,224,210,0.2)',
              }}
            >
              <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--refi-teal)' }} />
              Coming Soon
            </span>
          </motion.div>

          {/* Hero title */}
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35, duration: 0.7 }}
            className="text-4xl sm:text-5xl md:text-7xl lg:text-8xl font-black tracking-tighter mb-6"
            style={{ letterSpacing: '-0.05em', lineHeight: 1.05 }}
          >
            REFINET{' '}
            <span className="text-glow" style={{ color: 'var(--refi-teal)' }}>Browser</span>
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6 }}
            className="text-base sm:text-lg md:text-xl max-w-2xl leading-relaxed mb-10"
            style={{ color: 'var(--text-secondary)' }}
          >
            The first browser built for the sovereign web. Encrypted transit, decentralized DNS,
            wallet-native identity, and GROOT AI intelligence — all without a single byte of telemetry
            leaving your machine.
          </motion.p>

          {/* CTA button */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.65, duration: 0.5 }}
          >
            <button
              onClick={() => setModalOpen(true)}
              className="btn-primary px-8 py-3.5 rounded-lg text-sm font-bold tracking-wide transition-all hover:scale-[1.02] active:scale-[0.98]"
              style={{
                background: 'var(--refi-teal)',
                color: 'var(--bg-primary)',
                boxShadow: '0 0 30px rgba(92,224,210,0.25)',
              }}
            >
              Join the Waitlist
            </button>
          </motion.div>
        </div>

        {/* Scroll indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5, duration: 1 }}
          className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
        >
          <span className="text-[10px] font-mono tracking-widest uppercase" style={{ color: 'var(--text-tertiary)' }}>
            Scroll
          </span>
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }}
          >
            <svg width="16" height="24" viewBox="0 0 16 24" fill="none" stroke="var(--refi-teal)" strokeWidth="1.5">
              <rect x="1" y="1" width="14" height="22" rx="7" />
              <motion.circle
                cx="8"
                cy="8"
                r="2"
                fill="var(--refi-teal)"
                animate={{ cy: [8, 16, 8] }}
                transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }}
              />
            </svg>
          </motion.div>
        </motion.div>
      </section>

      {/* ═══════════════════ SECTION 2: BROWSER MOCKUP ═══════════════════ */}
      <section className="relative py-20 md:py-32 px-6 md:px-12">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.8 }}
            className="rounded-2xl overflow-hidden"
            style={{
              background: 'var(--terminal-bg)',
              border: '1px solid var(--border-default)',
              boxShadow: '0 20px 80px rgba(92,224,210,0.08), 0 0 0 1px rgba(92,224,210,0.05)',
            }}
          >
            {/* Title bar */}
            <div
              className="flex items-center gap-3 px-5 py-3"
              style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-subtle)' }}
            >
              <div className="flex gap-2">
                <span className="w-3 h-3 rounded-full" style={{ background: '#FF5F57' }} />
                <span className="w-3 h-3 rounded-full" style={{ background: '#FEBC2E' }} />
                <span className="w-3 h-3 rounded-full" style={{ background: '#28C840' }} />
              </div>
              <div
                className="flex-1 ml-2 px-4 py-1.5 rounded-lg text-[12px] font-mono flex items-center gap-2"
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)' }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <span style={{ color: 'var(--refi-teal)' }}>refinet://</span>
                <span style={{ color: 'var(--text-secondary)' }}>sovereign.net</span>
              </div>
            </div>

            {/* Terminal content */}
            <AnimatedTerminal />
          </motion.div>

          {/* Stat pills */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="flex flex-wrap justify-center gap-3 mt-8"
          >
            {['Zero Telemetry', 'No Cookies', 'No Tracking'].map((label) => (
              <span
                key={label}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-[11px] font-mono font-semibold tracking-wider uppercase"
                style={{
                  background: 'var(--bg-secondary)',
                  color: 'var(--refi-teal)',
                  border: '1px solid var(--border-default)',
                }}
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="3">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                {label}
              </span>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══════════════════ SECTION 3: FEATURES ═══════════════════ */}
      <section className="px-6 md:px-12">
        <div className="max-w-6xl mx-auto">
          {/* Section header */}
          <div className="text-center mb-8 md:mb-0">
            <span
              className="text-[10px] font-mono tracking-[0.4em] uppercase"
              style={{ color: 'var(--refi-teal)' }}
            >
              Capabilities
            </span>
            <h2
              className="text-2xl md:text-4xl font-bold mt-3 tracking-tight"
              style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}
            >
              Built Different. By Design.
            </h2>
          </div>

          {/* Feature rows with dividers */}
          <div style={{ borderTop: '1px solid var(--border-subtle)' }}>
            {FEATURES.map((feature, i) => (
              <div key={feature.num} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <FeatureRow feature={feature} index={i} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════ SECTION 4: COMPARISON ═══════════════════ */}
      <section className="py-20 md:py-32 px-6 md:px-12" ref={comparisonSection.ref}>
        <div
          className="max-w-4xl mx-auto"
          style={{
            opacity: comparisonSection.inView ? 1 : 0,
            transform: comparisonSection.inView ? 'translateY(0)' : 'translateY(40px)',
            transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          <div className="text-center mb-12">
            <span
              className="text-[10px] font-mono tracking-[0.4em] uppercase"
              style={{ color: 'var(--refi-teal)' }}
            >
              Comparison
            </span>
            <h2
              className="text-2xl md:text-4xl font-bold mt-3 tracking-tight"
              style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}
            >
              Why REFINET Browser?
            </h2>
          </div>

          {/* Comparison table */}
          <div
            className="rounded-xl overflow-hidden font-mono"
            style={{
              background: 'var(--terminal-bg)',
              border: '1px solid var(--border-default)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            }}
          >
            {/* Header row */}
            <div
              className="grid grid-cols-4 text-[10px] sm:text-[11px] tracking-[0.15em] uppercase font-semibold px-4 sm:px-6 py-4"
              style={{ borderBottom: '1px solid var(--border-default)', color: 'var(--text-tertiary)' }}
            >
              <div>Feature</div>
              <div className="text-center">Chrome</div>
              <div className="text-center">Brave</div>
              <div className="text-center" style={{ color: 'var(--refi-teal)' }}>REFINET</div>
            </div>

            {/* Data rows */}
            {COMPARE_ROWS.map((row, i) => (
              <div
                key={row.label}
                className="grid grid-cols-4 text-xs sm:text-sm px-4 sm:px-6 py-3.5 items-center"
                style={{
                  borderBottom: i < COMPARE_ROWS.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                  background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                }}
              >
                <div style={{ color: 'var(--text-secondary)' }}>{row.label}</div>
                <div className="text-center text-base" style={{ color: '#FF5F57' }}>
                  {'\u2717'}
                </div>
                <div className="text-center text-base" style={{ color: row.brave === 'partial' ? '#FEBC2E' : '#FF5F57' }}>
                  {row.brave === 'partial' ? '\u2713' : '\u2717'}
                </div>
                <div className="text-center text-base" style={{ color: 'var(--refi-teal)' }}>
                  {'\u2713'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════ SECTION 5: HOW IT WORKS ═══════════════════ */}
      <section className="py-20 md:py-32 px-6 md:px-12" ref={howSection.ref}>
        <div
          className="max-w-5xl mx-auto"
          style={{
            opacity: howSection.inView ? 1 : 0,
            transform: howSection.inView ? 'translateY(0)' : 'translateY(40px)',
            transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          <div className="text-center mb-16">
            <span
              className="text-[10px] font-mono tracking-[0.4em] uppercase"
              style={{ color: 'var(--refi-teal)' }}
            >
              Getting Started
            </span>
            <h2
              className="text-2xl md:text-4xl font-bold mt-3 tracking-tight"
              style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}
            >
              How It Works
            </h2>
          </div>

          {/* Timeline */}
          <div className="relative">
            {/* SVG connector line */}
            <svg
              className="absolute left-1/2 -translate-x-1/2 top-0 h-full hidden md:block"
              width="2"
              style={{ overflow: 'visible' }}
            >
              <line
                x1="0"
                y1="0"
                x2="0"
                y2="100%"
                stroke="var(--refi-teal)"
                strokeWidth="1"
                strokeDasharray="6 6"
                style={{
                  animation: howSection.inView ? 'dash 2s linear forwards' : 'none',
                }}
              />
              <style>{`
                @keyframes dash {
                  from { stroke-dashoffset: 100; }
                  to { stroke-dashoffset: 0; }
                }
              `}</style>
            </svg>

            <div className="space-y-16 md:space-y-24">
              {STEPS.map((step, i) => (
                <div
                  key={step.num}
                  className={`flex flex-col md:flex-row items-center gap-8 md:gap-16 ${
                    i % 2 === 1 ? 'md:flex-row-reverse' : ''
                  }`}
                >
                  {/* Text */}
                  <div className="flex-1 text-center md:text-left">
                    <div
                      className="text-5xl md:text-6xl font-mono font-black mb-4"
                      style={{ color: 'var(--refi-teal)', opacity: 0.25 }}
                    >
                      {step.num}
                    </div>
                    <h3
                      className="text-xl md:text-2xl font-bold mb-3"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {step.title}
                    </h3>
                    <p
                      className="text-sm md:text-base leading-relaxed max-w-sm mx-auto md:mx-0"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      {step.desc}
                    </p>
                  </div>

                  {/* Dot on the timeline */}
                  <div className="hidden md:flex items-center justify-center relative">
                    <div
                      className="w-4 h-4 rounded-full z-10"
                      style={{
                        background: 'var(--refi-teal)',
                        boxShadow: '0 0 20px rgba(92,224,210,0.4)',
                      }}
                    />
                  </div>

                  {/* Terminal snippet */}
                  <div className="flex-1 w-full max-w-sm">
                    <div
                      className="rounded-xl overflow-hidden"
                      style={{
                        background: 'var(--terminal-bg)',
                        border: '1px solid var(--border-default)',
                      }}
                    >
                      <div
                        className="flex items-center gap-1.5 px-3 py-2"
                        style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-subtle)' }}
                      >
                        <span className="w-2 h-2 rounded-full" style={{ background: '#FF5F57' }} />
                        <span className="w-2 h-2 rounded-full" style={{ background: '#FEBC2E' }} />
                        <span className="w-2 h-2 rounded-full" style={{ background: '#28C840' }} />
                      </div>
                      <div className="p-4 font-mono text-[11px] md:text-[12px] whitespace-pre-line" style={{ color: 'var(--text-secondary)' }}>
                        {step.terminal.split('\n').map((line, li) => (
                          <p key={li} style={{ color: line.includes('[OK]') ? 'var(--success)' : 'var(--text-secondary)' }}>
                            {line}
                          </p>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════ SECTION 6: CTA ═══════════════════ */}
      <section className="py-24 md:py-40 px-6 md:px-12 relative overflow-hidden" ref={ctaSection.ref}>
        {/* Background glow */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse 70% 50% at 50% 50%, rgba(92,224,210,0.06) 0%, transparent 70%)',
          }}
        />

        <div
          className="relative z-10 max-w-3xl mx-auto text-center"
          style={{
            opacity: ctaSection.inView ? 1 : 0,
            transform: ctaSection.inView ? 'translateY(0)' : 'translateY(40px)',
            transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          <h2
            className="text-2xl sm:text-3xl md:text-5xl font-black tracking-tighter mb-6"
            style={{ color: 'var(--text-primary)', letterSpacing: '-0.04em', lineHeight: 1.1 }}
          >
            Be First to Experience{' '}
            <span style={{ color: 'var(--refi-teal)' }}>Sovereign Browsing</span>
          </h2>
          <p
            className="text-sm md:text-base max-w-lg mx-auto mb-10 leading-relaxed"
            style={{ color: 'var(--text-secondary)' }}
          >
            Join the waitlist for early access. No telemetry. No tracking. No compromise.
            The sovereign web is coming.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={() => setModalOpen(true)}
              className="px-8 py-3.5 rounded-lg text-sm font-bold tracking-wide transition-all hover:scale-[1.02] active:scale-[0.98]"
              style={{
                background: 'var(--refi-teal)',
                color: 'var(--bg-primary)',
                boxShadow: '0 0 40px rgba(92,224,210,0.3)',
              }}
            >
              Join the Waitlist
            </button>

            <a
              href="https://github.com/circularityglobal/REFINET-BROWSER"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-lg text-sm font-mono font-medium transition-all hover:scale-[1.02]"
              style={{
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-default)',
                background: 'var(--bg-secondary)',
                textDecoration: 'none',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
              </svg>
              View Source
            </a>
          </div>
        </div>
      </section>

      {/* ═══════════════════ DOWNLOAD MODAL ═══════════════════ */}
      <DownloadModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        product="browser"
        displayName="REFINET Browser"
        available={false}
        downloads={{}}
      />
    </div>
  )
}
