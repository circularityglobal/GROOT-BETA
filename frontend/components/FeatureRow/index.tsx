'use client'

import { useInView } from '@/hooks/useInView'

interface FeatureData {
  num: string
  tag: string
  title: string
  desc: string
  terminal: string
}

interface FeatureRowProps {
  feature: FeatureData
  index: number
  terminalLabel?: string
}

/**
 * Reusable alternating feature row with text + terminal snippet.
 * Scroll-triggered reveal via IntersectionObserver.
 */
export default function FeatureRow({ feature, index, terminalLabel = 'terminal' }: FeatureRowProps) {
  const { ref, inView } = useInView(0.2)
  const isEven = index % 2 === 1

  return (
    <div
      ref={ref}
      className={`flex flex-col ${isEven ? 'md:flex-row-reverse' : 'md:flex-row'} gap-8 md:gap-16 items-center py-16 md:py-24`}
    >
      {/* Text side */}
      <div
        className="flex-1"
        style={{
          opacity: inView ? 1 : 0,
          transform: inView ? 'translateY(0)' : 'translateY(40px)',
          transition: 'all 0.7s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <div className="flex items-baseline gap-4 mb-4">
          <span
            className="text-5xl md:text-7xl font-mono font-black"
            style={{ color: 'var(--refi-teal)', opacity: 0.3 }}
          >
            {feature.num}
          </span>
          <span
            className="text-[10px] font-mono tracking-[0.3em] uppercase"
            style={{ color: 'var(--refi-teal)' }}
          >
            {feature.tag}
          </span>
        </div>
        <h3
          className="text-xl md:text-2xl font-bold mb-4"
          style={{ color: 'var(--text-primary)', letterSpacing: '-0.02em' }}
        >
          {feature.title}
        </h3>
        <p
          className="text-sm md:text-base leading-relaxed max-w-lg"
          style={{ color: 'var(--text-secondary)' }}
        >
          {feature.desc}
        </p>
      </div>

      {/* Terminal visual side */}
      <div
        className="flex-1 w-full max-w-md"
        style={{
          opacity: inView ? 1 : 0,
          transform: inView ? 'translateY(0)' : 'translateY(40px)',
          transition: 'all 0.7s cubic-bezier(0.16, 1, 0.3, 1) 0.15s',
        }}
      >
        <div
          className="rounded-xl overflow-hidden"
          style={{
            background: 'var(--terminal-bg)',
            border: '1px solid var(--border-default)',
            boxShadow: '0 8px 32px rgba(92,224,210,0.06)',
          }}
        >
          <div
            className="flex items-center gap-1.5 px-4 py-2"
            style={{
              background: 'var(--bg-secondary)',
              borderBottom: '1px solid var(--border-subtle)',
            }}
          >
            <span className="w-2 h-2 rounded-full" style={{ background: '#FF5F57' }} />
            <span className="w-2 h-2 rounded-full" style={{ background: '#FEBC2E' }} />
            <span className="w-2 h-2 rounded-full" style={{ background: '#28C840' }} />
            <span className="ml-3 text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
              {terminalLabel}
            </span>
          </div>
          <div className="p-5 font-mono text-[12px] md:text-[13px] whitespace-pre-line">
            {feature.terminal.split('\n').map((line, li) => (
              <p
                key={li}
                style={{
                  color: line.includes('[OK]') ? 'var(--success)' : 'var(--text-secondary)',
                }}
              >
                {line}
              </p>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
