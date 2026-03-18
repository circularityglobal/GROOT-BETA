'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, useAnimation } from 'framer-motion'
import PanelIndicator from './PanelIndicator'
import PanelHero from './panels/PanelHero'
import PanelDeveloper from './panels/PanelDeveloper'
import PanelPublic from './panels/PanelPublic'
import PanelBrowser from './panels/PanelBrowser'
import PanelAgentOS from './panels/PanelAgentOS'

const TOTAL_PANELS = 5
const COOLDOWN_MS = 800
const WHEEL_THRESHOLD = 30
const TOUCH_THRESHOLD = 80

const PANEL_LABELS = ['Hero', 'Developers', 'Productivity', 'Browser', 'AgentOS']

export default function HorizontalPanels() {
  const [currentPanel, setCurrentPanel] = useState(0)
  const cooldownRef = useRef(false)
  const touchStartRef = useRef<{ x: number; y: number } | null>(null)
  const controls = useAnimation()

  const goToPanel = useCallback((index: number) => {
    if (index < 0 || index >= TOTAL_PANELS || index === currentPanel) return
    setCurrentPanel(index)
  }, [currentPanel])

  const next = useCallback(() => {
    if (cooldownRef.current) return
    setCurrentPanel(p => {
      if (p >= TOTAL_PANELS - 1) return p
      cooldownRef.current = true
      setTimeout(() => { cooldownRef.current = false }, COOLDOWN_MS)
      return p + 1
    })
  }, [])

  const prev = useCallback(() => {
    if (cooldownRef.current) return
    setCurrentPanel(p => {
      if (p <= 0) return p
      cooldownRef.current = true
      setTimeout(() => { cooldownRef.current = false }, COOLDOWN_MS)
      return p - 1
    })
  }, [])

  // Animate on panel change
  useEffect(() => {
    controls.start({
      x: `${-currentPanel * 100}vw`,
      transition: { type: 'spring', stiffness: 260, damping: 30 },
    })
  }, [currentPanel, controls])

  // Wheel handler
  useEffect(() => {
    const handler = (e: WheelEvent) => {
      e.preventDefault()
      if (Math.abs(e.deltaY) > WHEEL_THRESHOLD) {
        if (e.deltaY > 0) next()
        else prev()
      }
    }
    window.addEventListener('wheel', handler, { passive: false })
    return () => window.removeEventListener('wheel', handler)
  }, [next, prev])

  // Keyboard handler
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault()
        next()
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        prev()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [next, prev])

  // Touch handlers
  useEffect(() => {
    const onStart = (e: TouchEvent) => {
      touchStartRef.current = {
        x: e.touches[0].clientX,
        y: e.touches[0].clientY,
      }
    }
    const onEnd = (e: TouchEvent) => {
      if (!touchStartRef.current) return
      const dx = e.changedTouches[0].clientX - touchStartRef.current.x
      const dy = e.changedTouches[0].clientY - touchStartRef.current.y
      // Only trigger if horizontal swipe is dominant
      if (Math.abs(dx) > TOUCH_THRESHOLD && Math.abs(dx) > Math.abs(dy)) {
        if (dx < 0) next()
        else prev()
      }
      touchStartRef.current = null
    }
    window.addEventListener('touchstart', onStart, { passive: true })
    window.addEventListener('touchend', onEnd, { passive: true })
    return () => {
      window.removeEventListener('touchstart', onStart)
      window.removeEventListener('touchend', onEnd)
    }
  }, [next, prev])

  return (
    <div className="h-full w-full overflow-hidden relative">
      <motion.div
        className="flex h-full"
        animate={controls}
        initial={{ x: 0 }}
        style={{ width: `${TOTAL_PANELS * 100}vw` }}
      >
        <PanelHero isActive={currentPanel === 0} onNext={next} />
        <PanelDeveloper isActive={currentPanel === 1} />
        <PanelPublic isActive={currentPanel === 2} />
        <PanelBrowser isActive={currentPanel === 3} />
        <PanelAgentOS isActive={currentPanel === 4} />
      </motion.div>

      <PanelIndicator
        current={currentPanel}
        total={TOTAL_PANELS}
        labels={PANEL_LABELS}
        goTo={goToPanel}
      />
    </div>
  )
}
