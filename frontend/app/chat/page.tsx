'use client'

import { useState, useRef, useEffect } from 'react'
import { API_URL } from '@/lib/config'

/* ── Types ─────────────────────────────────────────────────────── */

interface SourceReference {
  document_id: string
  document_title: string
  category: string
  doc_type?: string
  tags: string[]
  score: number
  preview: string
}

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  sources?: SourceReference[]
}

interface KnowledgeDoc {
  id: string; title: string; category: string; chunk_count: number;
  doc_type?: string; tags?: string[]; page_count?: number;
  source_filename?: string; created_at: string;
}

interface SavedConversation {
  id: string
  title: string
  messages: Message[]
  savedAt: string
}

interface GeneratedContent {
  type: string
  title: string
  content: string
  tokens_used: number
}

/* ── Constants ─────────────────────────────────────────────────── */

const CATEGORY_COLORS: Record<string, string> = {
  about: '#5CE0D2', product: '#60A5FA', docs: '#A78BFA',
  blockchain: '#F97316', contract: '#FBBF24', faq: '#4ADE80',
}

const SUGGESTED_PROMPTS = [
  'What is REFINET?',
  'How does the API work?',
  'Tell me about sovereign computing',
]

const INITIAL_MESSAGE: Message = {
  role: 'assistant',
  content: 'I am Groot.\n\nI\'m the AI that lives in REFINET Cloud — powered by BitNet, running on sovereign infrastructure at zero cost. Ask me anything about REFINET, or just chat.\n\nSelect documents in the sidebar to scope my knowledge to specific sources.',
}

/* ── Component ─────────────────────────────────────────────────── */

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([INITIAL_MESSAGE])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [savedConversations, setSavedConversations] = useState<SavedConversation[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Source sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDoc[]>([])
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set())
  const [docSearch, setDocSearch] = useState('')

  // Generation state
  const [generatingId, setGeneratingId] = useState<string | null>(null)
  const [generationType, setGenerationType] = useState<string | null>(null)
  const [generatedContent, setGeneratedContent] = useState<GeneratedContent | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Load saved conversations
  useEffect(() => {
    try {
      const saved = localStorage.getItem('groot_conversations')
      if (saved) setSavedConversations(JSON.parse(saved))
    } catch {}
  }, [])

  // Load documents for sidebar: user's own + platform/public
  const [myDocs, setMyDocs] = useState<KnowledgeDoc[]>([])
  const [platformDocs, setPlatformDocs] = useState<KnowledgeDoc[]>([])

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    if (!token) return
    const h = { Authorization: `Bearer ${token}` }
    // Fetch user's own documents
    fetch(`${API_URL}/knowledge/my/documents`, { headers: h })
      .then(r => r.ok ? r.json() : [])
      .then(setMyDocs)
      .catch(() => {})
    // Fetch admin/platform documents (may 403 for non-admins, that's fine)
    fetch(`${API_URL}/knowledge/documents`, { headers: h })
      .then(r => r.ok ? r.json() : [])
      .then(docs => {
        setPlatformDocs(docs)
        setKnowledgeDocs(docs)
      })
      .catch(() => {})
  }, [])

  /* ── Conversation management ───────────────────────────────────── */

  const saveConversation = () => {
    if (messages.length <= 1) return
    const firstUserMsg = messages.find(m => m.role === 'user')
    const title = firstUserMsg ? firstUserMsg.content.slice(0, 50) + (firstUserMsg.content.length > 50 ? '...' : '') : 'Conversation'
    const conv: SavedConversation = { id: Date.now().toString(), title, messages: [...messages], savedAt: new Date().toISOString() }
    const updated = [conv, ...savedConversations].slice(0, 20)
    setSavedConversations(updated)
    localStorage.setItem('groot_conversations', JSON.stringify(updated))
  }

  const loadConversation = (conv: SavedConversation) => { setMessages(conv.messages); setShowHistory(false) }
  const deleteConversation = (id: string) => {
    const updated = savedConversations.filter(c => c.id !== id)
    setSavedConversations(updated)
    localStorage.setItem('groot_conversations', JSON.stringify(updated))
  }
  const newChat = () => { if (messages.length > 1) saveConversation(); setMessages([INITIAL_MESSAGE]); setInput('') }
  const copyMessage = (text: string, idx: number) => { navigator.clipboard.writeText(text); setCopiedIdx(idx); setTimeout(() => setCopiedIdx(null), 1500) }

  /* ── Notebook mode ─────────────────────────────────────────────── */

  const toggleDocSelection = (docId: string) => {
    setSelectedDocIds(prev => {
      const next = new Set(prev)
      if (next.has(docId)) next.delete(docId)
      else next.add(docId)
      return next
    })
  }

  const clearSelection = () => setSelectedDocIds(new Set())

  /* ── Generate content ──────────────────────────────────────────── */

  const generateContent = async (docId: string, type: 'summarize' | 'generate-faq' | 'generate-overview' | 'timeline') => {
    setGeneratingId(docId); setGenerationType(type); setGeneratedContent(null)
    const token = localStorage.getItem('refinet_token') || ''
    // Route to user endpoint for user-owned docs, admin endpoint for platform docs
    const isUserDoc = myDocs.some(d => d.id === docId)
    const basePath = isUserDoc ? '/knowledge/my/documents' : '/knowledge/documents'
    try {
      const r = await fetch(`${API_URL}${basePath}/${docId}/${type}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: '{}',
      })
      if (r.ok) setGeneratedContent(await r.json())
    } catch {}
    finally { setGeneratingId(null); setGenerationType(null) }
  }

  /* ── Send message with sources ─────────────────────────────────── */

  const sendMessage = async (overrideInput?: string) => {
    const text = overrideInput ?? input
    if (!text.trim() || isStreaming) return

    const userMessage: Message = { role: 'user', content: text.trim() }
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setInput('')
    setIsStreaming(true)

    const assistantMessage: Message = { role: 'assistant', content: '' }
    setMessages([...newMessages, assistantMessage])

    try {
      const token = localStorage.getItem('refinet_token') || ''
      const body: any = {
        model: 'bitnet-b1.58-2b',
        messages: newMessages.map((m) => ({ role: m.role, content: m.content })),
        stream: true,
        max_tokens: 512,
      }
      // Notebook mode: scope to selected documents
      if (selectedDocIds.size > 0) {
        body.notebook_doc_ids = Array.from(selectedDocIds)
      }

      const response = await fetch(`${API_URL}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        const errText = response.status === 429 ? 'Rate limit reached. Create a free account for 250 requests/day.'
          : response.status === 401 ? 'Authentication required for full access.'
          : `Error: ${response.status}`
        setMessages((prev) => { const u = [...prev]; u[u.length - 1] = { role: 'assistant', content: errText }; return u })
        setIsStreaming(false)
        return
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let accumulated = ''
      let sources: SourceReference[] | undefined

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          for (const line of decoder.decode(value, { stream: true }).split('\n')) {
            if (!line.startsWith('data: ')) continue
            const data = line.slice(6)
            if (data === '[DONE]') break
            try {
              const parsed = JSON.parse(data)
              // Check if this is a sources event (no choices field)
              if (parsed.sources && !parsed.choices) {
                sources = parsed.sources
                continue
              }
              const content = parsed.choices?.[0]?.delta?.content || ''
              if (content) {
                accumulated += content
                setMessages((prev) => {
                  const u = [...prev]
                  u[u.length - 1] = { role: 'assistant', content: accumulated }
                  return u
                })
              }
            } catch {}
          }
        }
      }

      // Attach sources to the final message
      if (sources && sources.length > 0) {
        setMessages((prev) => {
          const u = [...prev]
          u[u.length - 1] = { ...u[u.length - 1], sources }
          return u
        })
      }
    } catch {
      setMessages((prev) => {
        const u = [...prev]
        u[u.length - 1] = { role: 'assistant', content: 'Connection error. REFINET Cloud may be starting up — try again.' }
        return u
      })
    }
    setIsStreaming(false)
  }

  /* ── Filtered docs ─────────────────────────────────────────────── */

  const filteredDocs = knowledgeDocs.filter(d =>
    d.title.toLowerCase().includes(docSearch.toLowerCase()) ||
    (d.tags || []).some(t => t.includes(docSearch.toLowerCase()))
  )

  /* ── Render ────────────────────────────────────────────────────── */

  return (
    <div className="flex" style={{ height: 'calc(100vh - 3.5rem)', background: 'var(--bg-primary)' }}>

      {/* ═══ SOURCE SIDEBAR ═══ */}
      {sidebarOpen && (
        <div style={{
          width: 280, minWidth: 280, borderRight: '1px solid var(--border-subtle)',
          display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)',
          overflow: 'hidden',
        }}>
          {/* Sidebar header */}
          <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', letterSpacing: '0.05em', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>
              Sources
            </span>
            <div style={{ display: 'flex', gap: 4 }}>
              {selectedDocIds.size > 0 && (
                <button onClick={clearSelection} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(248,113,113,0.1)', color: '#F87171', border: 'none', cursor: 'pointer' }}>
                  Clear ({selectedDocIds.size})
                </button>
              )}
              <button onClick={() => setSidebarOpen(false)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 14, padding: '0 4px' }}>
                &times;
              </button>
            </div>
          </div>

          {/* Notebook mode indicator */}
          {selectedDocIds.size > 0 && (
            <div style={{ padding: '8px 14px', background: 'rgba(92,224,210,0.06)', borderBottom: '1px solid var(--border-subtle)', fontSize: 11, color: 'var(--refi-teal)' }}>
              Notebook mode: {selectedDocIds.size} source{selectedDocIds.size > 1 ? 's' : ''} selected
            </div>
          )}

          {/* Search */}
          <div style={{ padding: '8px 10px' }}>
            <input type="text" value={docSearch} onChange={e => setDocSearch(e.target.value)}
              placeholder="Search sources..."
              style={{ width: '100%', fontSize: 11, padding: '6px 10px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 6, color: 'var(--text-primary)', boxSizing: 'border-box' }} />
          </div>

          {/* Document list — split into My Sources + Platform Sources */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {/* MY SOURCES section */}
            {myDocs.length > 0 && (
              <div style={{ padding: '6px 14px 4px', fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.08em', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>
                My Sources ({myDocs.filter(d => d.title.toLowerCase().includes(docSearch.toLowerCase())).length})
              </div>
            )}
            {myDocs.filter(d => d.title.toLowerCase().includes(docSearch.toLowerCase())).map(doc => {
              const isSelected = selectedDocIds.has(doc.id)
              const catColor = CATEGORY_COLORS[doc.category] || '#6B7280'
              return (
                <div key={doc.id} style={{
                  padding: '10px 14px', cursor: 'pointer',
                  borderBottom: '1px solid var(--border-subtle)',
                  background: isSelected ? 'rgba(92,224,210,0.06)' : 'transparent',
                  borderLeft: isSelected ? '3px solid var(--refi-teal)' : '3px solid transparent',
                  transition: 'all 0.15s',
                }}
                  onClick={() => toggleDocSelection(doc.id)}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 10 }}>{(doc as any).visibility === 'public' ? '🌐' : '🔒'}</span>
                    <span style={{ fontSize: 12, color: isSelected ? 'var(--refi-teal)' : 'var(--text-primary)', fontWeight: isSelected ? 600 : 400 }}>
                      {doc.title.length > 26 ? doc.title.slice(0, 26) + '...' : doc.title}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
                    {doc.doc_type && <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '1px 4px', borderRadius: 3, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase' }}>{doc.doc_type}</span>}
                    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '1px 4px', borderRadius: 3, background: `${catColor}15`, color: catColor }}>{doc.category}</span>
                    <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{doc.chunk_count}ch</span>
                  </div>
                  {doc.tags && doc.tags.length > 0 && (
                    <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', marginTop: 4 }}>
                      {doc.tags.slice(0, 3).map(tag => <span key={tag} style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'rgba(92,224,210,0.06)', color: 'var(--refi-teal)', border: '1px solid rgba(92,224,210,0.12)' }}>{tag}</span>)}
                    </div>
                  )}
                  {isSelected && (
                    <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }} onClick={e => e.stopPropagation()}>
                      <GenBtn label="Summary" loading={generatingId === doc.id && generationType === 'summarize'} onClick={() => generateContent(doc.id, 'summarize')} />
                      <GenBtn label="FAQ" loading={generatingId === doc.id && generationType === 'generate-faq'} onClick={() => generateContent(doc.id, 'generate-faq')} />
                      <GenBtn label="Overview" loading={generatingId === doc.id && generationType === 'generate-overview'} onClick={() => generateContent(doc.id, 'generate-overview')} />
                      <GenBtn label="Timeline" loading={generatingId === doc.id && generationType === 'timeline'} onClick={() => generateContent(doc.id, 'timeline')} />
                      <GenBtn label="Export MD" loading={false} onClick={() => {
                        const token = localStorage.getItem('refinet_token') || ''
                        window.open(`${API_URL}/knowledge/my/documents/${doc.id}/export?format=md&token=${token}`, '_blank')
                      }} />
                    </div>
                  )}
                </div>
              )
            })}

            {/* PLATFORM / PUBLIC section */}
            {filteredDocs.length > 0 && (
              <div style={{ padding: '8px 14px 4px', fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.08em', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace", borderTop: myDocs.length > 0 ? '2px solid var(--border-subtle)' : 'none' }}>
                Platform Sources ({filteredDocs.length})
              </div>
            )}
            {filteredDocs.map(doc => {
              const isSelected = selectedDocIds.has(doc.id)
              const catColor = CATEGORY_COLORS[doc.category] || '#6B7280'
              return (
                <div key={doc.id} style={{
                  padding: '10px 14px', cursor: 'pointer',
                  borderBottom: '1px solid var(--border-subtle)',
                  background: isSelected ? 'rgba(92,224,210,0.06)' : 'transparent',
                  borderLeft: isSelected ? '3px solid var(--refi-teal)' : '3px solid transparent',
                  transition: 'all 0.15s',
                }}
                  onClick={() => toggleDocSelection(doc.id)}>
                  {/* Title row */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: isSelected ? 'var(--refi-teal)' : 'var(--text-primary)', fontWeight: isSelected ? 600 : 400 }}>
                      {doc.title.length > 30 ? doc.title.slice(0, 30) + '...' : doc.title}
                    </span>
                  </div>
                  {/* Meta */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
                    {doc.doc_type && (
                      <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '1px 4px', borderRadius: 3, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase' }}>
                        {doc.doc_type}
                      </span>
                    )}
                    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '1px 4px', borderRadius: 3, background: `${catColor}15`, color: catColor }}>
                      {doc.category}
                    </span>
                    <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{doc.chunk_count}ch</span>
                  </div>
                  {/* Tags (first 3) */}
                  {doc.tags && doc.tags.length > 0 && (
                    <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', marginTop: 4 }}>
                      {doc.tags.slice(0, 3).map(tag => (
                        <span key={tag} style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'rgba(92,224,210,0.06)', color: 'var(--refi-teal)', border: '1px solid rgba(92,224,210,0.12)' }}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  {/* Generate buttons (only when selected) */}
                  {isSelected && (
                    <div style={{ display: 'flex', gap: 4, marginTop: 6 }} onClick={e => e.stopPropagation()}>
                      <GenBtn label="Summary" loading={generatingId === doc.id && generationType === 'summarize'} onClick={() => generateContent(doc.id, 'summarize')} />
                      <GenBtn label="FAQ" loading={generatingId === doc.id && generationType === 'generate-faq'} onClick={() => generateContent(doc.id, 'generate-faq')} />
                      <GenBtn label="Overview" loading={generatingId === doc.id && generationType === 'generate-overview'} onClick={() => generateContent(doc.id, 'generate-overview')} />
                    </div>
                  )}
                </div>
              )
            })}
            {filteredDocs.length === 0 && (
              <p style={{ padding: 16, textAlign: 'center', fontSize: 11, color: 'var(--text-tertiary)' }}>
                {knowledgeDocs.length === 0 ? 'No documents uploaded yet' : 'No matches'}
              </p>
            )}
          </div>
        </div>
      )}

      {/* ═══ CHAT AREA ═══ */}
      <div className="flex flex-col flex-1" style={{ overflow: 'hidden' }}>
        {/* Header bar */}
        <div className="flex items-center justify-between px-4 py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button onClick={() => setSidebarOpen(true)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 16, padding: '0 4px' }}>
                ☰
              </button>
            )}
            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Groot</span>
            <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--refi-teal-glow)', color: 'var(--refi-teal)', fontFamily: "'JetBrains Mono', monospace" }}>
              BitNet b1.58 2B4T &middot; CPU &middot; Sovereign
            </span>
            {selectedDocIds.size > 0 && (
              <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(92,224,210,0.1)', color: 'var(--refi-teal)', fontFamily: "'JetBrains Mono', monospace" }}>
                {selectedDocIds.size} source{selectedDocIds.size > 1 ? 's' : ''}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-secondary !py-1 !px-3 !text-xs" onClick={() => setShowHistory(!showHistory)}>
              History ({savedConversations.length})
            </button>
            <button className="btn-secondary !py-1 !px-3 !text-xs" onClick={newChat}>New Chat</button>
          </div>
        </div>

        {/* History Sidebar */}
        {showHistory && (
          <div className="absolute top-[7rem] right-4 z-30 w-80 card animate-slide-up" style={{ padding: 0, maxHeight: '60vh', overflow: 'hidden' }}>
            <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <span className="text-xs font-bold" style={{ color: 'var(--text-secondary)' }}>Saved Conversations</span>
            </div>
            <div className="overflow-y-auto" style={{ maxHeight: 'calc(60vh - 48px)' }}>
              {savedConversations.length === 0 ? (
                <p className="text-xs text-center py-6" style={{ color: 'var(--text-tertiary)' }}>No saved conversations</p>
              ) : savedConversations.map(c => (
                <div key={c.id} className="px-4 py-3 flex items-center gap-2 cursor-pointer transition-colors"
                  style={{ borderBottom: '1px solid var(--border-subtle)' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  <div className="flex-1 min-w-0" onClick={() => loadConversation(c)}>
                    <p className="text-xs truncate" style={{ color: 'var(--text-primary)' }}>{c.title}</p>
                    <p className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{new Date(c.savedAt).toLocaleDateString()}</p>
                  </div>
                  <button className="text-xs p-1 rounded" onClick={(e) => { e.stopPropagation(); deleteConversation(c.id) }}
                    style={{ color: 'var(--text-tertiary)' }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Generated content modal */}
        {generatedContent && (
          <div style={{
            position: 'absolute', top: '5rem', left: '50%', transform: 'translateX(-50%)',
            zIndex: 40, width: '90%', maxWidth: 600, maxHeight: '70vh', overflow: 'auto',
            padding: 20, borderRadius: 14, background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)', boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div>
                <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {generatedContent.type === 'summary' ? 'Summary' : generatedContent.type === 'faq' ? 'FAQ' : 'Overview'}
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 8 }}>
                  {generatedContent.title}
                </span>
              </div>
              <button onClick={() => setGeneratedContent(null)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 18 }}>&times;</button>
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
              {generatedContent.content}
            </div>
            <div style={{ marginTop: 12, fontSize: 10, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
              {generatedContent.tokens_used} tokens · Generated by BitNet
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.length <= 1 && (
              <div className="flex flex-wrap gap-2 justify-center mb-6 animate-fade-in">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button key={prompt} onClick={() => sendMessage(prompt)} className="btn-secondary text-xs" style={{ padding: '8px 16px', borderRadius: '9999px' }}>
                    {prompt}
                  </button>
                ))}
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex animate-slide-up ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'user' ? (
                  <div className="max-w-[85%] rounded-2xl rounded-br-md px-5 py-3 text-sm leading-relaxed"
                    style={{ background: 'var(--refi-teal)', color: 'var(--text-inverse)', fontFamily: "'DM Sans', system-ui, sans-serif" }}>
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  </div>
                ) : (
                  <div className="max-w-[85%] px-5 py-3 text-sm leading-relaxed prose-chat group"
                    style={{ background: 'transparent', borderLeft: '2px solid var(--refi-teal)', color: 'var(--text-primary)', fontFamily: "'DM Sans', system-ui, sans-serif" }}>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold"
                        style={{ background: 'var(--refi-teal-glow)', color: 'var(--refi-teal)' }}>G</div>
                      <span className="text-xs" style={{ color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>Groot</span>
                      {msg.content && !isStreaming && (
                        <button onClick={() => copyMessage(msg.content, i)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity ml-auto p-1 rounded"
                          style={{ color: copiedIdx === i ? 'var(--success)' : 'var(--text-tertiary)' }}>
                          {copiedIdx === i ? (
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
                          ) : (
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
                          )}
                        </button>
                      )}
                    </div>
                    <div className="whitespace-pre-wrap">
                      {msg.content}
                      {isStreaming && i === messages.length - 1 && <span style={{ color: 'var(--refi-teal)' }}>▌</span>}
                    </div>
                    {/* ── Source Citations ── */}
                    {msg.sources && msg.sources.length > 0 && !isStreaming && (
                      <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border-subtle)' }}>
                        <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-tertiary)', letterSpacing: '0.05em', textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace" }}>
                          Sources
                        </span>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                          {msg.sources.map((src, si) => (
                            <div key={si} title={src.preview} style={{
                              display: 'inline-flex', alignItems: 'center', gap: 4,
                              fontSize: 10, padding: '3px 8px', borderRadius: 6,
                              background: 'rgba(92,224,210,0.06)',
                              border: '1px solid rgba(92,224,210,0.15)',
                              color: 'var(--refi-teal)', cursor: 'default',
                              fontFamily: "'JetBrains Mono', monospace",
                            }}>
                              <span style={{ fontSize: 11 }}>📄</span>
                              <span>{src.document_title.length > 25 ? src.document_title.slice(0, 25) + '...' : src.document_title}</span>
                              {src.doc_type && <span style={{ fontSize: 8, textTransform: 'uppercase', opacity: 0.7 }}>{src.doc_type}</span>}
                              <span style={{ opacity: 0.6 }}>{Math.round(src.score * 100)}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <div className="px-4 py-4" style={{ borderTop: '1px solid var(--border-subtle)', background: 'var(--bg-secondary)' }}>
          <div className="mx-auto max-w-3xl flex gap-3">
            <textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
              placeholder={selectedDocIds.size > 0 ? `Ask about ${selectedDocIds.size} selected source${selectedDocIds.size > 1 ? 's' : ''}...` : 'Talk to Groot...'}
              rows={1} className="input-base focus-glow flex-1 resize-none"
              style={{ fontFamily: "'DM Sans', system-ui, sans-serif", fontSize: '14px' }} />
            <button onClick={() => sendMessage()} disabled={isStreaming || !input.trim()} className="btn-primary"
              style={{ fontSize: '13px', letterSpacing: '0.05em', opacity: isStreaming || !input.trim() ? 0.4 : 1, cursor: isStreaming || !input.trim() ? 'not-allowed' : 'pointer' }}>
              {isStreaming ? '...' : 'SEND'}
            </button>
          </div>
          <div className="mx-auto max-w-3xl mt-2 text-center">
            <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
              Powered by BitNet &middot; Sovereign AI
              {selectedDocIds.size > 0 ? ` · Notebook: ${selectedDocIds.size} sources` : ''}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Micro-components ──────────────────────────────────────────── */

function GenBtn({ label, loading, onClick }: { label: string; loading: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} disabled={loading}
      style={{
        fontSize: 9, padding: '2px 6px', borderRadius: 4,
        background: 'var(--bg-input)', border: '1px solid var(--border-default)',
        color: loading ? 'var(--text-tertiary)' : 'var(--refi-teal)',
        cursor: loading ? 'wait' : 'pointer', fontFamily: "'JetBrains Mono', monospace",
      }}>
      {loading ? '...' : label}
    </button>
  )
}
