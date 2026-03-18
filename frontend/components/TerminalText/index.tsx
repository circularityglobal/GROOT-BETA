'use client'

import { useState, useEffect } from 'react'

interface TerminalTextProps {
  text: string
  speed?: number
  delay?: number
  cursor?: boolean
  className?: string
  onComplete?: () => void
}

export default function TerminalText({
  text,
  speed = 40,
  delay = 0,
  cursor = true,
  className = '',
  onComplete,
}: TerminalTextProps) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)

  useEffect(() => {
    setDisplayed('')
    setDone(false)

    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (mq.matches) {
      setDisplayed(text)
      setDone(true)
      onComplete?.()
      return
    }

    let i = 0
    const timeout = setTimeout(() => {
      const interval = setInterval(() => {
        i++
        setDisplayed(text.slice(0, i))
        if (i >= text.length) {
          clearInterval(interval)
          setDone(true)
          onComplete?.()
        }
      }, speed)
      return () => clearInterval(interval)
    }, delay)

    return () => clearTimeout(timeout)
  }, [text, speed, delay])

  return (
    <span className={className}>
      {displayed}
      {cursor && !done && (
        <span className="cursor-blink ml-0.5" style={{ color: 'var(--refi-teal)' }}>█</span>
      )}
      {cursor && done && (
        <span className="cursor-blink ml-0.5" style={{ color: 'var(--refi-teal)' }}>█</span>
      )}
    </span>
  )
}
