'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'

const FALLBACK_CHAINS = ['ethereum', 'base', 'arbitrum', 'polygon', 'optimism', 'sepolia']
const LANGUAGES = ['solidity', 'vyper', 'rust', 'move']

const CHAIN_COLORS: Record<string, string> = {
  ethereum: '#627EEA', base: '#0052FF', arbitrum: '#28A0F0',
  polygon: '#8247E5', solana: '#14F195', 'multi-chain': 'var(--refi-teal)',
}

const STATUS_COLORS: Record<string, string> = {
  draft: '#6B7280', parsed: '#3B82F6', published: '#10B981', archived: '#EF4444',
}

function ChainBadge({ chain }: { chain: string }) {
  return (
    <span style={{
      fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
      padding: '2px 6px', borderRadius: 4,
      background: `${CHAIN_COLORS[chain] || '#6B7280'}20`,
      color: CHAIN_COLORS[chain] || '#6B7280',
      fontWeight: 600, textTransform: 'uppercase',
    }}>
      {chain}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span style={{
      fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
      padding: '2px 6px', borderRadius: 4,
      background: `${STATUS_COLORS[status] || '#6B7280'}20`,
      color: STATUS_COLORS[status] || '#6B7280',
      fontWeight: 600, textTransform: 'uppercase',
    }}>
      {status}
    </span>
  )
}

function AccessBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    public: '#10B981', owner: '#F59E0B', admin: '#EF4444',
    role_based: '#8B5CF6', unknown: '#6B7280',
  }
  return (
    <span style={{
      fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
      padding: '2px 6px', borderRadius: 4,
      background: `${colors[level] || '#6B7280'}20`,
      color: colors[level] || '#6B7280',
      fontWeight: 600,
    }}>
      {level}
    </span>
  )
}

export default function RepoPage() {
  const [repo, setRepo] = useState<any>(null)
  const [contracts, setContracts] = useState<any[]>([])
  const [repoExists, setRepoExists] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [selectedContract, setSelectedContract] = useState<any>(null)
  const [functions, setFunctions] = useState<any[]>([])
  const [events, setEvents] = useState<any[]>([])
  const [sdk, setSdk] = useState<any>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
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

  // Import from block explorer
  const [showImport, setShowImport] = useState(false)
  const [importAddress, setImportAddress] = useState('')
  const [importChain, setImportChain] = useState('ethereum')
  const [importing, setImporting] = useState(false)

  // Function testing (cag_execute)
  const [testFn, setTestFn] = useState<string | null>(null)
  const [testArgs, setTestArgs] = useState('')
  const [testResult, setTestResult] = useState<any>(null)
  const [testing, setTesting] = useState(false)

  // Upload form state
  const [uploadName, setUploadName] = useState('')
  const [uploadChain, setUploadChain] = useState('ethereum')
  const [uploadLanguage, setUploadLanguage] = useState('solidity')
  const [uploadABI, setUploadABI] = useState('')
  const [uploadSource, setUploadSource] = useState('')
  const [uploadAddress, setUploadAddress] = useState('')
  const [uploadDescription, setUploadDescription] = useState('')
  const [uploadTags, setUploadTags] = useState('')

  const headers = () => {
    const token = localStorage.getItem('refinet_token')
    const h: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) h.Authorization = `Bearer ${token}`
    return h
  }

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    
    loadRepo()
  }, [])

  async function loadRepo() {
    try {
      const resp = await fetch(`${API_URL}/repo/me`, { headers: headers() })
      if (resp.ok) {
        const data = await resp.json()
        setRepo(data)
        setRepoExists(true)
        loadContracts()
      } else if (resp.status === 404) {
        setRepoExists(false)
      }
    } catch {
      setRepoExists(false)
    }
    setLoading(false)
  }

  async function loadContracts() {
    try {
      const resp = await fetch(`${API_URL}/repo/contracts?page_size=50`, { headers: headers() })
      if (resp.ok) {
        const data = await resp.json()
        setContracts(data.items || [])
      }
    } catch {}
  }

  async function initRepo() {
    try {
      const resp = await fetch(`${API_URL}/repo/init`, {
        method: 'POST', headers: headers(), body: JSON.stringify({}),
      })
      if (resp.ok) {
        setMessage('Repository initialized!')
        loadRepo()
      } else {
        const data = await resp.json()
        setError(data.detail || 'Failed to initialize repository')
      }
    } catch { setError('Network error') }
  }

  async function uploadContract() {
    setError('')
    setMessage('')

    if (!uploadName.trim() || !uploadABI.trim()) {
      setError('Name and ABI JSON are required')
      return
    }

    try {
      JSON.parse(uploadABI)
    } catch {
      setError('Invalid ABI JSON format')
      return
    }

    const body: any = {
      name: uploadName, chain: uploadChain, language: uploadLanguage,
      abi_json: uploadABI,
    }
    if (uploadSource.trim()) body.source_code = uploadSource
    if (uploadAddress.trim()) body.address = uploadAddress
    if (uploadDescription.trim()) body.description = uploadDescription
    if (uploadTags.trim()) body.tags = uploadTags.split(',').map(t => t.trim()).filter(Boolean)

    try {
      const resp = await fetch(`${API_URL}/repo/contracts`, {
        method: 'POST', headers: headers(), body: JSON.stringify(body),
      })
      const data = await resp.json()
      if (resp.ok) {
        setMessage(`Contract "${uploadName}" uploaded!`)
        setShowUpload(false)
        setUploadName(''); setUploadABI(''); setUploadSource('')
        setUploadAddress(''); setUploadDescription(''); setUploadTags('')
        loadContracts()
      } else {
        setError(data.detail || 'Upload failed')
      }
    } catch { setError('Network error') }
  }

  async function parseContract(slug: string) {
    setMessage(''); setError('')
    try {
      const resp = await fetch(`${API_URL}/repo/contracts/${slug}/parse`, {
        method: 'POST', headers: headers(), body: '{}',
      })
      const data = await resp.json()
      if (resp.ok) {
        setMessage(`Parsed: ${data.function_count} functions, ${data.event_count} events`)
        loadContracts()
        if (selectedContract?.slug === slug) loadContractDetails(slug)
      } else {
        setError(data.detail?.message || data.detail || 'Parse failed')
      }
    } catch { setError('Network error') }
  }

  async function toggleVisibility(slug: string, isPublic: boolean) {
    try {
      const resp = await fetch(`${API_URL}/repo/contracts/${slug}/visibility`, {
        method: 'PUT', headers: headers(),
        body: JSON.stringify({ is_public: isPublic }),
      })
      const data = await resp.json()
      if (resp.ok) {
        setMessage(data.message)
        loadContracts()
        if (selectedContract?.slug === slug) {
          setSelectedContract({ ...selectedContract, is_public: isPublic })
        }
      } else {
        setError(data.detail || 'Failed to toggle visibility')
      }
    } catch { setError('Network error') }
  }

  async function loadContractDetails(slug: string) {
    try {
      const [detailResp, fnResp, evtResp] = await Promise.all([
        fetch(`${API_URL}/repo/contracts/${slug}/detail`, { headers: headers() }),
        fetch(`${API_URL}/repo/contracts/${slug}/functions`, { headers: headers() }),
        fetch(`${API_URL}/repo/contracts/${slug}/events`, { headers: headers() }),
      ])

      if (detailResp.ok) setSelectedContract(await detailResp.json())
      if (fnResp.ok) setFunctions(await fnResp.json())
      if (evtResp.ok) setEvents(await evtResp.json())

      // Try to load SDK
      try {
        const sdkResp = await fetch(`${API_URL}/repo/contracts/${slug}/sdk`, { headers: headers() })
        if (sdkResp.ok) setSdk(await sdkResp.json())
        else setSdk(null)
      } catch { setSdk(null) }
    } catch {}
  }

  async function toggleFunction(slug: string, fnId: string, isEnabled: boolean) {
    try {
      await fetch(`${API_URL}/repo/contracts/${slug}/functions/${fnId}/toggle`, {
        method: 'PUT', headers: headers(),
        body: JSON.stringify({ is_sdk_enabled: isEnabled }),
      })
      loadContractDetails(slug)
    } catch {}
  }

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto py-20 text-center">
        <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)', fontSize: 14 }}>
          Loading repository...
        </span>
      </div>
    )
  }

  // Repo not initialized
  if (repoExists === false) {
    return (
      <div className="max-w-2xl mx-auto py-20 text-center space-y-6">
        <h1 className="text-3xl font-bold">
          Contract <span style={{ color: 'var(--refi-teal)' }}>Repository</span>
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
          Initialize your private contract namespace to upload smart contracts,
          parse ABIs, and publish SDKs to GROOT's brain.
        </p>
        <button onClick={initRepo} className="btn-primary">
          Initialize Repository
        </button>
        {error && <p style={{ color: '#EF4444', fontSize: 13 }}>{error}</p>}
        {message && <p style={{ color: '#10B981', fontSize: 13 }}>{message}</p>}
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto py-10 px-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            @{repo?.namespace} <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>contracts</span>
          </h1>
          {repo?.bio && <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>{repo.bio}</p>}
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4, fontFamily: "'JetBrains Mono', monospace" }}>
            {repo?.total_contracts || 0} contracts &middot; {repo?.total_public || 0} public
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowImport(!showImport)} className="btn-secondary !py-2 !px-4 !text-sm">
            Import from Explorer
          </button>
          <button onClick={() => setShowUpload(!showUpload)} className="btn-primary !py-2 !px-4 !text-sm">
            + Upload Contract
          </button>
        </div>
      </div>

      {/* Messages */}
      {message && <div className="card" style={{ padding: 12, background: '#10B98120', color: '#10B981', fontSize: 13 }}>{message}</div>}
      {error && <div className="card" style={{ padding: 12, background: '#EF444420', color: '#EF4444', fontSize: 13 }}>{error}</div>}

      {/* Import from Block Explorer */}
      {showImport && (
        <div className="card" style={{ padding: 24 }}>
          <h2 className="font-bold mb-4" style={{ fontSize: 16 }}>Import from Block Explorer</h2>
          <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 12 }}>
            Paste a verified contract address and GROOT will fetch the ABI automatically.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="col-span-2">
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Contract Address *</label>
              <input value={importAddress} onChange={e => setImportAddress(e.target.value)} className="input-base w-full"
                placeholder="0x..." style={{ fontFamily: "'JetBrains Mono', monospace" }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Chain</label>
              <select value={importChain} onChange={e => setImportChain(e.target.value)} className="input-base w-full">
                {['ethereum', 'base', 'polygon', 'arbitrum', 'optimism', 'sepolia'].map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-3">
            <button onClick={async () => {
              if (!importAddress || importAddress.length !== 42) { setError('Enter a valid 42-character address'); return }
              setImporting(true); setError('')
              try {
                const resp = await fetch(`${API_URL}/explore/fetch-abi?address=${importAddress}&chain=${importChain}`, { headers: { Authorization: `Bearer ${localStorage.getItem('refinet_token')}` } })
                const data = await resp.json()
                if (!data.success) { setError(data.error || 'ABI not available — contract may not be verified'); setImporting(false); return }
                // Pre-fill the upload form with fetched data
                setUploadABI(JSON.stringify(data.abi, null, 2))
                setUploadAddress(importAddress)
                setUploadChain(importChain)
                setUploadName(importAddress.slice(0, 10) + '...')
                setShowImport(false)
                setShowUpload(true)
                setMessage(`Fetched ABI: ${data.function_count} functions, ${data.event_count} events. Review and submit.`)
              } catch (e: any) { setError(e.message) }
              setImporting(false)
            }} disabled={importing} className="btn-primary !py-2 !px-6 !text-sm">
              {importing ? 'Fetching...' : 'Fetch ABI'}
            </button>
            <button onClick={() => setShowImport(false)} className="btn-secondary !py-2 !px-4 !text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Upload Form */}
      {showUpload && (
        <div className="card" style={{ padding: 24 }}>
          <h2 className="font-bold mb-4" style={{ fontSize: 16 }}>Upload Smart Contract</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Contract Name *</label>
              <input value={uploadName} onChange={e => setUploadName(e.target.value)} className="input-base w-full" placeholder="MyToken" />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Chain</label>
              <select value={uploadChain} onChange={e => setUploadChain(e.target.value)} className="input-base w-full">
                {chains.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Language</label>
              <select value={uploadLanguage} onChange={e => setUploadLanguage(e.target.value)} className="input-base w-full">
                {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Contract Address</label>
              <input value={uploadAddress} onChange={e => setUploadAddress(e.target.value)} className="input-base w-full" placeholder="0x..." />
            </div>
          </div>
          <div className="mb-4">
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Description</label>
            <input value={uploadDescription} onChange={e => setUploadDescription(e.target.value)} className="input-base w-full" placeholder="What does this contract do?" />
          </div>
          <div className="mb-4">
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Tags (comma-separated)</label>
            <input value={uploadTags} onChange={e => setUploadTags(e.target.value)} className="input-base w-full" placeholder="defi, token, erc20" />
          </div>
          <div className="mb-4">
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>ABI JSON *</label>
            <textarea value={uploadABI} onChange={e => setUploadABI(e.target.value)} className="input-base w-full" rows={6}
              style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}
              placeholder='[{"type":"function","name":"transfer","inputs":[...],...}]' />
          </div>
          <div className="mb-4">
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
              Source Code (optional, kept private — GROOT never sees this)
            </label>
            <textarea value={uploadSource} onChange={e => setUploadSource(e.target.value)} className="input-base w-full" rows={6}
              style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}
              placeholder="// SPDX-License-Identifier: MIT&#10;pragma solidity ^0.8.0;&#10;..." />
          </div>
          <div className="flex gap-3">
            <button onClick={uploadContract} className="btn-primary !py-2 !px-6 !text-sm">Upload</button>
            <button onClick={() => setShowUpload(false)} className="btn-secondary !py-2 !px-4 !text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Contract List & Detail View */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Contract List */}
        <div className="space-y-3">
          <h2 className="font-bold" style={{ fontSize: 14, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Your Contracts
          </h2>
          {contracts.length === 0 ? (
            <p style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>No contracts yet. Upload one above.</p>
          ) : (
            contracts.map(c => (
              <div
                key={c.id}
                className="card cursor-pointer transition-all"
                style={{
                  padding: 14,
                  borderLeft: selectedContract?.id === c.id ? '3px solid var(--refi-teal)' : '3px solid transparent',
                }}
                onClick={() => { setSelectedContract(c); loadContractDetails(c.slug) }}
                onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 0 12px var(--refi-teal-glow)')}
                onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
              >
                <div className="flex items-center justify-between mb-1">
                  <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--refi-teal)' }}>{c.name}</span>
                  <StatusBadge status={c.status} />
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <ChainBadge chain={c.chain} />
                  {c.is_public && (
                    <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: '#10B98120', color: '#10B981', fontWeight: 600 }}>
                      PUBLIC
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Right: Detail View */}
        <div className="lg:col-span-2">
          {selectedContract ? (
            <div className="space-y-4">
              {/* Contract Header */}
              <div className="card" style={{ padding: 20 }}>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xl font-bold">{selectedContract.name}</h2>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={selectedContract.status} />
                    <ChainBadge chain={selectedContract.chain} />
                  </div>
                </div>
                {selectedContract.description && (
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>{selectedContract.description}</p>
                )}
                {selectedContract.address && (
                  <p style={{ fontSize: 12, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
                    Address: {selectedContract.address}
                  </p>
                )}
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={() => parseContract(selectedContract.slug)}
                    className="btn-primary !py-1.5 !px-4 !text-xs"
                  >
                    Parse ABI
                  </button>
                  {selectedContract.status !== 'draft' && (
                    <button
                      onClick={() => toggleVisibility(selectedContract.slug, !selectedContract.is_public)}
                      className="btn-secondary !py-1.5 !px-4 !text-xs"
                    >
                      {selectedContract.is_public ? 'Make Private' : 'Publish to GROOT'}
                    </button>
                  )}
                </div>
              </div>

              {/* Functions */}
              {functions.length > 0 && (
                <div className="card" style={{ padding: 20 }}>
                  <h3 className="font-bold mb-3" style={{ fontSize: 14 }}>
                    Functions ({functions.length})
                  </h3>
                  <div className="space-y-2">
                    {functions.map(fn => (
                      <div key={fn.id}>
                      <div className="flex items-center justify-between" style={{
                        padding: '8px 12px', borderRadius: 6, background: 'var(--bg-secondary)',
                      }}>
                        <div className="flex items-center gap-2">
                          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: 'var(--text-primary)' }}>
                            {fn.signature || fn.function_name}
                          </span>
                          <AccessBadge level={fn.access_level} />
                          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{fn.state_mutability}</span>
                          {fn.is_dangerous && (
                            <span style={{ fontSize: 10, padding: '1px 4px', borderRadius: 3, background: '#EF444420', color: '#EF4444' }}>
                              DANGEROUS
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {(fn.state_mutability === 'view' || fn.state_mutability === 'pure') && selectedContract?.address && (
                            <button onClick={() => { setTestFn(testFn === fn.function_name ? null : fn.function_name); setTestArgs(''); setTestResult(null) }}
                              style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, background: '#3B82F620', color: '#3B82F6', cursor: 'pointer', border: 'none' }}>
                              {testFn === fn.function_name ? 'Close' : 'Test'}
                            </button>
                          )}
                          <label className="flex items-center gap-1 cursor-pointer" style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                            <input
                              type="checkbox"
                              checked={fn.is_sdk_enabled}
                              onChange={() => toggleFunction(selectedContract.slug, fn.id, !fn.is_sdk_enabled)}
                            />
                            SDK
                          </label>
                        </div>
                      </div>
                      {/* Inline function test panel */}
                      {testFn === fn.function_name && selectedContract?.address && (
                        <div style={{ padding: '8px 12px', borderRadius: 6, background: '#3B82F610', border: '1px solid #3B82F630', marginTop: 2 }}>
                          <div className="flex gap-2 items-center">
                            <input value={testArgs} onChange={e => setTestArgs(e.target.value)}
                              placeholder='Args (JSON array): [1000, "0x..."]'
                              style={{ flex: 1, fontFamily: "'JetBrains Mono', monospace", fontSize: 11, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 4, padding: '4px 8px' }} />
                            <button disabled={testing} onClick={async () => {
                              setTesting(true); setTestResult(null)
                              try {
                                let args: any[] = []
                                if (testArgs.trim()) args = JSON.parse(testArgs)
                                const resp = await fetch(`${API_URL}/explore/cag/execute`, {
                                  method: 'POST',
                                  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('refinet_token')}` },
                                  body: JSON.stringify({ contract_address: selectedContract.address, chain: selectedContract.chain, function_name: fn.function_name, args }),
                                })
                                setTestResult(await resp.json())
                              } catch (e: any) { setTestResult({ success: false, error: e.message }) }
                              setTesting(false)
                            }} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 4, background: '#3B82F6', color: 'white', border: 'none', cursor: 'pointer', opacity: testing ? 0.5 : 1 }}>
                              {testing ? 'Calling...' : 'Call'}
                            </button>
                          </div>
                          {testResult && (
                            <div style={{ marginTop: 6, fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
                              {testResult.success ? (
                                <div style={{ color: '#10B981' }}>Result: {JSON.stringify(testResult.result)}</div>
                              ) : (
                                <div style={{ color: '#EF4444' }}>Error: {testResult.error}</div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Events */}
              {events.length > 0 && (
                <div className="card" style={{ padding: 20 }}>
                  <h3 className="font-bold mb-3" style={{ fontSize: 14 }}>
                    Events ({events.length})
                  </h3>
                  <div className="space-y-2">
                    {events.map(evt => (
                      <div key={evt.id} style={{
                        padding: '8px 12px', borderRadius: 6, background: 'var(--bg-secondary)',
                        fontFamily: "'JetBrains Mono', monospace", fontSize: 12,
                      }}>
                        {evt.signature || evt.event_name}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* SDK Viewer */}
              {sdk && (
                <div className="card" style={{ padding: 20 }}>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-bold" style={{ fontSize: 14 }}>
                      SDK Definition {sdk.is_public && <span style={{ color: '#10B981', fontWeight: 400 }}>(public — visible to GROOT)</span>}
                    </h3>
                    <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
                      v{sdk.sdk_version}
                    </span>
                  </div>
                  <pre style={{
                    fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
                    background: 'var(--bg-tertiary)', padding: 16, borderRadius: 8,
                    overflowX: 'auto', maxHeight: 400, lineHeight: 1.5,
                    color: 'var(--text-secondary)',
                  }}>
                    {typeof sdk.sdk_json === 'string'
                      ? JSON.stringify(JSON.parse(sdk.sdk_json), null, 2)
                      : JSON.stringify(sdk.sdk_json, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="card text-center" style={{ padding: 40 }}>
              <p style={{ color: 'var(--text-tertiary)', fontSize: 14 }}>
                Select a contract to view details, parse its ABI, and manage its SDK
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
