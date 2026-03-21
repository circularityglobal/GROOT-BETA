'use client'

import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '@/lib/config'

interface Template { id: string; name: string; description: string; preview_url?: string }
interface DAppBuild {
  id: string; template_name: string; status: string; config_json: string
  output_filename: string; validation_status: string | null
  validation_errors: string | null; created_at: string; completed_at: string | null
}

const CHAINS = ['sepolia', 'base', 'ethereum', 'polygon', 'arbitrum', 'optimism']

const VALIDATION_STYLES: Record<string, { bg: string; text: string }> = {
  passed: { bg: 'rgba(74,222,128,0.12)', text: 'var(--success)' },
  failed: { bg: 'rgba(248,113,113,0.12)', text: 'var(--error)' },
  pending: { bg: 'rgba(250,204,21,0.12)', text: 'rgb(250,204,21)' },
}

export default function DAppPage() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [builds, setBuilds] = useState<DAppBuild[]>([])
  const [loading, setLoading] = useState(true)
  const [showBuild, setShowBuild] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [contractName, setContractName] = useState('')
  const [contractAddress, setContractAddress] = useState('')
  const [chain, setChain] = useState('sepolia')
  const [abiJson, setAbiJson] = useState('')
  const [building, setBuilding] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const headers = useCallback(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('refinet_token') : null
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  }, [])

  const fetchData = useCallback(async () => {
    try {
      const [tResp, bResp] = await Promise.all([
        fetch(`${API_URL}/dapp/templates`, { headers: headers() }),
        fetch(`${API_URL}/dapp/builds`, { headers: headers() }),
      ])
      if (tResp.ok) setTemplates(await tResp.json())
      if (bResp.ok) setBuilds(await bResp.json())
    } catch {}
    setLoading(false)
  }, [headers])

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    
    fetchData()
  }, [fetchData])

  const buildDapp = async () => {
    setBuilding(true); setError('')
    try {
      const body: any = { template_name: selectedTemplate, contract_name: contractName, contract_address: contractAddress, chain }
      if (abiJson.trim()) body.abi_json = abiJson
      const resp = await fetch(`${API_URL}/dapp/build`, { method: 'POST', headers: headers(), body: JSON.stringify(body) })
      if (!resp.ok) { const d = await resp.json(); setError(d.detail || 'Build failed'); setBuilding(false); return }
      setShowBuild(false); setMsg('DApp build started'); setTimeout(() => setMsg(''), 3000); fetchData()
    } catch (e: any) { setError(e.message) }
    setBuilding(false)
  }

  const downloadBuild = async (buildId: string) => {
    const resp = await fetch(`${API_URL}/dapp/builds/${buildId}/download`, { headers: headers() })
    if (!resp.ok) return
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `dapp-${buildId.slice(0, 8)}.zip`
    a.click(); URL.revokeObjectURL(url)
  }

  const validateBuild = async (buildId: string) => {
    await fetch(`${API_URL}/dapp/builds/${buildId}/validate`, { method: 'POST', headers: headers() })
    fetchData()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)', fontSize: 13 }}>Loading DApp Factory...</span>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto py-10 px-6 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ letterSpacing: '-0.02em' }}>DApp Factory</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>Build downloadable React DApps from contract templates</p>
        </div>
        <button className="btn-primary" onClick={() => setShowBuild(true)}>Build DApp</button>
      </div>

      {error && <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--error)', border: '1px solid rgba(248,113,113,0.2)' }}>{error}</div>}
      {msg && <div className="mb-4 p-3 rounded-lg text-sm animate-fade-in" style={{ background: 'rgba(92,224,210,0.08)', color: 'var(--refi-teal)', border: '1px solid var(--refi-teal)' }}>{msg}</div>}

      {/* Templates */}
      <div className="mb-8">
        <h2 className="text-xs font-semibold uppercase mb-3" style={{ letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>Templates</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {templates.map(t => (
            <div key={t.id} className="card cursor-pointer transition-all" style={{ padding: '16px' }}
              onClick={() => { setSelectedTemplate(t.id); setShowBuild(true) }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-default)')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}>
              <h3 className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{t.name}</h3>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{t.description}</p>
            </div>
          ))}
          {templates.length === 0 && (
            <p className="text-sm col-span-4" style={{ color: 'var(--text-tertiary)' }}>No templates loaded</p>
          )}
        </div>
      </div>

      {/* Build Modal */}
      {showBuild && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ background: 'rgba(0,0,0,0.6)' }}>
          <div className="card max-w-lg w-full animate-slide-up" style={{ padding: 24 }}>
            <h2 className="font-bold text-lg mb-4" style={{ letterSpacing: '-0.02em' }}>Build DApp</h2>
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Template</label>
                <select value={selectedTemplate} onChange={e => setSelectedTemplate(e.target.value)} className="input-base focus-glow w-full">
                  <option value="">Select template</option>
                  {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  <option value="simple-dashboard">Simple Dashboard</option>
                  <option value="token-manager">Token Manager</option>
                  <option value="staking-ui">Staking UI</option>
                  <option value="governance-voting">Governance Voting</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Contract Name</label>
                  <input value={contractName} onChange={e => setContractName(e.target.value)} className="input-base focus-glow w-full" />
                </div>
                <div>
                  <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Chain</label>
                  <select value={chain} onChange={e => setChain(e.target.value)} className="input-base focus-glow w-full">
                    {CHAINS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Contract Address</label>
                <input value={contractAddress} onChange={e => setContractAddress(e.target.value)} placeholder="0x..." className="input-base focus-glow w-full" />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>ABI JSON <span style={{ color: 'var(--text-tertiary)' }}>(optional)</span></label>
                <textarea value={abiJson} onChange={e => setAbiJson(e.target.value)} placeholder="[{...}]"
                  className="input-base focus-glow w-full resize-none" rows={4} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }} />
              </div>
            </div>
            {error && <p className="text-sm mt-3" style={{ color: 'var(--error)' }}>{error}</p>}
            <div className="flex gap-2 mt-5">
              <button onClick={buildDapp} disabled={building || !selectedTemplate || !contractName || !contractAddress} className="btn-primary">
                {building ? 'Building...' : 'Build'}
              </button>
              <button onClick={() => { setShowBuild(false); setError('') }} className="btn-secondary">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Builds */}
      <div>
        <h2 className="text-xs font-semibold uppercase mb-3" style={{ letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>Your Builds</h2>
        {builds.length === 0 ? (
          <div className="card text-center py-8">
            <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No builds yet. Select a template above to start.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {builds.map(b => {
              const config = (() => { try { return JSON.parse(b.config_json || '{}') } catch { return {} } })()
              const vs = b.validation_status ? (VALIDATION_STYLES[b.validation_status] || VALIDATION_STYLES.pending) : null
              return (
                <div key={b.id} className="card flex items-center justify-between" style={{ padding: '12px 20px' }}>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{config.contract_name || 'DApp'}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>{b.template_name}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>{config.chain || '?'}</span>
                      {vs && (
                        <span className="text-[10px] px-2 py-0.5 rounded uppercase" style={{ background: vs.bg, color: vs.text, fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>
                          {b.validation_status}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] mt-1" style={{ color: 'var(--text-tertiary)' }}>{new Date(b.created_at).toLocaleString()}</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => validateBuild(b.id)} className="text-xs px-3 py-1.5 rounded-lg transition-colors"
                      style={{ background: 'rgba(96,165,250,0.1)', color: 'rgb(96,165,250)', border: '1px solid rgba(96,165,250,0.2)' }}>
                      Validate
                    </button>
                    <button onClick={() => downloadBuild(b.id)} className="text-xs px-3 py-1.5 rounded-lg transition-colors"
                      style={{ background: 'rgba(74,222,128,0.1)', color: 'var(--success)', border: '1px solid rgba(74,222,128,0.2)' }}>
                      Download
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
