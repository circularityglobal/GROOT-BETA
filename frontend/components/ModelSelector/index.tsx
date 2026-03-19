'use client'

import { useState, useEffect, useRef } from 'react'
import { API_URL } from '@/lib/config'

interface ModelOption {
  id: string
  provider: string
  owned_by: string
  context_window: number
  is_free: boolean
}

interface ModelSelectorProps {
  value: string
  onChange: (model: string) => void
}

const PROVIDER_LABELS: Record<string, string> = {
  refinet: 'Sovereign',
  google: 'Google',
  ollama: 'Local',
  lmstudio: 'Local',
  openrouter: 'Cloud',
}

const PROVIDER_COLORS: Record<string, string> = {
  refinet: '#5CE0D2',
  google: '#4285F4',
  ollama: '#84CC16',
  lmstudio: '#A78BFA',
  openrouter: '#F97316',
}

function formatContext(ctx: number): string {
  if (ctx >= 1000000) return `${(ctx / 1000000).toFixed(0)}M`
  if (ctx >= 1000) return `${(ctx / 1000).toFixed(0)}K`
  return `${ctx}`
}

export default function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const [models, setModels] = useState<ModelOption[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setLoading(true)
    fetch(`${API_URL}/v1/models`)
      .then(r => r.ok ? r.json() : { data: [] })
      .then(data => {
        const list = (data.data || []).map((m: any) => ({
          id: m.id,
          provider: m.provider || m.owned_by || 'refinet',
          owned_by: m.owned_by || 'refinet',
          context_window: m.context_window || 4096,
          is_free: m.is_free !== false,
        }))
        setModels(list)
        setLoading(false)
      })
      .catch(() => {
        setModels([{ id: 'bitnet-b1.58-2b', provider: 'refinet', owned_by: 'refinet', context_window: 2048, is_free: true }])
        setLoading(false)
      })
  }, [])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const currentModel = models.find(m => m.id === value)
  const currentProvider = currentModel?.provider || 'refinet'
  const providerColor = PROVIDER_COLORS[currentProvider] || '#888'

  // Group models by provider category
  const groups: Record<string, ModelOption[]> = {}
  for (const m of models) {
    const label = PROVIDER_LABELS[m.provider] || m.provider
    if (!groups[label]) groups[label] = []
    groups[label].push(m)
  }

  const providerCount = Object.keys(groups).length

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
          borderRadius: '8px', padding: '4px 10px', cursor: 'pointer',
          fontFamily: "'JetBrains Mono', monospace", fontSize: '11px',
          color: 'var(--text-secondary)', transition: 'all 0.15s',
        }}
      >
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: providerColor, display: 'inline-block',
          boxShadow: `0 0 4px ${providerColor}60`,
        }} />
        <span>{value || 'Select model'}</span>
        {providerCount > 1 && (
          <span style={{ fontSize: '8px', opacity: 0.5 }}>({providerCount})</span>
        )}
        <span style={{ fontSize: '8px', opacity: 0.5 }}>{open ? '\u25B2' : '\u25BC'}</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, marginTop: '4px',
          background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)',
          borderRadius: '10px', padding: '6px 0', zIndex: 100,
          minWidth: '280px', maxHeight: '360px', overflowY: 'auto',
          boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
        }}>
          {loading ? (
            <div style={{ padding: '12px 14px', fontSize: '11px', color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
              Loading models...
            </div>
          ) : Object.keys(groups).length === 0 ? (
            <div style={{ padding: '12px 14px', fontSize: '11px', color: 'var(--text-tertiary)' }}>
              No models available
            </div>
          ) : (
            Object.entries(groups).map(([label, groupModels]) => (
              <div key={label}>
                <div style={{
                  padding: '8px 14px 4px', fontSize: '9px', fontWeight: 700,
                  color: 'var(--text-tertiary)', textTransform: 'uppercase',
                  letterSpacing: '0.1em', fontFamily: "'JetBrains Mono', monospace",
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}>
                  <span>{label}</span>
                  <span style={{ fontWeight: 400, fontSize: '8px' }}>{groupModels.length} model{groupModels.length > 1 ? 's' : ''}</span>
                </div>
                {groupModels.map(m => {
                  const color = PROVIDER_COLORS[m.provider] || '#888'
                  return (
                    <button
                      key={m.id}
                      onClick={() => { onChange(m.id); setOpen(false) }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '8px',
                        width: '100%', padding: '7px 14px', border: 'none',
                        background: m.id === value ? 'var(--bg-tertiary)' : 'transparent',
                        cursor: 'pointer', textAlign: 'left', transition: 'background 0.1s',
                        fontFamily: "'JetBrains Mono', monospace", fontSize: '11px',
                        color: 'var(--text-primary)',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
                      onMouseLeave={e => (e.currentTarget.style.background = m.id === value ? 'var(--bg-tertiary)' : 'transparent')}
                    >
                      <span style={{
                        width: 6, height: 6, borderRadius: '50%',
                        background: color, flexShrink: 0,
                        boxShadow: `0 0 3px ${color}40`,
                      }} />
                      <span style={{ flex: 1 }}>{m.id}</span>
                      <span style={{
                        fontSize: '8px', color: 'var(--text-tertiary)',
                        fontWeight: 400,
                      }}>
                        {formatContext(m.context_window)}
                      </span>
                      {m.is_free && (
                        <span style={{
                          fontSize: '8px', background: 'rgba(92,224,210,0.15)',
                          color: '#5CE0D2', padding: '1px 5px', borderRadius: '4px',
                          fontWeight: 600,
                        }}>FREE</span>
                      )}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
