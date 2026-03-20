'use client'

import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '@/lib/config'

const FALLBACK_CHAINS = ['sepolia', 'base', 'ethereum', 'polygon', 'arbitrum', 'optimism']

interface PipelineStep {
  id: string; step_name: string; step_index: number; status: string
  worker_type: string; output: any; error: string | null
  started_at: string | null; completed_at: string | null
}
interface Pipeline {
  id: string; pipeline_type: string; status: string; current_step: string | null
  config: any; result: any; error: string | null; created_at: string
  started_at: string | null; completed_at: string | null; steps: PipelineStep[]
}

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  pending: { bg: 'rgba(250,204,21,0.12)', text: 'rgb(250,204,21)' },
  running: { bg: 'rgba(96,165,250,0.12)', text: 'rgb(96,165,250)' },
  completed: { bg: 'rgba(74,222,128,0.12)', text: 'var(--success)' },
  failed: { bg: 'rgba(248,113,113,0.12)', text: 'var(--error)' },
  paused: { bg: 'rgba(167,139,250,0.12)', text: 'rgb(167,139,250)' },
  cancelled: { bg: 'var(--bg-tertiary)', text: 'var(--text-tertiary)' },
  skipped: { bg: 'var(--bg-tertiary)', text: 'var(--text-tertiary)' },
}

const STEP_ICONS: Record<string, string> = {
  completed: '\u2705', running: '\u23F3', failed: '\u274C', pending: '\u23F8\uFE0F', skipped: '\u23ED\uFE0F',
}

export default function PipelinePage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([])
  const [selected, setSelected] = useState<Pipeline | null>(null)
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [sourceCode, setSourceCode] = useState('')
  const [chain, setChain] = useState('sepolia')
  const [constructorArgs, setConstructorArgs] = useState('')
  const [compilerVersion, setCompilerVersion] = useState('0.8.20')
  const [contractName, setContractName] = useState('')
  const [newOwner, setNewOwner] = useState('')
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [chains, setChains] = useState<string[]>(FALLBACK_CHAINS)

  useEffect(() => {
    fetch(`${API_URL}/explore/chains`)
      .then(r => r.ok ? r.json() : [])
      .then(data => { if (Array.isArray(data) && data.length > 0) setChains(data.map((c: any) => c.short_name || c.chain).filter(Boolean)) })
      .catch(() => {})
  }, [])

  const headers = useCallback(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('refinet_token') : null
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  }, [])

  const fetchPipelines = useCallback(async () => {
    try {
      const resp = await fetch(`${API_URL}/pipeline/?limit=30`, { headers: headers() })
      if (resp.ok) setPipelines(await resp.json())
    } catch {}
    setLoading(false)
  }, [headers])

  const fetchPipeline = useCallback(async (id: string) => {
    try {
      const resp = await fetch(`${API_URL}/pipeline/${id}`, { headers: headers() })
      if (resp.ok) { const data = await resp.json(); setSelected(data); return data }
    } catch {}
    return null
  }, [headers])

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    if (!token) { window.location.href = '/settings/'; return }
    fetchPipelines()
  }, [fetchPipelines])

  useEffect(() => {
    if (!selected || !['running', 'pending', 'paused'].includes(selected.status)) return
    const interval = setInterval(() => fetchPipeline(selected.id), 3000)
    return () => clearInterval(interval)
  }, [selected, fetchPipeline])

  const startWizard = async () => {
    setCreating(true); setError('')
    try {
      let args: any[] = []
      if (constructorArgs.trim()) { try { args = JSON.parse(constructorArgs) } catch { setError('Invalid constructor args JSON'); setCreating(false); return } }
      const body: any = { source_code: sourceCode, chain, compiler_version: compilerVersion }
      if (args.length) body.constructor_args = args
      if (contractName) body.contract_name = contractName
      if (newOwner) body.new_owner = newOwner
      const resp = await fetch(`${API_URL}/pipeline/start`, { method: 'POST', headers: headers(), body: JSON.stringify(body) })
      const data = await resp.json()
      if (!resp.ok) { setError(data.detail || 'Failed'); setCreating(false); return }
      setShowCreate(false); setSourceCode(''); await fetchPipelines(); fetchPipeline(data.pipeline_id)
    } catch (e: any) { setError(e.message) }
    setCreating(false)
  }

  const cancelPipeline = async (id: string) => {
    await fetch(`${API_URL}/pipeline/${id}/cancel`, { method: 'POST', headers: headers() })
    fetchPipelines(); if (selected?.id === id) fetchPipeline(id)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)', fontSize: 13 }}>Loading pipelines...</span>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto py-10 px-6 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ letterSpacing: '-0.02em' }}>Wizard Pipeline</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>GROOT compiles, tests, deploys, and generates DApps using its wallet</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>Start Pipeline</button>
      </div>

      {error && <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--error)', border: '1px solid rgba(248,113,113,0.2)' }}>{error}</div>}

      {/* Create Pipeline Modal */}
      {showCreate && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ background: 'rgba(0,0,0,0.6)' }}>
          <div className="card max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-slide-up" style={{ padding: 24 }}>
            <h2 className="font-bold text-lg mb-1" style={{ letterSpacing: '-0.02em' }}>Start Wizard Pipeline</h2>
            <p className="text-xs mb-5" style={{ color: 'var(--text-tertiary)' }}>
              GROOT will compile, test, parse, deploy (with admin approval), generate a frontend, and submit to the App Store.
            </p>

            <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Solidity Source Code *</label>
            <textarea value={sourceCode} onChange={e => setSourceCode(e.target.value)}
              className="input-base focus-glow w-full resize-y mb-4" rows={8}
              style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}
              placeholder={'// SPDX-License-Identifier: MIT\npragma solidity ^0.8.20;\n\ncontract MyToken { ... }'} />

            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Chain</label>
                <select value={chain} onChange={e => setChain(e.target.value)} className="input-base focus-glow w-full">
                  {chains.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Compiler Version</label>
                <input value={compilerVersion} onChange={e => setCompilerVersion(e.target.value)} className="input-base focus-glow w-full" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Contract Name <span style={{ color: 'var(--text-tertiary)' }}>(optional)</span></label>
                <input value={contractName} onChange={e => setContractName(e.target.value)} placeholder="Auto-detected" className="input-base focus-glow w-full" />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Transfer To <span style={{ color: 'var(--text-tertiary)' }}>(optional)</span></label>
                <input value={newOwner} onChange={e => setNewOwner(e.target.value)} placeholder="0x..." className="input-base focus-glow w-full" />
              </div>
            </div>
            <div className="mb-4">
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Constructor Args <span style={{ color: 'var(--text-tertiary)' }}>(JSON array, optional)</span></label>
              <input value={constructorArgs} onChange={e => setConstructorArgs(e.target.value)} placeholder='[1000, "0x..."]' className="input-base focus-glow w-full" />
            </div>

            {error && <p className="text-sm mt-2" style={{ color: 'var(--error)' }}>{error}</p>}
            <div className="flex gap-2 mt-5">
              <button onClick={startWizard} disabled={creating || !sourceCode.trim()} className="btn-primary">
                {creating ? 'Starting...' : 'Launch Pipeline'}
              </button>
              <button onClick={() => { setShowCreate(false); setError('') }} className="btn-secondary">Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-5" style={{ gridTemplateColumns: '280px 1fr' }}>
        {/* Pipeline List */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-xs font-semibold uppercase" style={{ letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>Recent Pipelines</span>
          </div>
          {pipelines.length === 0 ? (
            <div className="p-6 text-center" style={{ color: 'var(--text-tertiary)' }}>
              <p className="text-sm">No pipelines yet</p>
              <p className="text-xs mt-1">Click Start Pipeline to deploy your first contract</p>
            </div>
          ) : (
            <div style={{ maxHeight: 500, overflowY: 'auto' }}>
              {pipelines.map(p => {
                const st = STATUS_STYLES[p.status] || STATUS_STYLES.pending
                return (
                  <div key={p.id} onClick={() => fetchPipeline(p.id)} className="cursor-pointer transition-all"
                    style={{
                      padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)',
                      background: selected?.id === p.id ? 'var(--bg-tertiary)' : 'transparent',
                      borderLeft: selected?.id === p.id ? '2px solid var(--refi-teal)' : '2px solid transparent',
                    }}
                    onMouseEnter={e => { if (selected?.id !== p.id) e.currentTarget.style.background = 'var(--bg-elevated)' }}
                    onMouseLeave={e => { if (selected?.id !== p.id) e.currentTarget.style.background = 'transparent' }}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)' }}>{p.pipeline_type}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: st.bg, color: st.text, fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>{p.status}</span>
                    </div>
                    <p className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>{new Date(p.created_at).toLocaleString()}</p>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Pipeline Detail */}
        <div className="card" style={{ padding: 0, overflow: 'hidden', minHeight: 400 }}>
          {!selected ? (
            <div className="flex items-center justify-center h-full min-h-[400px]" style={{ color: 'var(--text-tertiary)' }}>
              <p className="text-sm">Select a pipeline to view DAG steps and progress</p>
            </div>
          ) : (
            <>
              <div className="px-5 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <div>
                  <span className="font-bold" style={{ letterSpacing: '-0.02em' }}>{selected.pipeline_type} Pipeline</span>
                  <span className="text-[11px] ml-2" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>{selected.id.slice(0, 12)}...</span>
                </div>
                <div className="flex items-center gap-2">
                  {(() => { const st = STATUS_STYLES[selected.status] || STATUS_STYLES.pending; return (
                    <span className="text-[10px] px-3 py-1 rounded-full" style={{ background: st.bg, color: st.text, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>{selected.status}</span>
                  ) })()}
                  {['running', 'pending', 'paused'].includes(selected.status) && (
                    <button onClick={() => cancelPipeline(selected.id)} className="text-xs px-3 py-1 rounded-lg"
                      style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--error)', border: '1px solid rgba(248,113,113,0.2)' }}>Cancel</button>
                  )}
                </div>
              </div>

              <div className="p-5">
                {selected.error && (
                  <div className="p-3 rounded-lg mb-4 text-sm" style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', color: 'var(--error)' }}>
                    {selected.error}
                  </div>
                )}

                {/* DAG Steps */}
                <div className="space-y-2">
                  {selected.steps?.map((step) => {
                    const st = STATUS_STYLES[step.status] || STATUS_STYLES.pending
                    return (
                      <div key={step.id} className="p-4 rounded-lg transition-all"
                        style={{ background: step.status === 'running' ? `${st.bg}` : 'var(--bg-tertiary)', border: `1px solid ${step.status === 'running' ? st.text + '40' : 'var(--border-subtle)'}` }}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="text-lg">{STEP_ICONS[step.status] || '\u2B55'}</span>
                            <div>
                              <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{step.step_name}</span>
                              <span className="text-xs ml-2" style={{ color: 'var(--text-tertiary)' }}>({step.worker_type})</span>
                            </div>
                          </div>
                          <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: st.bg, color: st.text, fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>{step.status}</span>
                        </div>
                        {step.error && <p className="text-xs mt-2" style={{ color: 'var(--error)' }}>{step.error}</p>}
                        {step.output && step.status === 'completed' && (
                          <details className="mt-2">
                            <summary className="text-xs cursor-pointer" style={{ color: 'var(--text-tertiary)' }}>Output</summary>
                            <pre className="text-[11px] mt-1 overflow-x-auto p-2 rounded" style={{ background: 'var(--bg-elevated)', fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)' }}>
                              {JSON.stringify(step.output, null, 2).slice(0, 500)}
                            </pre>
                          </details>
                        )}
                      </div>
                    )
                  })}
                </div>

                {selected.status === 'paused' && (
                  <div className="mt-4 p-4 rounded-lg text-center" style={{ background: 'rgba(167,139,250,0.08)', border: '1px solid rgba(167,139,250,0.2)' }}>
                    <p className="font-semibold text-sm" style={{ color: 'rgb(167,139,250)' }}>Awaiting Master Admin Approval</p>
                    <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>A Tier 2 action requires approval before GROOT can continue.</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
