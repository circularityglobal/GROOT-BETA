'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'

const DEVICE_TYPES = ['iot', 'plc', 'dlt']

interface Device {
  id: string; name: string; device_type: string; eth_address: string | null
  status: string; telemetry_count: number; last_seen_at: string | null
  device_metadata: string | null; created_at: string; api_key?: string
}
interface TelemetryEntry { id: string; device_id: string; payload: any; received_at: string }

export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(true)
  const [showRegister, setShowRegister] = useState(false)
  const [newName, setNewName] = useState('')
  const [newType, setNewType] = useState('iot')
  const [newEth, setNewEth] = useState('')
  const [newApiKey, setNewApiKey] = useState('')
  const [selectedDevice, setSelectedDevice] = useState<string | null>(null)
  const [telemetry, setTelemetry] = useState<TelemetryEntry[]>([])
  const [telemetryLoading, setTelemetryLoading] = useState(false)
  const [cmdText, setCmdText] = useState('')
  const [cmdParams, setCmdParams] = useState('')
  const [cmdResult, setCmdResult] = useState('')
  const [activeTab, setActiveTab] = useState<'telemetry' | 'commands'>('telemetry')
  const [error, setError] = useState('')

  const headers = () => {
    const token = localStorage.getItem('refinet_token')
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  }

  const fetchDevices = () => {
    fetch(`${API_URL}/devices`, { headers: headers() })
      .then(r => r.json())
      .then(data => { setDevices(Array.isArray(data) ? data : []); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    
    fetchDevices()
  }, [])

  const registerDevice = async () => {
    setError(''); setNewApiKey('')
    try {
      const resp = await fetch(`${API_URL}/devices/register`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ name: newName, device_type: newType, ...(newEth ? { eth_address: newEth } : {}) }),
      })
      if (!resp.ok) { setError(`Error: ${resp.status}`); return }
      const data = await resp.json()
      setNewApiKey(data.api_key || '')
      setNewName(''); setNewEth('')
      fetchDevices()
    } catch { setError('Connection error') }
  }

  const deregisterDevice = async (id: string) => {
    if (!confirm('Deregister this device? This cannot be undone.')) return
    await fetch(`${API_URL}/devices/${id}`, { method: 'DELETE', headers: headers() })
    if (selectedDevice === id) setSelectedDevice(null)
    fetchDevices()
  }

  const loadTelemetry = async (deviceId: string) => {
    setTelemetryLoading(true)
    try {
      const resp = await fetch(`${API_URL}/devices/${deviceId}/telemetry?limit=50`, { headers: headers() })
      const data = await resp.json()
      setTelemetry(Array.isArray(data) ? data : [])
    } catch { setTelemetry([]) }
    setTelemetryLoading(false)
  }

  const sendCommand = async (deviceId: string) => {
    setCmdResult('')
    try {
      let params = {}
      if (cmdParams.trim()) { try { params = JSON.parse(cmdParams) } catch { setCmdResult('Invalid JSON parameters'); return } }
      const resp = await fetch(`${API_URL}/devices/${deviceId}/command`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ command: cmdText, parameters: params }),
      })
      const data = await resp.json()
      setCmdResult(data.message || 'Command sent')
      setCmdText(''); setCmdParams('')
    } catch { setCmdResult('Failed to send command') }
  }

  const selectDevice = (id: string) => {
    setSelectedDevice(selectedDevice === id ? null : id)
    setActiveTab('telemetry')
    if (selectedDevice !== id) loadTelemetry(id)
  }

  const typeColors: Record<string, { bg: string; text: string }> = {
    iot: { bg: 'rgba(92,224,210,0.15)', text: 'var(--refi-teal)' },
    plc: { bg: 'rgba(96,165,250,0.15)', text: 'rgb(96,165,250)' },
    dlt: { bg: 'rgba(167,139,250,0.15)', text: 'rgb(167,139,250)' },
  }

  if (loading) return <div className="flex items-center justify-center min-h-[60vh]" style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Loading...</div>

  return (
    <div className="max-w-5xl mx-auto py-10 px-6 space-y-8 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ letterSpacing: '-0.02em' }}>Devices</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>Register IoT sensors, PLCs, and DLT nodes</p>
        </div>
        <button className="btn-primary" onClick={() => setShowRegister(!showRegister)}>{showRegister ? 'Cancel' : '+ Register Device'}</button>
      </div>

      {/* Register Form */}
      {showRegister && (
        <section className="card animate-slide-up" style={{ padding: 24 }}>
          <h2 className="font-bold mb-4" style={{ letterSpacing: '-0.02em' }}>Register New Device</h2>
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Device Name</label>
              <input className="input-base focus-glow w-full" placeholder="e.g. Temperature Sensor #1" value={newName} onChange={e => setNewName(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium mb-2 block" style={{ color: 'var(--text-secondary)' }}>Device Type</label>
              <div className="flex gap-2">
                {DEVICE_TYPES.map(t => (
                  <button key={t} onClick={() => setNewType(t)} className="text-xs px-4 py-2 rounded-lg transition-colors uppercase font-medium"
                    style={{ background: newType === t ? (typeColors[t]?.bg || 'var(--bg-tertiary)') : 'var(--bg-tertiary)', color: newType === t ? (typeColors[t]?.text || 'var(--text-primary)') : 'var(--text-secondary)', border: '1px solid ' + (newType === t ? 'transparent' : 'var(--border-default)'), fontFamily: "'JetBrains Mono', monospace" }}>
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>ETH Address <span style={{ color: 'var(--text-tertiary)' }}>(optional)</span></label>
              <input className="input-base focus-glow w-full" placeholder="0x..." value={newEth} onChange={e => setNewEth(e.target.value)} />
            </div>
            {error && <p style={{ color: 'var(--error)', fontSize: 13 }}>{error}</p>}
            <button className="btn-primary" onClick={registerDevice} disabled={!newName.trim()}>Register</button>
          </div>
          {newApiKey && (
            <div className="mt-4 p-4 rounded-lg animate-fade-in" style={{ background: 'rgba(92,224,210,0.08)', border: '1px solid var(--refi-teal)' }}>
              <p className="text-xs font-bold mb-1" style={{ color: 'var(--refi-teal)' }}>Device API Key (shown once — save it now)</p>
              <div className="flex items-center gap-2">
                <code className="text-sm flex-1 break-all" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>{newApiKey}</code>
                <CopyBtn text={newApiKey} />
              </div>
            </div>
          )}
        </section>
      )}

      {/* Device Grid */}
      {devices.length === 0 ? (
        <div className="card text-center py-12" style={{ color: 'var(--text-tertiary)' }}>
          <p className="text-sm">No devices registered</p>
          <p className="text-xs mt-1">Register your first IoT sensor, PLC, or DLT node</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {devices.map(d => (
            <div key={d.id}>
              <div className="card cursor-pointer transition-all" onClick={() => selectDevice(d.id)}
                style={{ padding: '16px 20px', borderColor: selectedDevice === d.id ? 'var(--refi-teal)' : undefined }}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ background: d.status === 'active' ? 'var(--success)' : 'var(--error)' }} />
                    <span className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{d.name}</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded uppercase" style={{ ...(typeColors[d.device_type] || typeColors.iot), fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>{d.device_type}</span>
                </div>
                <div className="flex gap-4 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  <span>{d.telemetry_count} events</span>
                  {d.last_seen_at && <span>Last seen: {new Date(d.last_seen_at).toLocaleDateString()}</span>}
                </div>
              </div>

              {/* Detail Panel */}
              {selectedDevice === d.id && (
                <div className="card mt-2 animate-slide-up" style={{ padding: '16px 20px' }}>
                  <div className="flex gap-2 mb-4">
                    <button className="text-xs px-3 py-1.5 rounded-lg" onClick={() => { setActiveTab('telemetry'); loadTelemetry(d.id) }}
                      style={{ background: activeTab === 'telemetry' ? 'var(--refi-teal-glow)' : 'var(--bg-tertiary)', color: activeTab === 'telemetry' ? 'var(--refi-teal)' : 'var(--text-secondary)' }}>
                      Telemetry
                    </button>
                    <button className="text-xs px-3 py-1.5 rounded-lg" onClick={() => setActiveTab('commands')}
                      style={{ background: activeTab === 'commands' ? 'var(--refi-teal-glow)' : 'var(--bg-tertiary)', color: activeTab === 'commands' ? 'var(--refi-teal)' : 'var(--text-secondary)' }}>
                      Commands
                    </button>
                    <div className="flex-1" />
                    <button className="text-xs px-3 py-1.5 rounded-lg" onClick={() => deregisterDevice(d.id)}
                      style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--error)', border: '1px solid rgba(248,113,113,0.2)' }}>
                      Deregister
                    </button>
                  </div>

                  {activeTab === 'telemetry' && (
                    <div>
                      {telemetryLoading ? <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Loading...</p> :
                        telemetry.length === 0 ? <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>No telemetry data yet</p> : (
                          <div className="space-y-2 max-h-64 overflow-y-auto">
                            {telemetry.map(t => (
                              <div key={t.id} className="p-3 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
                                <div className="text-[10px] mb-1" style={{ color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>{new Date(t.received_at).toLocaleString()}</div>
                                <pre className="text-xs overflow-x-auto" style={{ color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace" }}>{JSON.stringify(t.payload, null, 2)}</pre>
                              </div>
                            ))}
                          </div>
                        )}
                    </div>
                  )}

                  {activeTab === 'commands' && (
                    <div className="space-y-3">
                      <input className="input-base focus-glow w-full text-sm" placeholder="Command name (e.g. restart, configure)" value={cmdText} onChange={e => setCmdText(e.target.value)} />
                      <textarea className="input-base focus-glow w-full text-xs resize-none" rows={3} placeholder='Parameters JSON (optional): {"key": "value"}' value={cmdParams} onChange={e => setCmdParams(e.target.value)} style={{ fontFamily: "'JetBrains Mono', monospace" }} />
                      <button className="btn-primary !text-xs" onClick={() => sendCommand(d.id)} disabled={!cmdText.trim()}>Send Command</button>
                      {cmdResult && <p className="text-xs" style={{ color: 'var(--refi-teal)' }}>{cmdResult}</p>}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      className="p-2 rounded-lg" style={{ color: copied ? 'var(--success)' : 'var(--text-tertiary)' }}>
      {copied ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
        : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>}
    </button>
  )
}
