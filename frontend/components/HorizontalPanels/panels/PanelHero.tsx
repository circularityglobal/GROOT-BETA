'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'
import MatrixRain from '@/components/MatrixRain'
import TerminalText from '@/components/TerminalText'

interface PanelHeroProps {
  isActive: boolean
  onNext: () => void
}

export default function PanelHero({ isActive, onNext }: PanelHeroProps) {
  const [showContent, setShowContent] = useState(false)

  useEffect(() => {
    if (isActive) {
      const t = setTimeout(() => setShowContent(true), 200)
      return () => clearTimeout(t)
    }
  }, [isActive])

  return (
    <div className="w-screen h-full flex-shrink-0 relative overflow-hidden scanlines crt-vignette"
      style={{ background: 'var(--bg-primary)' }}>

      {/* Matrix Rain Background */}
      <MatrixRain color="#5CE0D2" opacity={0.06} density={20} speed={0.8} />

      {/* Radial glow */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: 'radial-gradient(ellipse 60% 50% at 50% 40%, var(--refi-teal-glow) 0%, transparent 70%)',
      }} />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center justify-center h-full px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={showContent ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="text-center max-w-3xl"
        >
          {/* Logo */}
          <div className="flex justify-center mb-8">
            <img
              src="/refi-logo.png"
              alt="REFINET"
              className="w-20 h-20 animate-float"
            />
          </div>

          {/* Terminal status line */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={showContent ? { opacity: 1 } : {}}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full mb-8 font-mono text-[12px]"
            style={{
              background: 'rgba(92,224,210,0.06)',
              border: '1px solid rgba(92,224,210,0.15)',
              color: 'var(--refi-teal)',
            }}
          >
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--success)' }} />
            <TerminalText
              text="sovereign infrastructure  ·  zero cost  ·  by the people  ·  for the planet"
              speed={20}
              delay={600}
              cursor={false}
            />
          </motion.div>

          {/* Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={showContent ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.2, duration: 0.7 }}
            className="text-4xl md:text-7xl font-extrabold tracking-tighter leading-[1.08] mb-6 text-glow"
          >
            A new internet built to<br />
            <span style={{ color: 'var(--refi-teal)' }}>regenerate the world</span>
          </motion.h1>

          {/* Subheadline */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={showContent ? { opacity: 1 } : {}}
            transition={{ delay: 0.5, duration: 0.6 }}
            className="text-base md:text-lg max-w-xl mx-auto mb-10 leading-relaxed font-body"
            style={{ color: 'var(--text-secondary)' }}
          >
            Sovereign AI infrastructure. Cryptographic identity.
            Self-operating agents. Built by the people who want to
            bring the world back to balance. Forever free.
          </motion.p>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={showContent ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.7, duration: 0.5 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-3"
          >
            <Link href="/login/" className="btn-primary !text-base !py-3 !px-8 w-full sm:w-auto text-center font-mono" prefetch={true}>
              {'>'} Get Started
            </Link>
            <Link href="/chat/" className="btn-secondary !text-base !py-3 !px-8 w-full sm:w-auto text-center font-mono" prefetch={true}>
              {'>'} Talk to Groot
            </Link>
          </motion.div>
        </motion.div>

        {/* Scroll prompt at bottom */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={showContent ? { opacity: 1 } : {}}
          transition={{ delay: 1.5, duration: 0.8 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 cursor-pointer group"
          onClick={onNext}
        >
          <span className="text-[11px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
            <TerminalText text="> scroll to explore" speed={30} delay={2000} cursor={true} />
          </span>
          <motion.svg
            animate={{ y: [0, 4, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
            width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="2"
          >
            <polyline points="9 18 15 12 9 6" />
          </motion.svg>
        </motion.div>
      </div>
    </div>
  )
}
