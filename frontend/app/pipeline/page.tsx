'use client'

import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '@/lib/config'

const FALLBACK_CHAINS = ['sepolia', 'base', 'ethereum', 'polygon', 'arbitrum', 'optimism']

interface PipelineStep {
  id: string
  step_name: string
  step_index: number
  status: string
  worker_type: string
  output: any
  error: string | null
  started_at: string | null
  completed_at: string | null
}

interface Pipeline {
  id: string
  pipeline_type: string
  status: string
  current_step: string | null
  config: any
  result: any
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  steps: PipelineStep[]
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400',
  running: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
  paused: 'bg-purple-500/20 text-purple-400',
  cancelled: 'bg-gray-500/20 text-gray-400',
  skipped: 'bg-gray-500/20 text-gray-400',
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

  // Fetch dynamic chains from API
  useEffect(() => {
    fetch(`${API_URL}/explore/chains`)
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
          setChains(data.map((c: any) => c.short_name || c.chain).filter(Boolean))
        }
      })
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
      if (resp.ok) {
        const data = await resp.json()
        setSelected(data)
        return data
      }
    } catch {}
    return null
  }, [headers])

  useEffect(() => { fetchPipelines() }, [fetchPipelines])

  // Auto-refresh selected pipeline every 3s while running
  useEffect(() => {
    if (!selected || !['running', 'pending', 'paused'].includes(selected.status)) return
    const interval = setInterval(() => fetchPipeline(selected.id), 3000)
    return () => clearInterval(interval)
  }, [selected, fetchPipeline])

  const startWizard = async () => {
    setCreating(true)
    setError('')
    try {
      let args: any[] = []
      if (constructorArgs.trim()) {
        try { args = JSON.parse(constructorArgs) } catch { setError('Invalid constructor args JSON'); setCreating(false); return }
      }
      const body: any = { source_code: sourceCode, chain, compiler_version: compilerVersion }
      if (args.length) body.constructor_args = args
      if (contractName) body.contract_name = contractName
      if (newOwner) body.new_owner = newOwner

      const resp = await fetch(`${API_URL}/pipeline/start`, {
        method: 'POST', headers: headers(), body: JSON.stringify(body)
      })
      const data = await resp.json()
      if (!resp.ok) { setError(data.detail || 'Failed'); setCreating(false); return }

      setShowCreate(false)
      setSourceCode('')
      await fetchPipelines()
      fetchPipeline(data.pipeline_id)
    } catch (e: any) { setError(e.message) }
    setCreating(false)
  }

  const cancelPipeline = async (id: string) => {
    await fetch(`${API_URL}/pipeline/${id}/cancel`, { method: 'POST', headers: headers() })
    fetchPipelines()
    if (selected?.id === id) fetchPipeline(id)
  }

  return (
    <div className="min-h-screen bg-[#0A0A1B] text-white p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Wizard Pipeline</h1>
            <p className="text-gray-400 mt-1">GROOT compiles, tests, deploys, and generates DApps using its wallet</p>
          </div>
          <button onClick={() => setShowCreate(true)}
            className="px-6 py-3 bg-orange-600 hover:bg-orange-700 rounded-lg font-semibold transition-colors">
            Start Pipeline
          </button>
        </div>

        {/* Create Pipeline Modal */}
        {showCreate && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
            <div className="bg-[#1A1A2E] rounded-2xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <h2 className="text-xl font-bold mb-4">Start Wizard Pipeline</h2>
              <p className="text-gray-400 text-sm mb-4">
                GROOT will compile, test, parse, deploy (with admin approval), generate a frontend, and submit to the App Store.
              </p>

              <label className="block text-sm text-gray-400 mb-1 mt-4">Solidity Source Code *</label>
              <textarea value={sourceCode} onChange={e => setSourceCode(e.target.value)}
                className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-3 text-sm font-mono h-48 focus:border-orange-500 focus:outline-none"
                placeholder="// SPDX-License-Identifier: MIT&#10;pragma solidity ^0.8.20;&#10;&#10;contract MyToken { ... }" />

              <div className="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Chain</label>
                  <select value={chain} onChange={e => setChain(e.target.value)}
                    className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-2.5 focus:border-orange-500 focus:outline-none">
                    {chains.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Compiler Version</label>
                  <input value={compilerVersion} onChange={e => setCompilerVersion(e.target.value)}
                    className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-2.5 focus:border-orange-500 focus:outline-none" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Contract Name (optional)</label>
                  <input value={contractName} onChange={e => setContractName(e.target.value)}
                    placeholder="Auto-detected from source"
                    className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-2.5 focus:border-orange-500 focus:outline-none" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Transfer Ownership To (optional)</label>
                  <input value={newOwner} onChange={e => setNewOwner(e.target.value)}
                    placeholder="0x..."
                    className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-2.5 focus:border-orange-500 focus:outline-none" />
                </div>
              </div>

              <label className="block text-sm text-gray-400 mb-1 mt-4">Constructor Args (JSON array, optional)</label>
              <input value={constructorArgs} onChange={e => setConstructorArgs(e.target.value)}
                placeholder='[1000, "0x..."]'
                className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-2.5 focus:border-orange-500 focus:outline-none" />

              {error && <p className="text-red-400 text-sm mt-3">{error}</p>}

              <div className="flex gap-3 mt-6">
                <button onClick={startWizard} disabled={creating || !sourceCode.trim()}
                  className="px-6 py-2.5 bg-orange-600 hover:bg-orange-700 disabled:opacity-50 rounded-lg font-semibold transition-colors">
                  {creating ? 'Starting...' : 'Launch Pipeline'}
                </button>
                <button onClick={() => { setShowCreate(false); setError('') }}
                  className="px-6 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-6">
          {/* Pipeline List */}
          <div className="col-span-1 space-y-3">
            <h2 className="text-lg font-semibold text-gray-300 mb-2">Recent Pipelines</h2>
            {loading && <p className="text-gray-500">Loading...</p>}
            {!loading && pipelines.length === 0 && <p className="text-gray-500">No pipelines yet</p>}
            {pipelines.map(p => (
              <button key={p.id} onClick={() => fetchPipeline(p.id)}
                className={`w-full text-left p-4 rounded-xl border transition-colors ${
                  selected?.id === p.id ? 'border-orange-500 bg-orange-500/10' : 'border-gray-700 bg-[#1A1A2E] hover:border-gray-500'
                }`}>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm text-gray-400">{p.pipeline_type}</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[p.status] || ''}`}>
                    {p.status}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">{new Date(p.created_at).toLocaleString()}</p>
              </button>
            ))}
          </div>

          {/* Pipeline Detail */}
          <div className="col-span-2">
            {!selected && <div className="bg-[#1A1A2E] rounded-2xl p-8 text-center text-gray-500">Select a pipeline to view details</div>}
            {selected && (
              <div className="bg-[#1A1A2E] rounded-2xl p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-bold">{selected.pipeline_type} Pipeline</h2>
                    <p className="text-sm text-gray-400 font-mono">{selected.id.slice(0, 12)}...</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${STATUS_COLORS[selected.status] || ''}`}>
                      {selected.status}
                    </span>
                    {['running', 'pending', 'paused'].includes(selected.status) && (
                      <button onClick={() => cancelPipeline(selected.id)}
                        className="px-4 py-1.5 bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded-lg text-sm transition-colors">
                        Cancel
                      </button>
                    )}
                  </div>
                </div>

                {selected.error && (
                  <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-4 text-red-400 text-sm">
                    {selected.error}
                  </div>
                )}

                {/* DAG Steps */}
                <div className="space-y-2">
                  {selected.steps?.map((step, i) => (
                    <div key={step.id}
                      className={`p-4 rounded-lg border ${
                        step.status === 'completed' ? 'border-green-500/30 bg-green-500/5' :
                        step.status === 'running' ? 'border-blue-500/30 bg-blue-500/5 animate-pulse' :
                        step.status === 'failed' ? 'border-red-500/30 bg-red-500/5' :
                        step.status === 'pending' ? 'border-purple-500/30 bg-purple-500/5' :
                        'border-gray-700 bg-[#0A0A1B]'
                      }`}>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="text-lg">
                            {step.status === 'completed' ? '\u2705' :
                             step.status === 'running' ? '\u23F3' :
                             step.status === 'failed' ? '\u274C' :
                             step.status === 'pending' ? '\u23F8\uFE0F' :
                             step.status === 'skipped' ? '\u23ED\uFE0F' : '\u2B55'}
                          </span>
                          <div>
                            <span className="font-semibold">{step.step_name}</span>
                            <span className="text-gray-500 text-sm ml-2">({step.worker_type})</span>
                          </div>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[step.status] || ''}`}>
                          {step.status}
                        </span>
                      </div>
                      {step.error && <p className="text-red-400 text-sm mt-2">{step.error}</p>}
                      {step.output && step.status === 'completed' && (
                        <details className="mt-2">
                          <summary className="text-gray-500 text-xs cursor-pointer hover:text-gray-300">Output</summary>
                          <pre className="text-xs text-gray-400 mt-1 overflow-x-auto bg-[#0A0A1B] rounded p-2">
                            {JSON.stringify(step.output, null, 2).slice(0, 500)}
                          </pre>
                        </details>
                      )}
                    </div>
                  ))}
                </div>

                {selected.status === 'paused' && (
                  <div className="mt-4 p-4 bg-purple-500/10 border border-purple-500/30 rounded-lg text-center">
                    <p className="text-purple-300 font-semibold">Awaiting Master Admin Approval</p>
                    <p className="text-purple-400 text-sm mt-1">
                      A Tier 2 action requires approval before GROOT can continue.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
