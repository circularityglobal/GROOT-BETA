'use client'

import { useState, useRef, useEffect } from 'react'
import { API_URL } from '@/lib/config'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function GrootChatWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([{
    role: 'assistant',
    content: 'Hey! I\'m **Groot** — REFINET Cloud\'s AI assistant. I can help you learn about REFINET, our products, blockchain infrastructure, and sovereign tech. What would you like to know?',
  }])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => { if (open) inputRef.current?.focus() }, [open])

  const send = async () => {
    if (!input.trim() || streaming) return
    const userMsg: Message = { role: 'user', content: input.trim() }
    const updated = [...messages, userMsg]
    setMessages([...updated, { role: 'assistant', content: '' }])
    setInput('')
    setStreaming(true)

    try {
      const token = localStorage.getItem('refinet_token') || ''
      const resp = await fetch(`${API_URL}/v1/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          model: (typeof window !== 'undefined' && localStorage.getItem('refinet_preferred_model')) || 'bitnet-b1.58-2b',
          messages: updated.map(m => ({ role: m.role, content: m.content })),
          stream: true,
          max_tokens: 1024,
        }),
      })

      if (!resp.ok) {
        setMessages(prev => {
          const u = [...prev]; u[u.length - 1] = { role: 'assistant', content: resp.status === 429 ? 'You\'ve reached the free usage limit. Create a free account for 250 requests/day!' : resp.status === 401 ? 'Please sign in for full access.' : `Something went wrong (${resp.status}). Try again.` }; return u
        })
        setStreaming(false)
        return
      }

      const reader = resp.body?.getReader()
      const decoder = new TextDecoder()
      let acc = ''
      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          for (const line of decoder.decode(value, { stream: true }).split('\n')) {
            if (!line.startsWith('data: ')) continue
            const d = line.slice(6)
            if (d === '[DONE]') break
            try {
              const c = JSON.parse(d).choices?.[0]?.delta?.content || ''
              if (c) { acc += c; setMessages(prev => { const u = [...prev]; u[u.length - 1] = { role: 'assistant', content: acc }; return u }) }
            } catch {}
          }
        }
      }
    } catch {
      setMessages(prev => { const u = [...prev]; u[u.length - 1] = { role: 'assistant', content: 'Connection error — REFINET Cloud may be starting up.' }; return u })
    }
    setStreaming(false)
  }

  return (
    <>
      {/* Floating button — REFINET logo */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full flex items-center justify-center animate-pulse-glow transition-all hover:scale-110"
          style={{ background: 'var(--refi-teal)', boxShadow: 'var(--shadow-glow)' }}
          aria-label="Chat with Groot"
        >
          <img src="/refi-logo.png" alt="Groot" className="w-8 h-8 rounded-full" />
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 w-[420px] max-w-[calc(100vw-24px)] animate-slide-up rounded-[20px] overflow-hidden flex flex-col"
          style={{
            height: 'min(600px, 85vh)',
            background: 'var(--bg-primary)',
            border: '1px solid var(--border-default)',
            boxShadow: 'var(--shadow-lg)',
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full overflow-hidden flex-shrink-0" style={{ boxShadow: '0 0 12px var(--refi-teal-glow)' }}>
                <img src="/refi-logo.png" alt="Groot" className="w-full h-full object-cover" />
              </div>
              <div>
                <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Groot</div>
                <div className="text-[11px] font-mono" style={{ color: 'var(--refi-teal)' }}>
                  {streaming ? 'Thinking...' : 'REFINET Cloud AI'}
                </div>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="w-11 h-11 rounded-lg flex items-center justify-center transition-colors" style={{ color: 'var(--text-tertiary)' }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              aria-label="Close chat"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            {messages.map((msg, i) => (
              <div key={i} className="animate-fade-in">
                {msg.role === 'assistant' ? (
                  <div>
                    <div className="flex items-center gap-2 mb-1.5">
                      <img src="/refi-logo.png" alt="" className="w-4 h-4 rounded-full" />
                      <span className="text-[11px] font-mono" style={{ color: 'var(--text-tertiary)' }}>Groot</span>
                    </div>
                    <div className="text-[13px] leading-relaxed pl-6" style={{
                      borderLeft: '2px solid var(--refi-teal)',
                      paddingLeft: '12px',
                      color: 'var(--text-primary)',
                    }}>
                      <div className="prose-chat whitespace-pre-wrap">
                        {msg.content}
                        {streaming && i === messages.length - 1 && (
                          <span className="cursor-blink" style={{ color: 'var(--refi-teal)' }}>▌</span>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-[13px] leading-relaxed"
                      style={{ background: 'var(--refi-teal)', color: 'var(--text-inverse)' }}
                    >
                      {msg.content}
                    </div>
                  </div>
                )}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <div className="px-5 py-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
            <div className="flex gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder="Ask Groot anything..."
                rows={1}
                className="input-base focus-glow flex-1 text-[13px] resize-none"
                style={{ minHeight: '40px', maxHeight: '80px' }}
              />
              <button
                onClick={send}
                disabled={streaming || !input.trim()}
                className="w-11 h-11 rounded-full flex items-center justify-center transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                style={{ background: 'var(--refi-teal)', color: 'var(--text-inverse)' }}
                aria-label="Send message"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                </svg>
              </button>
            </div>
            <div className="text-center mt-2">
              <span className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>Powered by BitNet · Sovereign AI</span>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
