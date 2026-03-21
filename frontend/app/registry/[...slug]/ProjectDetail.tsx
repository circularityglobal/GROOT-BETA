'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

const TABS = ['README', 'ABIs', 'SDKs', 'Execution Logic', 'Settings']

export default function ProjectDetailPage({ params }: { params: { slug: string[] } }) {
  const router = useRouter()
  const slug = params.slug?.join('/') || ''
  const [project, setProject] = useState<any>(null)
  const [abis, setAbis] = useState<any[]>([])
  const [sdks, setSdks] = useState<any[]>([])
  const [logic, setLogic] = useState<any[]>([])
  const [activeTab, setActiveTab] = useState('README')
  const [loading, setLoading] = useState(true)
  const [isOwner, setIsOwner] = useState(false)
  const [expandedAbi, setExpandedAbi] = useState<string | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    if (!slug) return

    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}

    Promise.all([
      fetch(`${API_URL}/registry/projects/${slug}`, { headers }).then(r => r.ok ? r.json() : null),
      fetch(`${API_URL}/registry/projects/${slug}/abis`, { headers }).then(r => r.ok ? r.json() : []),
      fetch(`${API_URL}/registry/projects/${slug}/sdks`, { headers }).then(r => r.ok ? r.json() : []),
      fetch(`${API_URL}/registry/projects/${slug}/logic`, { headers }).then(r => r.ok ? r.json() : []),
      fetch(`${API_URL}/auth/me`, { headers }).then(r => r.ok ? r.json() : null),
    ]).then(([proj, a, s, l, me]) => {
      setProject(proj)
      setAbis(Array.isArray(a) ? a : [])
      setSdks(Array.isArray(s) ? s : [])
      setLogic(Array.isArray(l) ? l : [])
      if (proj && me) setIsOwner(proj.owner_id === me.id)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [slug])

  const handleStar = async () => {
    const token = localStorage.getItem('refinet_token')
    if (!token || !project) return
    const resp = await fetch(`${API_URL}/registry/projects/${slug}/star`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.ok) {
      const data = await resp.json()
      setProject({ ...project, is_starred: data.starred, stars_count: data.stars_count })
    }
  }

  const handleFork = async () => {
    const token = localStorage.getItem('refinet_token')
    if (!token) return
    const resp = await fetch(`${API_URL}/registry/projects/${slug}/fork`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.ok) {
      const data = await resp.json()
      router.push(`/registry/${data.slug}/`)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)', fontSize: 14 }}>
          Loading project...
        </span>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="max-w-3xl mx-auto py-20 px-6 text-center">
        <h1 className="text-2xl font-bold mb-4">Project Not Found</h1>
        <p style={{ color: 'var(--text-secondary)' }}>The project "{slug}" doesn't exist or is private.</p>
        <Link href="/explore/" className="btn-primary mt-6 inline-block" style={{ textDecoration: 'none' }}>Back to Registry</Link>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto py-10 px-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link href={`/u/${project.owner_username}/`} style={{ fontSize: 14, color: 'var(--refi-teal)', textDecoration: 'none' }}
              onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
              onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
            >
              {project.owner_username}
            </Link>
            <span style={{ color: 'var(--text-tertiary)' }}>/</span>
            <h1 className="text-xl font-bold" style={{ letterSpacing: '-0.02em' }}>{project.name}</h1>
            <span style={{
              fontSize: 10, padding: '1px 6px', borderRadius: 10,
              border: '1px solid var(--border-subtle)', color: 'var(--text-tertiary)',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {project.visibility}
            </span>
          </div>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', maxWidth: 600 }}>{project.description}</p>
          <div className="flex items-center gap-2 mt-2">
            <span style={{
              fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
              padding: '2px 6px', borderRadius: 4,
              background: 'rgba(92,224,210,0.12)', color: 'var(--refi-teal)',
            }}>
              {project.chain}
            </span>
            <span style={{
              fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
              padding: '2px 6px', borderRadius: 4,
              background: 'var(--bg-tertiary)', color: 'var(--text-secondary)',
            }}>
              {project.category}
            </span>
            {project.tags?.map((tag: string) => (
              <span key={tag} style={{
                fontSize: 10, padding: '2px 6px', borderRadius: 4,
                background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)',
              }}>
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button onClick={handleStar} className="btn-secondary !py-1.5 !px-3 !text-xs flex items-center gap-1.5">
            <svg width="14" height="14" viewBox="0 0 24 24" fill={project.is_starred ? 'var(--refi-teal)' : 'none'} stroke="var(--refi-teal)" strokeWidth="2">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            {project.is_starred ? 'Starred' : 'Star'} ({project.stars_count})
          </button>
          <button onClick={handleFork} className="btn-secondary !py-1.5 !px-3 !text-xs flex items-center gap-1.5">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/>
              <path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9"/><line x1="12" y1="12" x2="12" y2="15"/>
            </svg>
            Fork ({project.forks_count})
          </button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-6" style={{ fontSize: 12, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
        <span>{project.abi_count || abis.length} ABIs</span>
        <span>{project.sdk_count || sdks.length} SDKs</span>
        <span>{project.logic_count || logic.length} Logic</span>
        {project.license && <span>License: {project.license}</span>}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 overflow-x-auto" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        {TABS.filter(t => t !== 'Settings' || isOwner).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-4 py-2.5 text-[13px] font-medium transition-colors whitespace-nowrap"
            style={{
              color: activeTab === tab ? 'var(--refi-teal)' : 'var(--text-secondary)',
              borderBottom: activeTab === tab ? '2px solid var(--refi-teal)' : '2px solid transparent',
              background: 'transparent',
              cursor: 'pointer',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[300px]">
        {activeTab === 'README' && (
          <div className="card" style={{ padding: 24 }}>
            {project.readme ? (
              <div style={{ fontSize: 14, lineHeight: 1.8, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
                {project.readme}
              </div>
            ) : (
              <p style={{ color: 'var(--text-tertiary)', fontSize: 14 }}>No README provided.</p>
            )}
          </div>
        )}

        {activeTab === 'ABIs' && (
          <div className="space-y-3">
            {abis.length === 0 ? (
              <p style={{ color: 'var(--text-tertiary)', fontSize: 14 }}>No ABIs added yet.</p>
            ) : (
              abis.map((abi: any) => (
                <div key={abi.id} className="card" style={{ padding: 16 }}>
                  <div className="flex items-center justify-between cursor-pointer"
                    onClick={() => setExpandedAbi(expandedAbi === abi.id ? null : abi.id)}
                  >
                    <div className="flex items-center gap-3">
                      <span style={{ fontSize: 14, fontWeight: 600 }}>{abi.contract_name}</span>
                      <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", padding: '2px 6px', borderRadius: 4, background: 'rgba(92,224,210,0.12)', color: 'var(--refi-teal)' }}>
                        {abi.chain}
                      </span>
                      {abi.is_verified && (
                        <span style={{ fontSize: 10, color: 'var(--success)', fontWeight: 600 }}>VERIFIED</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                      {abi.contract_address && (
                        <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                          {abi.contract_address.slice(0, 6)}...{abi.contract_address.slice(-4)}
                        </span>
                      )}
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                        style={{ transform: expandedAbi === abi.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </div>
                  </div>
                  {expandedAbi === abi.id && (
                    <div style={{ marginTop: 12 }}>
                      <AbiViewer abiId={abi.id} />
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'SDKs' && (
          <div className="space-y-3">
            {sdks.length === 0 ? (
              <p style={{ color: 'var(--text-tertiary)', fontSize: 14 }}>No SDKs added yet.</p>
            ) : (
              sdks.map((sdk: any) => (
                <div key={sdk.id} className="card" style={{ padding: 16 }}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span style={{ fontSize: 14, fontWeight: 600 }}>{sdk.name}</span>
                      <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", padding: '2px 6px', borderRadius: 4, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
                        {sdk.language}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>v{sdk.version}</span>
                    </div>
                  </div>
                  {sdk.install_command && (
                    <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 6, background: 'var(--bg-secondary)', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: 'var(--refi-teal)' }}>
                      $ {sdk.install_command}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'Execution Logic' && (
          <div className="space-y-3">
            {logic.length === 0 ? (
              <p style={{ color: 'var(--text-tertiary)', fontSize: 14 }}>No execution logic added yet.</p>
            ) : (
              logic.map((l: any) => (
                <div key={l.id} className="card" style={{ padding: 16 }}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span style={{ fontSize: 14, fontWeight: 600 }}>{l.name}</span>
                      <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", padding: '2px 6px', borderRadius: 4, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
                        {l.logic_type}
                      </span>
                      {l.is_verified && (
                        <span style={{ fontSize: 10, color: 'var(--success)', fontWeight: 600 }}>VERIFIED</span>
                      )}
                      {l.is_read_only && (
                        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>view</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3" style={{ fontSize: 12, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
                      {l.gas_estimate && <span>{l.gas_estimate} gas</span>}
                      <span>{l.execution_count} calls</span>
                    </div>
                  </div>
                  {l.function_signature && (
                    <div style={{ marginTop: 8, fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: 'var(--refi-teal)' }}>
                      {l.function_signature}
                    </div>
                  )}
                  {l.description && (
                    <p style={{ marginTop: 6, fontSize: 13, color: 'var(--text-secondary)' }}>{l.description}</p>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'Settings' && isOwner && (
          <div className="card" style={{ padding: 24 }}>
            <h3 className="font-bold mb-4">Project Settings</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              Edit your project settings, manage ABIs, SDKs, and execution logic from this panel.
            </p>
            <div className="mt-6 space-y-4">
              <Link href={`/registry/new/?edit=${slug}`} className="btn-primary !py-2 !px-4 !text-sm inline-block" style={{ textDecoration: 'none' }}>
                Edit Project
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const _abiCache: Record<string, any> = {}

function AbiViewer({ abiId }: { abiId: string }) {
  const [abiData, setAbiData] = useState<any>(_abiCache[abiId] || null)
  const [loading, setLoading] = useState(!_abiCache[abiId])

  useEffect(() => {
    if (_abiCache[abiId]) { setAbiData(_abiCache[abiId]); setLoading(false); return }
    fetch(`${API_URL}/registry/abis/${abiId}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { _abiCache[abiId] = data; setAbiData(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [abiId])

  if (loading) return <span className="animate-pulse" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Loading ABI...</span>
  if (!abiData) return <span style={{ fontSize: 12, color: 'var(--error)' }}>Failed to load ABI</span>

  let formatted = ''
  try { formatted = JSON.stringify(JSON.parse(abiData.abi_json), null, 2) }
  catch { formatted = abiData.abi_json }

  return (
    <pre style={{
      fontSize: 11, fontFamily: "'JetBrains Mono', monospace",
      background: 'var(--bg-secondary)', padding: 16, borderRadius: 8,
      overflow: 'auto', maxHeight: 400, color: 'var(--text-secondary)',
      lineHeight: 1.5,
    }}>
      {formatted}
    </pre>
  )
}
