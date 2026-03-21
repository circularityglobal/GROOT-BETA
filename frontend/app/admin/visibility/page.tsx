'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

const TAB_DEFS = [
  { key: 'dashboard', label: 'Dashboard', section: 'Core' },
  { key: 'chat', label: 'Chat', section: 'Core' },
  { key: 'agents', label: 'Agents', section: 'Core' },
  { key: 'knowledge', label: 'Knowledge', section: 'Core' },
  { key: 'devices', label: 'Devices', section: 'Core' },
  { key: 'messages', label: 'Messages', section: 'Core' },
  { key: 'network', label: 'Network', section: 'Core' },
  { key: 'pipeline', label: 'Wizard / Pipeline', section: 'Build' },
  { key: 'deployments', label: 'Deployments', section: 'Build' },
  { key: 'dapp', label: 'DApp Factory', section: 'Build' },
  { key: 'projects', label: 'Projects', section: 'Build' },
  { key: 'explore', label: 'Registry', section: 'Build' },
  { key: 'store', label: 'App Store', section: 'Build' },
  { key: 'repo', label: 'Repositories', section: 'Build' },
  { key: 'webhooks', label: 'Webhooks', section: 'Build' },
  { key: 'payments', label: 'Payments', section: 'Build' },
  { key: 'help', label: 'Help Desk', section: 'Build' },
]

export default function AdminVisibility() {
  const { headers } = useAdmin()
  const [tabs, setTabs] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(`${API_URL}/admin/tab-visibility`)
      .then(r => r.ok ? r.json() : { tabs: {} })
      .then(d => { setTabs(d.tabs || {}); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const toggle = (key: string) => {
    if (key === 'admin' || key === 'dashboard') return
    setTabs(prev => ({ ...prev, [key]: !prev[key] }))
    setMsg('')
  }

  const save = async () => {
    setSaving(true); setError(''); setMsg('')
    try {
      const r = await fetch(`${API_URL}/admin/tab-visibility`, { method: 'PUT', headers, body: JSON.stringify({ tabs }) })
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || 'Failed to save') }
      const data = await r.json()
      // Cache version so subsequent conditional requests work
      if (data.version) { try { localStorage.setItem('refinet_tab_vis_version', data.version) } catch {} }
      // Broadcast to all open tabs instantly via BroadcastChannel
      try {
        const bc = new BroadcastChannel('refinet_tab_visibility')
        bc.postMessage({ tabs, version: data.version })
        bc.close()
      } catch (_) { /* BroadcastChannel not supported — clients will pick up via fallback poll */ }
      setMsg('Tab visibility updated. Changes are live across all sessions.')
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  if (loading) return <LoadingState label="Loading visibility settings..." />

  const enabledCount = TAB_DEFS.filter(t => tabs[t.key] !== false).length
  const disabledCount = TAB_DEFS.length - enabledCount

  return (
    <div>
      <PageHeader title="Tab Visibility" subtitle="Control which tabs are visible to platform users. Disabled tabs are hidden and blocked at API level." />

      {error && <div className="mb-3 p-3 rounded-lg text-xs" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#EF4444' }}>{error}</div>}
      {msg && <div className="mb-3 p-3 rounded-lg text-xs" style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', color: '#22C55E' }}>{msg}</div>}

      <div className="mb-4 flex gap-4 text-xs" style={{ color: 'var(--text-tertiary)' }}>
        <span>Enabled: <strong style={{ color: 'var(--refi-teal)' }}>{enabledCount}</strong></span>
        <span>Disabled: <strong style={{ color: '#EF4444' }}>{disabledCount}</strong></span>
      </div>

      {['Core', 'Build'].map(section => (
        <div key={section} className="mb-6">
          <div className="text-[10px] uppercase font-semibold mb-2" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.08em' }}>{section}</div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
            {TAB_DEFS.filter(t => t.section === section).map(t => {
              const enabled = tabs[t.key] !== false
              const isLocked = t.key === 'dashboard'
              return (
                <button key={t.key} onClick={() => toggle(t.key)} disabled={isLocked}
                  className="card text-left transition-all"
                  style={{ padding: '10px 14px', opacity: enabled ? 1 : 0.5, borderColor: enabled ? 'var(--border-default)' : 'rgba(239,68,68,0.3)', cursor: isLocked ? 'default' : 'pointer' }}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium" style={{ color: enabled ? 'var(--text-primary)' : 'var(--text-tertiary)', textDecoration: enabled ? 'none' : 'line-through' }}>
                      {t.label}
                    </span>
                    <div style={{
                      width: 32, height: 18, borderRadius: 9, padding: 2,
                      background: enabled ? 'var(--refi-teal)' : 'var(--bg-tertiary)',
                      transition: 'background 0.2s', display: 'flex', alignItems: 'center',
                      justifyContent: enabled ? 'flex-end' : 'flex-start',
                    }}>
                      <div style={{ width: 14, height: 14, borderRadius: '50%', background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.3)' }} />
                    </div>
                  </div>
                  <div className="text-[10px] mt-1 font-mono" style={{ color: 'var(--text-tertiary)' }}>
                    {isLocked ? 'always on' : enabled ? 'visible' : 'hidden'}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      ))}

      <div className="flex items-center justify-between mt-4 pt-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <p className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
          Disabled tabs are hidden from all users except master_admin.
        </p>
        <button onClick={save} disabled={saving} className="px-5 py-2 text-xs font-semibold rounded-lg"
          style={{ background: 'var(--refi-teal)', color: '#000', opacity: saving ? 0.6 : 1, cursor: 'pointer' }}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  )
}
