'use client'

import { useState, useEffect, useRef, lazy, Suspense } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { useInView } from '@/hooks/useInView'
import FeatureRow from '@/components/FeatureRow'
import AnimatedTerminal from '@/components/AnimatedTerminal'

const MatrixRain = dynamic(() => import('@/components/MatrixRain'), { ssr: false })
const DownloadModal = dynamic(() => import('@/components/DownloadModal'), { ssr: false })

const PILLAR_TERMINAL_LINES = [
  { text: 'Loading mesh configuration...', color: 'var(--text-secondary)', prefix: '[INFO]' },
  { text: 'Generating node identity: pillar-7a3f', color: 'var(--text-secondary)', prefix: '[INFO]' },
  { text: 'Encrypted vault initialized (AES-256-GCM)', color: 'var(--text-secondary)', prefix: '[INFO]' },
  { text: 'NAT traversal: UDP hole punching active', color: 'var(--text-secondary)', prefix: '[INFO]' },
  { text: 'Mesh node online — 12 peers discovered', color: 'var(--success)', prefix: '[OK]' },
  { text: 'Anonymized proxy listening on randomized port', color: 'var(--success)', prefix: '[OK]' },
  { text: 'Gopher server active on port 70', color: 'var(--success)', prefix: '[OK]' },
]

/* ─── Feature data ─── */
const FEATURES = [
  {
    num: '01', tag: 'MESH NETWORK', title: 'Encrypted Mesh Tunnels',
    desc: 'Node-to-node encrypted communication with rotating port assignments. Automatic NAT traversal, peer discovery, and key exchange — no central coordinator needed.',
    terminal: '$ mesh connect --peers=auto\n[OK] 12 peers discovered, AES-256 tunnels active',
  },
  {
    num: '02', tag: 'ANON PROXY', title: 'Anonymized Port Routing',
    desc: 'Randomized high-port assignments per session prevent fixed-target attacks. Port changes every connection. DDoS mitigation built into the protocol layer.',
    terminal: '$ proxy --randomize-ports\n[OK] Listening on port 49721 (rotating)',
  },
  {
    num: '03', tag: 'GOPHER ROOT', title: 'Gopher Protocol Access',
    desc: 'Alternative protocol access that\'s harder to fingerprint and monitor. Censorship-resistant browsing in restrictive network environments — a supplement to HTTP, not a replacement.',
    terminal: '$ gopher serve --port=70\n[OK] Gopher root serving /registry',
  },
  {
    num: '04', tag: 'VAULT', title: 'Encrypted Storage Vault',
    desc: 'HSM-compatible key management with automatic rotation and full audit trails. Distribute Shamir shares across cluster vaults for maximum resilience.',
    terminal: '$ vault init --cipher=aes-256-gcm\n[OK] Vault sealed, 3-of-5 threshold set',
  },
  {
    num: '05', tag: 'RPC RELAY', title: 'RPC Relay Network',
    desc: 'Relay RPC calls across the mesh for distributed inference routing. Cluster interconnect with automatic failover and latency-based load balancing.',
    terminal: '$ rpc relay --mode=distributed\n[OK] Relay active, 4 upstream nodes',
  },
]

const DOWNLOADS: Record<string, string> = {
  windows: '/public-downloads/pillar/product/refinet-pillar-setup.exe',
  macos: '/public-downloads/pillar/product/refinet-pillar.dmg',
  linux: '/public-downloads/pillar/product/refinet-pillar.AppImage',
  debian: '/public-downloads/pillar/product/refinet-pillar.deb',
}

const PLATFORMS = [
  { key: 'windows', label: 'Windows', size: '37 MB' },
  { key: 'macos', label: 'macOS', size: '29 MB' },
  { key: 'linux', label: 'Linux AppImage', size: '48 MB' },
  { key: 'debian', label: 'Debian / Ubuntu', size: '47 MB' },
]

/* ─── Main page ─── */
export default function PillarsProductPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const platformSection = useInView(0.15)
  const ctaSection = useInView(0.15)

  return (
    <div style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>

      {/* ═══════ HERO ═══════ */}
      <section className="relative min-h-screen flex flex-col justify-center overflow-hidden scanlines">
        <MatrixRain color="#4ADE80" opacity={0.04} density={20} speed={0.4} />
        <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(ellipse 60% 50% at 50% 40%, rgba(74,222,128,0.06) 0%, transparent 70%)' }} />

        <div className="relative z-10 max-w-6xl mx-auto px-6 md:px-12 py-32">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6 }} className="mb-10">
            <Link href="/products/" className="text-[11px] font-mono hover:underline" style={{ color: 'var(--text-tertiary)', textDecoration: 'none' }}>Products</Link>
            <span className="mx-2 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>/</span>
            <span className="text-[11px] font-mono" style={{ color: 'var(--refi-teal)' }}>Pillars</span>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.6 }} className="mb-8">
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-mono font-semibold tracking-wider uppercase"
              style={{ background: 'rgba(74,222,128,0.08)', color: '#4ADE80', border: '1px solid rgba(74,222,128,0.2)' }}>
              <span className="w-2 h-2 rounded-full" style={{ background: '#4ADE80' }} /> Available — v0.3.0
            </span>
          </motion.div>

          <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35, duration: 0.7 }}
            className="text-4xl sm:text-5xl md:text-7xl lg:text-8xl font-black tracking-tighter mb-6" style={{ letterSpacing: '-0.05em', lineHeight: 1.05 }}>
            REFINET{' '}<span className="text-glow" style={{ color: 'var(--refi-teal)' }}>Pillars</span>
          </motion.h1>

          <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5, duration: 0.6 }}
            className="text-base sm:text-lg md:text-xl max-w-2xl leading-relaxed mb-10" style={{ color: 'var(--text-secondary)' }}>
            The foundational layer for sovereign internet connectivity. Encrypted mesh networking, anonymized port routing,
            Gopher protocol access, and an encrypted vault — all permissionless, all open source, all free.
          </motion.p>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.65, duration: 0.5 }}>
            <button onClick={() => setModalOpen(true)}
              className="px-8 py-3.5 rounded-lg text-sm font-bold tracking-wide transition-all hover:scale-[1.02] active:scale-[0.98]"
              style={{ background: 'var(--refi-teal)', color: 'var(--bg-primary)', boxShadow: '0 0 30px rgba(92,224,210,0.25)' }}>
              Download Now
            </button>
          </motion.div>
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.5, duration: 1 }}
          className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2">
          <span className="text-[10px] font-mono tracking-widest uppercase" style={{ color: 'var(--text-tertiary)' }}>Scroll</span>
          <motion.svg animate={{ y: [0, 8, 0] }} transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }}
            width="16" height="24" viewBox="0 0 16 24" fill="none" stroke="var(--refi-teal)" strokeWidth="1.5">
            <rect x="1" y="1" width="14" height="22" rx="7" />
            <motion.circle cx="8" cy="8" r="2" fill="var(--refi-teal)" animate={{ cy: [8, 16, 8] }} transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }} />
          </motion.svg>
        </motion.div>
      </section>

      {/* ═══════ TERMINAL MOCKUP ═══════ */}
      <section className="relative py-20 md:py-32 px-6 md:px-12">
        <div className="max-w-4xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 40 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-100px' }} transition={{ duration: 0.8 }}
            className="rounded-2xl overflow-hidden" style={{ background: 'var(--terminal-bg)', border: '1px solid var(--border-default)', boxShadow: '0 20px 80px rgba(92,224,210,0.08)' }}>
            <div className="flex items-center gap-3 px-5 py-3" style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-subtle)' }}>
              <div className="flex gap-2">
                <span className="w-3 h-3 rounded-full" style={{ background: '#FF5F57' }} />
                <span className="w-3 h-3 rounded-full" style={{ background: '#FEBC2E' }} />
                <span className="w-3 h-3 rounded-full" style={{ background: '#28C840' }} />
              </div>
              <span className="text-[12px] font-mono ml-2" style={{ color: 'var(--text-secondary)' }}>refinet-pillars</span>
            </div>
            <AnimatedTerminal
              initialCommand="$ refinet-pillar start"
              lines={PILLAR_TERMINAL_LINES}
              doneText="Ready. Sovereign infrastructure running"
            />
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.3, duration: 0.6 }}
            className="flex flex-wrap justify-center gap-3 mt-8">
            {['Permissionless', 'End-to-End Encrypted', 'Zero Cost'].map((label) => (
              <span key={label} className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-[11px] font-mono font-semibold tracking-wider uppercase"
                style={{ background: 'var(--bg-secondary)', color: 'var(--refi-teal)', border: '1px solid var(--border-default)' }}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="3"><path d="M20 6L9 17l-5-5" /></svg>
                {label}
              </span>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══════ FEATURES ═══════ */}
      <section className="px-6 md:px-12">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-8 md:mb-0">
            <span className="text-[10px] font-mono tracking-[0.4em] uppercase" style={{ color: 'var(--refi-teal)' }}>Capabilities</span>
            <h2 className="text-2xl md:text-4xl font-bold mt-3 tracking-tight" style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}>Infrastructure, Reimagined.</h2>
          </div>
          <div style={{ borderTop: '1px solid var(--border-subtle)' }}>
            {FEATURES.map((feature, i) => (
              <div key={feature.num} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <FeatureRow feature={feature} index={i} terminalLabel="refinet-pillars" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════ PLATFORM DOWNLOADS ═══════ */}
      <section className="py-20 md:py-32 px-6 md:px-12" ref={platformSection.ref}>
        <div className="max-w-4xl mx-auto" style={{ opacity: platformSection.inView ? 1 : 0, transform: platformSection.inView ? 'translateY(0)' : 'translateY(40px)', transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)' }}>
          <div className="text-center mb-12">
            <span className="text-[10px] font-mono tracking-[0.4em] uppercase" style={{ color: 'var(--refi-teal)' }}>Downloads</span>
            <h2 className="text-2xl md:text-4xl font-bold mt-3 tracking-tight" style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}>Available on Every Platform</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {PLATFORMS.map((p) => (
              <button key={p.key} onClick={() => setModalOpen(true)}
                className="flex items-center justify-between p-5 rounded-xl transition-all hover:scale-[1.02]"
                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', textAlign: 'left' }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(92,224,210,0.3)' }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-default)' }}>
                <div>
                  <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{p.label}</div>
                  <div className="text-[11px] font-mono mt-1" style={{ color: 'var(--text-tertiary)' }}>{p.size}</div>
                </div>
                <div className="flex items-center gap-2 text-[12px] font-mono font-semibold" style={{ color: 'var(--refi-teal)' }}>
                  Download
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>
                </div>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════ CTA ═══════ */}
      <section className="py-24 md:py-40 px-6 md:px-12 relative overflow-hidden" ref={ctaSection.ref}>
        <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(ellipse 70% 50% at 50% 50%, rgba(92,224,210,0.06) 0%, transparent 70%)' }} />
        <div className="relative z-10 max-w-3xl mx-auto text-center" style={{ opacity: ctaSection.inView ? 1 : 0, transform: ctaSection.inView ? 'translateY(0)' : 'translateY(40px)', transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)' }}>
          <h2 className="text-2xl sm:text-3xl md:text-5xl font-black tracking-tighter mb-6" style={{ letterSpacing: '-0.04em', lineHeight: 1.1 }}>
            Run the Infrastructure{' '}<span style={{ color: 'var(--refi-teal)' }}>You Own</span>
          </h2>
          <p className="text-sm md:text-base max-w-lg mx-auto mb-10 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            Download Pillars and become part of the sovereign infrastructure network. Open source. Zero cost. Permissionless.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button onClick={() => setModalOpen(true)} className="px-8 py-3.5 rounded-lg text-sm font-bold transition-all hover:scale-[1.02]"
              style={{ background: 'var(--refi-teal)', color: 'var(--bg-primary)', boxShadow: '0 0 40px rgba(92,224,210,0.3)' }}>
              Download Pillars v0.3.0
            </button>
            <a href="https://github.com/circularityglobal/REFINET-PILLARS" target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-lg text-sm font-mono font-medium transition-all hover:scale-[1.02]"
              style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-default)', background: 'var(--bg-secondary)', textDecoration: 'none' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" /></svg>
              View Source
            </a>
          </div>
        </div>
      </section>

      <DownloadModal isOpen={modalOpen} onClose={() => setModalOpen(false)} product="pillars" displayName="REFINET Pillars" available={true} downloads={DOWNLOADS} />
    </div>
  )
}
