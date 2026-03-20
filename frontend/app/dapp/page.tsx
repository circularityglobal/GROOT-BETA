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

  useEffect(() => { fetchData() }, [fetchData])

  const buildDapp = async () => {
    setBuilding(true); setError('')
    try {
      const body: any = {
        template_name: selectedTemplate, contract_name: contractName,
        contract_address: contractAddress, chain,
      }
      if (abiJson.trim()) body.abi_json = abiJson
      const resp = await fetch(`${API_URL}/dapp/build`, {
        method: 'POST', headers: headers(), body: JSON.stringify(body)
      })
      if (!resp.ok) { const d = await resp.json(); setError(d.detail || 'Build failed'); setBuilding(false); return }
      setShowBuild(false); fetchData()
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

  return (
    <div className="min-h-screen bg-[#0A0A1B] text-white p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">DApp Factory</h1>
            <p className="text-gray-400 mt-1">Build downloadable React DApps from contract templates</p>
          </div>
          <button onClick={() => setShowBuild(true)}
            className="px-6 py-3 bg-orange-600 hover:bg-orange-700 rounded-lg font-semibold transition-colors">
            Build DApp
          </button>
        </div>

        {/* Templates */}
        <h2 className="text-lg font-semibold text-gray-300 mb-3">Templates</h2>
        <div className="grid grid-cols-4 gap-4 mb-8">
          {templates.map(t => (
            <div key={t.id} className="bg-[#1A1A2E] rounded-xl p-4 border border-gray-700">
              <h3 className="font-semibold">{t.name}</h3>
              <p className="text-gray-400 text-sm mt-1">{t.description}</p>
            </div>
          ))}
          {templates.length === 0 && !loading && (
            <p className="text-gray-500 col-span-4">No templates loaded</p>
          )}
        </div>

        {/* Build Modal */}
        {showBuild && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
            <div className="bg-[#1A1A2E] rounded-2xl p-6 max-w-lg w-full">
              <h2 className="text-xl font-bold mb-4">Build DApp</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Template</label>
                  <select value={selectedTemplate} onChange={e => setSelectedTemplate(e.target.value)}
                    className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-2.5 focus:border-orange-500 focus:outline-none">
                    <option value="">Select template</option>
                    {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                    <option value="simple-dashboard">Simple Dashboard</option>
                    <option value="token-manager">Token Manager</option>
                    <option value="staking-ui">Staking UI</option>
                    <option value="governance-voting">Governance Voting</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Contract Name</label>
                    <input value={contractName} onChange={e => setContractName(e.target.value)}
                      className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-2.5 focus:border-orange-500 focus:outline-none" />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Chain</label>
                    <select value={chain} onChange={e => setChain(e.target.value)}
                      className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-2.5 focus:border-orange-500 focus:outline-none">
                      {CHAINS.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Contract Address</label>
                  <input value={contractAddress} onChange={e => setContractAddress(e.target.value)}
                    placeholder="0x..."
                    className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-2.5 focus:border-orange-500 focus:outline-none" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">ABI JSON (optional)</label>
                  <textarea value={abiJson} onChange={e => setAbiJson(e.target.value)}
                    className="w-full bg-[#0A0A1B] border border-gray-700 rounded-lg p-2.5 text-sm font-mono h-24 focus:border-orange-500 focus:outline-none"
                    placeholder="[{...}]" />
                </div>
              </div>
              {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
              <div className="flex gap-3 mt-6">
                <button onClick={buildDapp} disabled={building || !selectedTemplate || !contractName || !contractAddress}
                  className="px-6 py-2.5 bg-orange-600 hover:bg-orange-700 disabled:opacity-50 rounded-lg font-semibold transition-colors">
                  {building ? 'Building...' : 'Build'}
                </button>
                <button onClick={() => { setShowBuild(false); setError('') }}
                  className="px-6 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">Cancel</button>
              </div>
            </div>
          </div>
        )}

        {/* Builds */}
        <h2 className="text-lg font-semibold text-gray-300 mb-3">Your Builds</h2>
        {builds.length === 0 && !loading && <p className="text-gray-500">No builds yet</p>}
        <div className="space-y-3">
          {builds.map(b => {
            const config = JSON.parse(b.config_json || '{}')
            return (
              <div key={b.id} className="bg-[#1A1A2E] rounded-xl p-4 border border-gray-700 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <span className="font-semibold">{config.contract_name || 'DApp'}</span>
                    <span className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300">{b.template_name}</span>
                    <span className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300">{config.chain || '?'}</span>
                    {b.validation_status && (
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        b.validation_status === 'passed' ? 'bg-green-500/20 text-green-400' :
                        b.validation_status === 'failed' ? 'bg-red-500/20 text-red-400' :
                        'bg-yellow-500/20 text-yellow-400'
                      }`}>{b.validation_status}</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{new Date(b.created_at).toLocaleString()}</p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => validateBuild(b.id)}
                    className="px-3 py-1.5 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded-lg text-sm transition-colors">
                    Validate
                  </button>
                  <button onClick={() => downloadBuild(b.id)}
                    className="px-3 py-1.5 bg-green-600/20 text-green-400 hover:bg-green-600/30 rounded-lg text-sm transition-colors">
                    Download
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
