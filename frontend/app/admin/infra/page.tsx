'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

const PROVIDERS = ['oracle_cloud', 'aws', 'gcp', 'hetzner', 'bare_metal']
const ROLES = ['primary', 'worker', 'bitnet', 'database', 'gateway']
const STATUS_CLR: Record<string, string> = { online: '#22C55E', degraded: '#F59E0B', offline: '#EF4444', provisioning: '#3B82F6', terminated: '#6B7280' }
const HEALTH_CLR: Record<string, string> = { healthy: '#22C55E', unhealthy: '#EF4444', timeout: '#F59E0B' }

export default function AdminInfra() {
  const { headers } = useAdmin()
  const [nodes, setNodes] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [checking, setChecking] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '', provider: 'oracle_cloud', region: '', instance_type: '', instance_id: '',
    compartment_id: '', public_ip: '', private_ip: '', ssh_port: '22',
    cpu_count: '', memory_gb: '', disk_gb: '', role: 'worker',
    services: '', api_endpoint: '', notes: '',
  })

  const fetchNodes = async () => {
    try {
      const [nr, sr] = await Promise.all([
        fetch(`${API_URL}/admin/infrastructure/nodes`, { headers }),
        fetch(`${API_URL}/admin/infrastructure/stats`, { headers }),
      ])
      if (nr.ok) setNodes(await nr.json())
      if (sr.ok) setStats(await sr.json())
    } catch {}
    setLoading(false)
  }

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    fetchNodes()
  }, [headers.Authorization])

  const addNode = async () => {
    if (!form.name.trim()) { setError('Name is required'); return }
    setError(''); setMsg('')
    try {
      const body: any = { ...form }
      body.ssh_port = parseInt(form.ssh_port) || 22
      if (form.cpu_count) body.cpu_count = parseInt(form.cpu_count)
      if (form.memory_gb) body.memory_gb = parseInt(form.memory_gb)
      if (form.disk_gb) body.disk_gb = parseInt(form.disk_gb)
      if (form.services) body.services = form.services.split(',').map((s: string) => s.trim()).filter(Boolean)
      const r = await fetch(`${API_URL}/admin/infrastructure/nodes`, { method: 'POST', headers, body: JSON.stringify(body) })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || 'Failed'); return }
      setMsg(`Node '${form.name}' added`)
      setForm({ name: '', provider: 'oracle_cloud', region: '', instance_type: '', instance_id: '', compartment_id: '', public_ip: '', private_ip: '', ssh_port: '22', cpu_count: '', memory_gb: '', disk_gb: '', role: 'worker', services: '', api_endpoint: '', notes: '' })
      setShowAdd(false); fetchNodes()
    } catch (e: any) { setError(e.message) }
  }

  const healthCheck = async (nodeId: string) => {
    setChecking(nodeId)
    try {
      const r = await fetch(`${API_URL}/admin/infrastructure/nodes/${nodeId}/health`, { method: 'POST', headers })
      const d = await r.json()
      setMsg(`Health: ${d.status} (${d.latency_ms || '?'}ms)`)
      fetchNodes()
    } catch { setMsg('Health check failed') }
    setChecking(null)
  }

  const updateStatus = async (nodeId: string, status: string) => {
    await fetch(`${API_URL}/admin/infrastructure/nodes/${nodeId}`, { method: 'PUT', headers, body: JSON.stringify({ status }) })
    fetchNodes()
  }

  const removeNode = async (nodeId: string) => {
    await fetch(`${API_URL}/admin/infrastructure/nodes/${nodeId}`, { method: 'DELETE', headers })
    fetchNodes()
  }

  if (loading) return <LoadingState label="Loading infrastructure..." />

  return (
    <div>
      <PageHeader title="Infrastructure Nodes" subtitle="Manage cloud instances and server nodes" />

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          <div className="card p-3" style={{ border: '1px solid var(--border-subtle)' }}><div className="text-[10px] uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>Nodes</div><div className="text-xl font-bold" style={{ color: 'var(--refi-teal)' }}>{stats.total_nodes}</div></div>
          <div className="card p-3" style={{ border: '1px solid var(--border-subtle)' }}><div className="text-[10px] uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>Total CPU</div><div className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{stats.total_cpu} cores</div></div>
          <div className="card p-3" style={{ border: '1px solid var(--border-subtle)' }}><div className="text-[10px] uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>Memory</div><div className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{stats.total_memory_gb} GB</div></div>
          <div className="card p-3" style={{ border: '1px solid var(--border-subtle)' }}><div className="text-[10px] uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>Disk</div><div className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{stats.total_disk_gb} GB</div></div>
          <div className="card p-3" style={{ border: '1px solid var(--border-subtle)' }}><div className="text-[10px] uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>Providers</div><div className="text-sm font-mono" style={{ color: 'var(--text-secondary)' }}>{Object.entries(stats.by_provider || {}).map(([k, v]) => `${k}: ${v}`).join(', ') || 'none'}</div></div>
        </div>
      )}

      {error && <div className="mb-3 p-3 rounded-lg text-xs" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#EF4444' }}>{error}</div>}
      {msg && <div className="mb-3 p-3 rounded-lg text-xs" style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', color: '#22C55E' }}>{msg}</div>}

      <div className="flex justify-between items-center mb-4">
        <h3 className="font-bold text-base">Active Nodes ({nodes.filter(n => n.status !== 'terminated').length})</h3>
        <button onClick={() => setShowAdd(!showAdd)}
          style={{ background: 'var(--refi-teal)', color: '#000', border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
          + Add Node
        </button>
      </div>

      {showAdd && (
        <div className="card p-5 mb-4" style={{ border: '1px solid var(--refi-teal)' }}>
          <h4 className="font-semibold text-sm mb-3">Register New Node</h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-3">
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Node name *" className="text-xs p-2 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }} />
            <select value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })} className="text-xs p-2 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
              {PROVIDERS.map(p => <option key={p} value={p}>{p.replace('_', ' ')}</option>)}
            </select>
            <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} className="text-xs p-2 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
            <input value={form.region} onChange={e => setForm({ ...form, region: e.target.value })} placeholder="Region" className="text-xs p-2 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }} />
            <input value={form.public_ip} onChange={e => setForm({ ...form, public_ip: e.target.value })} placeholder="Public IP" className="text-xs p-2 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }} />
            <input value={form.api_endpoint} onChange={e => setForm({ ...form, api_endpoint: e.target.value })} placeholder="API endpoint" className="text-xs p-2 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }} />
            <input value={form.cpu_count} onChange={e => setForm({ ...form, cpu_count: e.target.value })} placeholder="CPUs" type="number" className="text-xs p-2 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }} />
            <input value={form.memory_gb} onChange={e => setForm({ ...form, memory_gb: e.target.value })} placeholder="Memory (GB)" type="number" className="text-xs p-2 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }} />
            <input value={form.disk_gb} onChange={e => setForm({ ...form, disk_gb: e.target.value })} placeholder="Disk (GB)" type="number" className="text-xs p-2 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }} />
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowAdd(false)} className="text-xs px-3 py-1.5 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-secondary)', cursor: 'pointer' }}>Cancel</button>
            <button onClick={addNode} className="text-xs px-4 py-1.5 rounded font-semibold" style={{ background: 'var(--refi-teal)', color: '#000', border: 'none', cursor: 'pointer' }}>Register Node</button>
          </div>
        </div>
      )}

      {/* Node list */}
      {nodes.filter(n => n.status !== 'terminated').length === 0 ? (
        <div className="text-center py-10">
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No infrastructure nodes registered</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Add your cloud instances to manage and scale the platform</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {nodes.filter(n => n.status !== 'terminated').map(n => (
            <div key={n.id} className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{n.name}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold" style={{ background: `${STATUS_CLR[n.status] || '#6B7280'}20`, color: STATUS_CLR[n.status] || '#6B7280' }}>{n.status}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>{n.role}</span>
                    {n.last_health_status && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: `${HEALTH_CLR[n.last_health_status] || '#6B7280'}15`, color: HEALTH_CLR[n.last_health_status] || '#6B7280' }}>
                        {n.last_health_status} {n.health_check_latency_ms ? `(${n.health_check_latency_ms}ms)` : ''}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-4 text-[11px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                    <span>{n.provider.replace('_', ' ')}</span>
                    {n.region && <span>{n.region}</span>}
                    {n.public_ip && <span>{n.public_ip}</span>}
                    {n.instance_type && <span>{n.instance_type}</span>}
                  </div>
                </div>
                <div className="flex gap-1">
                  {n.api_endpoint && (
                    <button onClick={() => healthCheck(n.id)} disabled={checking === n.id}
                      className="text-[10px] px-2 py-1 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                      {checking === n.id ? '...' : 'Health Check'}
                    </button>
                  )}
                  {n.status === 'online' && <button onClick={() => updateStatus(n.id, 'offline')} className="text-[10px] px-2 py-1 rounded" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#EF4444', cursor: 'pointer' }}>Stop</button>}
                  {n.status === 'offline' && <button onClick={() => updateStatus(n.id, 'online')} className="text-[10px] px-2 py-1 rounded" style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', color: '#22C55E', cursor: 'pointer' }}>Start</button>}
                  <button onClick={() => removeNode(n.id)} className="text-[10px] px-2 py-1 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-tertiary)', cursor: 'pointer' }}>Remove</button>
                </div>
              </div>
              <div className="flex gap-4 text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                {n.cpu_count && <span>{n.cpu_count} CPU</span>}
                {n.memory_gb && <span>{n.memory_gb} GB RAM</span>}
                {n.disk_gb && <span>{n.disk_gb} GB Disk</span>}
                {n.services?.length > 0 && <span>Services: {n.services.join(', ')}</span>}
                {n.last_health_check && <span>Last check: {new Date(n.last_health_check).toLocaleString()}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
