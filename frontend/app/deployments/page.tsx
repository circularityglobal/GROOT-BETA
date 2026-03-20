'use client'

import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '@/lib/config'

interface Deployment {
  id: string; contract_address: string; chain: string; chain_id: number
  deployer_address: string; owner_address: string; tx_hash: string
  block_number: number; ownership_status: string; transfer_tx_hash: string | null
  created_at: string; transferred_at: string | null
}

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  groot_owned: { bg: 'rgba(249,115,22,0.12)', text: 'rgb(249,115,22)' },
  transferring: { bg: 'rgba(250,204,21,0.12)', text: 'rgb(250,204,21)' },
  user_owned: { bg: 'rgba(74,222,128,0.12)', text: 'rgb(74,222,128)' },
  unknown: { bg: 'var(--bg-tertiary)', text: 'var(--text-tertiary)' },
}

const EXPLORER_URL: Record<string, string> = {
  ethereum: 'https://etherscan.io', sepolia: 'https://sepolia.etherscan.io',
  base: 'https://basescan.org', polygon: 'https://polygonscan.com',
  arbitrum: 'https://arbiscan.io', optimism: 'https://optimistic.etherscan.io',
}

export default function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([])
  const [loading, setLoading] = useState(true)
  const [transferTarget, setTransferTarget] = useState<{ id: string; address: string } | null>(null)
  const [newOwner, setNewOwner] = useState('')
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const headers = useCallback(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('refinet_token') : null
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  }, [])

  const fetchDeployments = useCallback(async () => {
    try {
      const resp = await fetch(`${API_URL}/deployments/`, { headers: headers() })
      if (resp.ok) setDeployments(await resp.json())
    } catch {}
    setLoading(false)
  }, [headers])

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    if (!token) { window.location.href = '/settings/'; return }
    fetchDeployments()
  }, [fetchDeployments])

  const initiateTransfer = async (id: string) => {
    setError('')
    if (!newOwner.startsWith('0x') || newOwner.length !== 42) { setError('Invalid Ethereum address'); return }
    try {
      const resp = await fetch(`${API_URL}/deployments/${id}/transfer`, {
        method: 'POST', headers: headers(), body: JSON.stringify({ new_owner: newOwner })
      })
      if (!resp.ok) { const d = await resp.json(); setError(d.detail || 'Transfer failed'); return }
      setTransferTarget(null); setNewOwner(''); setMsg('Ownership transfer initiated')
      setTimeout(() => setMsg(''), 3000); fetchDeployments()
    } catch (e: any) { setError(e.message) }
  }

  const explorerLink = (chain: string, hash: string, type: 'tx' | 'address') =>
    `${EXPLORER_URL[chain] || '#'}/${type}/${hash}`

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)', fontSize: 13 }}>Loading deployments...</span>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto py-10 px-6 animate-fade-in">
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ letterSpacing: '-0.02em' }}>Deployments</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>Contracts deployed by GROOT on your behalf</p>
      </div>

      {error && <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--error)', border: '1px solid rgba(248,113,113,0.2)' }}>{error}</div>}
      {msg && <div className="mb-4 p-3 rounded-lg text-sm animate-fade-in" style={{ background: 'rgba(92,224,210,0.08)', color: 'var(--refi-teal)', border: '1px solid var(--refi-teal)' }}>{msg}</div>}

      {/* Stats */}
      <div className="grid gap-3 mb-6" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
        <MiniStat label="Total" value={deployments.length.toString()} color="var(--refi-teal)" />
        <MiniStat label="GROOT Owned" value={deployments.filter(d => d.ownership_status === 'groot_owned').length.toString()} color="rgb(249,115,22)" />
        <MiniStat label="Transferred" value={deployments.filter(d => d.ownership_status === 'user_owned').length.toString()} color="var(--success)" />
      </div>

      {deployments.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No deployments yet</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Start a Wizard Pipeline to deploy your first contract</p>
          <a href="/pipeline/" className="btn-primary inline-block mt-4" style={{ textDecoration: 'none' }}>Go to Pipeline</a>
        </div>
      ) : (
        <div className="space-y-3">
          {deployments.map(d => {
            const st = STATUS_STYLES[d.ownership_status] || STATUS_STYLES.unknown
            return (
              <div key={d.id} className="card" style={{ padding: '16px 20px' }}>
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3 mb-2 flex-wrap">
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: 'var(--refi-teal)' }}>{d.contract_address}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded uppercase" style={{ background: st.bg, color: st.text, fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>
                        {d.ownership_status.replace('_', ' ')}
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded uppercase" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>
                        {d.chain}
                      </span>
                    </div>
                    <div className="flex gap-5 text-xs flex-wrap" style={{ color: 'var(--text-tertiary)' }}>
                      <span>Block #{d.block_number}</span>
                      <a href={explorerLink(d.chain, d.tx_hash, 'tx')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--refi-teal)', textDecoration: 'none' }}
                        onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')} onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}>
                        View Tx &rarr;
                      </a>
                      <a href={explorerLink(d.chain, d.contract_address, 'address')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--refi-teal)', textDecoration: 'none' }}
                        onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')} onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}>
                        View Contract &rarr;
                      </a>
                      <span>{new Date(d.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="text-[11px] mt-2" style={{ color: 'var(--text-tertiary)' }}>
                      Deployed by: <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{d.deployer_address?.slice(0, 10)}...</span>
                      {d.owner_address && d.owner_address !== d.deployer_address && (
                        <> | Owner: <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{d.owner_address?.slice(0, 10)}...</span></>
                      )}
                    </div>
                  </div>

                  {d.ownership_status === 'groot_owned' && (
                    <button onClick={() => setTransferTarget({ id: d.id, address: d.contract_address })}
                      className="shrink-0 text-xs px-3 py-1.5 rounded-lg transition-colors ml-4"
                      style={{ background: 'rgba(74,222,128,0.1)', color: 'var(--success)', border: '1px solid rgba(74,222,128,0.2)' }}>
                      Transfer to Me
                    </button>
                  )}
                </div>

                {transferTarget?.id === d.id && (
                  <div className="mt-4 p-4 rounded-lg animate-slide-up" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)' }}>
                    <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Your Wallet Address</label>
                    <div className="flex gap-2">
                      <input value={newOwner} onChange={e => setNewOwner(e.target.value)} placeholder="0x..."
                        className="input-base focus-glow flex-1" />
                      <button onClick={() => initiateTransfer(d.id)} className="btn-primary !text-xs">Transfer</button>
                      <button onClick={() => { setTransferTarget(null); setError('') }} className="btn-secondary !text-xs">Cancel</button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function MiniStat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 10, padding: '14px 16px', transition: 'all 0.2s' }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-default)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}>
      <span className="text-[11px] uppercase font-medium" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>{label}</span>
      <div className="text-xl font-bold mt-1" style={{ color, letterSpacing: '-0.02em' }}>{value}</div>
    </div>
  )
}
