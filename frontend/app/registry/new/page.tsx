'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

const CATEGORIES = ['defi', 'token', 'governance', 'bridge', 'utility', 'oracle', 'nft', 'dao', 'sdk', 'library']
const CHAINS = ['ethereum', 'base', 'arbitrum', 'polygon', 'solana', 'multi-chain']

export default function NewProjectPage() {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [readme, setReadme] = useState('')
  const [visibility, setVisibility] = useState('public')
  const [category, setCategory] = useState('utility')
  const [chain, setChain] = useState('ethereum')
  const [license, setLicense] = useState('')
  const [tags, setTags] = useState('')
  const [abiName, setAbiName] = useState('')
  const [abiJson, setAbiJson] = useState('')
  const [abiAddress, setAbiAddress] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    if (!token) window.location.href = '/settings/'
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)

    const token = localStorage.getItem('refinet_token')
    if (!token) { window.location.href = '/settings/'; return }

    // Validate ABI JSON if provided
    if (abiJson) {
      try {
        const parsed = JSON.parse(abiJson)
        if (!Array.isArray(parsed)) {
          setError('ABI JSON must be a JSON array'); setSubmitting(false); return
        }
      } catch {
        setError('Invalid ABI JSON — must be valid JSON'); setSubmitting(false); return
      }
    }

    try {
      // Create project
      const projResp = await fetch(`${API_URL}/registry/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name,
          description: description || null,
          readme: readme || null,
          visibility,
          category,
          chain,
          license: license || null,
          tags: tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : null,
        }),
      })

      if (!projResp.ok) {
        const data = await projResp.json()
        throw new Error(data.detail || 'Failed to create project')
      }

      const project = await projResp.json()

      // If ABI provided, add it
      if (abiName && abiJson) {
        const abiResp = await fetch(`${API_URL}/registry/projects/${project.slug}/abis`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            contract_name: abiName,
            abi_json: abiJson,
            contract_address: abiAddress || null,
            chain,
          }),
        })
        if (!abiResp.ok) {
          const abiErr = await abiResp.json().catch(() => ({}))
          // Project created but ABI failed — still redirect but warn
          console.warn('ABI upload failed:', abiErr.detail || 'unknown error')
        }
      }

      window.location.href = `/registry/${project.slug}/`
    } catch (err: any) {
      setError(err.message || 'An error occurred')
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto py-10 px-6">
      <h1 className="text-2xl font-bold mb-1" style={{ letterSpacing: '-0.02em' }}>
        Create New <span style={{ color: 'var(--refi-teal)' }}>Project</span>
      </h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 32 }}>
        Publish smart contract ABIs, SDKs, and execution logic to the registry
      </p>

      {error && (
        <div style={{
          padding: '12px 16px', borderRadius: 8, marginBottom: 24,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
          color: '#EF4444', fontSize: 13,
        }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Project Name */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
            Project Name *
          </label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. staking-pool"
            required
            className="input-base focus-glow w-full"
            style={{ fontSize: 14 }}
          />
        </div>

        {/* Description */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
            Description
          </label>
          <input
            type="text"
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="A short description of your project"
            className="input-base focus-glow w-full"
            style={{ fontSize: 14 }}
          />
        </div>

        {/* Row: Visibility, Category, Chain */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
              Visibility
            </label>
            <select
              value={visibility}
              onChange={e => setVisibility(e.target.value)}
              className="input-base w-full"
              style={{ fontSize: 13 }}
            >
              <option value="public">Public</option>
              <option value="private">Private</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
              Category
            </label>
            <select
              value={category}
              onChange={e => setCategory(e.target.value)}
              className="input-base w-full"
              style={{ fontSize: 13 }}
            >
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
              Chain
            </label>
            <select
              value={chain}
              onChange={e => setChain(e.target.value)}
              className="input-base w-full"
              style={{ fontSize: 13 }}
            >
              {CHAINS.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        {/* Tags + License */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
              Tags (comma-separated)
            </label>
            <input
              type="text"
              value={tags}
              onChange={e => setTags(e.target.value)}
              placeholder="e.g. staking, yield, defi"
              className="input-base focus-glow w-full"
              style={{ fontSize: 14 }}
            />
          </div>
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
              License
            </label>
            <input
              type="text"
              value={license}
              onChange={e => setLicense(e.target.value)}
              placeholder="e.g. MIT, Apache-2.0"
              className="input-base focus-glow w-full"
              style={{ fontSize: 14 }}
            />
          </div>
        </div>

        {/* README */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 6 }}>
            README (Markdown)
          </label>
          <textarea
            value={readme}
            onChange={e => setReadme(e.target.value)}
            placeholder="Describe your project in detail..."
            rows={8}
            className="input-base focus-glow w-full"
            style={{ fontSize: 13, fontFamily: "'JetBrains Mono', monospace", resize: 'vertical' }}
          />
        </div>

        {/* ABI Section */}
        <div className="card" style={{ padding: 20 }}>
          <h3 className="font-bold mb-3" style={{ fontSize: 14 }}>
            Initial ABI <span style={{ fontWeight: 400, color: 'var(--text-tertiary)', fontSize: 12 }}>(optional)</span>
          </h3>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Contract Name
                </label>
                <input
                  type="text"
                  value={abiName}
                  onChange={e => setAbiName(e.target.value)}
                  placeholder="e.g. StakingPool"
                  className="input-base focus-glow w-full"
                  style={{ fontSize: 13 }}
                />
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Contract Address
                </label>
                <input
                  type="text"
                  value={abiAddress}
                  onChange={e => setAbiAddress(e.target.value)}
                  placeholder="0x..."
                  className="input-base focus-glow w-full"
                  style={{ fontSize: 13, fontFamily: "'JetBrains Mono', monospace" }}
                />
              </div>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                ABI JSON
              </label>
              <textarea
                value={abiJson}
                onChange={e => setAbiJson(e.target.value)}
                placeholder='Paste your ABI JSON here...'
                rows={6}
                className="input-base focus-glow w-full"
                style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", resize: 'vertical' }}
              />
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={!name || submitting}
            className="btn-primary !py-2.5 !px-6"
            style={{ opacity: (!name || submitting) ? 0.5 : 1 }}
          >
            {submitting ? 'Creating...' : 'Create Project'}
          </button>
          <Link href="/explore/" style={{ fontSize: 13, color: 'var(--text-secondary)', textDecoration: 'none' }}>
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
