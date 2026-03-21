'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import Link from 'next/link'
import MatrixRain from '@/components/MatrixRain'

/* ───────────────────── Animated Counter Hook ───────────────────── */

function useCounter(target: number, duration = 2000, startOnView = true) {
  const [count, setCount] = useState(0)
  const [started, setStarted] = useState(!startOnView)
  const ref = useRef<HTMLSpanElement>(null)

  const start = useCallback(() => setStarted(true), [])

  useEffect(() => {
    if (!startOnView || !ref.current) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { start(); observer.disconnect() } },
      { threshold: 0.5 }
    )
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [start, startOnView])

  useEffect(() => {
    if (!started) return
    let raf: number
    const startTime = performance.now()
    const tick = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setCount(Math.round(eased * target))
      if (progress < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [started, target, duration])

  return { count, ref }
}

/* ───────────────────── Scroll-Triggered Section ───────────────────── */

function FadeInSection({ children, className = '', delay = 0 }: {
  children: React.ReactNode
  className?: string
  delay?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!ref.current) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); observer.disconnect() } },
      { threshold: 0.15 }
    )
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(40px)',
        transition: `opacity 0.8s cubic-bezier(0.16,1,0.3,1) ${delay}s, transform 0.8s cubic-bezier(0.16,1,0.3,1) ${delay}s`,
      }}
    >
      {children}
    </div>
  )
}

/* ───────────────────── Product Data ───────────────────── */

const PRODUCTS = [
  {
    name: 'browser',
    displayName: 'Browser',
    tagline: 'Sovereign Internet Access',
    description: 'A zero-telemetry browser that routes through the REFINET mesh, resolves decentralized domains, and keeps GROOT at your side.',
    status: 'Coming Soon',
    available: false,
    features: [
      'Zero-telemetry browsing with no data collection',
      'Decentralized DNS — ENS, Handshake, .crypto',
      'GROOT AI sidebar for on-page intelligence',
    ],
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    ),
  },
  {
    name: 'pillars',
    displayName: 'Pillars',
    tagline: 'Sovereign Infrastructure',
    description: 'The backbone of the sovereign internet. Encrypted mesh networking, anonymized routing, and Gopher protocol access for permissionless infrastructure.',
    status: 'Available v0.3.0',
    available: true,
    features: [
      'Encrypted mesh networking across nodes',
      'Anonymized port routing for privacy',
      'Gopher protocol access for legacy-free infra',
    ],
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    ),
  },
  {
    name: 'wizardos',
    displayName: 'WizardOS',
    tagline: 'Sovereign AI Desktop',
    description: 'A desktop operating system where GROOT runs locally. Multi-mode AI personalities, sovereign memory, and zero-cost inference — all on your hardware.',
    status: 'Coming Soon',
    available: false,
    features: [
      'GROOT-powered inference at $0/month',
      'Multi-mode AI personalities (analyst, creative, ops)',
      'Local sovereign memory — your data never leaves',
    ],
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2" />
        <line x1="8" y1="21" x2="16" y2="21" />
        <line x1="12" y1="17" x2="12" y2="21" />
      </svg>
    ),
  },
  {
    name: 'cluster',
    displayName: 'Cluster',
    tagline: 'Distributed Compute',
    description: 'Distributed compute on Oracle Cloud ARM instances. BitNet b1.58 runs CPU-native, five autonomous agents execute on cron — all within the Always Free tier.',
    status: 'Available',
    available: true,
    features: [
      'Oracle Cloud ARM (Always Free tier)',
      'BitNet b1.58 CPU-native inference',
      '5 autonomous agents running on cron',
    ],
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="2" width="20" height="8" rx="2" />
        <rect x="2" y="14" width="20" height="8" rx="2" />
        <line x1="6" y1="6" x2="6.01" y2="6" />
        <line x1="6" y1="18" x2="6.01" y2="18" />
      </svg>
    ),
  },
]

const STATS = [
  { label: 'API Endpoints', value: 330, suffix: '+' },
  { label: 'Autonomous Agents', value: 5, suffix: '' },
  { label: '$0/mo Forever', value: 0, suffix: '', display: '$0/mo' },
  { label: 'Open Source', value: 0, suffix: '', display: 'AGPL-3.0' },
]

/* ───────────────────── Ecosystem Diagram ───────────────────── */

function EcosystemDiagram() {
  const nodes = [
    { id: 'browser', label: 'Browser', x: 200, y: 60, href: '/products/browser/' },
    { id: 'pillars', label: 'Pillars', x: 400, y: 200, href: '/products/pillars/' },
    { id: 'wizardos', label: 'WizardOS', x: 200, y: 340, href: '/products/wizardos/' },
    { id: 'cluster', label: 'Cluster', x: 0, y: 200, href: '/products/cluster/' },
  ]
  const center = { x: 200, y: 200 }

  return (
    <div className="relative w-full max-w-[480px] mx-auto" style={{ aspectRatio: '480/420' }}>
      <svg
        viewBox="-40 0 480 420"
        fill="none"
        className="w-full h-full"
        style={{ overflow: 'visible' }}
      >
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Connection lines */}
        {nodes.map((node, i) => (
          <line
            key={node.id}
            x1={center.x}
            y1={center.y}
            x2={node.x}
            y2={node.y}
            stroke="#5CE0D2"
            strokeWidth="1"
            strokeOpacity="0.3"
            strokeDasharray="6 4"
            style={{
              animation: `dashFlow ${2 + i * 0.3}s linear infinite`,
            }}
          />
        ))}

        {/* Center GROOT node */}
        <circle cx={center.x} cy={center.y} r="36" fill="#0C0C0C" stroke="#5CE0D2" strokeWidth="1.5" filter="url(#glow)" />
        <text x={center.x} y={center.y + 1} textAnchor="middle" dominantBaseline="middle" fill="#5CE0D2" fontSize="13" fontFamily="JetBrains Mono, monospace" fontWeight="700">
          GROOT
        </text>

        {/* Outer nodes */}
        {nodes.map((node) => (
          <a key={node.id} href={node.href}>
            <rect
              x={node.x - 52}
              y={node.y - 24}
              width="104"
              height="48"
              rx="10"
              fill="#0C0C0C"
              stroke="#262626"
              strokeWidth="1"
              style={{ cursor: 'pointer' }}
            />
            <rect
              x={node.x - 52}
              y={node.y - 24}
              width="104"
              height="48"
              rx="10"
              fill="transparent"
              stroke="#5CE0D2"
              strokeWidth="0"
              className="diagram-node-hover"
              style={{ cursor: 'pointer', transition: 'stroke-width 0.3s' }}
            />
            <text
              x={node.x}
              y={node.y + 1}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="#F5F5F5"
              fontSize="12"
              fontFamily="JetBrains Mono, monospace"
              fontWeight="500"
              style={{ cursor: 'pointer' }}
            >
              {node.label}
            </text>
          </a>
        ))}
      </svg>

      {/* CSS for animated dashes */}
      <style jsx>{`
        @keyframes dashFlow {
          to { stroke-dashoffset: -20; }
        }
        .diagram-node-hover:hover {
          stroke-width: 1.5 !important;
        }
      `}</style>
    </div>
  )
}

/* ───────────────────── Stat Counter ───────────────────── */

function StatCounter({ label, value, suffix, display }: {
  label: string
  value: number
  suffix: string
  display?: string
}) {
  const { count, ref } = useCounter(value, 1800)

  if (display) {
    return (
      <div className="text-center">
        <span ref={ref} className="block text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: 'var(--refi-teal)', fontFamily: 'JetBrains Mono, monospace' }}>
          {display}
        </span>
        <span className="block text-xs mt-2 uppercase tracking-widest" style={{ color: 'var(--text-tertiary)' }}>
          {label}
        </span>
      </div>
    )
  }

  return (
    <div className="text-center">
      <span ref={ref} className="block text-3xl md:text-4xl font-extrabold tracking-tight" style={{ color: 'var(--refi-teal)', fontFamily: 'JetBrains Mono, monospace' }}>
        {count}{suffix}
      </span>
      <span className="block text-xs mt-2 uppercase tracking-widest" style={{ color: 'var(--text-tertiary)' }}>
        {label}
      </span>
    </div>
  )
}

/* ───────────────────── Product Card ───────────────────── */

function ProductCard({ product, index }: { product: typeof PRODUCTS[0]; index: number }) {
  const isReversed = index % 2 === 1

  return (
    <FadeInSection delay={0.1}>
      <Link
        href={`/products/${product.name}/`}
        className="block group"
        style={{ textDecoration: 'none' }}
      >
        <div
          className="relative rounded-2xl overflow-hidden transition-all duration-500"
          style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-default)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'rgba(92,224,210,0.35)'
            e.currentTarget.style.boxShadow = '0 0 60px rgba(92,224,210,0.08), 0 20px 60px rgba(0,0,0,0.4)'
            e.currentTarget.style.transform = 'scale(1.01)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border-default)'
            e.currentTarget.style.boxShadow = 'none'
            e.currentTarget.style.transform = 'scale(1)'
          }}
        >
          <div className={`flex flex-col ${isReversed ? 'md:flex-row-reverse' : 'md:flex-row'} items-stretch`}>
            {/* Icon / Visual Panel */}
            <div
              className="flex items-center justify-center p-10 md:p-16 md:w-2/5 relative"
              style={{
                background: 'linear-gradient(135deg, rgba(92,224,210,0.04) 0%, transparent 60%)',
                borderRight: isReversed ? 'none' : '1px solid var(--border-subtle)',
                borderLeft: isReversed ? '1px solid var(--border-subtle)' : 'none',
              }}
            >
              {/* Decorative grid dots */}
              <div className="absolute inset-0 opacity-[0.04]" style={{
                backgroundImage: 'radial-gradient(circle, #5CE0D2 1px, transparent 1px)',
                backgroundSize: '24px 24px',
              }} />
              <div
                className="relative transition-transform duration-500 group-hover:scale-110"
                style={{ color: 'var(--refi-teal)' }}
              >
                <div className="w-20 h-20 flex items-center justify-center rounded-2xl" style={{
                  background: 'rgba(92,224,210,0.08)',
                  border: '1px solid rgba(92,224,210,0.15)',
                }}>
                  {product.icon}
                </div>
              </div>
            </div>

            {/* Content Panel */}
            <div className="flex-1 p-8 md:p-12 flex flex-col justify-center">
              <div className="flex items-center gap-3 mb-4">
                <span
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-mono uppercase tracking-wider"
                  style={{
                    background: product.available ? 'rgba(74,222,128,0.08)' : 'var(--refi-teal-glow)',
                    color: product.available ? 'var(--success)' : 'var(--refi-teal)',
                    border: `1px solid ${product.available ? 'rgba(74,222,128,0.2)' : 'rgba(92,224,210,0.2)'}`,
                  }}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${product.available ? '' : 'animate-pulse'}`}
                    style={{ background: product.available ? 'var(--success)' : 'var(--refi-teal)' }}
                  />
                  {product.status}
                </span>
              </div>

              <h3 className="text-2xl md:text-3xl font-extrabold tracking-tight mb-1" style={{ color: 'var(--text-primary)' }}>
                {product.displayName}
              </h3>
              <p className="text-sm font-mono mb-4" style={{ color: 'var(--refi-teal)' }}>
                {product.tagline}
              </p>
              <p className="text-sm leading-relaxed mb-6" style={{ color: 'var(--text-secondary)', maxWidth: '480px' }}>
                {product.description}
              </p>

              {/* Feature list */}
              <ul className="space-y-2.5 mb-8">
                {product.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    <svg className="w-4 h-4 mt-0.5 flex-shrink-0" viewBox="0 0 16 16" fill="none">
                      <path d="M3 8l3.5 3.5L13 5" stroke="#5CE0D2" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    {feature}
                  </li>
                ))}
              </ul>

              <div className="flex items-center gap-1.5 text-sm font-mono group-hover:gap-3 transition-all duration-300" style={{ color: 'var(--refi-teal)' }}>
                Explore {product.displayName}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </Link>
    </FadeInSection>
  )
}

/* ───────────────────── Main Page ───────────────────── */

export default function ProductsPage() {
  const { scrollYProgress } = useScroll()
  const heroOpacity = useTransform(scrollYProgress, [0, 0.15], [1, 0])

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>

      {/* ════════════════ HERO SECTION ════════════════ */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden scanlines">
        {/* Matrix rain background */}
        <div className="absolute inset-0 z-0">
          <MatrixRain color="#5CE0D2" opacity={0.04} density={22} speed={0.6} />
        </div>

        {/* Radial teal glow */}
        <div
          className="absolute inset-0 z-[1] pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse 60% 50% at 50% 40%, var(--refi-teal-glow) 0%, transparent 70%)',
          }}
        />

        {/* CRT vignette */}
        <div className="absolute inset-0 z-[2] pointer-events-none crt-vignette" />

        {/* Hero content */}
        <motion.div
          style={{ opacity: heroOpacity }}
          className="relative z-10 text-center px-6 max-w-4xl mx-auto"
        >
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-[11px] font-mono uppercase tracking-[0.3em] mb-6"
            style={{ color: 'var(--text-tertiary)', fontFamily: 'JetBrains Mono, monospace' }}
          >
            REFINET Cloud Products
          </motion.p>

          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.4 }}
            className="text-5xl md:text-7xl lg:text-8xl font-extrabold tracking-tighter leading-[0.95]"
            style={{ color: 'var(--text-primary)', letterSpacing: '-0.05em' }}
          >
            The <span className="text-glow" style={{ color: 'var(--refi-teal)' }}>Sovereign</span> Stack
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.7 }}
            className="text-base md:text-lg mt-6 max-w-xl mx-auto leading-relaxed"
            style={{ color: 'var(--text-secondary)' }}
          >
            Four products. One mission. Take back your digital sovereignty.
          </motion.p>

          {/* Animated stat counters */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 1.0 }}
            className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12"
          >
            {STATS.map((stat) => (
              <StatCounter key={stat.label} {...stat} />
            ))}
          </motion.div>

          {/* Scroll indicator */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.6, duration: 0.8 }}
            className="mt-20 animate-float"
          >
            <svg width="20" height="32" viewBox="0 0 20 32" fill="none" className="mx-auto">
              <rect x="1" y="1" width="18" height="30" rx="9" stroke="#5CE0D2" strokeOpacity="0.3" strokeWidth="1" />
              <motion.circle
                cx="10"
                cy="10"
                r="3"
                fill="#5CE0D2"
                fillOpacity="0.6"
                animate={{ cy: [10, 22, 10] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              />
            </svg>
          </motion.div>
        </motion.div>
      </section>

      {/* ════════════════ ECOSYSTEM DIAGRAM ════════════════ */}
      <section className="relative py-32 px-6" style={{ background: 'var(--bg-primary)' }}>
        <div className="max-w-5xl mx-auto">
          <FadeInSection>
            <div className="text-center mb-16">
              <p
                className="text-[11px] font-mono uppercase tracking-[0.3em] mb-4"
                style={{ color: 'var(--refi-teal)', fontFamily: 'JetBrains Mono, monospace' }}
              >
                {'>'} ecosystem
              </p>
              <h2
                className="text-3xl md:text-5xl font-extrabold tracking-tighter mb-6"
                style={{ color: 'var(--text-primary)', letterSpacing: '-0.04em' }}
              >
                One Wizard. Four Products.
              </h2>
              <p className="text-base max-w-2xl mx-auto leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                Every product in the REFINET ecosystem connects through GROOT — sovereign AI infrastructure that runs at zero cost.
              </p>
            </div>
          </FadeInSection>

          <FadeInSection delay={0.2}>
            <EcosystemDiagram />
          </FadeInSection>
        </div>
      </section>

      {/* ════════════════ PRODUCT SHOWCASE ════════════════ */}
      <section className="relative py-32 px-6">
        {/* Subtle top divider */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[200px] h-px" style={{ background: 'linear-gradient(90deg, transparent, rgba(92,224,210,0.2), transparent)' }} />

        <div className="max-w-5xl mx-auto">
          <FadeInSection>
            <div className="text-center mb-20">
              <p
                className="text-[11px] font-mono uppercase tracking-[0.3em] mb-4"
                style={{ color: 'var(--refi-teal)', fontFamily: 'JetBrains Mono, monospace' }}
              >
                {'>'} products
              </p>
              <h2
                className="text-3xl md:text-5xl font-extrabold tracking-tighter"
                style={{ color: 'var(--text-primary)', letterSpacing: '-0.04em' }}
              >
                Built for Sovereignty
              </h2>
            </div>
          </FadeInSection>

          <div className="space-y-8">
            {PRODUCTS.map((product, i) => (
              <ProductCard key={product.name} product={product} index={i} />
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════ BOTTOM CTA ════════════════ */}
      <section className="relative py-32 px-6">
        {/* Top divider */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[200px] h-px" style={{ background: 'linear-gradient(90deg, transparent, rgba(92,224,210,0.2), transparent)' }} />

        <FadeInSection>
          <div className="max-w-3xl mx-auto text-center">
            <h2
              className="text-3xl md:text-5xl font-extrabold tracking-tighter mb-6"
              style={{ color: 'var(--text-primary)', letterSpacing: '-0.04em' }}
            >
              Ready to build the<br />
              <span style={{ color: 'var(--refi-teal)' }}>sovereign internet</span>?
            </h2>
            <p className="text-base mb-10 max-w-lg mx-auto" style={{ color: 'var(--text-secondary)' }}>
              Open source. Zero cost. No venture capital. No telemetry. Just infrastructure that belongs to you.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/login/"
                className="btn-primary inline-flex items-center gap-2 px-8 py-3.5 rounded-lg text-sm font-semibold transition-all duration-300"
                style={{
                  background: 'var(--refi-teal)',
                  color: '#050505',
                  textDecoration: 'none',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow = '0 0 30px rgba(92,224,210,0.3)'
                  e.currentTarget.style.transform = 'translateY(-1px)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = 'none'
                  e.currentTarget.style.transform = 'translateY(0)'
                }}
              >
                Get Started
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </Link>
              <button
                onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                className="btn-secondary inline-flex items-center gap-2 px-8 py-3.5 rounded-lg text-sm font-semibold transition-all duration-300"
                style={{
                  background: 'transparent',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-default)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(92,224,210,0.3)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-default)'
                }}
              >
                View All Products
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              </button>
            </div>
          </div>
        </FadeInSection>
      </section>
    </div>
  )
}
