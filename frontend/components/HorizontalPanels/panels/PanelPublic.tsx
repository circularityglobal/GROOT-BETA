'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'

interface PanelPublicProps {
  isActive: boolean
}

const USE_CASES = [
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
    ),
    title: 'AI Chat',
    desc: 'Have natural conversations with Groot about anything — research, ideas, code, and creative projects.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
      </svg>
    ),
    title: 'Document Analysis',
    desc: 'Upload documents to the knowledge base and let Groot extract insights, summarize, and answer questions.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
    ),
    title: 'Research Assistant',
    desc: 'Use Groot as a sovereign research partner that never shares your data with third parties.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
      </svg>
    ),
    title: 'Creative Writing',
    desc: 'Draft stories, poetry, essays, and more with an AI that runs entirely on sovereign infrastructure.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
      </svg>
    ),
    title: 'Code Help',
    desc: 'Get programming assistance, debug code, and learn new concepts — all powered by BitNet inference.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/>
      </svg>
    ),
    title: 'Productivity',
    desc: 'Organize tasks, brainstorm ideas, create outlines, and manage workflows with conversational AI.',
  },
]

export default function PanelPublic({ isActive }: PanelPublicProps) {
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

      {/* Subtle dot grid */}
      <div className="absolute inset-0 pointer-events-none dot-grid" style={{
        backgroundImage: 'radial-gradient(circle, var(--border-subtle) 1px, transparent 1px)',
        backgroundSize: '24px 24px',
      }} />

      {/* Radial accent */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: 'radial-gradient(ellipse 40% 40% at 50% 30%, rgba(92,224,210,0.05) 0%, transparent 70%)',
      }} />

      <div className="relative z-10 flex flex-col items-center justify-center h-full px-6 py-12">
        <div className="max-w-5xl w-full">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={animate ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5 }}
            className="text-center mb-4"
          >
            <p className="text-[12px] font-mono uppercase tracking-widest mb-3" style={{ color: 'var(--refi-teal)' }}>
              {'>'} for_everyone
            </p>
            <h2 className="text-3xl md:text-5xl font-extrabold tracking-tighter mb-4" style={{ letterSpacing: '-0.04em' }}>
              Intelligence that<br />
              <span style={{ color: 'var(--refi-teal)' }}>serves everyone</span>
            </h2>
            <p className="text-base md:text-lg max-w-lg mx-auto" style={{ color: 'var(--text-secondary)' }}>
              Free forever. No account required. No data harvesting.
              Sovereign AI that respects your autonomy and works for the commons.
            </p>
          </motion.div>

          {/* Use case grid */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={animate ? { opacity: 1 } : {}}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mt-10"
          >
            {USE_CASES.map((uc, i) => (
              <motion.div
                key={uc.title}
                initial={{ opacity: 0, y: 20 }}
                animate={animate ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: 0.3 + i * 0.08, duration: 0.4 }}
                className="card p-5 group hover:border-refi-teal/30 transition-all"
              >
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4 transition-colors"
                  style={{ background: 'var(--refi-teal-glow)', color: 'var(--refi-teal)' }}>
                  {uc.icon}
                </div>
                <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                  {uc.title}
                </h3>
                <p className="text-[12px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {uc.desc}
                </p>
              </motion.div>
            ))}
          </motion.div>

          {/* CTA */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={animate ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.8, duration: 0.4 }}
            className="text-center mt-10"
          >
            <Link href="/chat/" className="btn-primary !py-3 !px-8 font-mono text-sm" prefetch={true}>
              {'>'} Start Chatting — Free
            </Link>
            <p className="text-[11px] font-mono mt-3" style={{ color: 'var(--text-tertiary)' }}>
              No sign-up. No credit card. Just open and talk.
            </p>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
