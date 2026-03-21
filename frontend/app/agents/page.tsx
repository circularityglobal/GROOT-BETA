'use client'

import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '@/lib/config'

interface Agent {
  id: string; name: string; archetype: string; status: string
  delegation_policy: string; description?: string; created_at: string; last_heartbeat?: string
}
interface AgentTask {
  id: string; description: string; status: string; phase: string
  result_summary?: string; created_at: string; completed_at?: string
  steps?: { phase: string; output: string }[]
}

const ARCHETYPES = [
  'groot-chat', 'contract-analyst', 'knowledge-curator', 'platform-ops',
  'dapp-builder', 'device-monitor', 'contract-watcher', 'onboarding',
  'maintenance', 'orchestrator', 'security-sentinel', 'repo-migrator',
]

const ARCHETYPE_COLORS: Record<string, { bg: string; text: string }> = {
  'groot-chat': { bg: 'rgba(92,224,210,0.12)', text: 'var(--refi-teal)' },
  'contract-analyst': { bg: 'rgba(250,204,21,0.12)', text: 'rgb(250,204,21)' },
  'knowledge-curator': { bg: 'rgba(167,139,250,0.12)', text: 'rgb(167,139,250)' },
  'platform-ops': { bg: 'rgba(96,165,250,0.12)', text: 'rgb(96,165,250)' },
  'dapp-builder': { bg: 'rgba(249,115,22,0.12)', text: 'rgb(249,115,22)' },
  'device-monitor': { bg: 'rgba(74,222,128,0.12)', text: 'rgb(74,222,128)' },
  'contract-watcher': { bg: 'rgba(250,204,21,0.12)', text: 'rgb(250,204,21)' },
  'security-sentinel': { bg: 'rgba(248,113,113,0.12)', text: 'rgb(248,113,113)' },
  'repo-migrator': { bg: 'rgba(56,189,248,0.12)', text: 'rgb(56,189,248)' },
  'orchestrator': { bg: 'rgba(192,132,252,0.12)', text: 'rgb(192,132,252)' },
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'var(--success)', running: 'rgb(96,165,250)', in_progress: 'rgb(96,165,250)',
  failed: 'var(--error)', error: 'var(--error)', cancelled: 'var(--text-tertiary)',
  pending: 'rgb(250,204,21)', idle: 'var(--text-tertiary)', active: 'var(--success)',
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
  const [taskFilter, setTaskFilter] = useState<string>('')
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [tab, setTab] = useState<'tasks' | 'soul' | 'config'>('tasks')
  const [taskRunning, setTaskRunning] = useState(false)

  const headers = useCallback(() => {
    const token = localStorage.getItem('refinet_token')
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  }, [])

  const fetchAgents = useCallback(() => {
    fetch(`${API_URL}/agents/`, { headers: headers() })
      .then(r => r.ok ? r.json() : [])
      .then(data => { setAgents(Array.isArray(data) ? data : data.agents || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [headers])

  const fetchTasks = useCallback((agentId: string) => {
    const qs = taskFilter ? `?status=${taskFilter}` : ''
    fetch(`${API_URL}/agents/${agentId}/tasks${qs}`, { headers: headers() })
      .then(r => r.ok ? r.json() : [])
      .then(data => setTasks(Array.isArray(data) ? data : data.tasks || []))
      .catch(() => setTasks([]))
  }, [headers, taskFilter])

  const fetchSoul = useCallback((agentId: string) => {
    fetch(`${API_URL}/agents/${agentId}/soul`, { headers: headers() })
      .then(r => r.ok ? r.json() : {} as Record<string, string>)
      .then((data: Record<string, string>) => setSoulText(data.soul_md || data.soul || ''))
      .catch(() => setSoulText(''))
  }, [headers])

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    
    fetchAgents()
  }, [fetchAgents])

  useEffect(() => {
    if (selectedAgent) { fetchTasks(selectedAgent); fetchSoul(selectedAgent) }
  }, [selectedAgent, taskFilter, fetchTasks, fetchSoul])

  const registerAgent = async () => {
    if (!newName.trim()) return
    setError('')
    try {
      const resp = await fetch(`${API_URL}/agents/register`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ name: newName, archetype: newArchetype, description: newDesc }),
      })
      if (!resp.ok) { setError(`Error: ${resp.status}`); return }
      setShowRegister(false); setNewName(''); setNewDesc(''); fetchAgents()
      setMsg('Agent registered successfully')
      setTimeout(() => setMsg(''), 3000)
    } catch (e: any) { setError(e.message) }
  }

  const runTask = async () => {
    if (!selectedAgent || !taskInput.trim()) return
    setTaskRunning(true); setError('')
    try {
      const resp = await fetch(`${API_URL}/agents/${selectedAgent}/run`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ task: taskInput }),
      })
      if (!resp.ok) { setError(`Error: ${resp.status}`); setTaskRunning(false); return }
      setTaskInput(''); fetchTasks(selectedAgent)
      setMsg('Task submitted to cognitive loop')
      setTimeout(() => setMsg(''), 3000)
    } catch (e: any) { setError(e.message) }
    setTaskRunning(false)
  }

  const saveSoul = async () => {
    if (!selectedAgent) return
    try {
      await fetch(`${API_URL}/agents/${selectedAgent}/soul`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ soul_md: soulText }),
      })
      setMsg('SOUL updated'); setTimeout(() => setMsg(''), 3000)
    } catch (e: any) { setError(e.message) }
  }

  const cancelTask = async (taskId: string) => {
    if (!selectedAgent) return
    await fetch(`${API_URL}/agents/${selectedAgent}/tasks/${taskId}/cancel`, { method: 'POST', headers: headers() })
    fetchTasks(selectedAgent)
  }

  const selected = agents.find(a => a.id === selectedAgent)
  const ac = (archetype: string) => ARCHETYPE_COLORS[archetype] || { bg: 'var(--bg-tertiary)', text: 'var(--text-secondary)' }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)', fontSize: 13 }}>Loading agents...</span>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto py-10 px-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ letterSpacing: '-0.02em' }}>Agent Management</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>
            Register, configure, and run autonomous agents through the 6-phase cognitive loop
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowRegister(!showRegister)}>
          {showRegister ? 'Cancel' : '+ Register Agent'}
        </button>
      </div>

      {/* Messages */}
      {error && <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--error)', border: '1px solid rgba(248,113,113,0.2)' }}>{error}</div>}
      {msg && <div className="mb-4 p-3 rounded-lg text-sm animate-fade-in" style={{ background: 'rgba(92,224,210,0.08)', color: 'var(--refi-teal)', border: '1px solid var(--refi-teal)' }}>{msg}</div>}

      {/* Register Form */}
      {showRegister && (
        <section className="card animate-slide-up mb-6" style={{ padding: 24 }}>
          <h2 className="font-bold mb-4" style={{ letterSpacing: '-0.02em' }}>Register New Agent</h2>
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Agent Name</label>
              <input className="input-base focus-glow w-full" placeholder="e.g. My Contract Analyzer" value={newName} onChange={e => setNewName(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium mb-2 block" style={{ color: 'var(--text-secondary)' }}>Archetype</label>
              <div className="flex flex-wrap gap-2">
                {ARCHETYPES.map(a => {
                  const c = ac(a)
                  return (
                    <button key={a} onClick={() => setNewArchetype(a)} className="text-xs px-3 py-1.5 rounded-lg transition-colors"
                      style={{
                        background: newArchetype === a ? c.bg : 'var(--bg-tertiary)',
                        color: newArchetype === a ? c.text : 'var(--text-secondary)',
                        border: `1px solid ${newArchetype === a ? 'transparent' : 'var(--border-default)'}`,
                        fontFamily: "'JetBrains Mono', monospace", fontWeight: 500,
                      }}>
                      {a}
                    </button>
                  )
                })}
              </div>
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--text-secondary)' }}>Description <span style={{ color: 'var(--text-tertiary)' }}>(optional)</span></label>
              <input className="input-base focus-glow w-full" placeholder="What does this agent do?" value={newDesc} onChange={e => setNewDesc(e.target.value)} />
            </div>
            <button className="btn-primary" onClick={registerAgent} disabled={!newName.trim()}>Register Agent</button>
          </div>
        </section>
      )}

      {/* Stats */}
      <div className="grid gap-3 mb-6" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))' }}>
        <StatCard icon={<AgentIcon />} label="Total Agents" value={agents.length.toString()} color="var(--refi-teal)" />
        <StatCard icon={<ActiveIcon />} label="Active" value={agents.filter(a => a.status === 'active' || a.status === 'idle').length.toString()} color="var(--success)" />
        <StatCard icon={<TaskIcon />} label="Tasks" value={tasks.length.toString()} color="rgb(96,165,250)" />
      </div>

      {/* Main content: agent list + detail */}
      <div className="grid gap-5" style={{ gridTemplateColumns: agents.length > 0 ? '280px 1fr' : '1fr' }}>
        {/* Agent List */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-xs font-semibold uppercase" style={{ letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>
              Agents ({agents.length})
            </span>
          </div>
          {agents.length === 0 ? (
            <div className="p-6 text-center">
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No agents registered</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Click + Register Agent to create your first autonomous agent</p>
            </div>
          ) : (
            <div style={{ maxHeight: 500, overflowY: 'auto' }}>
              {agents.map(a => {
                const c = ac(a.archetype)
                return (
                  <div key={a.id} onClick={() => { setSelectedAgent(a.id); setTab('tasks') }}
                    className="cursor-pointer transition-all"
                    style={{
                      padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)',
                      background: selectedAgent === a.id ? 'var(--bg-tertiary)' : 'transparent',
                      borderLeft: selectedAgent === a.id ? '2px solid var(--refi-teal)' : '2px solid transparent',
                    }}
                    onMouseEnter={e => { if (selectedAgent !== a.id) e.currentTarget.style.background = 'var(--bg-elevated)' }}
                    onMouseLeave={e => { if (selectedAgent !== a.id) e.currentTarget.style.background = 'transparent' }}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{a.name}</span>
                      <span className="w-2 h-2 rounded-full" style={{ background: STATUS_COLORS[a.status] || 'var(--text-tertiary)' }} />
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: c.bg, color: c.text, fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>{a.archetype}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Detail Panel */}
        {agents.length > 0 && (
          <div className="card" style={{ padding: 0, overflow: 'hidden', minHeight: 400 }}>
            {!selected ? (
              <div className="flex items-center justify-center h-full min-h-[400px]" style={{ color: 'var(--text-tertiary)' }}>
                <div className="text-center">
                  <AgentIcon size={32} />
                  <p className="text-sm mt-3">Select an agent to view tasks, SOUL, and configuration</p>
                </div>
              </div>
            ) : (
              <>
                {/* Detail header */}
                <div className="px-5 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-base" style={{ letterSpacing: '-0.02em' }}>{selected.name}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded" style={{ ...ac(selected.archetype), fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>
                      {selected.archetype}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    {(['tasks', 'soul', 'config'] as const).map(t => (
                      <button key={t} onClick={() => setTab(t)} className="text-xs px-3 py-1.5 rounded-lg transition-colors"
                        style={{
                          background: tab === t ? 'var(--refi-teal-glow)' : 'var(--bg-tertiary)',
                          color: tab === t ? 'var(--refi-teal)' : 'var(--text-secondary)',
                        }}>
                        {t === 'tasks' ? 'Tasks' : t === 'soul' ? 'SOUL' : 'Config'}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Tab content */}
                <div className="p-5">
                  {tab === 'tasks' && (
                    <>
                      {/* Task input */}
                      <div className="flex gap-2 mb-4">
                        <input className="input-base focus-glow flex-1" placeholder="Describe a task for the cognitive loop..."
                          value={taskInput} onChange={e => setTaskInput(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && runTask()} />
                        <button className="btn-primary whitespace-nowrap" onClick={runTask} disabled={!taskInput.trim() || taskRunning}>
                          {taskRunning ? 'Submitting...' : 'Run Task'}
                        </button>
                      </div>

                      {/* Filter pills */}
                      <div className="flex gap-1 mb-4">
                        {['', 'pending', 'running', 'completed', 'failed'].map(f => (
                          <button key={f} onClick={() => setTaskFilter(f)} className="text-[11px] px-3 py-1 rounded-lg transition-colors"
                            style={{
                              background: taskFilter === f ? 'var(--refi-teal-glow)' : 'var(--bg-tertiary)',
                              color: taskFilter === f ? 'var(--refi-teal)' : 'var(--text-secondary)',
                              fontFamily: "'JetBrains Mono', monospace",
                            }}>
                            {f || 'all'}
                          </button>
                        ))}
                      </div>

                      {/* Task list */}
                      {tasks.length === 0 ? (
                        <div className="text-center py-8" style={{ color: 'var(--text-tertiary)' }}>
                          <p className="text-sm">No tasks yet</p>
                          <p className="text-xs mt-1">Submit a task above to start the PERCEIVE &rarr; PLAN &rarr; ACT &rarr; OBSERVE &rarr; REFLECT &rarr; STORE cycle</p>
                        </div>
                      ) : (
                        <div className="space-y-2 max-h-[420px] overflow-y-auto">
                          {tasks.map(t => (
                            <div key={t.id} className="p-3 rounded-lg" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)' }}>
                              <div className="flex items-start justify-between gap-3">
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{t.description}</p>
                                  <div className="flex items-center gap-3 mt-2">
                                    <span className="text-[10px] px-2 py-0.5 rounded" style={{
                                      background: `${STATUS_COLORS[t.status] || 'var(--text-tertiary)'}20`,
                                      color: STATUS_COLORS[t.status] || 'var(--text-tertiary)',
                                      fontFamily: "'JetBrains Mono', monospace", fontWeight: 500,
                                    }}>{t.status}</span>
                                    <span className="text-[10px]" style={{ color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
                                      phase: {t.phase}
                                    </span>
                                    <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                                      {timeAgo(t.created_at)}
                                    </span>
                                  </div>
                                  {t.result_summary && (
                                    <div className="mt-2 p-2 rounded text-xs" style={{ background: 'var(--bg-elevated)', fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
                                      {t.result_summary}
                                    </div>
                                  )}
                                </div>
                                {(t.status === 'pending' || t.status === 'running') && (
                                  <button onClick={() => cancelTask(t.id)} className="text-[10px] px-2 py-1 rounded-lg shrink-0"
                                    style={{ background: 'rgba(248,113,113,0.1)', color: 'var(--error)', border: '1px solid rgba(248,113,113,0.2)' }}>
                                    Cancel
                                  </button>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}

                  {tab === 'soul' && (
                    <div>
                      <p className="text-xs mb-3" style={{ color: 'var(--text-tertiary)' }}>
                        SOUL.md defines this agent&apos;s identity, personality, knowledge domains, and behavioral constraints. Markdown format.
                      </p>
                      <textarea value={soulText} onChange={e => setSoulText(e.target.value)}
                        className="input-base focus-glow w-full resize-y"
                        style={{ minHeight: 320, fontFamily: "'JetBrains Mono', monospace", fontSize: 12, lineHeight: 1.6 }}
                        placeholder={'# Agent Identity\n\nDescribe who this agent is...\n\n## Personality\n\n## Knowledge Domains\n\n## Capabilities\n\n## Boundaries'} />
                      <button className="btn-primary mt-3" onClick={saveSoul}>Save SOUL</button>
                    </div>
                  )}

                  {tab === 'config' && (
                    <div className="space-y-1">
                      <ConfigRow label="Agent ID" value={selected.id} mono />
                      <ConfigRow label="Archetype" value={selected.archetype} />
                      <ConfigRow label="Status" value={selected.status} color={STATUS_COLORS[selected.status]} />
                      <ConfigRow label="Delegation Policy" value={selected.delegation_policy || 'none'} />
                      <ConfigRow label="Created" value={new Date(selected.created_at).toLocaleString()} />
                      {selected.last_heartbeat && <ConfigRow label="Last Heartbeat" value={new Date(selected.last_heartbeat).toLocaleString()} />}
                      {selected.description && <ConfigRow label="Description" value={selected.description} />}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── Sub-components ─── */

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) {
  return (
    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 10, padding: '14px 16px', transition: 'all 0.2s' }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-default)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}>
      <div className="flex items-center gap-2 mb-2">
        <span style={{ color, display: 'flex' }}>{icon}</span>
        <span className="text-[11px] uppercase font-medium" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>{label}</span>
      </div>
      <div className="text-xl font-bold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>{value}</div>
    </div>
  )
}

function ConfigRow({ label, value, mono, color }: { label: string; value: string; mono?: boolean; color?: string }) {
  return (
    <div className="flex items-center py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <span className="text-xs font-medium w-36 shrink-0" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
      <span className="text-sm" style={{ color: color || 'var(--text-primary)', fontFamily: mono ? "'JetBrains Mono', monospace" : undefined, fontSize: mono ? 11 : undefined }}>
        {value}
      </span>
    </div>
  )
}

function AgentIcon({ size = 16 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
}
function ActiveIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> }
function TaskIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> }

function timeAgo(dateStr: string) {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}
