'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

const CATEGORIES = ['all', 'defi', 'token', 'governance', 'bridge', 'utility', 'oracle', 'nft', 'dao', 'sdk', 'library']
const CHAINS = ['all', 'ethereum', 'base', 'arbitrum', 'polygon', 'solana', 'multi-chain']
const SORTS = [
  { value: 'stars', label: 'Most Stars' },
  { value: 'recent', label: 'Recently Updated' },
  { value: 'name', label: 'Name' },
]

const CHAIN_COLORS: Record<string, string> = {
  ethereum: '#627EEA',
  base: '#0052FF',
  arbitrum: '#28A0F0',
  polygon: '#8247E5',
  solana: '#14F195',
  'multi-chain': 'var(--refi-teal)',
}

const CATEGORY_COLORS: Record<string, string> = {
  defi: '#F59E0B',
  token: '#8B5CF6',
  governance: '#EC4899',
  bridge: '#06B6D4',
  utility: '#6B7280',
  oracle: '#F97316',
  nft: '#EF4444',
  dao: '#10B981',
  sdk: '#3B82F6',
  library: '#6366F1',
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

function CategoryBadge({ category }: { category: string }) {
  return (
    <span style={{
      fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
      padding: '2px 6px', borderRadius: 4,
      background: `${CATEGORY_COLORS[category] || '#6B7280'}20`,
      color: CATEGORY_COLORS[category] || '#6B7280',
      fontWeight: 600,
    }}>
      {category}
    </span>
  )
}

function StarIcon({ filled }: { filled?: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill={filled ? 'var(--refi-teal)' : 'none'} stroke="var(--refi-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  )
}

function ForkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/>
      <path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9"/><line x1="12" y1="12" x2="12" y2="15"/>
    </svg>
  )
}

function ProjectCard({ project }: { project: any }) {
  return (
    <Link
      href={`/registry/${project.slug}/`}
      className="card transition-all block"
      style={{ padding: 20, textDecoration: 'none' }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 0 20px var(--refi-teal-glow)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--refi-teal)' }}>
            {project.owner_username}/{project.name}
          </div>
        </div>
        <div className="flex items-center gap-3" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          <span className="flex items-center gap-1"><StarIcon />{project.stars_count}</span>
          <span className="flex items-center gap-1"><ForkIcon />{project.forks_count}</span>
        </div>
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12, lineHeight: 1.5 }}>
        {project.description ? (project.description.length > 120 ? project.description.slice(0, 120) + '...' : project.description) : 'No description'}
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        <ChainBadge chain={project.chain} />
        <CategoryBadge category={project.category} />
        {project.tags?.slice(0, 3).map((tag: string) => (
          <span key={tag} style={{
            fontSize: 10, padding: '2px 6px', borderRadius: 4,
            background: 'var(--bg-tertiary)', color: 'var(--text-secondary)',
          }}>
            {tag}
          </span>
        ))}
      </div>
    </Link>
  )
}

function SmartContractCard({ contract, isExpanded, onToggle }: { contract: any; isExpanded: boolean; onToggle: () => void }) {
  const [sdk, setSdk] = useState<any>(null)
  const [loadingSdk, setLoadingSdk] = useState(false)

  const loadSdk = async () => {
    if (sdk) return
    setLoadingSdk(true)
    try {
      const token = localStorage.getItem('refinet_token')
      const resp = await fetch(`${API_URL}/explore/contracts/${contract.id}/sdk`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (resp.ok) setSdk(await resp.json())
    } catch {}
    setLoadingSdk(false)
  }

  useEffect(() => { if (isExpanded) loadSdk() }, [isExpanded])

  return (
    <div
      className="card transition-all block cursor-pointer"
      style={{ padding: 20 }}
      onClick={onToggle}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 0 20px var(--refi-teal-glow)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--refi-teal)' }}>
            {contract.slug || contract.name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
            @{contract.owner_namespace}
          </div>
        </div>
        <div className="flex items-center gap-2" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
            {contract.function_count} fn
          </span>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
            {contract.event_count} evt
          </span>
          <span style={{ fontSize: 12, transform: isExpanded ? 'rotate(180deg)' : '', transition: 'transform 0.2s' }}>
            &#9660;
          </span>
        </div>
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12, lineHeight: 1.5 }}>
        {contract.description ? (contract.description.length > 120 ? contract.description.slice(0, 120) + '...' : contract.description) : 'No description'}
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        <ChainBadge chain={contract.chain} />
        <span style={{
          fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
          padding: '2px 6px', borderRadius: 4,
          background: '#3B82F620', color: '#3B82F6', fontWeight: 600,
        }}>
          {contract.language}
        </span>
        {contract.is_verified && (
          <span style={{
            fontSize: 10, padding: '2px 6px', borderRadius: 4,
            background: '#10B98120', color: '#10B981', fontWeight: 600,
          }}>
            VERIFIED
          </span>
        )}
        {contract.address && (
          <span style={{
            fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
            color: 'var(--text-tertiary)',
          }}>
            {contract.address.slice(0, 6)}...{contract.address.slice(-4)}
          </span>
        )}
      </div>

      {/* Expanded detail panel */}
      {isExpanded && (
        <div onClick={e => e.stopPropagation()} style={{ marginTop: 16, borderTop: '1px solid var(--border-subtle)', paddingTop: 16 }}>
          {loadingSdk && <p style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Loading SDK...</p>}
          {sdk && (
            <div>
              {/* Public functions */}
              {sdk.functions?.public?.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>
                    Public Functions ({sdk.functions.public.length})
                  </h4>
                  <div className="space-y-1">
                    {sdk.functions.public.map((fn: any, i: number) => (
                      <div key={i} style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)', padding: '3px 8px', borderRadius: 4, background: 'var(--bg-secondary)' }}>
                        <span style={{ color: fn.is_read_only ? '#3B82F6' : '#F59E0B' }}>{fn.mutability}</span>
                        {' '}{fn.signature || fn.name}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {/* Admin functions */}
              {sdk.functions?.owner_admin?.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <h4 style={{ fontSize: 12, fontWeight: 700, color: '#EF4444', marginBottom: 6 }}>
                    Restricted Functions ({sdk.functions.owner_admin.length})
                  </h4>
                  <div className="space-y-1">
                    {sdk.functions.owner_admin.map((fn: any, i: number) => (
                      <div key={i} style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)', padding: '3px 8px', borderRadius: 4, background: '#EF444410' }}>
                        [{fn.access}] {fn.signature || fn.name}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {/* Security summary */}
              {sdk.security_summary && (
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  <span>Pattern: <strong>{sdk.security_summary.access_control_pattern}</strong></span>
                  <span>Public: {sdk.security_summary.public_functions}</span>
                  <span>Admin: {sdk.security_summary.admin_functions}</span>
                  {sdk.security_summary.dangerous_functions > 0 && (
                    <span style={{ color: '#EF4444' }}>Dangerous: {sdk.security_summary.dangerous_functions}</span>
                  )}
                </div>
              )}
            </div>
          )}
          {!sdk && !loadingSdk && <p style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>No SDK available</p>}
        </div>
      )}
    </div>
  )
}

export default function ExplorePage() {
  const [activeTab, setActiveTab] = useState<'projects' | 'contracts' | 'knowledge'>('projects')
  const [projects, setProjects] = useState<any[]>([])
  const [trending, setTrending] = useState<any[]>([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [chain, setChain] = useState('all')
  const [sort, setSort] = useState('stars')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  // Smart contracts state
  const [smartContracts, setSmartContracts] = useState<any[]>([])
  const [expandedContract, setExpandedContract] = useState<string | null>(null)
  const [scTotal, setScTotal] = useState(0)
  const [scHasNext, setScHasNext] = useState(false)
  const [scLoading, setScLoading] = useState(false)
  const [chainCounts, setChainCounts] = useState<any[]>([])
  // Knowledge search state
  const [kbQuery, setKbQuery] = useState('')
  const [kbTags, setKbTags] = useState('')
  const [kbResults, setKbResults] = useState<any[]>([])
  const [kbLoading, setKbLoading] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')

    fetch(`${API_URL}/registry/projects/trending?limit=6`)
      .then(r => r.ok ? r.json() : [])
      .then(setTrending)
      .catch(() => {})
  }, [])

  // Debounced search
  const [debouncedQuery, setDebouncedQuery] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    if (!token) return

    if (activeTab === 'projects') {
      setLoading(true)
      const params = new URLSearchParams()
      if (debouncedQuery) params.set('q', debouncedQuery)
      if (category !== 'all') params.set('category', category)
      if (chain !== 'all') params.set('chain', chain)
      params.set('sort', sort)
      params.set('page', page.toString())
      params.set('page_size', '12')

      const headers: Record<string, string> = { Authorization: `Bearer ${token}` }

      fetch(`${API_URL}/registry/projects?${params}`, { headers })
        .then(r => r.ok ? r.json() : { items: [], total: 0, has_next: false })
        .then(data => {
          setProjects(data.items || [])
          setTotal(data.total || 0)
          setHasNext(data.has_next || false)
          setLoading(false)
        })
        .catch(() => setLoading(false))
    } else {
      setScLoading(true)
      const params = new URLSearchParams()
      if (debouncedQuery) params.set('q', debouncedQuery)
      if (chain !== 'all') params.set('chain', chain)
      params.set('sort', sort === 'stars' ? 'recent' : sort)
      params.set('page', page.toString())
      params.set('page_size', '12')

      fetch(`${API_URL}/explore/contracts?${params}`)
        .then(r => r.ok ? r.json() : { items: [], total: 0, has_next: false })
        .then(data => {
          setSmartContracts(data.items || [])
          setScTotal(data.total || 0)
          setScHasNext(data.has_next || false)
          setScLoading(false)
        })
        .catch(() => setScLoading(false))

      // Load chain counts
      fetch(`${API_URL}/explore/chains`)
        .then(r => r.ok ? r.json() : [])
        .then(setChainCounts)
        .catch(() => {})
    }
  }, [debouncedQuery, category, chain, sort, page, activeTab])

  return (
    <div className="max-w-6xl mx-auto py-10 px-6 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold" style={{ letterSpacing: '-0.03em' }}>
          Contract <span style={{ color: 'var(--refi-teal)' }}>Registry</span>
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 6 }}>
          Discover smart contract ABIs, SDKs, and execution logic — accessible to any AI agent via MCP
        </p>
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-1" style={{ borderBottom: '1px solid var(--border-primary)' }}>
        <button
          onClick={() => { setActiveTab('projects'); setPage(1) }}
          style={{
            padding: '8px 16px', fontSize: 13, fontWeight: 600,
            color: activeTab === 'projects' ? 'var(--refi-teal)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'projects' ? '2px solid var(--refi-teal)' : '2px solid transparent',
            background: 'none', cursor: 'pointer',
          }}
        >
          Registry Projects
        </button>
        <button
          onClick={() => { setActiveTab('contracts'); setPage(1) }}
          style={{
            padding: '8px 16px', fontSize: 13, fontWeight: 600,
            color: activeTab === 'contracts' ? 'var(--refi-teal)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'contracts' ? '2px solid var(--refi-teal)' : '2px solid transparent',
            background: 'none', cursor: 'pointer',
          }}
        >
          Smart Contracts (GROOT Brain)
        </button>
        <button
          onClick={() => { setActiveTab('knowledge'); setPage(1) }}
          style={{
            padding: '8px 16px', fontSize: 13, fontWeight: 600,
            color: activeTab === 'knowledge' ? 'var(--refi-teal)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'knowledge' ? '2px solid var(--refi-teal)' : '2px solid transparent',
            background: 'none', cursor: 'pointer',
          }}
        >
          Knowledge Search
        </button>
      </div>

      {/* ── Projects Tab ── */}
      {activeTab === 'projects' && <>

      {/* Trending */}
      {trending.length > 0 && (
        <section>
          <h2 className="font-bold mb-3" style={{ fontSize: 14, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Trending Projects
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {trending.map((p: any) => <ProjectCard key={p.id} project={p} />)}
          </div>
        </section>
      )}

      {/* Search & Filters */}
      <section className="card" style={{ padding: 20 }}>
        <div className="flex flex-col md:flex-row gap-3">
          <input
            type="text"
            placeholder="Search projects..."
            value={query}
            onChange={e => { setQuery(e.target.value); setPage(1) }}
            className="input-base focus-glow flex-1"
            style={{ fontSize: 14 }}
          />
          <select
            value={category}
            onChange={e => { setCategory(e.target.value); setPage(1) }}
            className="input-base"
            style={{ fontSize: 13, minWidth: 120 }}
          >
            {CATEGORIES.map(c => (
              <option key={c} value={c}>{c === 'all' ? 'All Categories' : c.toUpperCase()}</option>
            ))}
          </select>
          <select
            value={chain}
            onChange={e => { setChain(e.target.value); setPage(1) }}
            className="input-base"
            style={{ fontSize: 13, minWidth: 120 }}
          >
            {CHAINS.map(c => (
              <option key={c} value={c}>{c === 'all' ? 'All Chains' : c}</option>
            ))}
          </select>
          <select
            value={sort}
            onChange={e => { setSort(e.target.value); setPage(1) }}
            className="input-base"
            style={{ fontSize: 13, minWidth: 140 }}
          >
            {SORTS.map(s => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center justify-between mt-3">
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
            {total} project{total !== 1 ? 's' : ''} found
          </span>
          <Link href="/registry/new/" className="btn-primary !py-1.5 !px-4 !text-xs !rounded-lg" style={{ textDecoration: 'none' }}>
            + New Project
          </Link>
        </div>
      </section>

      {/* Results */}
      {loading ? (
        <div className="text-center py-20">
          <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)', fontSize: 14 }}>
            Loading projects...
          </span>
        </div>
      ) : projects.length === 0 ? (
        <div className="text-center py-20">
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
            No projects found. Be the first to publish!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p: any) => <ProjectCard key={p.id} project={p} />)}
        </div>
      )}

      {/* Pagination */}
      {total > 12 && (
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="btn-secondary !py-1.5 !px-4 !text-xs"
            style={{ opacity: page <= 1 ? 0.5 : 1 }}
          >
            Previous
          </button>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>
            Page {page}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={!hasNext}
            className="btn-secondary !py-1.5 !px-4 !text-xs"
            style={{ opacity: !hasNext ? 0.5 : 1 }}
          >
            Next
          </button>
        </div>
      )}

      </>}

      {/* ── Smart Contracts Tab ── */}
      {activeTab === 'contracts' && <>

      {/* Chain Overview */}
      {chainCounts.length > 0 && (
        <div className="flex gap-3 flex-wrap">
          {chainCounts.map((cc: any) => (
            <div key={cc.chain} className="card" style={{ padding: '8px 14px', cursor: 'pointer' }}
              onClick={() => { setChain(cc.chain); setPage(1) }}
            >
              <ChainBadge chain={cc.chain} />
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 6 }}>{cc.count}</span>
            </div>
          ))}
        </div>
      )}

      {/* Search & Filters */}
      <section className="card" style={{ padding: 20 }}>
        <div className="flex flex-col md:flex-row gap-3">
          <input
            type="text"
            placeholder="Search smart contracts, functions..."
            value={query}
            onChange={e => { setQuery(e.target.value); setPage(1) }}
            className="input-base focus-glow flex-1"
            style={{ fontSize: 14 }}
          />
          <select
            value={chain}
            onChange={e => { setChain(e.target.value); setPage(1) }}
            className="input-base"
            style={{ fontSize: 13, minWidth: 120 }}
          >
            {CHAINS.map(c => (
              <option key={c} value={c}>{c === 'all' ? 'All Chains' : c}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center justify-between mt-3">
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
            {scTotal} smart contract{scTotal !== 1 ? 's' : ''} published to GROOT
          </span>
          <Link href="/repo/" className="btn-primary !py-1.5 !px-4 !text-xs !rounded-lg" style={{ textDecoration: 'none' }}>
            + Upload Contract
          </Link>
        </div>
      </section>

      {/* Smart Contract Results */}
      {scLoading ? (
        <div className="text-center py-20">
          <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)', fontSize: 14 }}>
            Loading smart contracts...
          </span>
        </div>
      ) : smartContracts.length === 0 ? (
        <div className="text-center py-20">
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
            No public smart contracts yet. Upload and publish yours to make them part of GROOT's brain!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {smartContracts.map((c: any) => <SmartContractCard key={c.id} contract={c} isExpanded={expandedContract === c.id} onToggle={() => setExpandedContract(expandedContract === c.id ? null : c.id)} />)}
        </div>
      )}

      {/* Pagination */}
      {scTotal > 12 && (
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
            className="btn-secondary !py-1.5 !px-4 !text-xs" style={{ opacity: page <= 1 ? 0.5 : 1 }}>
            Previous
          </button>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>
            Page {page}
          </span>
          <button onClick={() => setPage(p => p + 1)} disabled={!scHasNext}
            className="btn-secondary !py-1.5 !px-4 !text-xs" style={{ opacity: !scHasNext ? 0.5 : 1 }}>
            Next
          </button>
        </div>
      )}

      </>}

      {/* ═══ KNOWLEDGE TAB ═══ */}
      {activeTab === 'knowledge' && <>
        <section className="card" style={{ padding: 20 }}>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
            Search Groot&apos;s knowledge base using natural language. Results are ranked by hybrid scoring (semantic + keyword + tag match).
          </p>
          <div className="flex flex-col md:flex-row gap-3 mb-3">
            <input
              type="text"
              placeholder="Ask a question... e.g. 'How does staking work?'"
              value={kbQuery}
              onChange={e => setKbQuery(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && kbQuery.trim()) {
                  setKbLoading(true)
                  const token = localStorage.getItem('refinet_token') || ''
                  const params = new URLSearchParams({ q: kbQuery })
                  if (kbTags.trim()) params.set('tags', kbTags.trim())
                  fetch(`${API_URL}/knowledge/search?${params}`, {
                    headers: { Authorization: `Bearer ${token}` },
                  })
                    .then(r => r.ok ? r.json() : { results: [] })
                    .then(data => { setKbResults(data.results || []); setKbLoading(false) })
                    .catch(() => setKbLoading(false))
                }
              }}
              className="input-base focus-glow flex-1"
              style={{ fontSize: 14 }}
            />
            <button
              onClick={() => {
                if (!kbQuery.trim()) return
                setKbLoading(true)
                const token = localStorage.getItem('refinet_token') || ''
                const params = new URLSearchParams({ q: kbQuery })
                if (kbTags.trim()) params.set('tags', kbTags.trim())
                fetch(`${API_URL}/knowledge/search?${params}`, {
                  headers: { Authorization: `Bearer ${token}` },
                })
                  .then(r => r.ok ? r.json() : { results: [] })
                  .then(data => { setKbResults(data.results || []); setKbLoading(false) })
                  .catch(() => setKbLoading(false))
              }}
              className="btn-primary !py-2 !px-6 !text-sm"
              style={{ whiteSpace: 'nowrap' }}
            >
              Search
            </button>
          </div>
          <input
            type="text"
            placeholder="Filter by tags (comma-separated, e.g. defi, staking, erc20)"
            value={kbTags}
            onChange={e => setKbTags(e.target.value)}
            className="input-base focus-glow"
            style={{ fontSize: 12, width: '100%' }}
          />
        </section>

        {kbLoading ? (
          <div className="text-center py-16">
            <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)', fontSize: 14 }}>
              Searching knowledge base...
            </span>
          </div>
        ) : kbResults.length > 0 ? (
          <div className="space-y-3">
            {kbResults.map((r: any, i: number) => (
              <div key={r.chunk_id || i} className="card" style={{ padding: 16 }}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {r.document_title}
                    </span>
                    {r.doc_type && (
                      <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '2px 6px', borderRadius: 4, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase' }}>
                        {r.doc_type}
                      </span>
                    )}
                    <CategoryBadge category={r.category} />
                  </div>
                  <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: 'var(--refi-teal)' }}>
                    {(r.score * 100).toFixed(1)}%
                  </span>
                </div>
                {r.tags && r.tags.length > 0 && (
                  <div className="flex gap-1 flex-wrap mb-2">
                    {r.tags.slice(0, 6).map((tag: string) => (
                      <span key={tag} style={{ fontSize: 10, padding: '1px 5px', borderRadius: 4, background: 'rgba(92,224,210,0.08)', color: 'var(--refi-teal)', border: '1px solid rgba(92,224,210,0.15)' }}>
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {r.content.substring(0, 400)}{r.content.length > 400 ? '...' : ''}
                </p>
              </div>
            ))}
          </div>
        ) : kbQuery ? (
          <div className="text-center py-16">
            <p style={{ color: 'var(--text-tertiary)', fontSize: 14 }}>
              No results found. Try a different query or broader search terms.
            </p>
          </div>
        ) : (
          <div className="text-center py-16">
            <p style={{ color: 'var(--text-tertiary)', fontSize: 14 }}>
              Enter a question to search Groot&apos;s knowledge base. Supports natural language queries and tag filtering.
            </p>
          </div>
        )}
      </>}
    </div>
  )
}
