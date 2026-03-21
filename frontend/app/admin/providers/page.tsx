'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader } from '../shared'

export default function AdminProviders() {
  const { headers } = useAdmin()
  const [data, setData] = useState<any>(null)
  const [usageData, setUsageData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [healthLoading, setHealthLoading] = useState(false)

  const ADMIN_WALLET = '0xE302932D42C751404AeD466C8929F1704BA89D5A'
  const PROVIDER_COLORS: Record<string, string> = { bitnet: '#5CE0D2', gemini: '#4285F4', ollama: '#84CC16', lmstudio: '#A78BFA', openrouter: '#F97316' }
  const PROVIDER_ICONS: Record<string, string> = { bitnet: '1', gemini: 'G', ollama: 'O', lmstudio: 'L', openrouter: 'R' }

  const load = () => {
    setLoading(true)
    Promise.all([
      fetch(`${API_URL}/admin/providers`, { headers }).then(r => r.ok ? r.json() : null),
      fetch(`${API_URL}/admin/providers/usage?period=day`, { headers }).then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([d, u]) => { setData(d); setUsageData(u); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    load()
  }, [headers.Authorization])

  const runHealthCheck = async () => {
    setHealthLoading(true)
    try {
      const r = await fetch(`${API_URL}/admin/providers/health`, { headers })
      if (r.ok) load()
    } catch {}
    setHealthLoading(false)
  }

  if (loading && !data) return <div className="py-20 text-center"><p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading providers...</p></div>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold" style={{ letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>AI Model Providers</h1>
          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Configure which AI backends GROOT can use for inference.</p>
        </div>
        <button onClick={runHealthCheck} disabled={healthLoading} className="px-3 py-1.5 text-xs font-semibold rounded-lg"
          style={{ background: healthLoading ? 'var(--bg-tertiary)' : 'var(--refi-teal)', color: healthLoading ? 'var(--text-tertiary)' : '#000', cursor: healthLoading ? 'not-allowed' : 'pointer' }}>
          {healthLoading ? 'Checking...' : 'Run Health Check'}
        </button>
      </div>

      {/* Admin Wallet */}
      <div className="card p-3 mb-4" style={{ border: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>Platform Admin Wallet</div>
            <div className="text-xs font-mono" style={{ color: 'var(--refi-teal)' }}>{ADMIN_WALLET}</div>
          </div>
          <div className="text-[9px] px-2 py-0.5 rounded" style={{ background: 'rgba(92,224,210,0.15)', color: '#5CE0D2' }}>OWNER</div>
        </div>
      </div>

      {/* Fallback Chain */}
      {data && (
        <div className="card p-3 mb-4" style={{ border: '1px solid var(--border-subtle)' }}>
          <div className="text-[10px] font-mono uppercase mb-2" style={{ color: 'var(--text-tertiary)' }}>Fallback Chain (priority order)</div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {data.fallback_chain.map((p: string, i: number) => (
              <span key={p} className="flex items-center gap-1">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded"
                  style={{ background: `${PROVIDER_COLORS[p] || '#888'}15`, color: PROVIDER_COLORS[p] || '#888', border: `1px solid ${PROVIDER_COLORS[p] || '#888'}30` }}>
                  {p}
                </span>
                {i < data.fallback_chain.length - 1 && <span style={{ color: 'var(--text-tertiary)', fontSize: '10px' }}>→</span>}
              </span>
            ))}
          </div>
          <div className="text-[10px] mt-2" style={{ color: 'var(--text-tertiary)' }}>
            Default model: <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>{data.default_model}</span>
          </div>
        </div>
      )}

      {/* Provider Cards */}
      {data && (
        <div className="space-y-3 mb-6">
          {data.providers.map((p: any) => {
            const color = PROVIDER_COLORS[p.type] || '#888'
            const icon = PROVIDER_ICONS[p.type] || '?'
            const isHealthy = p.healthy === true
            const isUnknown = p.healthy === null
            const usageRow = usageData?.by_provider?.find((u: any) => u.provider === p.type)

            return (
              <div key={p.type} className="card p-4"
                style={{ border: `1px solid ${p.enabled ? color + '40' : 'var(--border-subtle)'}`, opacity: p.enabled ? 1 : 0.6 }}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold flex-shrink-0"
                      style={{ background: `${color}20`, color }}>{icon}</div>
                    <div>
                      <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{p.name}</div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{p.description}</div>
                      {p.models.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {p.models.slice(0, 8).map((m: string) => (
                            <span key={m} className="text-[9px] font-mono px-1.5 py-0.5 rounded"
                              style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>{m}</span>
                          ))}
                          {p.models.length > 8 && <span className="text-[9px] px-1.5 py-0.5" style={{ color: 'var(--text-tertiary)' }}>+{p.models.length - 8} more</span>}
                        </div>
                      )}
                      {usageRow && (
                        <div className="flex gap-3 mt-2 text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                          <span>{usageRow.calls} calls today</span>
                          <span>{(usageRow.prompt_tokens + usageRow.completion_tokens).toLocaleString()} tokens</span>
                          <span>{usageRow.avg_latency_ms}ms avg</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                    <div className="flex items-center gap-1.5">
                      {p.enabled
                        ? <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(74,222,128,0.15)', color: 'var(--success)' }}>ENABLED</span>
                        : <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--text-tertiary)' }}>DISABLED</span>}
                      {p.registered && (
                        isHealthy
                          ? <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(74,222,128,0.15)', color: 'var(--success)' }}>HEALTHY</span>
                          : isUnknown
                          ? <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}>PENDING</span>
                          : <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(248,113,113,0.15)', color: 'var(--error)' }}>UNHEALTHY</span>
                      )}
                    </div>
                    {p.latency_ms !== null && <span className="text-[9px] font-mono" style={{ color: 'var(--text-tertiary)' }}>{p.latency_ms}ms</span>}
                    {p.error && <span className="text-[9px] max-w-[200px] truncate" style={{ color: 'var(--error)' }}>{p.error}</span>}
                  </div>
                </div>
                <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>{p.config_key}</span>
                    <span className="text-[10px] font-mono" style={{ color: p.config_value ? 'var(--text-secondary)' : 'var(--error)' }}>
                      {p.config_value || '(not set)'}
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Setup Guide */}
      <div className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
        <h3 className="text-xs font-mono mb-3 uppercase" style={{ color: 'var(--text-tertiary)' }}>Enable Providers (.env)</h3>
        <pre className="text-[11px] font-mono p-3 rounded overflow-x-auto" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
{`GEMINI_API_KEY=your-google-api-key
OLLAMA_HOST=http://127.0.0.1:11434
LMSTUDIO_HOST=http://127.0.0.1:1234
OPENROUTER_API_KEY=your-openrouter-key
DEFAULT_MODEL=bitnet-b1.58-2b
PROVIDER_FALLBACK_CHAIN=bitnet,gemini,ollama,lmstudio,openrouter`}
        </pre>
      </div>
    </div>
  )
}
