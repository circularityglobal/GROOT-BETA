'use client'

import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'

interface TerminalLine {
  text: string
  color: string
  prefix?: string
}

interface AnimatedTerminalProps {
  lines: TerminalLine[]
  /** Initial command shown before lines appear (e.g. "$ refinet-pillar start") */
  initialCommand?: string
  /** Prompt text shown after all lines are revealed */
  doneText?: string
  /** Delay before first line appears (ms) */
  initialDelay?: number
  /** Delay between each line (ms) */
  lineDelay?: number
}

/**
 * Reusable animated terminal that reveals lines one at a time.
 * Properly cleans up timers on unmount.
 */
export default function AnimatedTerminal({
  lines,
  initialCommand,
  doneText,
  initialDelay = 500,
  lineDelay = 150,
}: AnimatedTerminalProps) {
  const [visibleCount, setVisibleCount] = useState(0)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (visibleCount >= lines.length) return
    timerRef.current = setTimeout(
      () => setVisibleCount((c) => c + 1),
      initialDelay + visibleCount * lineDelay,
    )
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [visibleCount, lines.length, initialDelay, lineDelay])

  // Cleanup on unmount
  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [])

  return (
    <div className="font-mono text-[12px] md:text-[13px] space-y-2 p-6 md:p-8 min-h-[240px]">
      {initialCommand && (
        <p style={{ color: 'var(--refi-teal)' }}>{initialCommand}</p>
      )}
      {lines.slice(0, visibleCount).map((line, i) => (
        <motion.p
          key={i}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3 }}
          style={{ color: line.color }}
        >
          {line.prefix && (
            <span style={{
              color: line.color === 'var(--success)' ? 'var(--success)' : 'var(--text-tertiary)',
            }}>
              {line.prefix}
            </span>
          )}{' '}{line.text}
        </motion.p>
      ))}
      {visibleCount >= lines.length && doneText && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-4 pt-4"
          style={{ borderTop: '1px solid var(--border-subtle)' }}
        >
          <p style={{ color: 'var(--refi-teal)' }}>
            {'>'} {doneText}_<span className="animate-pulse">|</span>
          </p>
        </motion.div>
      )}
    </div>
  )
}
