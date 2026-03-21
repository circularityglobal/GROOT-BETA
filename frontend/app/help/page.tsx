'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

type View = 'list' | 'new' | 'detail'

const CATEGORIES = [
  { id: 'general', label: 'General Question' },
  { id: 'bug', label: 'Bug Report' },
  { id: 'billing', label: 'Billing & Payments' },
  { id: 'security', label: 'Security Concern' },
  { id: 'feature', label: 'Feature Request' },
  { id: 'account', label: 'Account Issue' },
]

const PRIORITIES = [
  { id: 'low', label: 'Low' },
  { id: 'normal', label: 'Normal' },
  { id: 'high', label: 'High' },
  { id: 'urgent', label: 'Urgent' },
]

const STATUS_COLORS: Record<string, string> = {
  open: '#5CE0D2',
  in_progress: '#F59E0B',
  waiting_on_user: '#F97316',
  resolved: '#22C55E',
  closed: '#6B7280',
}

const STATUS_LABELS: Record<string, string> = {
  open: 'Open',
  in_progress: 'In Progress',
  waiting_on_user: 'Waiting on You',
  resolved: 'Resolved',
  closed: 'Closed',
}

const PRIORITY_COLORS: Record<string, string> = {
  low: '#6B7280',
  normal: '#3B82F6',
  high: '#F59E0B',
  urgent: '#EF4444',
}

export default function HelpPage() {
  const router = useRouter()
  const [token, setToken] = useState('')
  const [view, setView] = useState<View>('list')
  const [tickets, setTickets] = useState<any[]>([])
  const [selectedTicket, setSelectedTicket] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  // New ticket form
  const [subject, setSubject] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('general')
  const [priority, setPriority] = useState('normal')

  // Reply
  const [replyContent, setReplyContent] = useState('')

  const headers = useCallback(() => {
    const t = localStorage.getItem('refinet_token') || ''
    return { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' }
  }, [])

  const loadTickets = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/support/tickets?page_size=50`, { headers: headers() })
      if (!r.ok) throw new Error('Failed to load tickets')
      const data = await r.json()
      setTickets(data.tickets || [])
    } catch {
      setTickets([])
    } finally {
      setLoading(false)
    }
  }, [headers])

  const loadTicketDetail = useCallback(async (id: string) => {
    try {
      const r = await fetch(`${API_URL}/support/tickets/${id}`, { headers: headers() })
      if (!r.ok) throw new Error('Ticket not found')
      const data = await r.json()
      setSelectedTicket(data)
      setView('detail')
    } catch {
      setError('Could not load ticket')
    }
  }, [headers])

  useEffect(() => {
    const t = localStorage.getItem('refinet_token')
    if (!t) { router.replace('/login/'); return }
    setToken(t)
    loadTickets()
  }, [router, loadTickets])

  const handleCreateTicket = async () => {
    if (!subject.trim() || !description.trim()) {
      setError('Subject and description are required')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const r = await fetch(`${API_URL}/support/tickets`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          subject: subject.trim(),
          description: description.trim(),
          category,
          priority,
          metadata: { page: typeof window !== 'undefined' ? window.location.href : null, ua: typeof navigator !== 'undefined' ? navigator.userAgent : null },
        }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to create ticket')
      }
      const ticket = await r.json()
      setMsg('Ticket created successfully')
      setSubject('')
      setDescription('')
      setCategory('general')
      setPriority('normal')
      await loadTickets()
      loadTicketDetail(ticket.id)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleReply = async () => {
    if (!replyContent.trim() || !selectedTicket) return
    setSubmitting(true)
    try {
      const r = await fetch(`${API_URL}/support/tickets/${selectedTicket.id}/reply`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ content: replyContent.trim() }),
      })
      if (!r.ok) throw new Error('Failed to send reply')
      setReplyContent('')
      loadTicketDetail(selectedTicket.id)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = async () => {
    if (!selectedTicket) return
    try {
      await fetch(`${API_URL}/support/tickets/${selectedTicket.id}/close`, {
        method: 'POST',
        headers: headers(),
      })
      loadTicketDetail(selectedTicket.id)
      loadTickets()
    } catch {}
  }

  if (loading) {
    return <div style={{ minHeight: '80vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="animate-pulse" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>Loading Help Desk...</div>
    </div>
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '24px 28px' }} className="animate-fade-in">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Link href="/dashboard" style={{ fontSize: 11, color: 'var(--text-tertiary)', textDecoration: 'none', fontFamily: "'JetBrains Mono', monospace" }}>Dashboard</Link>
            <span style={{ color: 'var(--text-tertiary)', fontSize: 10 }}>/</span>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>Help Desk</span>
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)', margin: 0 }}>
            Help Desk
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4, margin: 0 }}>
            Get support from our team. All conversations are encrypted.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {view !== 'list' && (
            <button onClick={() => { setView('list'); setSelectedTicket(null); setError(''); setMsg('') }}
              style={{ padding: '8px 16px', fontSize: 12, borderRadius: 8, border: '1px solid var(--border-default)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', cursor: 'pointer' }}>
              Back to Tickets
            </button>
          )}
          {view === 'list' && (
            <button onClick={() => { setView('new'); setError(''); setMsg('') }}
              className="btn-primary"
              style={{ padding: '8px 16px', fontSize: 12, borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600 }}>
              + New Ticket
            </button>
          )}
        </div>
      </div>

      {error && <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#EF4444', fontSize: 12, marginBottom: 16 }}>{error}</div>}
      {msg && <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', color: '#22C55E', fontSize: 12, marginBottom: 16 }}>{msg}</div>}

      {/* ── Ticket List ── */}
      {view === 'list' && (
        <div>
          {tickets.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 20px' }}>
              <div style={{ fontSize: 36, marginBottom: 12, opacity: 0.5 }}>?</div>
              <div style={{ fontSize: 15, color: 'var(--text-secondary)', marginBottom: 6 }}>No support tickets yet</div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 20 }}>Create a ticket to get help from our team</div>
              <button onClick={() => setView('new')} className="btn-primary" style={{ padding: '8px 20px', fontSize: 12, borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600 }}>
                Create Your First Ticket
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {tickets.map(t => (
                <div key={t.id} onClick={() => loadTicketDetail(t.id)}
                  className="card" style={{ padding: '14px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>#{t.ticket_number}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{t.subject}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11, color: 'var(--text-tertiary)' }}>
                      <span>{t.category}</span>
                      <span>·</span>
                      <span>{new Date(t.created_at).toLocaleDateString()}</span>
                      {t.is_encrypted && <span title="Encrypted">E2E</span>}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: '3px 8px', borderRadius: 10,
                      background: `${STATUS_COLORS[t.status] || '#6B7280'}20`,
                      color: STATUS_COLORS[t.status] || '#6B7280',
                    }}>
                      {STATUS_LABELS[t.status] || t.status}
                    </span>
                    <span style={{
                      fontSize: 10, padding: '3px 8px', borderRadius: 10,
                      background: `${PRIORITY_COLORS[t.priority] || '#6B7280'}15`,
                      color: PRIORITY_COLORS[t.priority] || '#6B7280',
                    }}>
                      {t.priority}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── New Ticket Form ── */}
      {view === 'new' && (
        <div className="card" style={{ padding: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginTop: 0, marginBottom: 20 }}>Create Support Ticket</h2>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>Subject</label>
            <input value={subject} onChange={e => setSubject(e.target.value)} placeholder="Brief summary of your issue"
              className="input-base" style={{ width: '100%', padding: '10px 12px', fontSize: 13, borderRadius: 8 }} />
          </div>

          <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>Category</label>
              <select value={category} onChange={e => setCategory(e.target.value)}
                className="input-base" style={{ width: '100%', padding: '10px 12px', fontSize: 13, borderRadius: 8 }}>
                {CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>Priority</label>
              <select value={priority} onChange={e => setPriority(e.target.value)}
                className="input-base" style={{ width: '100%', padding: '10px 12px', fontSize: 13, borderRadius: 8 }}>
                {PRIORITIES.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>Description</label>
            <textarea value={description} onChange={e => setDescription(e.target.value)}
              placeholder="Describe your issue in detail. Include steps to reproduce if reporting a bug."
              className="input-base" rows={6}
              style={{ width: '100%', padding: '10px 12px', fontSize: 13, borderRadius: 8, resize: 'vertical' }} />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button onClick={() => setView('list')} style={{ padding: '8px 16px', fontSize: 12, borderRadius: 8, border: '1px solid var(--border-default)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', cursor: 'pointer' }}>
              Cancel
            </button>
            <button onClick={handleCreateTicket} disabled={submitting}
              className="btn-primary" style={{ padding: '8px 20px', fontSize: 12, borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600, opacity: submitting ? 0.6 : 1 }}>
              {submitting ? 'Submitting...' : 'Submit Ticket'}
            </button>
          </div>
        </div>
      )}

      {/* ── Ticket Detail ── */}
      {view === 'detail' && selectedTicket && (
        <div>
          {/* Ticket Header */}
          <div className="card" style={{ padding: '16px 20px', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>#{selectedTicket.ticket_number}</span>
                <span style={{
                  fontSize: 10, fontWeight: 600, padding: '3px 8px', borderRadius: 10,
                  background: `${STATUS_COLORS[selectedTicket.status] || '#6B7280'}20`,
                  color: STATUS_COLORS[selectedTicket.status] || '#6B7280',
                }}>
                  {STATUS_LABELS[selectedTicket.status] || selectedTicket.status}
                </span>
                <span style={{
                  fontSize: 10, padding: '3px 8px', borderRadius: 10,
                  background: `${PRIORITY_COLORS[selectedTicket.priority] || '#6B7280'}15`,
                  color: PRIORITY_COLORS[selectedTicket.priority] || '#6B7280',
                }}>
                  {selectedTicket.priority}
                </span>
                {selectedTicket.is_encrypted && (
                  <span style={{ fontSize: 10, padding: '3px 8px', borderRadius: 10, background: 'rgba(34,197,94,0.1)', color: '#22C55E' }} title="End-to-end encrypted via XMTP">
                    E2E Encrypted
                  </span>
                )}
              </div>
              {selectedTicket.status !== 'closed' && (
                <button onClick={handleClose} style={{ padding: '6px 12px', fontSize: 11, borderRadius: 6, border: '1px solid var(--border-default)', background: 'var(--bg-secondary)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  Close Ticket
                </button>
              )}
            </div>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 4px 0' }}>{selectedTicket.subject}</h2>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              {selectedTicket.category} · Created {new Date(selectedTicket.created_at).toLocaleString()}
            </div>
          </div>

          {/* Messages */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
            {(selectedTicket.messages || []).map((m: any) => (
              <div key={m.id} style={{
                padding: '12px 16px', borderRadius: 10,
                background: m.message_type === 'system' ? 'transparent' :
                  m.is_admin ? 'rgba(92,224,210,0.08)' : 'var(--bg-elevated)',
                border: m.message_type === 'system' ? 'none' : '1px solid var(--border-subtle)',
                marginLeft: m.is_admin ? 40 : 0,
                marginRight: m.is_admin ? 0 : 40,
              }}>
                {m.message_type === 'system' ? (
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'center', fontStyle: 'italic' }}>{m.content}</div>
                ) : (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: m.is_admin ? 'var(--refi-teal)' : 'var(--text-secondary)' }}>
                        {m.is_admin ? 'Support Team' : (m.author_name || 'You')}
                      </span>
                      <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                        {new Date(m.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{m.content}</div>
                  </>
                )}
              </div>
            ))}
          </div>

          {/* Reply Box */}
          {selectedTicket.status !== 'closed' && (
            <div className="card" style={{ padding: 16 }}>
              <textarea value={replyContent} onChange={e => setReplyContent(e.target.value)}
                placeholder="Type your reply..."
                className="input-base" rows={3}
                style={{ width: '100%', padding: '10px 12px', fontSize: 13, borderRadius: 8, resize: 'vertical', marginBottom: 8 }} />
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button onClick={handleReply} disabled={submitting || !replyContent.trim()}
                  className="btn-primary" style={{ padding: '8px 16px', fontSize: 12, borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600, opacity: (submitting || !replyContent.trim()) ? 0.5 : 1 }}>
                  {submitting ? 'Sending...' : 'Send Reply'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
