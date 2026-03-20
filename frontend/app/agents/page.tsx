'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'

interface Agent {
  id: string; name: string; archetype: string; status: string
  delegation_policy: string; created_at: string; last_heartbeat?: string
}
interface AgentTask {
  id: string; description: string; status: string; phase: string
  result_summary?: string; created_at: string; completed_at?: string
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [tasks, setTasks] = useState<AgentTask[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [showRegister, setShowRegister] = useState(false)
  const [newName, setNewName] = useState('')
  const [newArchetype, setNewArchetype] = useState('groot-chat')
  const [newDesc, setNewDesc] = useState('')
  const [taskInput, setTaskInput] = useState('')
  const [soulText, setSoulText] = useState('')
  const [showSoul, setShowSoul] = useState(false)
  const [taskFilter, setTaskFilter] = useState<string>('')
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'tasks' | 'soul' | 'config'>('tasks')

  const ARCHETYPES = [
    'groot-chat', 'contract-analyst', 'knowledge-curator', 'platform-ops',
    'dapp-builder', 'device-monitor', 'contract-watcher', 'onboarding',
    'maintenance', 'orchestrator', 'security-sentinel', 'repo-migrator',
  ]

  const headers = () => {
    const token = localStorage.getItem('refinet_token')
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  }

  const fetchAgents = () => {
    fetch(`${API_URL}/agents/`, { headers: headers() })
      .then(r => r.json())
      .then(data => { setAgents(Array.isArray(data) ? data : data.agents || []); setLoading(false) })
      .catch(() => setLoading(false))
  }

  const fetchTasks = (agentId: string) => {
    const qs = taskFilter ? `?status=${taskFilter}` : ''
    fetch(`${API_URL}/agents/${agentId}/tasks${qs}`, { headers: headers() })
      .then(r => r.json())
      .then(data => setTasks(Array.isArray(data) ? data : data.tasks || []))
      .catch(() => setTasks([]))
  }

  const fetchSoul = (agentId: string) => {
    fetch(`${API_URL}/agents/${agentId}/soul`, { headers: headers() })
      .then(r => r.json())
      .then(data => setSoulText(data.soul_md || data.soul || ''))
      .catch(() => setSoulText(''))
  }

  useEffect(() => { fetchAgents() }, [])

  useEffect(() => {
    if (selectedAgent) {
      fetchTasks(selectedAgent)
      fetchSoul(selectedAgent)
    }
  }, [selectedAgent, taskFilter])

  const registerAgent = () => {
    if (!newName.trim()) return
    fetch(`${API_URL}/agents/register`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ name: newName, archetype: newArchetype, description: newDesc }),
    })
      .then(r => r.json())
      .then(() => { setShowRegister(false); setNewName(''); setNewDesc(''); fetchAgents() })
      .catch(e => setError(e.message))
  }

  const runTask = () => {
    if (!selectedAgent || !taskInput.trim()) return
    fetch(`${API_URL}/agents/${selectedAgent}/run`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ task: taskInput }),
    })
      .then(r => r.json())
      .then(() => { setTaskInput(''); fetchTasks(selectedAgent!) })
      .catch(e => setError(e.message))
  }

  const saveSoul = () => {
    if (!selectedAgent) return
    fetch(`${API_URL}/agents/${selectedAgent}/soul`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ soul_md: soulText }),
    })
      .then(r => r.json())
      .then(() => setError(''))
      .catch(e => setError(e.message))
  }

  const cancelTask = (taskId: string) => {
    if (!selectedAgent) return
    fetch(`${API_URL}/agents/${selectedAgent}/tasks/${taskId}/cancel`, {
      method: 'POST', headers: headers(),
    })
      .then(() => fetchTasks(selectedAgent!))
  }

  const statusColor = (s: string) => {
    if (s === 'completed') return '#22c55e'
    if (s === 'running' || s === 'in_progress') return '#3b82f6'
    if (s === 'failed' || s === 'error') return '#ef4444'
    if (s === 'cancelled') return '#6b7280'
    return '#f59e0b'
  }

  const selected = agents.find(a => a.id === selectedAgent)

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Agent Management</h1>
        <button onClick={() => setShowRegister(!showRegister)}
          style={{ padding: '8px 16px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
          + Register Agent
        </button>
      </div>

      {error && <div style={{ padding: 12, background: '#dc2626', color: '#fff', borderRadius: 6, marginBottom: 16 }}>{error}</div>}

      {showRegister && (
        <div style={{ padding: 16, border: '1px solid var(--border-subtle)', borderRadius: 8, marginBottom: 20, background: 'var(--bg-secondary)' }}>
          <h3 style={{ marginBottom: 12 }}>Register New Agent</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Agent name"
              style={{ padding: 8, borderRadius: 6, border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)', color: 'inherit' }} />
            <select value={newArchetype} onChange={e => setNewArchetype(e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)', color: 'inherit' }}>
              {ARCHETYPES.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <input value={newDesc} onChange={e => setNewDesc(e.target.value)} placeholder="Description (optional)"
            style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)', color: 'inherit', marginBottom: 12 }} />
          <button onClick={registerAgent} style={{ padding: '8px 20px', background: '#22c55e', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
            Register
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 20 }}>
        {/* Agent list */}
        <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)', fontWeight: 600, fontSize: 13 }}>
            Agents ({agents.length})
          </div>
          {loading ? (
            <div style={{ padding: 16, color: 'var(--text-secondary)' }}>Loading...</div>
          ) : agents.length === 0 ? (
            <div style={{ padding: 16, color: 'var(--text-secondary)' }}>No agents registered. Click + Register Agent to start.</div>
          ) : (
            agents.map(a => (
              <div key={a.id} onClick={() => { setSelectedAgent(a.id); setTab('tasks') }}
                style={{ padding: '10px 16px', cursor: 'pointer', borderBottom: '1px solid var(--border-subtle)',
                  background: selectedAgent === a.id ? 'var(--bg-secondary)' : 'transparent' }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{a.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{a.archetype}</div>
                <div style={{ fontSize: 10, color: statusColor(a.status), marginTop: 2 }}>{a.status}</div>
              </div>
            ))
          )}
        </div>

        {/* Agent detail */}
        <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, minHeight: 400 }}>
          {!selected ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>
              Select an agent to view tasks, SOUL, and configuration
            </div>
          ) : (
            <>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <span style={{ fontWeight: 700, fontSize: 16 }}>{selected.name}</span>
                  <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--text-secondary)' }}>{selected.archetype}</span>
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(['tasks', 'soul', 'config'] as const).map(t => (
                    <button key={t} onClick={() => setTab(t)}
                      style={{ padding: '4px 12px', borderRadius: 4, border: 'none', cursor: 'pointer',
                        background: tab === t ? '#3b82f6' : 'var(--bg-secondary)', color: tab === t ? '#fff' : 'inherit', fontSize: 12 }}>
                      {t.charAt(0).toUpperCase() + t.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ padding: 16 }}>
                {tab === 'tasks' && (
                  <>
                    {/* Run task input */}
                    <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                      <input value={taskInput} onChange={e => setTaskInput(e.target.value)} placeholder="Describe a task for this agent..."
                        onKeyDown={e => e.key === 'Enter' && runTask()}
                        style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)', color: 'inherit' }} />
                      <button onClick={runTask} style={{ padding: '8px 16px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                        Run Task
                      </button>
                    </div>

                    {/* Filter */}
                    <div style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
                      {['', 'pending', 'running', 'completed', 'failed'].map(f => (
                        <button key={f} onClick={() => setTaskFilter(f)}
                          style={{ padding: '3px 10px', borderRadius: 4, border: 'none', cursor: 'pointer', fontSize: 11,
                            background: taskFilter === f ? '#3b82f6' : 'var(--bg-secondary)', color: taskFilter === f ? '#fff' : 'inherit' }}>
                          {f || 'All'}
                        </button>
                      ))}
                    </div>

                    {/* Task list */}
                    {tasks.length === 0 ? (
                      <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-secondary)' }}>No tasks yet</div>
                    ) : (
                      tasks.map(t => (
                        <div key={t.id} style={{ padding: 12, border: '1px solid var(--border-subtle)', borderRadius: 6, marginBottom: 8, background: 'var(--bg-primary)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: 13, fontWeight: 500 }}>{t.description}</div>
                              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                                Phase: {t.phase} | Status: <span style={{ color: statusColor(t.status) }}>{t.status}</span>
                              </div>
                              {t.result_summary && (
                                <div style={{ fontSize: 11, marginTop: 4, padding: 8, background: 'var(--bg-secondary)', borderRadius: 4 }}>
                                  {t.result_summary}
                                </div>
                              )}
                            </div>
                            {(t.status === 'pending' || t.status === 'running') && (
                              <button onClick={() => cancelTask(t.id)}
                                style={{ padding: '3px 8px', background: '#dc2626', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 11, marginLeft: 8 }}>
                                Cancel
                              </button>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </>
                )}

                {tab === 'soul' && (
                  <>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                      SOUL.md defines this agent&apos;s identity, personality, and capabilities. Markdown format.
                    </p>
                    <textarea value={soulText} onChange={e => setSoulText(e.target.value)}
                      style={{ width: '100%', minHeight: 300, padding: 12, borderRadius: 6, border: '1px solid var(--border-subtle)',
                        background: 'var(--bg-primary)', color: 'inherit', fontFamily: 'monospace', fontSize: 13, resize: 'vertical' }} />
                    <button onClick={saveSoul}
                      style={{ marginTop: 8, padding: '8px 20px', background: '#22c55e', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
                      Save SOUL
                    </button>
                  </>
                )}

                {tab === 'config' && (
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px 16px' }}>
                      <span style={{ fontWeight: 600 }}>Agent ID:</span> <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{selected.id}</span>
                      <span style={{ fontWeight: 600 }}>Archetype:</span> <span>{selected.archetype}</span>
                      <span style={{ fontWeight: 600 }}>Status:</span> <span style={{ color: statusColor(selected.status) }}>{selected.status}</span>
                      <span style={{ fontWeight: 600 }}>Delegation:</span> <span>{selected.delegation_policy}</span>
                      <span style={{ fontWeight: 600 }}>Created:</span> <span>{new Date(selected.created_at).toLocaleString()}</span>
                      {selected.last_heartbeat && (
                        <><span style={{ fontWeight: 600 }}>Last Heartbeat:</span> <span>{new Date(selected.last_heartbeat).toLocaleString()}</span></>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
