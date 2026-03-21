'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { useInView } from '@/hooks/useInView'
import FeatureRow from '@/components/FeatureRow'
import AnimatedTerminal from '@/components/AnimatedTerminal'

const MatrixRain = dynamic(() => import('@/components/MatrixRain'), { ssr: false })
const DownloadModal = dynamic(() => import('@/components/DownloadModal'), { ssr: false })

const CLUSTER_TERMINAL_LINES = [
  { text: 'curl -sSL refinet.io/cluster-setup | bash', color: 'var(--refi-teal)', prefix: '$' },
  { text: 'Verifying Oracle Cloud ARM A1 environment...', color: 'var(--text-secondary)', prefix: '[1/12]' },
  { text: 'ARM64 detected — 4 OCPUs, 24GB RAM', color: 'var(--success)', prefix: '[OK]' },
  { text: 'Installing system dependencies...', color: 'var(--text-secondary)', prefix: '[2/12]' },
  { text: 'Cloning GROOT-BETA repository...', color: 'var(--text-secondary)', prefix: '[3/12]' },
  { text: 'Installing BitNet b1.58 via bitnet.cpp...', color: 'var(--text-secondary)', prefix: '[4/12]' },
  { text: 'BitNet inference ready (CPU-native ARM)', color: 'var(--success)', prefix: '[OK]' },
  { text: 'Configuring nginx + Let\'s Encrypt TLS...', color: 'var(--text-secondary)', prefix: '[5/12]' },
  { text: 'Installing 5 autonomous agent cron jobs...', color: 'var(--text-secondary)', prefix: '[6/12]' },
  { text: 'Registered with origin REFINET Cloud', color: 'var(--success)', prefix: '[OK]' },
]

const FEATURES = [
  {
    num: '01', tag: 'ORACLE ARM', title: 'Always Free Cloud Compute',
    desc: '4 Arm OCPUs, 24GB RAM, 200GB storage on Oracle Cloud\'s Always Free tier. No credit card holds, no surprise bills, no expiration. Sovereign compute that costs nothing.',
    terminal: '$ oci compute instance launch --shape=VM.Standard.A1.Flex\n[OK] Instance provisioned: 4 OCPU, 24GB RAM',
  },
  {
    num: '02', tag: 'BITNET CPU', title: 'Ternary AI, Zero GPU',
    desc: 'BitNet b1.58 — 2 billion parameters quantized to ternary (-1, 0, 1). Runs natively on ARM CPU via bitnet.cpp. Sub-second inference without a single GPU cycle.',
    terminal: '$ bitnet inference --model=b1.58-2b --device=cpu\n[OK] Response: 340ms, 0 GPU cycles used',
  },
  {
    num: '03', tag: 'AUTO REGISTER', title: 'One Script, Fully Operational',
    desc: 'A single curl command installs everything: GROOT platform, BitNet model, nginx with TLS, 5 autonomous agents on cron, and auto-registration with the origin network.',
    terminal: '$ cluster_setup.sh --register\n[OK] Node registered with REFINET Cloud',
  },
  {
    num: '04', tag: 'LOAD BALANCE', title: 'Distributed Inference Routing',
    desc: 'Requests route to the least-loaded cluster node. Sticky sessions maintain conversation context for 30 minutes. Automatic failover if a node goes offline.',
    terminal: '$ cluster status --routing\n[OK] 3 nodes active, avg latency: 280ms',
  },
  {
    num: '05', tag: 'AUTONOMOUS', title: 'Five Agents, Always Running',
    desc: 'Platform ops, knowledge curator, contract watcher, security sentinel, and repo migrator — all running on cron. Your node monitors itself, heals itself, and reports to you.',
    terminal: '$ crontab -l | grep refinet\n[OK] 5 skills, 25 scheduled tasks active',
  },
]

const SPEC_ROWS = [
  { label: 'CPU', value: '4x Arm Ampere A1 OCPUs' },
  { label: 'RAM', value: '24 GB' },
  { label: 'Storage', value: '200 GB Block Volume' },
  { label: 'Network', value: '480 Mbps (4 Gbps max)' },
  { label: 'OS', value: 'Ubuntu 22.04 LTS (ARM)' },
  { label: 'Cost', value: '$0/month — Always Free' },
]

const DOWNLOADS: Record<string, string> = {
  linux: '/public-downloads/cluster/product/cluster_setup.sh',
}



export default function ClusterProductPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const specSection = useInView(0.15)
  const ctaSection = useInView(0.15)

  return (
    <div style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>

      {/* ═══════ HERO ═══════ */}
      <section className="relative min-h-screen flex flex-col justify-center overflow-hidden scanlines">
        <MatrixRain color="#A8F0E6" opacity={0.03} density={22} speed={0.3} />
        <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(ellipse 60% 50% at 50% 40%, rgba(168,240,230,0.05) 0%, transparent 70%)' }} />

        <div className="relative z-10 max-w-6xl mx-auto px-6 md:px-12 py-32">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6 }} className="mb-10">
            <Link href="/products/" className="text-[11px] font-mono" style={{ color: 'var(--text-tertiary)', textDecoration: 'none' }}>Products</Link>
            <span className="mx-2 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>/</span>
            <span className="text-[11px] font-mono" style={{ color: 'var(--refi-teal)' }}>Cluster</span>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.6 }} className="mb-8">
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-mono font-semibold tracking-wider uppercase"
              style={{ background: 'rgba(74,222,128,0.08)', color: '#4ADE80', border: '1px solid rgba(74,222,128,0.2)' }}>
              <span className="w-2 h-2 rounded-full" style={{ background: '#4ADE80' }} /> Available
            </span>
          </motion.div>

          <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35, duration: 0.7 }}
            className="text-4xl sm:text-5xl md:text-7xl lg:text-8xl font-black tracking-tighter mb-6" style={{ letterSpacing: '-0.05em', lineHeight: 1.05 }}>
            REFINET{' '}<span className="text-glow" style={{ color: 'var(--refi-teal)' }}>Cluster</span>
          </motion.h1>

          <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5, duration: 0.6 }}
            className="text-base sm:text-lg md:text-xl max-w-2xl leading-relaxed mb-10" style={{ color: 'var(--text-secondary)' }}>
            Contribute compute to the sovereign network. Run a full GROOT node on Oracle Cloud ARM —
            BitNet inference, 5 autonomous agents, distributed routing — all within the Always Free tier.
            One command. Zero cost. Infinite potential.
          </motion.p>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.65, duration: 0.5 }}>
            <button onClick={() => setModalOpen(true)}
              className="px-8 py-3.5 rounded-lg text-sm font-bold tracking-wide transition-all hover:scale-[1.02] active:scale-[0.98]"
              style={{ background: 'var(--refi-teal)', color: 'var(--bg-primary)', boxShadow: '0 0 30px rgba(92,224,210,0.25)' }}>
              Get Setup Script
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

      {/* ═══════ SETUP TERMINAL ═══════ */}
      <section className="relative py-20 md:py-32 px-6 md:px-12">
        <div className="max-w-4xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 40 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-100px' }} transition={{ duration: 0.8 }}
            className="rounded-2xl overflow-hidden" style={{ background: 'var(--terminal-bg)', border: '1px solid var(--border-default)', boxShadow: '0 20px 80px rgba(168,240,230,0.06)' }}>
            <div className="flex items-center gap-3 px-5 py-3" style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-subtle)' }}>
              <div className="flex gap-2">
                <span className="w-3 h-3 rounded-full" style={{ background: '#FF5F57' }} />
                <span className="w-3 h-3 rounded-full" style={{ background: '#FEBC2E' }} />
                <span className="w-3 h-3 rounded-full" style={{ background: '#28C840' }} />
              </div>
              <span className="text-[12px] font-mono ml-2" style={{ color: 'var(--text-secondary)' }}>cluster-setup</span>
            </div>
            <AnimatedTerminal
              lines={CLUSTER_TERMINAL_LINES}
              doneText="Cluster node online. Serving inference requests"
              initialDelay={400}
              lineDelay={120}
            />
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.3, duration: 0.6 }}
            className="flex flex-wrap justify-center gap-3 mt-8">
            {['One Command Setup', 'Auto Registration', 'Zero Cost'].map((label) => (
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
            <h2 className="text-2xl md:text-4xl font-bold mt-3 tracking-tight" style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}>Compute Without Compromise.</h2>
          </div>
          <div style={{ borderTop: '1px solid var(--border-subtle)' }}>
            {FEATURES.map((feature, i) => (
              <div key={feature.num} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <FeatureRow feature={feature} index={i} terminalLabel="cluster-node" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════ HARDWARE SPECS ═══════ */}
      <section className="py-20 md:py-32 px-6 md:px-12" ref={specSection.ref}>
        <div className="max-w-3xl mx-auto" style={{ opacity: specSection.inView ? 1 : 0, transform: specSection.inView ? 'translateY(0)' : 'translateY(40px)', transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)' }}>
          <div className="text-center mb-12">
            <span className="text-[10px] font-mono tracking-[0.4em] uppercase" style={{ color: 'var(--refi-teal)' }}>Specifications</span>
            <h2 className="text-2xl md:text-4xl font-bold mt-3 tracking-tight" style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}>What You Get (for Free)</h2>
          </div>
          <div className="rounded-xl overflow-hidden" style={{ background: 'var(--terminal-bg)', border: '1px solid var(--border-default)' }}>
            {SPEC_ROWS.map((row, i) => (
              <div key={row.label} className="flex items-center justify-between px-6 py-4 font-mono"
                style={{ borderBottom: i < SPEC_ROWS.length - 1 ? '1px solid var(--border-subtle)' : 'none', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}>
                <span className="text-[12px]" style={{ color: 'var(--text-tertiary)' }}>{row.label}</span>
                <span className="text-[12px] font-semibold" style={{ color: row.label === 'Cost' ? 'var(--success)' : 'var(--text-primary)' }}>{row.value}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════ CTA ═══════ */}
      <section className="py-24 md:py-40 px-6 md:px-12 relative overflow-hidden" ref={ctaSection.ref}>
        <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(ellipse 70% 50% at 50% 50%, rgba(168,240,230,0.06) 0%, transparent 70%)' }} />
        <div className="relative z-10 max-w-3xl mx-auto text-center" style={{ opacity: ctaSection.inView ? 1 : 0, transform: ctaSection.inView ? 'translateY(0)' : 'translateY(40px)', transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)' }}>
          <h2 className="text-2xl sm:text-3xl md:text-5xl font-black tracking-tighter mb-6" style={{ letterSpacing: '-0.04em', lineHeight: 1.1 }}>
            Add Your Node to the{' '}<span style={{ color: 'var(--refi-teal)' }}>Sovereign Network</span>
          </h2>
          <p className="text-sm md:text-base max-w-lg mx-auto mb-10 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            One command. Five minutes. Zero cost. Your node joins the REFINET network and starts serving sovereign inference immediately.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button onClick={() => setModalOpen(true)} className="px-8 py-3.5 rounded-lg text-sm font-bold transition-all hover:scale-[1.02]"
              style={{ background: 'var(--refi-teal)', color: 'var(--bg-primary)', boxShadow: '0 0 40px rgba(92,224,210,0.3)' }}>
              Get Setup Script
            </button>
          </div>
        </div>
      </section>

      <DownloadModal isOpen={modalOpen} onClose={() => setModalOpen(false)} product="cluster" displayName="REFINET Cluster" available={true} downloads={DOWNLOADS} />
    </div>
  )
}
