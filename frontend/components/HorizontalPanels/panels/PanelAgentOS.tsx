'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import TerminalText from '@/components/TerminalText'

interface PanelAgentOSProps {
  isActive: boolean
}

const AGENTS = [
  { name: 'QuickCast Agent', status: 'online', type: 'inference', id: 'agent-001' },
  { name: 'Telemetry Collector', status: 'online', type: 'device', id: 'agent-002' },
  { name: 'Knowledge Indexer', status: 'syncing', type: 'knowledge', id: 'agent-003' },
  { name: 'Webhook Dispatcher', status: 'online', type: 'webhook', id: 'agent-004' },
  { name: 'Guardian Node', status: 'offline', type: 'security', id: 'agent-005' },
]

const LOG_LINES = [
  '[2026-03-18T00:26:01Z] agent-001 registered via /agents/register',
  '[2026-03-18T00:26:02Z] agent-002 heartbeat received — latency: 12ms',
  '[2026-03-18T00:26:03Z] agent-003 syncing knowledge base — 47 documents',
  '[2026-03-18T00:26:04Z] agent-004 webhook delivered to https://hook.example.com',
  '[2026-03-18T00:26:05Z] groot inference: BitNet b1.58 2B — 142 tok/s',
]

const HIGHLIGHTS = [
  { title: 'Multi-Agent Management', desc: 'Register, monitor, and orchestrate any number of autonomous agents from one dashboard.' },
  { title: 'Direct GROOT Connection', desc: 'Every agent connects to GROOT for sovereign AI inference, knowledge retrieval, and coordination.' },
  { title: 'Fully Open Source', desc: 'MIT-licensed desktop application. Fork it, extend it, self-host it. Your agents, your rules.' },
]

function statusColor(status: string) {
  if (status === 'online') return 'var(--success)'
  if (status === 'syncing') return 'var(--warning)'
  return 'var(--text-tertiary)'
}

export default function PanelAgentOS({ isActive }: PanelAgentOSProps) {
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

      <div className="relative z-10 flex flex-col h-full px-6 py-10">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={animate ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="text-center mb-6 flex-shrink-0"
        >
          <p className="text-[12px] font-mono uppercase tracking-widest mb-3" style={{ color: 'var(--refi-teal)' }}>
            {'>'} agent_os
          </p>
          <h2 className="text-3xl md:text-5xl font-extrabold tracking-tighter mb-3" style={{ letterSpacing: '-0.04em' }}>
            Command your agents
          </h2>
          <p className="text-base max-w-lg mx-auto" style={{ color: 'var(--text-secondary)' }}>
            An open source desktop app for managing all agents
            in the REFINET ecosystem — powered by GROOT.
          </p>
        </motion.div>

        {/* Main content: app mockup */}
        <div className="flex-1 flex items-center justify-center min-h-0">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={animate ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="w-full max-w-4xl rounded-xl overflow-hidden"
            style={{
              background: 'var(--terminal-bg)',
              border: '1px solid var(--border-default)',
              boxShadow: '0 12px 48px rgba(0,0,0,0.5)',
            }}
          >
            {/* App title bar */}
            <div className="flex items-center justify-between px-4 py-2.5"
              style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-subtle)' }}>
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#FF5F57' }} />
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#FEBC2E' }} />
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#28C840' }} />
                </div>
                <span className="text-[11px] font-mono font-semibold" style={{ color: 'var(--refi-teal)' }}>
                  AgentOS v1.0
                </span>
              </div>
              <span className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                REFINET Ecosystem
              </span>
            </div>

            {/* App body: sidebar + main */}
            <div className="flex min-h-[240px] md:min-h-[300px]">
              {/* Sidebar: agent list */}
              <div className="w-48 md:w-56 flex-shrink-0 p-3 space-y-1"
                style={{ borderRight: '1px solid var(--border-subtle)' }}>
                <p className="text-[10px] font-mono uppercase tracking-wider mb-2 px-2" style={{ color: 'var(--text-tertiary)' }}>
                  Agents ({AGENTS.length})
                </p>
                {AGENTS.map((a, i) => (
                  <motion.div
                    key={a.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={animate ? { opacity: 1, x: 0 } : {}}
                    transition={{ delay: 0.5 + i * 0.08 }}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-md text-[11px] font-mono cursor-default transition-colors"
                    style={{
                      background: i === 0 ? 'var(--bg-hover)' : 'transparent',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                      style={{ background: statusColor(a.status) }} />
                    <span className="truncate">{a.name}</span>
                  </motion.div>
                ))}
              </div>

              {/* Main: terminal log */}
              <div className="flex-1 p-4 font-mono text-[11px] leading-relaxed overflow-hidden">
                <p className="text-[10px] uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>
                  Live Activity Log
                </p>
                {LOG_LINES.map((line, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0 }}
                    animate={animate ? { opacity: 1 } : {}}
                    transition={{ delay: 0.7 + i * 0.15 }}
                    className="mb-1"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {animate ? (
                      <TerminalText text={line} speed={10} delay={700 + i * 400} cursor={i === LOG_LINES.length - 1} />
                    ) : null}
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>

        {/* Feature highlights + CTA */}
        <div className="flex-shrink-0 mt-6">
          <motion.div
            initial={{ opacity: 0 }}
            animate={animate ? { opacity: 1 } : {}}
            transition={{ delay: 0.9, duration: 0.5 }}
            className="grid grid-cols-1 md:grid-cols-3 gap-3 max-w-4xl mx-auto mb-6"
          >
            {HIGHLIGHTS.map((h, i) => (
              <motion.div
                key={h.title}
                initial={{ opacity: 0, y: 15 }}
                animate={animate ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: 1 + i * 0.1 }}
                className="text-center px-4"
              >
                <h3 className="text-sm font-semibold font-mono mb-1" style={{ color: 'var(--refi-teal)' }}>
                  {h.title}
                </h3>
                <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {h.desc}
                </p>
              </motion.div>
            ))}
          </motion.div>

          {/* Learn More + Footer bar */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={animate ? { opacity: 1 } : {}}
            transition={{ delay: 1.2, duration: 0.4 }}
            className="max-w-4xl mx-auto pt-4"
            style={{ borderTop: '1px solid var(--border-subtle)' }}
          >
            <div className="flex flex-col md:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <img src="/refi-logo.png" alt="" className="w-4 h-4" />
                <span className="text-[11px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                  REFINET Cloud · Sovereign Infrastructure for a Regenerative Internet
                </span>
              </div>
              <div className="flex items-center gap-4">
                <a href="/products/wizardos/" className="inline-flex items-center gap-1.5 text-[11px] font-mono font-semibold transition-all hover:gap-2"
                  style={{ color: 'var(--refi-teal)', textDecoration: 'none' }}>
                  WizardOS
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                </a>
                <div className="flex items-center gap-4 text-[11px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                  <span className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--success)' }} />
                    1 node
                  </span>
                  <span>BitNet CPU</span>
                  <span>AGPL-3.0</span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
