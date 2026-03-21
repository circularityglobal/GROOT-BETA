'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'
import TerminalText from '@/components/TerminalText'

interface PanelDeveloperProps {
  isActive: boolean
}

const CODE_LINES = [
  { text: '$ curl -X POST https://api.refinet.io/v1/chat/completions \\', color: 'var(--text-secondary)' },
  { text: '  -H "Authorization: Bearer rf_your_key" \\', color: 'var(--refi-mint)' },
  { text: '  -d \'{"model":"bitnet-b1.58-2b","messages":[{"role":"user","content":"Hello"}]}\'', color: 'var(--refi-mint)' },
  { text: '', color: '' },
  { text: '{"id":"chatcmpl-groot","choices":[{"message":{"role":"assistant",', color: 'var(--refi-teal)' },
  { text: '  "content":"I am Groot. How can I help you today?"}}]}', color: 'var(--refi-teal)' },
]

const FEATURES = [
  { icon: '⚡', label: 'Inference', desc: 'OpenAI-compatible /v1/chat/completions' },
  { icon: '🔗', label: 'Webhooks', desc: 'Real-time event delivery to your endpoints' },
  { icon: '📡', label: 'Devices', desc: 'IoT registration, telemetry, heartbeat' },
  { icon: '🤖', label: 'Agents', desc: 'Autonomous agent registration & management' },
  { icon: '🧠', label: 'Knowledge', desc: 'RAG-powered context injection pipeline' },
  { icon: '🔑', label: 'Auth', desc: 'Sign-In with Ethereum (SIWE) + optional 2FA' },
]

const SDK_BADGES = [
  { name: 'Python', color: '#3776AB' },
  { name: 'JavaScript', color: '#F7DF1E' },
  { name: 'cURL', color: '#5CE0D2' },
  { name: 'Go', color: '#00ADD8' },
]

export default function PanelDeveloper({ isActive }: PanelDeveloperProps) {
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
        backgroundSize: '32px 32px',
      }} />

      <div className="relative z-10 flex flex-col items-center justify-center h-full px-6 py-12">
        <div className="max-w-5xl w-full">
          {/* Section header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={animate ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5 }}
            className="text-center mb-10"
          >
            <p className="text-[12px] font-mono uppercase tracking-widest mb-3" style={{ color: 'var(--refi-teal)' }}>
              {'>'} developer_api
            </p>
            <h2 className="text-3xl md:text-5xl font-extrabold tracking-tighter" style={{ letterSpacing: '-0.04em' }}>
              Built for developers
            </h2>
          </motion.div>

          {/* SDK badges */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={animate ? { opacity: 1 } : {}}
            transition={{ delay: 0.2, duration: 0.4 }}
            className="flex items-center justify-center gap-2 mb-8"
          >
            {SDK_BADGES.map(b => (
              <span key={b.name} className="px-3 py-1 rounded-full text-[11px] font-mono font-medium"
                style={{
                  border: `1px solid ${b.color}40`,
                  color: b.color,
                  background: `${b.color}10`,
                }}>
                {b.name}
              </span>
            ))}
          </motion.div>

          {/* Terminal window */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={animate ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="rounded-xl overflow-hidden mb-10"
            style={{
              background: 'var(--terminal-bg)',
              border: '1px solid var(--border-default)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            }}
          >
            {/* Title bar */}
            <div className="flex items-center gap-2 px-4 py-3" style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-subtle)' }}>
              <div className="flex gap-1.5">
                <span className="w-3 h-3 rounded-full" style={{ background: '#FF5F57' }} />
                <span className="w-3 h-3 rounded-full" style={{ background: '#FEBC2E' }} />
                <span className="w-3 h-3 rounded-full" style={{ background: '#28C840' }} />
              </div>
              <span className="text-[11px] font-mono ml-2" style={{ color: 'var(--text-tertiary)' }}>
                groot@refinet:~/api $
              </span>
            </div>

            {/* Code content */}
            <div className="p-5 font-mono text-[13px] leading-relaxed overflow-x-auto">
              {CODE_LINES.map((line, i) => (
                <div key={i} className="min-h-[1.5em]">
                  {animate && line.text ? (
                    <TerminalText
                      text={line.text}
                      speed={15}
                      delay={i * 300}
                      cursor={i === CODE_LINES.length - 1}
                      className={line.color ? '' : ''}
                    />
                  ) : null}
                </div>
              ))}
            </div>
          </motion.div>

          {/* Feature grid */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={animate ? { opacity: 1 } : {}}
            transition={{ delay: 0.6, duration: 0.5 }}
            className="grid grid-cols-2 md:grid-cols-3 gap-3"
          >
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.label}
                initial={{ opacity: 0, y: 15 }}
                animate={animate ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: 0.7 + i * 0.08, duration: 0.4 }}
                className="card p-4 group cursor-default"
              >
                <div className="text-lg mb-2">{f.icon}</div>
                <h3 className="text-sm font-semibold font-mono mb-1" style={{ color: 'var(--text-primary)' }}>
                  {f.label}
                </h3>
                <p className="text-[12px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {f.desc}
                </p>
              </motion.div>
            ))}
          </motion.div>

          {/* CTA */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={animate ? { opacity: 1 } : {}}
            transition={{ delay: 1, duration: 0.4 }}
            className="text-center mt-8"
          >
            <Link href="/docs/" className="btn-primary !py-2.5 !px-6 font-mono text-sm" prefetch={true}>
              {'>'} Full API Documentation
            </Link>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
