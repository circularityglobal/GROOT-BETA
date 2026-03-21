'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

interface AppDetail {
  id: string
  slug: string
  name: string
  description: string
  readme: string | null
  category: string
  chain: string | null
  version: string
  icon_url: string | null
  screenshots: string[]
  tags: string[]
  owner_id: string
  owner_username: string | null
  install_count: number
  download_count: number
  rating_avg: number
  rating_count: number
  is_published: boolean
  is_verified: boolean
  is_featured: boolean
  listed_by_admin: boolean
  price_type: string
  price_amount: number
  price_token: string | null
  price_token_amount: number | null
  license_type: string
  download_url: string | null
  external_url: string | null
  registry_project_id: string | null
  dapp_build_id: string | null
  agent_id: string | null
  reviews: Review[]
  created_at: string
  updated_at: string
}

interface Review {
  id: string
  user_id: string
  username: string | null
  rating: number
  comment: string | null
  created_at: string
}

export default function StoreDetailClient() {
  const params = useParams()
  const slug = params.slug as string
  const [app, setApp] = useState<AppDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [installing, setInstalling] = useState(false)
  const [installMsg, setInstallMsg] = useState('')
  const [reviewRating, setReviewRating] = useState(5)
  const [reviewComment, setReviewComment] = useState('')
  const [reviewMsg, setReviewMsg] = useState('')

  const token = typeof window !== 'undefined' ? localStorage.getItem('refinet_token') || '' : ''
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const fetchApp = async () => {
    setLoading(true)
    try {
      const resp = await fetch(`${API_URL}/apps/${slug}`)
      if (!resp.ok) {
        setError(resp.status === 404 ? 'App not found' : `Error: ${resp.status}`)
        return
      }
      setApp(await resp.json())
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (slug) fetchApp() }, [slug])

  const handleInstall = async () => {
    if (!token) { setInstallMsg('Sign in to install apps'); return }
    setInstalling(true)
    try {
      const resp = await fetch(`${API_URL}/apps/${slug}/install`, { method: 'POST', headers })
      const data = await resp.json()
      setInstallMsg(data.message || data.detail || 'Installed')
      if (resp.ok) fetchApp()
    } catch { setInstallMsg('Install failed') }
    setInstalling(false)
  }

  const handleUninstall = async () => {
    try {
      const resp = await fetch(`${API_URL}/apps/${slug}/uninstall`, { method: 'POST', headers })
      const data = await resp.json()
      setInstallMsg(data.message || data.detail || 'Uninstalled')
      if (resp.ok) fetchApp()
    } catch { setInstallMsg('Uninstall failed') }
  }

  const handleReview = async () => {
    if (!token) { setReviewMsg('Sign in to review'); return }
    try {
      const resp = await fetch(`${API_URL}/apps/${slug}/review`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ rating: reviewRating, comment: reviewComment || undefined }),
      })
      const data = await resp.json()
      setReviewMsg(data.message || data.detail || 'Review submitted')
      if (resp.ok) { setReviewComment(''); fetchApp() }
    } catch { setReviewMsg('Review failed') }
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto py-20 px-6 text-center">
        <div className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading...</div>
      </div>
    )
  }

  if (error || !app) {
    return (
      <div className="max-w-4xl mx-auto py-20 px-6 text-center">
        <h1 className="text-xl font-bold mb-2" style={{ color: 'var(--error)' }}>{error || 'App not found'}</h1>
        <Link href="/store" style={{ color: 'var(--refi-teal)', textDecoration: 'none', fontSize: 14 }}>Back to Store</Link>
      </div>
    )
  }

  const priceLabel = app.price_type === 'free'
    ? 'Free'
    : app.price_token
      ? `${app.price_amount} ${app.price_token}${app.price_type === 'subscription' ? '/mo' : ''}`
      : `$${app.price_amount.toFixed(2)}${app.price_type === 'subscription' ? '/mo' : ''}`

  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      {/* Breadcrumb */}
      <div className="mb-6">
        <Link href="/store" className="text-xs" style={{ color: 'var(--text-tertiary)', textDecoration: 'none' }}>
          Store
        </Link>
        <span className="text-xs mx-1" style={{ color: 'var(--text-tertiary)' }}>/</span>
        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{app.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <div
          className="flex items-center justify-center rounded-xl shrink-0"
          style={{ width: 64, height: 64, background: 'var(--bg-tertiary)', fontSize: 28 }}
        >
          {app.icon_url ? (
            <img src={app.icon_url} alt="" style={{ width: 64, height: 64, borderRadius: 12, objectFit: 'cover' }} />
          ) : (
            <span>{app.category === 'dapp' ? '\u25A0' : app.category === 'agent' ? '\u25C6' : '\u2699'}</span>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>{app.name}</h1>
            {app.is_verified && <span title="Verified" className="text-sm" style={{ color: 'var(--refi-teal)' }}>&#10003;</span>}
            {app.is_featured && <span title="Featured" className="text-sm" style={{ color: '#fbbf24' }}>&#9733;</span>}
          </div>
          <p className="text-xs mb-2" style={{ color: 'var(--text-tertiary)' }}>
            {app.owner_username ? `@${app.owner_username}` : 'platform'}
            {' · v'}{app.version}
            {app.chain && ` · ${app.chain}`}
          </p>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-[10px] px-2 py-0.5 rounded font-mono" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
              {app.category}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded font-mono" style={{
              background: app.price_type === 'free' ? 'rgba(74,222,128,0.15)' : 'rgba(96,165,250,0.15)',
              color: app.price_type === 'free' ? 'var(--success)' : 'var(--info, #60a5fa)',
            }}>
              {priceLabel}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded font-mono" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>
              {app.license_type} license
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2 shrink-0">
          <button
            onClick={handleInstall}
            disabled={installing}
            className="px-4 py-2 text-xs font-semibold rounded-lg transition-colors"
            style={{ background: 'var(--refi-teal)', color: '#000', cursor: installing ? 'wait' : 'pointer' }}
          >
            {installing ? 'Installing...' : 'Install'}
          </button>
          {app.download_url && (
            <a
              href={app.download_url.startsWith('/') ? `${API_URL}${app.download_url}` : app.download_url}
              className="px-4 py-2 text-xs font-semibold rounded-lg text-center"
              style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', textDecoration: 'none', border: '1px solid var(--border-default)' }}
            >
              Download
            </a>
          )}
          {app.external_url && (
            <a
              href={app.external_url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 text-xs font-semibold rounded-lg text-center"
              style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', textDecoration: 'none', border: '1px solid var(--border-default)' }}
            >
              Live Demo
            </a>
          )}
          <button
            onClick={handleUninstall}
            className="px-4 py-1.5 text-[10px] rounded-lg"
            style={{ background: 'transparent', color: 'var(--text-tertiary)', border: '1px solid var(--border-subtle)', cursor: 'pointer' }}
          >
            Uninstall
          </button>
        </div>
      </div>

      {installMsg && (
        <div className="mb-4 px-3 py-2 rounded text-xs" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
          {installMsg}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Installs', value: app.install_count },
          { label: 'Downloads', value: app.download_count },
          { label: 'Rating', value: app.rating_count > 0 ? `${app.rating_avg.toFixed(1)} / 5` : '-' },
          { label: 'Reviews', value: app.rating_count },
        ].map(s => (
          <div key={s.label} className="card p-3 text-center">
            <div className="text-lg font-bold" style={{ color: 'var(--refi-teal)' }}>{s.value}</div>
            <div className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Description */}
      <div className="mb-8">
        <h2 className="text-xs font-mono font-semibold mb-2 uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Description</h2>
        <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{app.description || 'No description provided.'}</p>
      </div>

      {/* Screenshots */}
      {app.screenshots.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-mono font-semibold mb-2 uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Screenshots</h2>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {app.screenshots.map((url, i) => (
              <img key={i} src={url} alt={`Screenshot ${i + 1}`} className="rounded-lg" style={{ height: 200, objectFit: 'cover', border: '1px solid var(--border-subtle)' }} />
            ))}
          </div>
        </div>
      )}

      {/* Readme */}
      {app.readme && (
        <div className="mb-8">
          <h2 className="text-xs font-mono font-semibold mb-2 uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>README</h2>
          <div className="card p-4 text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
            {app.readme}
          </div>
        </div>
      )}

      {/* Tags */}
      {app.tags.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-mono font-semibold mb-2 uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Tags</h2>
          <div className="flex gap-2 flex-wrap">
            {app.tags.map(tag => (
              <Link
                key={tag}
                href={`/store?query=${encodeURIComponent(tag)}`}
                className="text-xs px-2 py-1 rounded"
                style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', textDecoration: 'none' }}
              >
                {tag}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Reviews */}
      <div className="mb-8">
        <h2 className="text-xs font-mono font-semibold mb-3 uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
          Reviews ({app.rating_count})
        </h2>

        {/* Submit Review */}
        {token && (
          <div className="card p-4 mb-4" style={{ border: '1px solid var(--border-subtle)' }}>
            <div className="flex items-center gap-3 mb-2">
              <label className="text-xs" style={{ color: 'var(--text-secondary)' }}>Rating:</label>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map(n => (
                  <button
                    key={n}
                    onClick={() => setReviewRating(n)}
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, padding: 0,
                      color: n <= reviewRating ? '#f59e0b' : 'var(--text-tertiary)',
                    }}
                  >
                    &#9733;
                  </button>
                ))}
              </div>
            </div>
            <textarea
              value={reviewComment}
              onChange={e => setReviewComment(e.target.value)}
              placeholder="Write a review (optional)..."
              rows={2}
              className="w-full px-3 py-2 text-sm rounded mb-2"
              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none', resize: 'vertical' }}
            />
            <div className="flex items-center gap-3">
              <button
                onClick={handleReview}
                className="px-3 py-1.5 text-xs font-semibold rounded"
                style={{ background: 'var(--refi-teal)', color: '#000', cursor: 'pointer' }}
              >
                Submit Review
              </button>
              {reviewMsg && <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{reviewMsg}</span>}
            </div>
          </div>
        )}

        {/* Review List */}
        {app.reviews.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No reviews yet.</p>
        ) : (
          <div className="space-y-3">
            {app.reviews.map(r => (
              <div key={r.id} className="card p-3" style={{ border: '1px solid var(--border-subtle)' }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {r.username || 'Anonymous'}
                  </span>
                  <span style={{ color: '#f59e0b', fontSize: 11 }}>
                    {'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}
                  </span>
                  <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                    {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                  </span>
                </div>
                {r.comment && <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{r.comment}</p>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Metadata */}
      <div className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
        <h2 className="text-xs font-mono font-semibold mb-2 uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Details</h2>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {[
            ['Category', app.category],
            ['Chain', app.chain || '-'],
            ['Version', app.version],
            ['License', app.license_type],
            ['Price', priceLabel],
            ['Published', app.created_at ? new Date(app.created_at).toLocaleDateString() : '-'],
            ['Updated', app.updated_at ? new Date(app.updated_at).toLocaleDateString() : '-'],
            ['Source', app.listed_by_admin ? 'Platform' : 'Community'],
          ].map(([k, v]) => (
            <div key={k as string} className="flex justify-between py-1" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-tertiary)' }}>{k}</span>
              <span style={{ color: 'var(--text-primary)' }}>{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
