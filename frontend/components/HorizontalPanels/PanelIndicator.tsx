'use client'

import { useState } from 'react'

interface PanelIndicatorProps {
  current: number
  total: number
  labels: string[]
  goTo: (index: number) => void
}

export default function PanelIndicator({ current, total, labels, goTo }: PanelIndicatorProps) {
  const [hovered, setHovered] = useState<number | null>(null)

  return (
    <>
      {/* Desktop: vertical dots on right */}
      <div className="hidden md:flex fixed right-6 top-1/2 -translate-y-1/2 z-30 flex-col items-center gap-3">
        {/* Connecting line */}
        <div
          className="absolute top-0 bottom-0 w-px"
          style={{ background: 'var(--border-subtle)' }}
        />
        {Array.from({ length: total }).map((_, i) => (
          <button
            key={i}
            onClick={() => goTo(i)}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
            className="relative z-10 flex items-center gap-3 group"
            aria-label={`Go to ${labels[i]}`}
          >
            {/* Label on hover */}
            <div
              className="absolute right-full mr-3 px-2.5 py-1 rounded-md text-[11px] font-mono whitespace-nowrap transition-all duration-200"
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                color: i === current ? 'var(--refi-teal)' : 'var(--text-secondary)',
                opacity: hovered === i ? 1 : 0,
                transform: hovered === i ? 'translateX(0)' : 'translateX(4px)',
                pointerEvents: 'none',
              }}
            >
              {labels[i]}
            </div>

            {/* Dot */}
            <div
              className="rounded-full transition-all duration-300"
              style={{
                width: i === current ? 12 : 8,
                height: i === current ? 12 : 8,
                background: i === current ? 'var(--refi-teal)' : 'var(--border-default)',
                boxShadow: i === current ? '0 0 12px var(--refi-teal-glow-strong), 0 0 4px var(--refi-teal)' : 'none',
              }}
            />
          </button>
        ))}
      </div>

      {/* Mobile: horizontal dots at bottom */}
      <div className="flex md:hidden fixed bottom-6 left-1/2 -translate-x-1/2 z-30 items-center gap-2.5">
        {Array.from({ length: total }).map((_, i) => (
          <button
            key={i}
            onClick={() => goTo(i)}
            className="rounded-full transition-all duration-300"
            style={{
              width: i === current ? 10 : 6,
              height: i === current ? 10 : 6,
              background: i === current ? 'var(--refi-teal)' : 'var(--border-default)',
              boxShadow: i === current ? '0 0 10px var(--refi-teal-glow-strong)' : 'none',
            }}
            aria-label={`Go to ${labels[i]}`}
          />
        ))}
      </div>
    </>
  )
}
