'use client'

import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { API_URL } from '@/lib/config'

/* ─── Types ─── */
interface DocSection {
  id: string
  title: string
  icon: string
  children?: { id: string; title: string }[]
}

/* ─── Table of contents structure ─── */
const TOC: DocSection[] = [
  { id: 'welcome', title: 'Welcome', icon: '👋' },
  { id: 'quickstart', title: 'Quick Start', icon: '⚡' },
  {
    id: 'authentication', title: 'Authentication', icon: '🔐',
    children: [
      { id: 'auth-siwe', title: 'Sign-In with Ethereum' },
      { id: 'auth-password', title: 'Password & 2FA' },
      { id: 'auth-tokens', title: 'Token Management' },
    ],
  },
  {
    id: 'inference', title: 'Inference API', icon: '🧠',
    children: [
      { id: 'inf-models', title: 'List Models' },
      { id: 'inf-chat', title: 'Chat Completions' },
      { id: 'inf-streaming', title: 'Streaming' },
      { id: 'inf-providers', title: 'Multi-Provider Gateway' },
      { id: 'inf-byok', title: 'Bring Your Own Key (BYOK)' },
    ],
  },
  {
    id: 'knowledge', title: 'Knowledge Base', icon: '📚',
    children: [
      { id: 'kb-upload', title: 'Upload Documents' },
      { id: 'kb-search', title: 'Search & RAG' },
      { id: 'kb-tags', title: 'Auto-Tagging' },
      { id: 'kb-compare', title: 'Document Comparison' },
    ],
  },
  {
    id: 'devices', title: 'Devices & IoT', icon: '📡',
    children: [
      { id: 'dev-register', title: 'Register Device' },
      { id: 'dev-telemetry', title: 'Telemetry' },
      { id: 'dev-commands', title: 'Commands' },
    ],
  },
  { id: 'webhooks', title: 'Webhooks', icon: '🔔' },
  {
    id: 'mcp', title: 'MCP Tools', icon: '🔧',
    children: [
      { id: 'mcp-protocols', title: '6-Protocol Gateway' },
      { id: 'mcp-document-tools', title: 'Document Tools' },
    ],
  },
  {
    id: 'appstore', title: 'App Store', icon: '🏪',
    children: [
      { id: 'as-browse', title: 'Browse & Install' },
      { id: 'as-submit', title: 'Submit an App' },
      { id: 'as-review', title: 'Review Pipeline' },
    ],
  },
  { id: 'interactive', title: 'Interactive Docs', icon: '🧪' },
]

/** Flat ordered list of all navigable section IDs for prev/next */
const FLAT_IDS: string[] = TOC.flatMap(s => s.children ? [s.id, ...s.children.map(c => c.id)] : [s.id])

/** Find which parent owns a child ID */
function findParentId(childId: string): string | null {
  for (const s of TOC) {
    if (s.children?.some(c => c.id === childId)) return s.id
  }
  return null
}

/** Get human-readable title for any section ID */
function getTitleForId(id: string): string {
  for (const s of TOC) {
    if (s.id === id) return s.title
    if (s.children) {
      const child = s.children.find(c => c.id === id)
      if (child) return child.title
    }
  }
  return id
}

/* ─── Main Component ─── */
export default function DocsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [activeSection, setActiveSection] = useState('welcome')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['authentication', 'inference', 'knowledge']))
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [pageTransition, setPageTransition] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)
  const modalRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  // Reset state when modal opens; capture focus origin
  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement as HTMLElement
      setSearchQuery('')
      setMobileSidebarOpen(false)
      setActiveSection('welcome')
      setPageTransition(false)
      // Move focus into modal on next frame
      requestAnimationFrame(() => modalRef.current?.focus())
    } else if (previousFocusRef.current) {
      previousFocusRef.current.focus()
      previousFocusRef.current = null
    }
  }, [open])

  // Escape to close + Cmd/Ctrl+K for search
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (mobileSidebarOpen) setMobileSidebarOpen(false)
        else onClose()
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        searchInputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose, mobileSidebarOpen])

  // Focus trap
  useEffect(() => {
    if (!open || !modalRef.current) return
    const modal = modalRef.current
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return
      const focusable = modal.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    modal.addEventListener('keydown', handler)
    return () => modal.removeEventListener('keydown', handler)
  }, [open])

  // Prevent body scroll when modal open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  const toggleGroup = useCallback((id: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const navigateTo = useCallback((id: string) => {
    setPageTransition(true)
    // Expand parent group if navigating to a child
    const parent = findParentId(id)
    if (parent) {
      setExpandedGroups(prev => {
        const next = new Set(prev)
        next.add(parent)
        return next
      })
    }
    setTimeout(() => {
      setActiveSection(id)
      contentRef.current?.scrollTo({ top: 0 })
      setMobileSidebarOpen(false)
      // Clear transition after animation
      requestAnimationFrame(() => setPageTransition(false))
    }, 80)
  }, [])

  // Filter TOC by search — auto-expand matching groups
  const filteredToc = useMemo(() => {
    if (!searchQuery) return TOC
    const q = searchQuery.toLowerCase()
    return TOC.filter(s =>
      s.title.toLowerCase().includes(q) ||
      s.children?.some(c => c.title.toLowerCase().includes(q))
    )
  }, [searchQuery])

  // Auto-expand groups whose children match the search
  useEffect(() => {
    if (!searchQuery) return
    const q = searchQuery.toLowerCase()
    setExpandedGroups(prev => {
      const next = new Set(prev)
      for (const s of TOC) {
        if (s.children?.some(c => c.title.toLowerCase().includes(q))) {
          next.add(s.id)
        }
      }
      return next
    })
  }, [searchQuery])

  // Prev / Next navigation
  const currentIdx = FLAT_IDS.indexOf(activeSection)
  const prevId = currentIdx > 0 ? FLAT_IDS[currentIdx - 1] : null
  const nextId = currentIdx < FLAT_IDS.length - 1 ? FLAT_IDS[currentIdx + 1] : null

  // Check if a parent section or one of its children is active
  const isGroupActive = useCallback((section: DocSection): boolean => {
    if (activeSection === section.id) return true
    return !!section.children?.some(c => c.id === activeSection)
  }, [activeSection])

  if (!open) return null

  return (
    <div className="docs-modal-overlay" onClick={onClose}>
      <div
        className="docs-modal"
        ref={modalRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="REFINET Platform Documentation"
        onClick={e => e.stopPropagation()}
      >
        {/* ── Sidebar ── */}
        <aside className={`docs-sidebar ${mobileSidebarOpen ? 'docs-sidebar-mobile-open' : ''}`}>
          {/* Header */}
          <div className="docs-sidebar-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
              <div className="docs-logo-circle">
                <img src="/refi-logo.png" alt="" style={{ width: 22, height: 22 }} />
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '0.02em' }}>
                  REFINET<span style={{ color: 'var(--refi-teal)' }}> Docs</span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', letterSpacing: '0.04em' }}>Platform Documentation</div>
              </div>
            </div>
            <span className="docs-version-badge">v3.0</span>
            {/* Mobile close sidebar */}
            <button
              className="docs-mobile-sidebar-close"
              onClick={() => setMobileSidebarOpen(false)}
              aria-label="Close navigation"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          {/* Search */}
          <div className="docs-search-wrap">
            <svg className="docs-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              ref={searchInputRef}
              className="docs-search"
              placeholder="Search docs..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              aria-label="Search documentation"
            />
            <kbd className="docs-search-kbd">⌘K</kbd>
            {searchQuery && (
              <button className="docs-search-clear" onClick={() => setSearchQuery('')} aria-label="Clear search">&times;</button>
            )}
          </div>

          {/* Navigation */}
          <nav className="docs-nav" aria-label="Documentation sections">
            {filteredToc.map(section => (
              <div key={section.id}>
                <button
                  className={`docs-nav-item ${isGroupActive(section) ? 'docs-nav-active' : ''}`}
                  onClick={() => {
                    navigateTo(section.id)
                    if (section.children) toggleGroup(section.id)
                  }}
                  aria-expanded={section.children ? expandedGroups.has(section.id) : undefined}
                  aria-current={activeSection === section.id ? 'page' : undefined}
                >
                  <span className="docs-nav-icon" aria-hidden="true">{section.icon}</span>
                  <span className="docs-nav-label">{section.title}</span>
                  {section.children && (
                    <svg
                      className="docs-nav-chevron"
                      width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                      style={{ transform: expandedGroups.has(section.id) ? 'rotate(90deg)' : 'rotate(0deg)' }}
                      aria-hidden="true"
                    >
                      <polyline points="9 18 15 12 9 6"/>
                    </svg>
                  )}
                </button>
                {section.children && expandedGroups.has(section.id) && (
                  <div className="docs-nav-children" role="group" aria-label={`${section.title} sub-pages`}>
                    {section.children
                      .filter(c => !searchQuery || c.title.toLowerCase().includes(searchQuery.toLowerCase()))
                      .map(child => (
                        <button
                          key={child.id}
                          className={`docs-nav-child ${activeSection === child.id ? 'docs-nav-active' : ''}`}
                          onClick={() => navigateTo(child.id)}
                          aria-current={activeSection === child.id ? 'page' : undefined}
                        >
                          {child.title}
                        </button>
                      ))
                    }
                  </div>
                )}
              </div>
            ))}
          </nav>

          {/* Sidebar footer */}
          <div className="docs-sidebar-footer">
            <a href={`${API_URL}/docs`} target="_blank" rel="noopener noreferrer" className="docs-sidebar-link">
              <ExternalLinkIcon /> Swagger UI
            </a>
            <a href={`${API_URL}/redoc`} target="_blank" rel="noopener noreferrer" className="docs-sidebar-link">
              <ExternalLinkIcon /> ReDoc
            </a>
          </div>
        </aside>

        {/* Mobile sidebar backdrop */}
        {mobileSidebarOpen && (
          <div className="docs-mobile-backdrop" onClick={() => setMobileSidebarOpen(false)} />
        )}

        {/* ── Main Content ── */}
        <div className="docs-content-area">
          {/* Top bar */}
          <div className="docs-topbar">
            {/* Mobile hamburger */}
            <button
              className="docs-mobile-menu-btn"
              onClick={() => setMobileSidebarOpen(true)}
              aria-label="Open navigation"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
              </svg>
            </button>
            <Breadcrumb activeSection={activeSection} />
            <button className="docs-close-btn" onClick={onClose} aria-label="Close documentation">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          {/* Scrollable content */}
          <div className="docs-content-scroll" ref={contentRef}>
            <div className={`docs-content ${pageTransition ? 'docs-content-transitioning' : ''}`}>
              <DocContent section={activeSection} onNavigate={navigateTo} />

              {/* ── Prev / Next Navigation (GitBook signature) ── */}
              <div className="docs-page-nav">
                {prevId ? (
                  <button className="docs-page-nav-btn docs-page-nav-prev" onClick={() => navigateTo(prevId)}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
                    </svg>
                    <div>
                      <div className="docs-page-nav-label">Previous</div>
                      <div className="docs-page-nav-title">{getTitleForId(prevId)}</div>
                    </div>
                  </button>
                ) : <div />}
                {nextId ? (
                  <button className="docs-page-nav-btn docs-page-nav-next" onClick={() => navigateTo(nextId)}>
                    <div>
                      <div className="docs-page-nav-label">Next</div>
                      <div className="docs-page-nav-title">{getTitleForId(nextId)}</div>
                    </div>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                    </svg>
                  </button>
                ) : <div />}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─── Small shared icon ─── */
function ExternalLinkIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
      <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
    </svg>
  )
}

/* ─── Breadcrumb ─── */
function Breadcrumb({ activeSection }: { activeSection: string }) {
  let parent: string | null = null
  let current = activeSection

  for (const s of TOC) {
    if (s.id === activeSection) { current = s.title; break }
    if (s.children) {
      const child = s.children.find(c => c.id === activeSection)
      if (child) { parent = s.title; current = child.title; break }
    }
  }

  return (
    <nav className="docs-breadcrumb" aria-label="Breadcrumb">
      <span style={{ color: 'var(--text-tertiary)' }}>Docs</span>
      {parent && <>
        <span className="docs-breadcrumb-sep">/</span>
        <span style={{ color: 'var(--text-tertiary)' }}>{parent}</span>
      </>}
      <span className="docs-breadcrumb-sep">/</span>
      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{current}</span>
    </nav>
  )
}

/* ─── Content Renderer ─── */
function DocContent({ section, onNavigate }: { section: string; onNavigate: (id: string) => void }) {
  switch (section) {
    case 'welcome': return <WelcomeContent onNavigate={onNavigate} />
    case 'quickstart': return <QuickStartContent />
    case 'authentication':
    case 'auth-siwe': return <AuthSIWEContent />
    case 'auth-password': return <AuthPasswordContent />
    case 'auth-tokens': return <AuthTokensContent />
    case 'inference':
    case 'inf-models': return <InfModelsContent />
    case 'inf-chat': return <InfChatContent />
    case 'inf-streaming': return <InfStreamingContent />
    case 'inf-providers': return <InfProvidersContent />
    case 'inf-byok': return <InfByokContent />
    case 'knowledge':
    case 'kb-upload': return <KBUploadContent />
    case 'kb-search': return <KBSearchContent />
    case 'kb-tags': return <KBTagsContent />
    case 'kb-compare': return <KBCompareContent />
    case 'devices':
    case 'dev-register': return <DevRegisterContent />
    case 'dev-telemetry': return <DevTelemetryContent />
    case 'dev-commands': return <DevCommandsContent />
    case 'webhooks': return <WebhooksContent />
    case 'mcp':
    case 'mcp-protocols': return <MCPProtocolsContent />
    case 'mcp-document-tools': return <MCPDocToolsContent />
    case 'appstore':
    case 'as-browse': return <ASBrowseContent />
    case 'as-submit': return <ASSubmitContent />
    case 'as-review': return <ASReviewContent />
    case 'interactive': return <InteractiveContent />
    default: return <WelcomeContent onNavigate={onNavigate} />
  }
}

/* ─── Reusable Components ─── */
function PageTitle({ children }: { children: React.ReactNode }) {
  return <h1 className="docs-page-title">{children}</h1>
}

function PageDesc({ children }: { children: React.ReactNode }) {
  return <p className="docs-page-desc">{children}</p>
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="docs-section-heading">{children}</h2>
}

function Paragraph({ children }: { children: React.ReactNode }) {
  return <p className="docs-paragraph">{children}</p>
}

function InlineCode({ children }: { children: React.ReactNode }) {
  return <code className="docs-inline-code">{children}</code>
}

function CodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Clean up timer on unmount to prevent state updates after unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const handleCopy = () => {
    navigator.clipboard?.writeText(code)
    setCopied(true)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="docs-codeblock">
      <div className="docs-codeblock-header">
        <span className="docs-codeblock-lang">{language || 'code'}</span>
        <button className="docs-codeblock-copy" onClick={handleCopy} aria-label="Copy code to clipboard">
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre className="docs-codeblock-pre"><code>{code}</code></pre>
    </div>
  )
}

function Endpoint({ method, path, desc }: { method: string; path: string; desc: string }) {
  const methodColors: Record<string, string> = {
    GET: '#4ADE80', POST: '#60A5FA', PUT: '#FBBF24', DELETE: '#F87171', TOOL: '#C084FC',
  }
  return (
    <div className="docs-endpoint">
      <span className="docs-endpoint-method" style={{ color: methodColors[method] || 'var(--text-primary)' }}>
        {method}
      </span>
      <code className="docs-endpoint-path">{path}</code>
      <span className="docs-endpoint-desc">{desc}</span>
    </div>
  )
}

function Callout({ type = 'info', children }: { type?: 'info' | 'warning' | 'tip'; children: React.ReactNode }) {
  const labels = { info: 'Info', warning: 'Warning', tip: 'Tip' }
  const icons = { info: 'ℹ️', warning: '⚠️', tip: '💡' }
  const borders = { info: 'var(--refi-teal)', warning: 'var(--warning)', tip: '#C084FC' }
  return (
    <div className="docs-callout" style={{ borderLeftColor: borders[type] }} role="note" aria-label={labels[type]}>
      <span className="docs-callout-icon" aria-hidden="true">{icons[type]}</span>
      <div>{children}</div>
    </div>
  )
}

function NavCard({ title, desc, onClick }: { title: string; desc: string; onClick: () => void }) {
  return (
    <button className="docs-navcard" onClick={onClick}>
      <div className="docs-navcard-title">{title}</div>
      <div className="docs-navcard-desc">{desc}</div>
      <svg className="docs-navcard-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
      </svg>
    </button>
  )
}

/* ═══════════════════════════════════════════
   Content Pages
   ═══════════════════════════════════════════ */

function WelcomeContent({ onNavigate }: { onNavigate: (id: string) => void }) {
  return (
    <>
      <PageTitle>Welcome to REFINET Cloud</PageTitle>
      <PageDesc>
        REFINET Cloud is a sovereign AI platform that runs entirely on your infrastructure.
        No vendor lock-in, no data exfiltration — just powerful AI tools with full ownership.
      </PageDesc>

      <Callout type="tip">
        New here? Start with the <button className="docs-inline-link" onClick={() => onNavigate('quickstart')}>Quick Start</button> guide
        to make your first API call in under 2 minutes.
      </Callout>

      <SectionHeading>What can you build?</SectionHeading>

      <div className="docs-navcard-grid">
        <NavCard title="AI Chat & Inference" desc="OpenAI-compatible API — use your existing SDK" onClick={() => onNavigate('inference')} />
        <NavCard title="Knowledge Base" desc="Upload docs, auto-tag, semantic search with RAG" onClick={() => onNavigate('knowledge')} />
        <NavCard title="IoT & Devices" desc="Register devices, stream telemetry, send commands" onClick={() => onNavigate('devices')} />
        <NavCard title="App Store" desc="Publish and discover community applications" onClick={() => onNavigate('appstore')} />
        <NavCard title="MCP Gateway" desc="6-protocol gateway for AI agent interop" onClick={() => onNavigate('mcp')} />
        <NavCard title="Webhooks" desc="Subscribe to events and get real-time notifications" onClick={() => onNavigate('webhooks')} />
      </div>

      <SectionHeading>Core Principles</SectionHeading>
      <div className="docs-principles">
        <div className="docs-principle">
          <div className="docs-principle-icon" aria-hidden="true">🏛️</div>
          <div>
            <strong>Sovereign</strong>
            <Paragraph>Your data never leaves your infrastructure. Zero external API calls for core operations.</Paragraph>
          </div>
        </div>
        <div className="docs-principle">
          <div className="docs-principle-icon" aria-hidden="true">🔗</div>
          <div>
            <strong>Wallet-Native</strong>
            <Paragraph>Sign in with Ethereum — no email/password required. Your wallet is your identity.</Paragraph>
          </div>
        </div>
        <div className="docs-principle">
          <div className="docs-principle-icon" aria-hidden="true">🤖</div>
          <div>
            <strong>Agent-Ready</strong>
            <Paragraph>Every endpoint is accessible to AI agents via the MCP gateway across 6 protocols.</Paragraph>
          </div>
        </div>
      </div>
    </>
  )
}

function QuickStartContent() {
  return (
    <>
      <PageTitle>Quick Start</PageTitle>
      <PageDesc>Make your first API call in under 2 minutes.</PageDesc>

      <SectionHeading>1. Connect your wallet</SectionHeading>
      <Paragraph>
        Visit the REFINET Cloud dashboard and connect your Ethereum wallet.
        No registration form — your wallet address is your account.
      </Paragraph>

      <SectionHeading>2. Make an API call</SectionHeading>
      <Paragraph>
        REFINET exposes an OpenAI-compatible API. Use your existing SDK — just change the base URL.
      </Paragraph>

      <CodeBlock language="python" code={`from openai import OpenAI

client = OpenAI(
    base_url="${API_URL}/v1",
    api_key="rf_your_key_here"
)

response = client.chat.completions.create(
    model="bitnet-b1.58-2b",
    messages=[{"role": "user", "content": "Hello, Groot"}],
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content, end="")`} />

      <CodeBlock language="javascript" code={`import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: '${API_URL}/v1',
  apiKey: 'rf_your_key_here',
});

const stream = await client.chat.completions.create({
  model: 'bitnet-b1.58-2b',
  messages: [{ role: 'user', content: 'Hello, Groot' }],
  stream: true,
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || '');
}`} />

      <Callout type="info">
        The API is fully OpenAI-compatible. Any library or tool that works with the OpenAI API will work with REFINET.
      </Callout>

      <SectionHeading>3. Upload a document</SectionHeading>
      <CodeBlock language="bash" code={`curl -X POST ${API_URL}/knowledge/documents/upload \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -F "file=@whitepaper.pdf"`} />
    </>
  )
}

function AuthSIWEContent() {
  return (
    <>
      <PageTitle>Sign-In with Ethereum</PageTitle>
      <PageDesc>
        Wallet-based authentication using the SIWE standard. No registration — connect and go.
      </PageDesc>

      <SectionHeading>How it works</SectionHeading>
      <ol className="docs-list">
        <li>Request a nonce from the server</li>
        <li>Sign a SIWE message with your wallet</li>
        <li>Submit the signature to get a JWT token</li>
        <li>Use the JWT for all subsequent API calls</li>
      </ol>

      <SectionHeading>Endpoints</SectionHeading>
      <Endpoint method="GET" path="/auth/siwe/nonce" desc="Get a fresh nonce for signing" />
      <Endpoint method="POST" path="/auth/siwe/verify" desc="Submit signature → receive JWT + refresh token" />
      <Endpoint method="GET" path="/auth/me" desc="Get current user profile" />
      <Endpoint method="PUT" path="/auth/me" desc="Update username or email" />

      <SectionHeading>Example flow</SectionHeading>
      <CodeBlock language="javascript" code={`// 1. Get nonce
const { nonce } = await fetch('${API_URL}/auth/siwe/nonce')
  .then(r => r.json());

// 2. Create SIWE message
const message = new SiweMessage({
  domain: window.location.host,
  address: walletAddress,
  statement: 'Sign in to REFINET Cloud',
  uri: window.location.origin,
  version: '1',
  chainId: 1,
  nonce,
});

// 3. Sign with wallet
const signature = await signer.signMessage(
  message.prepareMessage()
);

// 4. Verify → get JWT
const { token } = await fetch('${API_URL}/auth/siwe/verify', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: message.prepareMessage(),
    signature,
  }),
}).then(r => r.json());`} />

      <Callout type="tip">
        Supports Ethereum, Polygon, Arbitrum, Base, Optimism, BSC, and their testnets.
      </Callout>
    </>
  )
}

function AuthPasswordContent() {
  return (
    <>
      <PageTitle>Password & Two-Factor Auth</PageTitle>
      <PageDesc>Optional email/password and TOTP 2FA for additional security.</PageDesc>

      <Callout type="info">
        Password login is fully optional. Wallet-based login is the primary authentication method.
      </Callout>

      <SectionHeading>Endpoints</SectionHeading>
      <Endpoint method="POST" path="/auth/settings/password" desc="Set email + password (optional)" />
      <Endpoint method="POST" path="/auth/login" desc="Password login (if password set)" />
      <Endpoint method="POST" path="/auth/login/totp" desc="Complete password login with TOTP code" />
      <Endpoint method="POST" path="/auth/settings/totp/setup" desc="Enable TOTP 2FA" />
      <Endpoint method="POST" path="/auth/settings/totp/verify" desc="Verify TOTP setup code" />

      <SectionHeading>Setting up 2FA</SectionHeading>
      <ol className="docs-list">
        <li>Call the TOTP setup endpoint to receive a QR code URI</li>
        <li>Scan the QR code with your authenticator app (Google Authenticator, Authy, etc.)</li>
        <li>Submit the 6-digit code to the verify endpoint to activate 2FA</li>
      </ol>
    </>
  )
}

function AuthTokensContent() {
  return (
    <>
      <PageTitle>Token Management</PageTitle>
      <PageDesc>How JWT tokens and refresh tokens work in REFINET.</PageDesc>

      <SectionHeading>Token lifecycle</SectionHeading>
      <Paragraph>
        After authentication, you receive a short-lived JWT access token and a longer-lived refresh token.
        Use the refresh endpoint to rotate tokens without re-authenticating.
      </Paragraph>

      <Endpoint method="POST" path="/auth/token/refresh" desc="Rotate refresh token → new access + refresh pair" />

      <SectionHeading>Example</SectionHeading>
      <CodeBlock language="javascript" code={`// Refresh your token
const { token, refresh } = await fetch(
  '${API_URL}/auth/token/refresh',
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      refresh_token: currentRefreshToken,
    }),
  }
).then(r => r.json());`} />

      <Callout type="warning">
        Store refresh tokens securely. If a refresh token is compromised, use the logout endpoint to invalidate all sessions.
      </Callout>
    </>
  )
}

function InfModelsContent() {
  return (
    <>
      <PageTitle>List Models</PageTitle>
      <PageDesc>Discover available AI models on this REFINET instance.</PageDesc>

      <Endpoint method="GET" path="/v1/models" desc="List all available models (no auth required)" />

      <SectionHeading>Example</SectionHeading>
      <CodeBlock language="bash" code={`curl ${API_URL}/v1/models`} />

      <SectionHeading>Response</SectionHeading>
      <CodeBlock language="json" code={`{
  "object": "list",
  "data": [
    {
      "id": "bitnet-b1.58-2b",
      "object": "model",
      "created": 1700000000,
      "owned_by": "refinet",
      "provider": "refinet",
      "context_window": 2048,
      "is_free": true
    },
    {
      "id": "gemini-2.0-flash",
      "object": "model",
      "created": 1700000000,
      "owned_by": "google",
      "provider": "gemini",
      "context_window": 1048576,
      "is_free": true
    }
  ]
}`} />

      <Callout type="info">
        Available models depend on which providers are configured. BitNet is always available. Gemini, Ollama, LM Studio, and OpenRouter are enabled via environment variables.
      </Callout>
    </>
  )
}

function InfChatContent() {
  return (
    <>
      <PageTitle>Chat Completions</PageTitle>
      <PageDesc>Send messages and receive AI responses using the OpenAI-compatible chat completions endpoint.</PageDesc>

      <Endpoint method="POST" path="/v1/chat/completions" desc="Create a chat completion (streaming or non-streaming)" />

      <SectionHeading>Request body</SectionHeading>
      <CodeBlock language="json" code={`{
  "model": "bitnet-b1.58-2b",
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "What is regenerative finance?" }
  ],
  "temperature": 0.7,
  "max_tokens": 512,
  "stream": false
}`} />

      <SectionHeading>Multi-model: Switch providers</SectionHeading>
      <Paragraph>
        Change the <InlineCode>model</InlineCode> field to route to any configured provider:
      </Paragraph>
      <CodeBlock language="json" code={`{
  "model": "gemini-2.0-flash",
  "messages": [{ "role": "user", "content": "Hello" }],
  "stream": true,
  "grounding": true
}`} />

      <SectionHeading>Supported parameters</SectionHeading>
      <div className="docs-badge-row">
        {['model', 'temperature', 'top_p', 'max_tokens', 'stream', 'grounding', 'notebook_doc_ids'].map(p => (
          <span key={p} className="docs-badge">{p}</span>
        ))}
      </div>

      <Callout type="info">
        All standard OpenAI parameters are supported. Use <InlineCode>grounding: true</InlineCode> with Gemini models to enable Google Search for web-enriched answers. Use <InlineCode>notebook_doc_ids</InlineCode> to scope RAG to specific documents.
      </Callout>
    </>
  )
}

function InfStreamingContent() {
  return (
    <>
      <PageTitle>Streaming Responses</PageTitle>
      <PageDesc>Get token-by-token responses using Server-Sent Events (SSE).</PageDesc>

      <Paragraph>
        Set <InlineCode>stream: true</InlineCode> in your request to receive incremental chunks as they are generated.
      </Paragraph>

      <CodeBlock language="python" code={`response = client.chat.completions.create(
    model="bitnet-b1.58-2b",
    messages=[{"role": "user", "content": "Explain DeFi"}],
    stream=True
)

for chunk in response:
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="", flush=True)`} />

      <CodeBlock language="javascript" code={`const stream = await client.chat.completions.create({
  model: 'bitnet-b1.58-2b',
  messages: [{ role: 'user', content: 'Explain DeFi' }],
  stream: true,
});

for await (const chunk of stream) {
  const content = chunk.choices[0]?.delta?.content;
  if (content) process.stdout.write(content);
}`} />
    </>
  )
}

function InfProvidersContent() {
  return (
    <>
      <PageTitle>Multi-Provider Gateway</PageTitle>
      <PageDesc>
        REFINET routes inference through multiple AI backends via a strategy-pattern gateway. BitNet is the sovereign default.
        The gateway automatically falls back to healthy providers when one is unavailable.
      </PageDesc>

      <SectionHeading>Supported Providers</SectionHeading>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
        {[
          { name: 'BitNet b1.58-2B', type: 'Sovereign', free: true },
          { name: 'Google Gemini', type: 'Cloud', free: true },
          { name: 'Ollama', type: 'Local', free: true },
          { name: 'LM Studio', type: 'Local', free: true },
          { name: 'OpenRouter', type: 'Cloud', free: true },
          { name: 'OpenAI (BYOK)', type: 'BYOK', free: false },
          { name: 'Anthropic (BYOK)', type: 'BYOK', free: false },
          { name: 'Groq (BYOK)', type: 'BYOK', free: true },
          { name: 'Mistral (BYOK)', type: 'BYOK', free: false },
          { name: 'Together AI (BYOK)', type: 'BYOK', free: true },
        ].map(p => (
          <div key={p.name} className="docs-badge" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>{p.name}</span>
            <span style={{ opacity: 0.6 }}>{p.free ? 'FREE' : 'PAID'}</span>
          </div>
        ))}
      </div>

      <SectionHeading>Model Selection</SectionHeading>
      <Paragraph>
        Set the <InlineCode>model</InlineCode> field in your request. The gateway resolves the provider automatically
        from the model name prefix: <InlineCode>gpt-*</InlineCode> routes to OpenAI,{' '}
        <InlineCode>claude-*</InlineCode> to Anthropic, <InlineCode>gemini-*</InlineCode> to Google.
      </Paragraph>

      <SectionHeading>Fallback Chain</SectionHeading>
      <Paragraph>
        Configure via <InlineCode>PROVIDER_FALLBACK_CHAIN</InlineCode> env var (default:{' '}
        <InlineCode>bitnet,gemini,ollama,lmstudio,openrouter</InlineCode>).
        If the resolved provider is unhealthy, the gateway walks the chain until a healthy one is found.
      </Paragraph>

      <Callout type="info">
        RAG context injection works identically across all providers. Every model gets the same knowledge base enrichment.
      </Callout>
    </>
  )
}

function InfByokContent() {
  return (
    <>
      <PageTitle>Bring Your Own Key (BYOK)</PageTitle>
      <PageDesc>
        Connect your own API keys for external AI providers. Use GPT-4o, Claude, Gemini Pro, and more
        with your own billing — the platform never sees your charges.
      </PageDesc>

      <SectionHeading>Security Requirement</SectionHeading>
      <Paragraph>
        BYOK requires all three security layers to be complete before you can save or use external keys:
      </Paragraph>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', margin: '8px 0' }}>
        <div className="docs-badge">Layer 3: SIWE (wallet signature)</div>
        <div className="docs-badge">Layer 1: Email + Password (Argon2id)</div>
        <div className="docs-badge">Layer 2: TOTP 2FA (authenticator app)</div>
      </div>

      <SectionHeading>How to Connect</SectionHeading>
      <Paragraph>
        1. Complete all 3 security layers in Settings → Security<br />
        2. Go to Settings → AI Services<br />
        3. Click a provider and enter your API key<br />
        4. Test the connection — green checkmark confirms success<br />
        5. Select the model in the chat header and start using it
      </Paragraph>

      <SectionHeading>API Usage</SectionHeading>
      <CodeBlock language="bash" code={`# Save a provider key
curl -X POST ${API_URL}/provider-keys \\
  -H "Authorization: Bearer YOUR_JWT" \\
  -H "Content-Type: application/json" \\
  -d '{"provider_type": "openai", "display_name": "My OpenAI Key", "api_key": "sk-..."}'

# Use it for inference (just change the model name)
curl -X POST ${API_URL}/v1/chat/completions \\
  -H "Authorization: Bearer YOUR_JWT" \\
  -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}'`} />

      <Callout type="info">
        Keys are encrypted with AES-256-GCM at rest. The platform creates an ephemeral provider per-request — your key is
        decrypted only for the duration of the API call, then discarded from memory. Platform keys are never touched.
      </Callout>
    </>
  )
}

function KBUploadContent() {
  return (
    <>
      <PageTitle>Upload Documents</PageTitle>
      <PageDesc>
        Upload any document to the knowledge base — auto-parsed, auto-tagged, and ready for LLM search.
      </PageDesc>

      <SectionHeading>Endpoints</SectionHeading>
      <Endpoint method="POST" path="/knowledge/documents" desc="Upload via JSON body (title + content)" />
      <Endpoint method="POST" path="/knowledge/documents/upload" desc="Upload file (multipart form)" />
      <Endpoint method="GET" path="/knowledge/documents" desc="List all documents with metadata" />
      <Endpoint method="DELETE" path="/knowledge/documents/{id}" desc="Remove document" />

      <SectionHeading>Supported file types</SectionHeading>
      <div className="docs-badge-row">
        {['PDF', 'DOCX', 'XLSX', 'CSV', 'TXT', 'Markdown', 'JSON/ABI', 'Solidity'].map(t => (
          <span key={t} className="docs-badge">{t}</span>
        ))}
      </div>

      <SectionHeading>Example: upload a file</SectionHeading>
      <CodeBlock language="bash" code={`curl -X POST ${API_URL}/knowledge/documents/upload \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -F "file=@whitepaper.pdf"`} />

      <Callout type="tip">
        All parsing is sovereign — zero external API calls. PDFs use PyMuPDF, DOCX uses python-docx, XLSX uses openpyxl.
      </Callout>
    </>
  )
}

function KBSearchContent() {
  return (
    <>
      <PageTitle>Search & RAG</PageTitle>
      <PageDesc>Hybrid search combining semantic vectors and keyword matching with tag filtering.</PageDesc>

      <SectionHeading>Endpoint</SectionHeading>
      <Endpoint method="GET" path="/knowledge/search?q=&tags=" desc="Hybrid RAG search with tag filtering" />

      <SectionHeading>Parameters</SectionHeading>
      <div className="docs-params">
        <div className="docs-param"><InlineCode>q</InlineCode><span>Natural language search query</span></div>
        <div className="docs-param"><InlineCode>tags</InlineCode><span>Comma-separated tag filter (e.g., <InlineCode>defi,sustainability</InlineCode>)</span></div>
      </div>

      <SectionHeading>Example</SectionHeading>
      <CodeBlock language="bash" code={`curl "${API_URL}/knowledge/search?q=carbon+credits&tags=defi,sustainability" \\
  -H "Authorization: Bearer YOUR_TOKEN"`} />
    </>
  )
}

function KBTagsContent() {
  return (
    <>
      <PageTitle>Auto-Tagging</PageTitle>
      <PageDesc>Documents are automatically tagged with semantic labels upon upload.</PageDesc>

      <SectionHeading>Endpoints</SectionHeading>
      <Endpoint method="GET" path="/knowledge/documents/{id}/tags" desc="Get auto-generated semantic tags" />
      <Endpoint method="POST" path="/knowledge/documents/{id}/retag" desc="Re-generate tags for existing document" />

      <Callout type="info">
        Tags are generated using the local LLM — no data leaves your infrastructure. Re-tagging is useful after model upgrades.
      </Callout>
    </>
  )
}

function KBCompareContent() {
  return (
    <>
      <PageTitle>Document Comparison</PageTitle>
      <PageDesc>Compare two documents by semantic similarity, keyword overlap, and tag intersection.</PageDesc>

      <SectionHeading>Endpoint</SectionHeading>
      <Endpoint method="POST" path="/knowledge/documents/compare" desc="Compare two documents" />

      <SectionHeading>Request body</SectionHeading>
      <CodeBlock language="json" code={`{
  "document_id_a": "doc_abc123",
  "document_id_b": "doc_def456"
}`} />

      <Paragraph>
        Returns a similarity score across three dimensions: semantic embedding distance, keyword overlap ratio, and tag intersection count.
      </Paragraph>
    </>
  )
}

function DevRegisterContent() {
  return (
    <>
      <PageTitle>Register Device</PageTitle>
      <PageDesc>Register IoT, PLC, and DLT devices on the platform.</PageDesc>

      <SectionHeading>Endpoints</SectionHeading>
      <Endpoint method="POST" path="/devices/register" desc="Register a new device" />
      <Endpoint method="GET" path="/devices" desc="List your registered devices" />

      <SectionHeading>Example</SectionHeading>
      <CodeBlock language="json" code={`{
  "name": "Solar Panel Array #3",
  "type": "IoT",
  "metadata": {
    "location": "Building A, Roof",
    "manufacturer": "SunPower"
  }
}`} />
    </>
  )
}

function DevTelemetryContent() {
  return (
    <>
      <PageTitle>Telemetry</PageTitle>
      <PageDesc>Stream real-time telemetry data from your devices.</PageDesc>

      <SectionHeading>Endpoints</SectionHeading>
      <Endpoint method="POST" path="/devices/{id}/telemetry" desc="Ingest telemetry data point" />
      <Endpoint method="GET" path="/devices/{id}/telemetry" desc="Query telemetry history" />

      <SectionHeading>Ingest example</SectionHeading>
      <CodeBlock language="json" code={`{
  "timestamp": "2026-03-19T12:00:00Z",
  "metrics": {
    "power_output_kw": 4.2,
    "temperature_c": 35.1,
    "efficiency": 0.87
  }
}`} />
    </>
  )
}

function DevCommandsContent() {
  return (
    <>
      <PageTitle>Device Commands</PageTitle>
      <PageDesc>Send remote commands to registered devices.</PageDesc>

      <SectionHeading>Endpoint</SectionHeading>
      <Endpoint method="POST" path="/devices/{id}/command" desc="Send command to device" />

      <SectionHeading>Example</SectionHeading>
      <CodeBlock language="json" code={`{
  "command": "restart",
  "params": { "delay_seconds": 5 }
}`} />
    </>
  )
}

function WebhooksContent() {
  return (
    <>
      <PageTitle>Webhooks</PageTitle>
      <PageDesc>Subscribe to platform events and receive real-time HTTP callbacks.</PageDesc>

      <SectionHeading>Endpoints</SectionHeading>
      <Endpoint method="POST" path="/webhooks/subscribe" desc="Register webhook URL + events" />
      <Endpoint method="GET" path="/webhooks" desc="List your webhook subscriptions" />
      <Endpoint method="POST" path="/webhooks/{id}/test" desc="Send a test event" />

      <SectionHeading>Example subscription</SectionHeading>
      <CodeBlock language="json" code={`{
  "url": "https://your-server.com/webhook",
  "events": [
    "document.created",
    "device.telemetry",
    "inference.complete"
  ],
  "secret": "whsec_your_signing_secret"
}`} />

      <SectionHeading>Available events</SectionHeading>
      <div className="docs-badge-row">
        {['document.created', 'document.deleted', 'device.telemetry', 'device.command', 'inference.complete', 'app.submitted', 'app.approved'].map(e => (
          <span key={e} className="docs-badge">{e}</span>
        ))}
      </div>

      <Callout type="warning">
        Always verify webhook signatures using the shared secret to prevent spoofed events.
      </Callout>
    </>
  )
}

function MCPProtocolsContent() {
  return (
    <>
      <PageTitle>6-Protocol MCP Gateway</PageTitle>
      <PageDesc>
        Every REFINET tool is accessible to AI agents via all 6 MCP protocols simultaneously.
      </PageDesc>

      <div className="docs-badge-row">
        {['REST', 'GraphQL', 'gRPC', 'SOAP', 'WebSocket', 'Webhooks'].map(p => (
          <span key={p} className="docs-badge">{p}</span>
        ))}
      </div>

      <SectionHeading>How it works</SectionHeading>
      <Paragraph>
        The MCP gateway exposes a unified tool registry. AI agents discover available tools via a standard
        manifest and invoke them using whichever protocol their framework supports.
      </Paragraph>

      <Callout type="info">
        Compatible with LangChain, AutoGPT, CrewAI, and any framework that supports function/tool calling.
      </Callout>
    </>
  )
}

function MCPDocToolsContent() {
  return (
    <>
      <PageTitle>Document Tools</PageTitle>
      <PageDesc>MCP tools available to GROOT and external AI agents for document operations.</PageDesc>

      <SectionHeading>Available tools</SectionHeading>
      <Endpoint method="TOOL" path="search_documents" desc="Search knowledge base with natural language + tag filtering" />
      <Endpoint method="TOOL" path="compare_documents" desc="Compare two documents by similarity and structure" />
      <Endpoint method="TOOL" path="get_document_tags" desc="Get auto-generated semantic tags for a document" />

      <Callout type="tip">
        These tools are auto-discovered by AI agents via the MCP manifest. No manual integration required.
      </Callout>
    </>
  )
}

function ASBrowseContent() {
  return (
    <>
      <PageTitle>Browse & Install</PageTitle>
      <PageDesc>Discover community applications in the REFINET App Store.</PageDesc>

      <Paragraph>
        The App Store provides a curated marketplace of applications built on REFINET Cloud.
        Browse by category, search by name, and install with one click.
      </Paragraph>

      <SectionHeading>Features</SectionHeading>
      <ul className="docs-list">
        <li>Category-based browsing with search</li>
        <li>One-click install with automatic configuration</li>
        <li>Ratings and reviews from the community</li>
        <li>Sandbox-tested for security before listing</li>
      </ul>
    </>
  )
}

function ASSubmitContent() {
  return (
    <>
      <PageTitle>Submit an App</PageTitle>
      <PageDesc>Publish your application to the REFINET App Store.</PageDesc>

      <SectionHeading>Submission pipeline</SectionHeading>
      <Paragraph>
        Apps go through an Apple/Google-style review pipeline:
      </Paragraph>
      <ol className="docs-list">
        <li>Submit your app with metadata, screenshots, and source</li>
        <li>Automated sandbox testing validates functionality</li>
        <li>Admin review for security, quality, and compliance</li>
        <li>Approved apps appear in the public store</li>
      </ol>

      <SectionHeading>Requirements</SectionHeading>
      <ul className="docs-list">
        <li>Valid REFINET agent manifest (<InlineCode>refinet-agent.standard.yaml</InlineCode>)</li>
        <li>At least one screenshot or demo</li>
        <li>Description, category, and version info</li>
        <li>Must pass sandbox execution without errors</li>
      </ul>
    </>
  )
}

function ASReviewContent() {
  return (
    <>
      <PageTitle>Review Pipeline</PageTitle>
      <PageDesc>How the admin review process works for submitted apps.</PageDesc>

      <SectionHeading>Review stages</SectionHeading>
      <ol className="docs-list">
        <li><strong>Submitted</strong> — App enters the review queue</li>
        <li><strong>Sandbox testing</strong> — Automated execution in an isolated environment</li>
        <li><strong>Admin review</strong> — Manual review for security, quality, and compliance</li>
        <li><strong>Approved / Rejected</strong> — Published to store or returned with feedback</li>
      </ol>

      <Callout type="info">
        Only platform admins can approve or reject submissions. Rejected apps include actionable feedback so you can resubmit.
      </Callout>
    </>
  )
}

function InteractiveContent() {
  return (
    <>
      <PageTitle>Interactive API Docs</PageTitle>
      <PageDesc>Try the API directly in your browser with auto-generated interactive documentation.</PageDesc>

      <div className="docs-navcard-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <a href={`${API_URL}/docs`} target="_blank" rel="noopener noreferrer" className="docs-navcard" style={{ textDecoration: 'none' }}>
          <div className="docs-navcard-title">Swagger UI</div>
          <div className="docs-navcard-desc">Interactive endpoint explorer with try-it-out functionality</div>
        </a>
        <a href={`${API_URL}/redoc`} target="_blank" rel="noopener noreferrer" className="docs-navcard" style={{ textDecoration: 'none' }}>
          <div className="docs-navcard-title">ReDoc</div>
          <div className="docs-navcard-desc">Clean, three-panel API reference documentation</div>
        </a>
      </div>

      <Callout type="tip">
        Both Swagger UI and ReDoc are auto-generated from the FastAPI backend. They stay in sync with the API automatically.
      </Callout>
    </>
  )
}
