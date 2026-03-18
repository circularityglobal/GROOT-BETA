'use client'

import { useState, useEffect, useRef } from 'react'
import { API_URL } from '@/lib/config'

interface Participant {
  user_id: string
  eth_address: string
  display_name: string | null
  role: string
}

interface Conversation {
  id: string
  title: string | null
  is_group: boolean
  participants: Participant[]
  last_message_at: string | null
  last_message_preview: string | null
  unread_count: number
  my_role: string
}

interface Message {
  id: string
  conversation_id: string
  sender_id: string
  sender_address: string
  content: string
  content_type: string
  reply_to_id: string | null
  metadata: Record<string, unknown> | null
  is_edited: boolean
  created_at: string
}

interface EmailAlias {
  auto: string | null
  custom: string | null
  ens: string | null
  eth_address: string
}

export default function MessagesPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedConvo, setSelectedConvo] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [newMessage, setNewMessage] = useState('')
  const [dmRecipient, setDmRecipient] = useState('')
  const [dmContent, setDmContent] = useState('')
  const [aliases, setAliases] = useState<EmailAlias[]>([])
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const [view, setView] = useState<'conversations' | 'compose' | 'aliases' | 'group'>('conversations')
  const [searchQuery, setSearchQuery] = useState('')
  const [groupTitle, setGroupTitle] = useState('')
  const [groupParticipants, setGroupParticipants] = useState('')
  const [typingUsers, setTypingUsers] = useState<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const token = typeof window !== 'undefined' ? localStorage.getItem('refinet_token') : null
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }

  // Load conversations
  useEffect(() => {
    if (!token) return
    fetch(`${API_URL}/messages/conversations`, { headers })
      .then((r) => r.json())
      .then((data) => setConversations(data.conversations || []))
      .catch(() => {})
  }, [token])

  // Load messages when conversation selected
  useEffect(() => {
    if (!selectedConvo || !token) return
    fetch(`${API_URL}/messages/conversations/${selectedConvo}`, { headers })
      .then((r) => r.json())
      .then((data) => {
        setMessages(data.messages || [])
        // Mark as read
        fetch(`${API_URL}/messages/conversations/${selectedConvo}/read`, {
          method: 'POST',
          headers,
        }).catch(() => {})
      })
      .catch(() => {})
  }, [selectedConvo, token])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendDM = async () => {
    if (!dmRecipient.trim() || !dmContent.trim()) return
    setSending(true)
    setError('')
    try {
      const r = await fetch(`${API_URL}/messages/dm`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ recipient: dmRecipient, content: dmContent }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: 'Send failed' }))
        throw new Error(err.detail)
      }
      const msg = await r.json()
      setDmRecipient('')
      setDmContent('')
      setSelectedConvo(msg.conversation_id)
      setView('conversations')
      // Refresh conversations
      const cr = await fetch(`${API_URL}/messages/conversations`, { headers })
      const cd = await cr.json()
      setConversations(cd.conversations || [])
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  const handleSendMessage = async () => {
    if (!selectedConvo || !newMessage.trim()) return
    setSending(true)
    try {
      const r = await fetch(`${API_URL}/messages/conversations/${selectedConvo}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ content: newMessage }),
      })
      if (!r.ok) throw new Error('Send failed')
      const msg = await r.json()
      setMessages((prev) => [...prev, msg])
      setNewMessage('')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  const loadAliases = () => {
    fetch(`${API_URL}/messages/email/aliases`, { headers })
      .then((r) => r.json())
      .then((data) => setAliases(Array.isArray(data) ? data : []))
      .catch(() => {})
    setView('aliases')
  }

  const handleCreateGroup = async () => {
    if (!groupTitle.trim() || !groupParticipants.trim()) return
    setSending(true); setError('')
    try {
      const participants = groupParticipants.split(',').map(p => p.trim()).filter(Boolean)
      const r = await fetch(`${API_URL}/messages/conversations/group`, {
        method: 'POST', headers,
        body: JSON.stringify({ title: groupTitle, participants }),
      })
      if (!r.ok) { const err = await r.json().catch(() => ({ detail: 'Failed' })); throw new Error(err.detail) }
      const convo = await r.json()
      setGroupTitle(''); setGroupParticipants('')
      setSelectedConvo(convo.id); setView('conversations')
      const cr = await fetch(`${API_URL}/messages/conversations`, { headers })
      const cd = await cr.json()
      setConversations(cd.conversations || [])
    } catch (e: any) { setError(e.message) } finally { setSending(false) }
  }

  // Typing indicators — poll when viewing a conversation
  useEffect(() => {
    if (!selectedConvo || !token) { setTypingUsers([]); return }
    const poll = setInterval(() => {
      fetch(`${API_URL}/p2p/typing/${selectedConvo}`, { headers })
        .then(r => r.ok ? r.json() : { typing_users: [] })
        .then(data => setTypingUsers(data.typing_users || []))
        .catch(() => {})
    }, 3000)
    return () => clearInterval(poll)
  }, [selectedConvo, token])

  const filteredConversations = conversations.filter(c => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    if (c.title?.toLowerCase().includes(q)) return true
    if (c.last_message_preview?.toLowerCase().includes(q)) return true
    if (c.participants.some(p => (p.display_name || p.eth_address).toLowerCase().includes(q))) return true
    return false
  })

  if (!token) {
    return (
      <div className="p-8 text-center" style={{ color: 'var(--text-secondary)' }}>
        <p>Sign in to access messages.</p>
        <a href="/" className="btn-primary inline-block mt-4 !py-2 !px-6 !text-sm">
          SIGN IN
        </a>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-60px)]">
      {/* Sidebar */}
      <div
        className="w-80 flex-shrink-0 border-r overflow-y-auto"
        style={{ borderColor: 'var(--border-primary)', background: 'var(--bg-primary)' }}
      >
        <div className="p-4 space-y-2">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-bold">Messages</h2>
            <div className="flex gap-1">
              <button onClick={() => setView('compose')} className="px-2 py-1 rounded text-xs"
                style={{ background: 'var(--refi-teal-glow)', color: 'var(--refi-teal)' }}>New DM</button>
              <button onClick={() => setView('group')} className="px-2 py-1 rounded text-xs"
                style={{ background: 'rgba(167,139,250,0.15)', color: 'rgb(167,139,250)' }}>Group</button>
              <button onClick={loadAliases} className="px-2 py-1 rounded text-xs"
                style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>Email</button>
            </div>
          </div>

          {/* Search */}
          <input className="input-base focus-glow w-full mb-2 !py-1.5 !text-xs" placeholder="Search conversations..."
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />

          {filteredConversations.length === 0 && (
            <p className="text-xs py-8 text-center" style={{ color: 'var(--text-tertiary)' }}>
              {searchQuery ? 'No matching conversations' : 'No conversations yet. Send a DM to get started.'}
            </p>
          )}

          {filteredConversations.map((c) => (
            <button
              key={c.id}
              onClick={() => {
                setSelectedConvo(c.id)
                setView('conversations')
              }}
              className="w-full text-left p-3 rounded-lg transition-colors"
              style={{
                background: selectedConvo === c.id ? 'var(--bg-secondary)' : 'transparent',
              }}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium truncate">
                  {c.title || c.participants.map((p) => p.display_name || p.eth_address.slice(0, 8)).join(', ')}
                </span>
                {c.unread_count > 0 && (
                  <span
                    className="text-xs font-bold px-1.5 py-0.5 rounded-full"
                    style={{ background: 'var(--refi-teal)', color: 'var(--bg-primary)' }}
                  >
                    {c.unread_count}
                  </span>
                )}
              </div>
              {c.last_message_preview && (
                <p className="text-xs truncate mt-1" style={{ color: 'var(--text-tertiary)' }}>
                  {c.last_message_preview}
                </p>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        {error && (
          <div className="m-4 p-2 bg-red-900/30 border border-red-800 rounded text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Compose DM */}
        {view === 'compose' && (
          <div className="p-6 max-w-lg">
            <h3 className="text-lg font-bold mb-4">New Direct Message</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: 'var(--text-tertiary)' }}>
                  Recipient (address, ENS, or email alias)
                </label>
                <input
                  value={dmRecipient}
                  onChange={(e) => setDmRecipient(e.target.value)}
                  placeholder="0x... or alice.eth or alice@cifi.global"
                  className="w-full p-2 rounded-lg text-sm font-mono"
                  style={{
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-primary)',
                    color: 'var(--text-primary)',
                  }}
                />
              </div>
              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: 'var(--text-tertiary)' }}>
                  Message
                </label>
                <textarea
                  value={dmContent}
                  onChange={(e) => setDmContent(e.target.value)}
                  placeholder="Type your message..."
                  rows={4}
                  className="w-full p-2 rounded-lg text-sm"
                  style={{
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-primary)',
                    color: 'var(--text-primary)',
                  }}
                />
              </div>
              <button
                onClick={handleSendDM}
                disabled={sending || !dmRecipient.trim() || !dmContent.trim()}
                className="btn-primary !py-2 !px-6 !text-sm"
                style={{ opacity: sending ? 0.7 : 1 }}
              >
                {sending ? 'SENDING...' : 'SEND'}
              </button>
            </div>
          </div>
        )}

        {/* Create Group */}
        {view === 'group' && (
          <div className="p-6 max-w-lg">
            <h3 className="text-lg font-bold mb-4">Create Group</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: 'var(--text-tertiary)' }}>Group Title</label>
                <input value={groupTitle} onChange={e => setGroupTitle(e.target.value)} placeholder="e.g. DeFi Research"
                  className="w-full p-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }} />
              </div>
              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: 'var(--text-tertiary)' }}>Participants (comma-separated addresses, ENS, or emails)</label>
                <textarea value={groupParticipants} onChange={e => setGroupParticipants(e.target.value)}
                  placeholder="0x742d..., alice.eth, bob@cifi.global" rows={3}
                  className="w-full p-2 rounded-lg text-sm font-mono" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }} />
              </div>
              <button onClick={handleCreateGroup} disabled={sending || !groupTitle.trim() || !groupParticipants.trim()}
                className="btn-primary !py-2 !px-6 !text-sm" style={{ opacity: sending ? 0.7 : 1 }}>
                {sending ? 'CREATING...' : 'CREATE GROUP'}
              </button>
            </div>
          </div>
        )}

        {/* Email Aliases */}
        {view === 'aliases' && (
          <div className="p-6 max-w-lg">
            <h3 className="text-lg font-bold mb-4">Email Aliases</h3>
            <p className="text-xs mb-4" style={{ color: 'var(--text-tertiary)' }}>
              Your wallet email addresses. Others can message you using any of these.
            </p>
            {aliases.map((a, i) => (
              <div key={i} className="card p-3 mb-2 space-y-1 text-sm">
                {a.auto && (
                  <p>
                    <span style={{ color: 'var(--text-tertiary)' }}>Auto:</span>{' '}
                    <span className="font-mono">{a.auto}</span>
                  </p>
                )}
                {a.custom && (
                  <p>
                    <span style={{ color: 'var(--text-tertiary)' }}>Custom:</span>{' '}
                    <span className="font-mono">{a.custom}</span>
                  </p>
                )}
                {a.ens && (
                  <p>
                    <span style={{ color: 'var(--text-tertiary)' }}>ENS:</span>{' '}
                    <span className="font-mono">{a.ens}</span>
                  </p>
                )}
              </div>
            ))}
            {aliases.length === 0 && (
              <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                No aliases registered yet. They are created automatically on sign-in.
              </p>
            )}
          </div>
        )}

        {/* Conversation Messages */}
        {view === 'conversations' && selectedConvo && (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.length === 0 && (
                <p className="text-xs text-center py-8" style={{ color: 'var(--text-tertiary)' }}>
                  No messages yet.
                </p>
              )}
              {messages.map((m) => (
                <div key={m.id} className="flex flex-col">
                  <div className="flex items-baseline gap-2">
                    <span className="text-xs font-mono font-medium" style={{ color: 'var(--refi-teal)' }}>
                      {m.sender_address.slice(0, 8)}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                      {m.created_at ? new Date(m.created_at).toLocaleTimeString() : ''}
                    </span>
                  </div>
                  <p className="text-sm mt-0.5" style={{ color: 'var(--text-primary)' }}>
                    {m.content}
                  </p>
                </div>
              ))}
              {typingUsers.length > 0 && (
                <div className="text-xs animate-fade-in" style={{ color: 'var(--refi-teal)', fontStyle: 'italic' }}>
                  {typingUsers.length === 1 ? 'Someone is typing...' : `${typingUsers.length} people typing...`}
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Message Input */}
            <div
              className="p-3 border-t flex gap-2"
              style={{ borderColor: 'var(--border-primary)' }}
            >
              <input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                placeholder="Type a message..."
                className="flex-1 p-2 rounded-lg text-sm"
                style={{
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-primary)',
                  color: 'var(--text-primary)',
                }}
              />
              <button
                onClick={handleSendMessage}
                disabled={sending || !newMessage.trim()}
                className="btn-primary !py-2 !px-4 !text-sm"
              >
                Send
              </button>
            </div>
          </>
        )}

        {/* Empty state */}
        {view === 'conversations' && !selectedConvo && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                Select a conversation or start a new DM
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
