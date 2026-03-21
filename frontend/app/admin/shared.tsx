'use client'

/* ─── Shared UI helpers for admin pages ─── */

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-bold" style={{ letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>{title}</h1>
      {subtitle && <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{subtitle}</p>}
    </div>
  )
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="py-20 text-center">
      <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
    </div>
  )
}
