'use client'

import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '@/lib/config'

interface Deployment {
  id: string
  contract_address: string
  chain: string
  chain_id: number
  deployer_address: string
  owner_address: string
  tx_hash: string
  block_number: number
  ownership_status: string
  transfer_tx_hash: string | null
  created_at: string
  transferred_at: string | null
}

const STATUS_BADGE: Record<string, string> = {
  groot_owned: 'bg-orange-500/20 text-orange-400',
  transferring: 'bg-yellow-500/20 text-yellow-400',
  user_owned: 'bg-green-500/20 text-green-400',
  unknown: 'bg-gray-500/20 text-gray-400',
}

const EXPLORER_URL: Record<string, string> = {
  ethereum: 'https://etherscan.io',
  sepolia: 'https://sepolia.etherscan.io',
  base: 'https://basescan.org',
  polygon: 'https://polygonscan.com',
  arbitrum: 'https://arbiscan.io',
  optimism: 'https://optimistic.etherscan.io',
}

export default function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([])
  const [loading, setLoading] = useState(true)
  const [transferTarget, setTransferTarget] = useState<{ id: string; address: string } | null>(null)
  const [newOwner, setNewOwner] = useState('')
  const [error, setError] = useState('')

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

  useEffect(() => { fetchDeployments() }, [fetchDeployments])

  const initiateTransfer = async (id: string) => {
    setError('')
    if (!newOwner.startsWith('0x') || newOwner.length !== 42) {
      setError('Invalid address'); return
    }
    try {
      const resp = await fetch(`${API_URL}/deployments/${id}/transfer`, {
        method: 'POST', headers: headers(), body: JSON.stringify({ new_owner: newOwner })
      })
      if (!resp.ok) { const d = await resp.json(); setError(d.detail || 'Failed'); return }
      setTransferTarget(null); setNewOwner('')
      fetchDeployments()
    } catch (e: any) { setError(e.message) }
  }

  const explorerLink = (chain: string, hash: string, type: 'tx' | 'address') =>
    `${EXPLORER_URL[chain] || '#'}/${type}/${hash}`

  return (
    <div className="min-h-screen bg-[#0A0A1B] text-white p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">Deployments</h1>
        <p className="text-gray-400 mb-8">Contracts deployed by GROOT on your behalf</p>

        {loading && <p className="text-gray-500">Loading...</p>}
        {!loading && deployments.length === 0 && (
          <div className="bg-[#1A1A2E] rounded-2xl p-12 text-center">
            <p className="text-gray-400 text-lg">No deployments yet</p>
            <p className="text-gray-500 mt-2">Start a Wizard Pipeline to deploy your first contract</p>
            <a href="/pipeline" className="inline-block mt-4 px-6 py-2.5 bg-orange-600 hover:bg-orange-700 rounded-lg font-semibold transition-colors">
              Go to Pipeline
            </a>
          </div>
        )}

        <div className="space-y-4">
          {deployments.map(d => (
            <div key={d.id} className="bg-[#1A1A2E] rounded-xl p-5 border border-gray-700">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="font-mono text-orange-400">{d.contract_address}</span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[d.ownership_status] || ''}`}>
                      {d.ownership_status.replace('_', ' ')}
                    </span>
                    <span className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300">{d.chain}</span>
                  </div>
                  <div className="flex gap-6 text-sm text-gray-400">
                    <span>Block #{d.block_number}</span>
                    <a href={explorerLink(d.chain, d.tx_hash, 'tx')} target="_blank" rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300">
                      View Tx
                    </a>
                    <a href={explorerLink(d.chain, d.contract_address, 'address')} target="_blank" rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300">
                      View Contract
                    </a>
                    <span>{new Date(d.created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    Deployed by: <span className="font-mono">{d.deployer_address?.slice(0, 10)}...</span>
                    {d.owner_address && d.owner_address !== d.deployer_address && (
                      <> | Owner: <span className="font-mono">{d.owner_address?.slice(0, 10)}...</span></>
                    )}
                  </div>
                </div>

                {d.ownership_status === 'groot_owned' && (
                  <button onClick={() => setTransferTarget({ id: d.id, address: d.contract_address })}
                    className="px-4 py-2 bg-green-600/20 text-green-400 hover:bg-green-600/30 rounded-lg text-sm font-medium transition-colors">
                    Transfer to Me
                  </button>
                )}
              </div>

              {transferTarget?.id === d.id && (
                <div className="mt-4 p-4 bg-[#0A0A1B] rounded-lg border border-gray-700">
                  <label className="block text-sm text-gray-400 mb-1">Your Wallet Address</label>
                  <div className="flex gap-2">
                    <input value={newOwner} onChange={e => setNewOwner(e.target.value)}
                      placeholder="0x..." className="flex-1 bg-[#1A1A2E] border border-gray-600 rounded-lg p-2.5 text-sm focus:border-orange-500 focus:outline-none" />
                    <button onClick={() => initiateTransfer(d.id)}
                      className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium transition-colors">
                      Transfer
                    </button>
                    <button onClick={() => { setTransferTarget(null); setError('') }}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">
                      Cancel
                    </button>
                  </div>
                  {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
