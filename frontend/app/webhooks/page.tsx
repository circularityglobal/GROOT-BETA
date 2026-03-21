'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'

const EVENT_PATTERNS = [
  { label: 'All Events', value: '*' },
  { label: 'Registry', value: 'registry.*' },
  { label: 'Messaging', value: 'messaging.*' },
  { label: 'Devices', value: 'device.*' },
  { label: 'System', value: 'system.*' },
]

interface Webhook {
  id: string
  url: string
  events: string[]
  is_active: boolean
  failure_count: number
  last_delivery_at: string | null
  created_at: string
}

export default function WebhooksPage() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newUrl, setNewUrl] = useState('')
  const [newEvents, setNewEvents] = useState<string[]>(['*'])
  const [newDeviceId, setNewDeviceId] = useState('')
  const [signingSecret, setSigningSecret] = useState('')
  const [testResults, setTestResults] = useState<Record<string, { delivered: boolean; message: string } | null>>({})
  const [error, setError] = useState('')

  const headers = () => {
    const token = localStorage.getItem('refinet_token')
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  }

  const fetchWebhooks = () => {
    fetch(`${API_URL}/webhooks`, { headers: headers() })
      .then(r => r.json())
      .then(data => { setWebhooks(Array.isArray(data) ? data : []); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    
    fetchWebhooks()
  }, [])

  const createWebhook = async () => {
    setError('')
    setSigningSecret('')
    try {
      const resp = await fetch(`${API_URL}/webhooks/subscribe`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          url: newUrl,
          events: newEvents,
          ...(newDeviceId ? { device_id: newDeviceId } : {}),
        }),
      })
      if (!resp.ok) { setError(`Error: ${resp.status}`); return }
      const data = await resp.json()
      setSigningSecret(data.signing_secret || '')
      setNewUrl('')
      setNewEvents(['*'])
      setNewDeviceId('')
      fetchWebhooks()
    } catch { setError('Connection error') }
  }

  const deleteWebhook = async (id: string) => {
    if (!confirm('Delete this webhook subscription?')) return
    await fetch(`${API_URL}/webhooks/${id}`, { method: 'DELETE', headers: headers() })
    fetchWebhooks()
  }

  const testWebhook = async (id: string) => {
    setTestResults(prev => ({ ...prev, [id]: null }))
    try {
      const resp = await fetch(`${API_URL}/webhooks/${id}/test`, { method: 'POST', headers: headers() })
      const data = await resp.json()
      setTestResults(prev => ({ ...prev, [id]: data }))
    } catch {
      setTestResults(prev => ({ ...prev, [id]: { delivered: false, message: 'Connection error' } }))
    }
  }

  const toggleEvent = (val: string) => {
    setNewEvents(prev => prev.includes(val) ? prev.filter(e => e !== val) : [...prev, val])
  }

  if (loading) return <div className="flex items-center justify-center min-h-[60vh]" style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Loading...</div>

  return (
    <div className="max-w-5xl mx-auto py-10 px-6 space-y-8 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ letterSpacing: '-0.02em' }}>Webhooks</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>
            Subscribe to events and receive HMAC-signed payloads in real time
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Cancel' : '+ New Subscription'}
        </button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <section className="card animate-slide-up" style={{ padding: 24 }}>
          <h2 className="font-bold mb-4" style={{ letterSpacing: '-0.02em' }}>New Webhook Subscription</h2>
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Endpoint URL</label>
              <input className="input-base focus-glow w-full" placeholder="https://your-server.com/webhook" value={newUrl} onChange={e => setNewUrl(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium mb-2 block" style={{ color: 'var(--text-secondary)' }}>Event Patterns</label>
              <div className="flex flex-wrap gap-2">
                {EVENT_PATTERNS.map(ep => (
                  <button key={ep.value} onClick={() => toggleEvent(ep.value)}
                    className="text-xs px-3 py-1.5 rounded-full transition-colors"
                    style={{
                      background: newEvents.includes(ep.value) ? 'var(--refi-teal)' : 'var(--bg-tertiary)',
                      color: newEvents.includes(ep.value) ? 'var(--text-inverse)' : 'var(--text-secondary)',
                      border: '1px solid ' + (newEvents.includes(ep.value) ? 'var(--refi-teal)' : 'var(--border-default)'),
                    }}>
                    {ep.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Device ID <span style={{ color: 'var(--text-tertiary)' }}>(optional — scope to a device)</span></label>
              <input className="input-base focus-glow w-full" placeholder="Leave empty for all devices" value={newDeviceId} onChange={e => setNewDeviceId(e.target.value)} />
            </div>
            {error && <p style={{ color: 'var(--error)', fontSize: 13 }}>{error}</p>}
            <button className="btn-primary" onClick={createWebhook} disabled={!newUrl.trim() || newEvents.length === 0}>Create Subscription</button>
          </div>

          {signingSecret && (
            <div className="mt-4 p-4 rounded-lg animate-fade-in" style={{ background: 'rgba(92,224,210,0.08)', border: '1px solid var(--refi-teal)' }}>
              <p className="text-xs font-bold mb-1" style={{ color: 'var(--refi-teal)' }}>Signing Secret (shown once — save it now)</p>
              <div className="flex items-center gap-2">
                <code className="text-sm flex-1 break-all" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>{signingSecret}</code>
                <CopyBtn text={signingSecret} />
              </div>
            </div>
          )}
        </section>
      )}

      {/* Subscription List */}
      <section className="space-y-3">
        {webhooks.length === 0 ? (
          <div className="card text-center py-12" style={{ color: 'var(--text-tertiary)' }}>
            <p className="text-sm">No webhook subscriptions yet</p>
            <p className="text-xs mt-1">Create one to start receiving events</p>
          </div>
        ) : webhooks.map(wh => (
          <div key={wh.id} className="card" style={{ padding: '16px 20px' }}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: wh.is_active ? 'var(--success)' : 'var(--error)' }} />
                  <code className="text-sm truncate block" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>{wh.url}</code>
                </div>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {(wh.events || []).map((ev: string) => (
                    <span key={ev} className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>{ev}</span>
                  ))}
                </div>
                <div className="flex gap-4 mt-2 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  {wh.failure_count > 0 && <span style={{ color: 'var(--error)' }}>{wh.failure_count} failures</span>}
                  {wh.last_delivery_at && <span>Last: {new Date(wh.last_delivery_at).toLocaleDateString()}</span>}
                </div>
                {testResults[wh.id] !== undefined && testResults[wh.id] !== null && (
                  <div className="mt-2 text-xs" style={{ color: testResults[wh.id]!.delivered ? 'var(--success)' : 'var(--error)' }}>
                    {testResults[wh.id]!.delivered ? 'Delivered' : 'Failed'}: {testResults[wh.id]!.message}
                  </div>
                )}
              </div>
              <div className="flex gap-2 flex-shrink-0">
                <button className="btn-secondary !py-1.5 !px-3 !text-xs" onClick={() => testWebhook(wh.id)}>Test</button>
                <button className="!py-1.5 !px-3 !text-xs rounded-lg transition-colors" onClick={() => deleteWebhook(wh.id)}
                  style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--error)', border: '1px solid rgba(248,113,113,0.2)' }}>
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      className="p-2 rounded-lg transition-colors" style={{ color: copied ? 'var(--success)' : 'var(--text-tertiary)' }}>
      {copied ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
      )}
    </button>
  )
}
