'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

const CATEGORIES = [
  { value: '', label: 'All' },
  { value: 'dapp', label: 'DApps' },
  { value: 'agent', label: 'Agents' },
  { value: 'tool', label: 'Tools' },
  { value: 'template', label: 'Templates' },
  { value: 'dataset', label: 'Datasets' },
  { value: 'api-service', label: 'API Services' },
  { value: 'digital-asset', label: 'Digital Assets' },
]

const SORT_OPTIONS = [
  { value: 'installs', label: 'Most Installed' },
  { value: 'rating', label: 'Top Rated' },
  { value: 'recent', label: 'Newest' },
  { value: 'name', label: 'A-Z' },
  { value: 'price_low', label: 'Price: Low' },
  { value: 'price_high', label: 'Price: High' },
]

interface AppItem {
  id: string
  slug: string
  name: string
  description: string
  category: string
  chain: string | null
  version: string
  icon_url: string | null
  tags: string[]
  owner_username: string | null
  install_count: number
  rating_avg: number
  rating_count: number
  is_verified: boolean
  is_featured: boolean
  listed_by_admin: boolean
  price_type: string
  price_amount: number
  price_token: string | null
  license_type: string
}

function PriceTag({ app }: { app: AppItem }) {
  if (app.price_type === 'free') {
    return <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: 'rgba(74,222,128,0.15)', color: 'var(--success)' }}>FREE</span>
  }
  const label = app.price_token
    ? `${app.price_amount} ${app.price_token}`
    : `$${app.price_amount.toFixed(2)}`
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: 'rgba(96,165,250,0.15)', color: 'var(--info, #60a5fa)' }}>
      {label}{app.price_type === 'subscription' ? '/mo' : ''}
    </span>
  )
}

function StarRating({ avg, count }: { avg: number; count: number }) {
  if (count === 0) return <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>No reviews</span>
  return (
    <span className="text-[10px] flex items-center gap-1" style={{ color: 'var(--text-secondary)' }}>
      <span style={{ color: '#f59e0b' }}>{'★'.repeat(Math.round(avg))}</span>
      <span>{avg.toFixed(1)} ({count})</span>
    </span>
  )
}

function CategoryBadge({ category }: { category: string }) {
  const colors: Record<string, string> = {
    dapp: 'rgba(139,92,246,0.15)',
    agent: 'rgba(236,72,153,0.15)',
    tool: 'rgba(34,211,238,0.15)',
    template: 'rgba(251,191,36,0.15)',
    dataset: 'rgba(74,222,128,0.15)',
    'api-service': 'rgba(96,165,250,0.15)',
    'digital-asset': 'rgba(244,114,182,0.15)',
  }
  const textColors: Record<string, string> = {
    dapp: '#8b5cf6',
    agent: '#ec4899',
    tool: '#22d3ee',
    template: '#fbbf24',
    dataset: '#4ade80',
    'api-service': '#60a5fa',
    'digital-asset': '#f472b6',
  }
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: colors[category] || 'var(--bg-tertiary)', color: textColors[category] || 'var(--text-secondary)' }}>
      {category}
    </span>
  )
}

function AppCard({ app }: { app: AppItem }) {
  return (
    <Link
      href={`/store/${app.slug}`}
      className="card p-4 transition-all block"
      style={{ textDecoration: 'none', border: '1px solid var(--border-subtle)' }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--refi-teal)'; e.currentTarget.style.transform = 'translateY(-1px)' }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-subtle)'; e.currentTarget.style.transform = 'none' }}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <div
          className="flex items-center justify-center rounded-lg shrink-0"
          style={{ width: 40, height: 40, background: 'var(--bg-tertiary)', fontSize: 20 }}
        >
          {app.icon_url ? (
            <img src={app.icon_url} alt="" style={{ width: 40, height: 40, borderRadius: 8, objectFit: 'cover' }} />
          ) : (
            <span>{app.category === 'dapp' ? '\u25A0' : app.category === 'agent' ? '\u25C6' : app.category === 'tool' ? '\u2699' : '\u25B2'}</span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <h3 className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>{app.name}</h3>
            {app.is_verified && <span title="Verified" style={{ color: 'var(--refi-teal)', fontSize: 12 }}>&#10003;</span>}
            {app.is_featured && <span title="Featured" style={{ color: '#fbbf24', fontSize: 12 }}>&#9733;</span>}
          </div>
          <p className="text-xs truncate" style={{ color: 'var(--text-tertiary)' }}>
            {app.owner_username ? `@${app.owner_username}` : 'platform'}
            {app.chain && <span> · {app.chain}</span>}
          </p>
        </div>
      </div>

      {/* Description */}
      <p className="text-xs mb-3 line-clamp-2" style={{ color: 'var(--text-secondary)', minHeight: 32 }}>
        {app.description || 'No description'}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <CategoryBadge category={app.category} />
          <PriceTag app={app} />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
            {app.install_count} installs
          </span>
          <StarRating avg={app.rating_avg} count={app.rating_count} />
        </div>
      </div>

      {/* Tags */}
      {app.tags.length > 0 && (
        <div className="flex gap-1 mt-2 flex-wrap">
          {app.tags.slice(0, 3).map(tag => (
            <span key={tag} className="text-[9px] px-1 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>
              {tag}
            </span>
          ))}
        </div>
      )}
    </Link>
  )
}

export default function StorePage() {
  const [apps, setApps] = useState<AppItem[]>([])
  const [featured, setFeatured] = useState<AppItem[]>([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [sortBy, setSortBy] = useState('installs')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const fetchApps = async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (query) params.set('query', query)
    if (category) params.set('category', category)
    params.set('sort_by', sortBy)
    params.set('page', String(page))
    params.set('page_size', '20')
    try {
      const resp = await fetch(`${API_URL}/apps?${params}`)
      if (resp.ok) {
        const data = await resp.json()
        setApps(data.apps)
        setTotalPages(data.total_pages)
        setTotal(data.total)
      }
    } catch {}
    setLoading(false)
  }

  const fetchFeatured = async () => {
    try {
      const resp = await fetch(`${API_URL}/apps/featured?limit=6`)
      if (resp.ok) setFeatured(await resp.json())
    } catch {}
  }

  useEffect(() => { fetchFeatured() }, [])
  useEffect(() => { fetchApps() }, [query, category, sortBy, page])

  return (
    <div className="max-w-6xl mx-auto py-8 px-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold mb-2" style={{ letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
            App Store
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Discover and install DApps, agents, tools, templates, and digital assets.
          </p>
        </div>
        <Link href="/store/submit" className="px-4 py-2 text-xs font-semibold rounded-lg shrink-0"
          style={{ background: 'var(--refi-teal)', color: '#000', textDecoration: 'none' }}>
          Submit Your App
        </Link>
      </div>

      {/* Featured Section */}
      {featured.length > 0 && !query && !category && (
        <div className="mb-10">
          <h2 className="text-xs font-mono font-semibold mb-3 uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
            Featured
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {featured.map(app => <AppCard key={app.id} app={app} />)}
          </div>
        </div>
      )}

      {/* Search & Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search apps..."
            value={query}
            onChange={e => { setQuery(e.target.value); setPage(1) }}
            className="w-full px-3 py-2 text-sm rounded-lg"
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-default)',
              color: 'var(--text-primary)',
              outline: 'none',
            }}
          />
        </div>
        <select
          value={category}
          onChange={e => { setCategory(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm rounded-lg"
          style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}
        >
          {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <select
          value={sortBy}
          onChange={e => { setSortBy(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm rounded-lg"
          style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}
        >
          {SORT_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>

      {/* Results count */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>
          {total} app{total !== 1 ? 's' : ''} found
        </span>
        <Link
          href="/store"
          className="text-xs"
          style={{ color: 'var(--refi-teal)', textDecoration: 'none' }}
          onClick={e => { e.preventDefault(); setQuery(''); setCategory(''); setSortBy('installs'); setPage(1) }}
        >
          Reset filters
        </Link>
      </div>

      {/* App Grid */}
      {loading ? (
        <div className="text-center py-20">
          <div className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading...</div>
        </div>
      ) : apps.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-lg mb-2" style={{ color: 'var(--text-tertiary)' }}>No apps found</div>
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Try adjusting your search or filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {apps.map(app => <AppCard key={app.id} app={app} />)}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-8">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
            className="px-3 py-1.5 text-xs rounded"
            style={{
              background: page <= 1 ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
              color: page <= 1 ? 'var(--text-tertiary)' : 'var(--text-primary)',
              border: '1px solid var(--border-default)',
              cursor: page <= 1 ? 'not-allowed' : 'pointer',
            }}
          >
            Previous
          </button>
          <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1.5 text-xs rounded"
            style={{
              background: page >= totalPages ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
              color: page >= totalPages ? 'var(--text-tertiary)' : 'var(--text-primary)',
              border: '1px solid var(--border-default)',
              cursor: page >= totalPages ? 'not-allowed' : 'pointer',
            }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
