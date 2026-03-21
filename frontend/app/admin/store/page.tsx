'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

export default function AdminStore() {
  const { headers } = useAdmin()
  const [storeApps, setStoreApps] = useState<any[]>([])
  const [storeStats, setStoreStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [showPublish, setShowPublish] = useState(false)
  const [publishMsg, setPublishMsg] = useState('')
  const [publishForm, setPublishForm] = useState({
    name: '', description: '', category: 'dapp', chain: '', version: '1.0.0',
    readme: '', icon_url: '', price_type: 'free', price_amount: '0',
    price_token: '', license_type: 'open', download_url: '', external_url: '',
    tags: '',
  })

  const loadStoreApps = async () => {
    const resp = await fetch(`${API_URL}/admin/apps?include_inactive=true&page_size=50`, { headers })
    if (resp.ok) { const data = await resp.json(); setStoreApps(data.apps || []) }
    setLoading(false)
  }
  const loadStoreStats = async () => {
    const resp = await fetch(`${API_URL}/admin/apps/stats`, { headers })
    if (resp.ok) setStoreStats(await resp.json())
  }
  const verifyApp = async (appId: string, verified: boolean) => {
    await fetch(`${API_URL}/admin/apps/${appId}/verify`, { method: 'PUT', headers, body: JSON.stringify({ verified }) })
    loadStoreApps()
  }
  const featureApp = async (appId: string, featured: boolean) => {
    await fetch(`${API_URL}/admin/apps/${appId}/feature`, { method: 'PUT', headers, body: JSON.stringify({ featured }) })
    loadStoreApps()
  }
  const setAppStatus = async (appId: string, active: boolean) => {
    await fetch(`${API_URL}/admin/apps/${appId}/status`, { method: 'PUT', headers, body: JSON.stringify({ active }) })
    loadStoreApps()
  }
  const publishProduct = async () => {
    setPublishMsg('')
    const body: any = {
      name: publishForm.name, description: publishForm.description, category: publishForm.category,
      version: publishForm.version, price_type: publishForm.price_type,
      price_amount: parseFloat(publishForm.price_amount) || 0, license_type: publishForm.license_type,
    }
    if (publishForm.chain) body.chain = publishForm.chain
    if (publishForm.readme) body.readme = publishForm.readme
    if (publishForm.icon_url) body.icon_url = publishForm.icon_url
    if (publishForm.price_token) body.price_token = publishForm.price_token
    if (publishForm.download_url) body.download_url = publishForm.download_url
    if (publishForm.external_url) body.external_url = publishForm.external_url
    if (publishForm.tags) body.tags = publishForm.tags.split(',').map((t: string) => t.trim()).filter(Boolean)
    try {
      const resp = await fetch(`${API_URL}/admin/apps/publish`, { method: 'POST', headers, body: JSON.stringify(body) })
      const data = await resp.json()
      if (resp.ok) {
        setPublishMsg(`Published: ${data.slug}`)
        setShowPublish(false)
        setPublishForm({ name: '', description: '', category: 'dapp', chain: '', version: '1.0.0', readme: '', icon_url: '', price_type: 'free', price_amount: '0', price_token: '', license_type: 'open', download_url: '', external_url: '', tags: '' })
        loadStoreApps(); loadStoreStats()
      } else {
        setPublishMsg(data.detail || 'Publish failed')
      }
    } catch { setPublishMsg('Publish failed') }
  }

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    loadStoreApps(); loadStoreStats()
  }, [headers.Authorization])

  if (loading) return <LoadingState label="Loading app store..." />

  return (
    <div>
      <PageHeader title="App Store" subtitle="Manage published products and listings" />

      {/* Stats */}
      {storeStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total Apps', value: storeStats.total_apps },
            { label: 'Published', value: storeStats.published_apps },
            { label: 'Verified', value: storeStats.verified_apps },
            { label: 'Featured', value: storeStats.featured_apps },
            { label: 'Total Installs', value: storeStats.total_installs },
            { label: 'Total Reviews', value: storeStats.total_reviews },
            { label: 'Total Downloads', value: storeStats.total_downloads },
          ].map(s => (
            <div key={s.label} className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
              <div className="text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>{s.label}</div>
              <div className="text-xl font-bold" style={{ color: 'var(--refi-teal)' }}>{s.value}</div>
            </div>
          ))}
          {storeStats.categories && Object.keys(storeStats.categories).length > 0 && (
            <div className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
              <div className="text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>By Category</div>
              <div className="text-[10px] space-y-0.5">
                {Object.entries(storeStats.categories).map(([cat, count]) => (
                  <div key={cat} className="flex justify-between" style={{ color: 'var(--text-secondary)' }}>
                    <span>{cat}</span><span className="font-mono">{String(count)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Publish Button */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => setShowPublish(!showPublish)} className="px-4 py-2 text-xs font-semibold rounded-lg"
          style={{ background: 'var(--refi-teal)', color: '#000', cursor: 'pointer' }}>
          {showPublish ? 'Cancel' : 'Publish Product'}
        </button>
        {publishMsg && <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{publishMsg}</span>}
      </div>

      {/* Publish Form */}
      {showPublish && (
        <div className="card p-4 mb-6" style={{ border: '1px solid var(--border-default)' }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>List Product in App Store</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              { key: 'name', label: 'Name *', type: 'text' }, { key: 'version', label: 'Version', type: 'text' },
              { key: 'icon_url', label: 'Icon URL', type: 'text' }, { key: 'chain', label: 'Chain', type: 'text' },
              { key: 'price_amount', label: 'Price (USD)', type: 'number' }, { key: 'price_token', label: 'Token Symbol', type: 'text' },
              { key: 'download_url', label: 'Download URL', type: 'text' }, { key: 'external_url', label: 'External URL', type: 'text' },
              { key: 'tags', label: 'Tags (comma-separated)', type: 'text' },
            ].map(f => (
              <div key={f.key}>
                <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>{f.label}</label>
                <input type={f.type} value={(publishForm as any)[f.key]}
                  onChange={e => setPublishForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                  className="w-full px-2 py-1.5 text-xs rounded"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }} />
              </div>
            ))}
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Category *</label>
              <select value={publishForm.category} onChange={e => setPublishForm(prev => ({ ...prev, category: e.target.value }))}
                className="w-full px-2 py-1.5 text-xs rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
                {['dapp', 'agent', 'tool', 'template', 'dataset', 'api-service', 'digital-asset'].map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Price Type</label>
              <select value={publishForm.price_type} onChange={e => setPublishForm(prev => ({ ...prev, price_type: e.target.value }))}
                className="w-full px-2 py-1.5 text-xs rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
                {['free', 'one-time', 'subscription'].map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>License</label>
              <select value={publishForm.license_type} onChange={e => setPublishForm(prev => ({ ...prev, license_type: e.target.value }))}
                className="w-full px-2 py-1.5 text-xs rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
                {['open', 'single-use', 'multi-use', 'enterprise'].map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          </div>
          <div className="mt-3">
            <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Description</label>
            <textarea value={publishForm.description} onChange={e => setPublishForm(prev => ({ ...prev, description: e.target.value }))}
              rows={2} className="w-full px-2 py-1.5 text-xs rounded"
              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none', resize: 'vertical' }} />
          </div>
          <div className="mt-3">
            <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>README (Markdown)</label>
            <textarea value={publishForm.readme} onChange={e => setPublishForm(prev => ({ ...prev, readme: e.target.value }))}
              rows={4} className="w-full px-2 py-1.5 text-xs rounded font-mono"
              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none', resize: 'vertical' }} />
          </div>
          <button onClick={publishProduct} className="mt-3 px-4 py-2 text-xs font-semibold rounded-lg"
            style={{ background: 'var(--refi-teal)', color: '#000', cursor: 'pointer' }}>
            Publish to Store
          </button>
        </div>
      )}

      {/* Apps Table */}
      <div className="card overflow-hidden overflow-x-auto" style={{ border: '1px solid var(--border-subtle)' }}>
        {storeApps.length === 0 ? (
          <p className="text-sm p-6 text-center" style={{ color: 'var(--text-tertiary)' }}>No apps in the store yet.</p>
        ) : (
          <table className="w-full text-sm min-w-[800px]">
            <thead style={{ background: 'var(--bg-elevated)' }}>
              <tr>
                {['Name', 'Category', 'Owner', 'Price', 'Installs', 'Rating', 'Status', 'Actions'].map(h => (
                  <th key={h} className="text-left px-3 py-2.5 text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {storeApps.map((app: any) => (
                <tr key={app.id} style={{ borderTop: '1px solid var(--border-subtle)' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  <td className="px-3 py-2.5">
                    <div className="font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{app.name}</div>
                    <div className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{app.slug}</div>
                  </td>
                  <td className="px-3 py-2.5 text-xs">{app.category}</td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: 'var(--text-secondary)' }}>{app.owner_username || 'platform'}</td>
                  <td className="px-3 py-2.5 text-xs font-mono">
                    {app.price_type === 'free' ? <span style={{ color: 'var(--success)' }}>FREE</span> : <span>${app.price_amount}</span>}
                  </td>
                  <td className="px-3 py-2.5 text-xs font-mono">{app.install_count}</td>
                  <td className="px-3 py-2.5 text-xs">{app.rating_count > 0 ? `${app.rating_avg.toFixed(1)} (${app.rating_count})` : '-'}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-1.5">
                      {app.is_verified && <span className="text-[9px] px-1 py-0.5 rounded" style={{ background: 'rgba(74,222,128,0.15)', color: 'var(--success)' }}>verified</span>}
                      {app.is_featured && <span className="text-[9px] px-1 py-0.5 rounded" style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}>featured</span>}
                      {app.listed_by_admin && <span className="text-[9px] px-1 py-0.5 rounded" style={{ background: 'rgba(96,165,250,0.15)', color: '#60a5fa' }}>platform</span>}
                      {!app.is_published && <span className="text-[9px] px-1 py-0.5 rounded" style={{ background: 'rgba(248,113,113,0.15)', color: 'var(--error)' }}>unpublished</span>}
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex gap-1">
                      <button onClick={() => verifyApp(app.id, !app.is_verified)} className="text-[9px] px-1.5 py-0.5 rounded"
                        style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>
                        {app.is_verified ? 'Unverify' : 'Verify'}
                      </button>
                      <button onClick={() => featureApp(app.id, !app.is_featured)} className="text-[9px] px-1.5 py-0.5 rounded"
                        style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>
                        {app.is_featured ? 'Unfeature' : 'Feature'}
                      </button>
                      <button onClick={() => setAppStatus(app.id, !app.is_active)} className="text-[9px] px-1.5 py-0.5 rounded"
                        style={{ background: app.is_active ? 'rgba(248,113,113,0.15)' : 'rgba(74,222,128,0.15)', color: app.is_active ? 'var(--error)' : 'var(--success)', border: 'none', cursor: 'pointer' }}>
                        {app.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
