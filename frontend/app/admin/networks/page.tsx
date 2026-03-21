'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

export default function AdminNetworks() {
  const { headers } = useAdmin()
  const [chains, setChains] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [importId, setImportId] = useState('')
  const [importing, setImporting] = useState(false)
  const [msg, setMsg] = useState('')

  const fetchChains = async () => {
    try {
      const resp = await fetch(`${API_URL}/admin/chains`, { headers })
      if (resp.ok) setChains(await resp.json())
    } catch {}
    setLoading(false)
  }

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    fetchChains()
  }, [headers.Authorization])

  const importFromChainlist = async () => {
    const chainId = parseInt(importId)
    if (!chainId || isNaN(chainId)) { setMsg('Enter a valid chain ID (number)'); return }
    setImporting(true); setMsg('')
    try {
      const resp = await fetch(`${API_URL}/admin/chains/import`, { method: 'POST', headers, body: JSON.stringify({ chain_id: chainId }) })
      const data = await resp.json()
      if (!resp.ok) { setMsg(data.detail || 'Import failed'); setImporting(false); return }
      setMsg(`Imported: ${data.name} (${data.short_name})`)
      setImportId('')
      fetchChains()
    } catch (e: any) { setMsg(e.message) }
    setImporting(false)
  }

  const toggleChain = async (chainId: number, active: boolean) => {
    await fetch(`${API_URL}/admin/chains/${chainId}`, { method: 'PUT', headers, body: JSON.stringify({ is_active: active }) })
    fetchChains()
  }

  if (loading) return <LoadingState label="Loading networks..." />

  return (
    <div>
      <PageHeader title="EVM Networks" subtitle={`${chains.length} chains configured`} />

      <div className="flex justify-between items-center mb-4">
        <div />
        <button onClick={() => setShowAdd(!showAdd)}
          style={{ background: 'var(--refi-teal)', color: '#000', border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
          + Add Network
        </button>
      </div>

      {showAdd && (
        <div className="card p-4 mb-4" style={{ border: '1px solid var(--border-subtle)' }}>
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Import from Chainlist.org</h4>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
            Enter a chain ID to auto-import network config (RPC, explorer, currency).
          </p>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input value={importId} onChange={e => setImportId(e.target.value)} placeholder="Chain ID (e.g., 43114 for Avalanche)"
              style={{ flex: 1, background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', fontSize: 12 }} />
            <button onClick={importFromChainlist} disabled={importing}
              style={{ background: 'var(--refi-teal)', color: '#000', border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: importing ? 0.5 : 1 }}>
              {importing ? 'Importing...' : 'Import'}
            </button>
          </div>
          {msg && <p style={{ fontSize: 11, color: msg.includes('Imported') ? '#10B981' : '#EF4444', marginTop: 6 }}>{msg}</p>}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {chains.map((c: any) => (
          <div key={c.chain_id} className="card" style={{
            padding: 12, opacity: c.is_active ? 1 : 0.5,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            border: '1px solid var(--border-subtle)',
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                {c.name}
                {c.is_testnet && <span style={{ fontSize: 10, color: '#F59E0B', marginLeft: 6 }}>TESTNET</span>}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                ID: {c.chain_id} | {c.short_name} | {c.currency}
              </div>
            </div>
            <button onClick={() => toggleChain(c.chain_id, !c.is_active)}
              style={{
                fontSize: 10, padding: '3px 8px', borderRadius: 4, border: 'none', cursor: 'pointer',
                background: c.is_active ? '#10B98120' : '#EF444420',
                color: c.is_active ? '#10B981' : '#EF4444', fontWeight: 600,
              }}>
              {c.is_active ? 'Active' : 'Inactive'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
