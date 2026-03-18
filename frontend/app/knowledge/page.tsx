'use client'

import { useState, useEffect, useCallback, useRef, DragEvent, ChangeEvent } from 'react'
import { API_URL } from '@/lib/config'

/* ── Types ─────────────────────────────────────────────────────── */

interface KnowledgeDoc {
  id: string; title: string; category: string; chunk_count: number;
  content?: string; source_filename?: string; created_at: string;
  tags?: string[]; doc_type?: string; page_count?: number;
}

interface Contract {
  id: string; name: string; chain: string; address?: string;
  category: string; description: string;
}

interface SearchResult {
  chunk_id: string; document_id: string; document_title: string;
  category: string; content: string; score: number;
  tags?: string[]; doc_type?: string;
}

interface CompareResult {
  doc_a: { id: string; title: string; category: string };
  doc_b: { id: string; title: string; category: string };
  semantic_similarity: number;
  keyword_overlap: { score: number; shared_keywords: string[]; unique_to_a: string[]; unique_to_b: string[] };
  structural_diff: { length_a: number; length_b: number; chunk_count_a: number; chunk_count_b: number };
  tag_overlap: { score: number; shared_tags: string[]; unique_to_a: string[]; unique_to_b: string[] };
}

/* ── Constants ─────────────────────────────────────────────────── */

const CATEGORY_COLORS: Record<string, string> = {
  about: 'var(--refi-teal)', product: '#60A5FA', docs: '#A78BFA',
  blockchain: '#F97316', contract: '#FBBF24', faq: '#4ADE80',
}

const DOCTYPE_LABELS: Record<string, string> = {
  pdf: 'PDF', docx: 'DOCX', xlsx: 'XLSX', csv: 'CSV',
  txt: 'TXT', md: 'MD', json: 'JSON', sol: 'SOL',
}

const SUPPORTED_EXTS = ['.pdf', '.docx', '.xlsx', '.csv', '.txt', '.md', '.json', '.sol']

const CHAIN_ICONS: Record<string, string> = {
  ethereum: '◆', base: '🔵', arbitrum: '🔶', polygon: '🟣',
}

/* ── Component ─────────────────────────────────────────────────── */

export default function KnowledgePage() {
  const [token, setToken] = useState('')
  const [tab, setTab] = useState<'documents' | 'contracts' | 'upload' | 'compare'>('documents')
  const [docs, setDocs] = useState<KnowledgeDoc[]>([])
  const [contracts, setContracts] = useState<Contract[]>([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  // Upload state
  const [isUploading, setIsUploading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploadCategory, setUploadCategory] = useState('')
  const [uploadContent, setUploadContent] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dropZoneRef = useRef<HTMLDivElement>(null)

  // Document list
  const [searchFilter, setSearchFilter] = useState('')
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null)
  const [editingDocId, setEditingDocId] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')
  const [editTitle, setEditTitle] = useState('')
  const [retaggingId, setRetaggingId] = useState<string | null>(null)

  // Contracts
  const [contractName, setContractName] = useState('')
  const [contractChain, setContractChain] = useState('ethereum')
  const [contractAddress, setContractAddress] = useState('')
  const [contractDesc, setContractDesc] = useState('')
  const [contractLogic, setContractLogic] = useState('')

  // Search
  const [showTestSearch, setShowTestSearch] = useState(false)
  const [testSearchQuery, setTestSearchQuery] = useState('')
  const [searchTags, setSearchTags] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)

  // Compare
  const [compareA, setCompareA] = useState('')
  const [compareB, setCompareB] = useState('')
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null)
  const [isComparing, setIsComparing] = useState(false)

  useEffect(() => {
    setToken(localStorage.getItem('refinet_token') || '')
  }, [])

  const headers: Record<string, string> = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }

  /* ── Data Loading ──────────────────────────────────────────────── */

  const loadDocs = async () => {
    try {
      const r = await fetch(`${API_URL}/knowledge/documents`, { headers })
      if (r.ok) setDocs(await r.json())
      else setError(`Failed to load documents (${r.status})`)
    } catch { setError('Connection error') }
  }

  const loadContracts = async () => {
    try {
      const r = await fetch(`${API_URL}/knowledge/contracts`, { headers })
      if (r.ok) setContracts(await r.json())
    } catch {}
  }

  useEffect(() => {
    if (!token) return
    loadDocs()
    loadContracts()
  }, [token])

  /* ── File Upload (multipart) ───────────────────────────────────── */

  const handleFileSelect = (file: File) => {
    const ext = '.' + (file.name.split('.').pop()?.toLowerCase() || '')
    if (!SUPPORTED_EXTS.includes(ext)) {
      setError(`Unsupported file type: ${ext}. Supported: ${SUPPORTED_EXTS.join(', ')}`)
      return
    }
    setUploadFile(file)
    if (!uploadTitle) {
      setUploadTitle(file.name.replace(/\.\w+$/, '').replace(/[-_]/g, ' '))
    }
    setUploadContent('')
    setError('')
  }

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(false)
    const files = e.dataTransfer.files
    if (files.length > 0) handleFileSelect(files[0])
  }, [uploadTitle])

  const handleBrowse = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) handleFileSelect(files[0])
  }

  const doUpload = async () => {
    if (!uploadFile && !uploadContent) return
    setIsUploading(true); setError(''); setMsg('')
    try {
      let result: any
      if (uploadFile) {
        // Multipart file upload — backend auto-parses, auto-tags, auto-categorizes
        const form = new FormData()
        form.append('file', uploadFile)
        if (uploadTitle) form.append('title', uploadTitle)
        if (uploadCategory) form.append('category', uploadCategory)
        const h: Record<string, string> = { Authorization: `Bearer ${token}` }
        const r = await fetch(`${API_URL}/knowledge/documents/upload`, {
          method: 'POST', headers: h, body: form,
        })
        if (!r.ok) {
          const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
          throw new Error(err.detail || 'Upload failed')
        }
        result = await r.json()
      } else {
        // Text-only upload (manual paste)
        const r = await fetch(`${API_URL}/knowledge/documents`, {
          method: 'POST', headers,
          body: JSON.stringify({
            title: uploadTitle, content: uploadContent,
            category: uploadCategory || 'docs',
          }),
        })
        if (!r.ok) {
          const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
          throw new Error(err.detail || 'Upload failed')
        }
        result = await r.json()
      }
      const tags = result.tags?.length ? ` · Tags: ${result.tags.slice(0, 5).join(', ')}` : ''
      setMsg(`Ingested "${result.title}" → ${result.chunk_count} chunks · ${result.category}${tags}`)
      setUploadFile(null); setUploadTitle(''); setUploadCategory(''); setUploadContent('')
      setTab('documents')
      loadDocs()
    } catch (e: any) {
      setError(e.message || 'Upload failed')
    } finally { setIsUploading(false) }
  }

  /* ── Document Operations ───────────────────────────────────────── */

  const deleteDoc = async (id: string) => {
    if (!confirm('Remove this document from Groot\'s knowledge base?')) return
    await fetch(`${API_URL}/knowledge/documents/${id}`, { method: 'DELETE', headers })
    loadDocs()
  }

  const startEdit = (doc: KnowledgeDoc) => {
    setEditingDocId(doc.id); setEditTitle(doc.title); setEditContent(doc.content || '')
  }

  const saveEdit = async (oldDoc: KnowledgeDoc) => {
    await fetch(`${API_URL}/knowledge/documents/${oldDoc.id}`, { method: 'DELETE', headers })
    const resp = await fetch(`${API_URL}/knowledge/documents`, {
      method: 'POST', headers,
      body: JSON.stringify({ title: editTitle, category: oldDoc.category, content: editContent }),
    })
    if (resp.ok) { setEditingDocId(null); setEditContent(''); setEditTitle(''); loadDocs() }
  }

  const retagDoc = async (doc: KnowledgeDoc) => {
    setRetaggingId(doc.id)
    try {
      const r = await fetch(`${API_URL}/knowledge/documents/${doc.id}/retag`, {
        method: 'POST', headers,
      })
      if (r.ok) {
        const result = await r.json()
        setMsg(`Re-tagged "${result.title}" → ${result.tags?.length || 0} tags · ${result.category}`)
        loadDocs()
      }
    } catch {}
    finally { setRetaggingId(null) }
  }

  /* ── Contract Operations ───────────────────────────────────────── */

  const addContract = async () => {
    if (!contractName || !contractDesc) return
    try {
      const r = await fetch(`${API_URL}/knowledge/contracts`, {
        method: 'POST', headers,
        body: JSON.stringify({
          name: contractName, chain: contractChain,
          address: contractAddress || undefined,
          description: contractDesc, logic_summary: contractLogic || undefined,
        }),
      })
      if (r.ok) {
        setContractName(''); setContractAddress(''); setContractDesc(''); setContractLogic('')
        loadContracts()
      }
    } catch {}
  }

  /* ── Search ────────────────────────────────────────────────────── */

  const runTestSearch = async () => {
    if (!testSearchQuery.trim()) return
    setIsSearching(true); setSearchResults([])
    try {
      const params = new URLSearchParams({ q: testSearchQuery })
      if (searchTags.trim()) params.set('tags', searchTags.trim())
      const r = await fetch(`${API_URL}/knowledge/search?${params}`, { headers })
      if (r.ok) {
        const data = await r.json()
        setSearchResults(Array.isArray(data) ? data : data.results || [])
      }
    } catch { setError('Search failed') }
    finally { setIsSearching(false) }
  }

  /* ── Compare ───────────────────────────────────────────────────── */

  const runCompare = async () => {
    if (!compareA || !compareB || compareA === compareB) return
    setIsComparing(true); setCompareResult(null)
    try {
      const r = await fetch(`${API_URL}/knowledge/documents/compare`, {
        method: 'POST', headers,
        body: JSON.stringify({ doc_id_a: compareA, doc_id_b: compareB }),
      })
      if (r.ok) setCompareResult(await r.json())
      else setError('Compare failed')
    } catch { setError('Compare failed') }
    finally { setIsComparing(false) }
  }

  /* ── Filtered Docs ─────────────────────────────────────────────── */

  const filteredDocs = docs.filter(d =>
    d.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
    (d.tags || []).some(t => t.includes(searchFilter.toLowerCase())) ||
    (d.doc_type || '').includes(searchFilter.toLowerCase())
  )

  /* ── Render ────────────────────────────────────────────────────── */

  if (!token) {
    return (
      <div style={{ maxWidth: 640, margin: '0 auto', padding: '80px 24px', textAlign: 'center' }}>
        <h1 style={{ letterSpacing: '-0.02em', fontSize: 28, fontWeight: 700, marginBottom: 16, color: 'var(--text-primary)' }}>
          Knowledge Base
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
          Sign in with admin access to manage Groot&apos;s knowledge.
        </p>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '40px 24px', color: 'var(--text-primary)' }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ letterSpacing: '-0.02em', fontSize: 28, fontWeight: 700 }}>Knowledge Base</h1>
        <p style={{ fontSize: 13, marginTop: 4, color: 'var(--text-secondary)' }}>
          Manage what Groot knows. Upload any document (PDF, DOCX, XLSX, CSV, Solidity, JSON), auto-tag for LLM search, compare documents.
        </p>
      </div>

      {/* Banners */}
      {error && (
        <div style={{ marginBottom: 24, padding: '12px 16px', borderRadius: 12, fontSize: 13, background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', color: '#F87171', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{error}</span>
          <button onClick={() => setError('')} style={{ background: 'none', border: 'none', color: '#F87171', cursor: 'pointer', fontSize: 16, padding: '0 4px' }}>&times;</button>
        </div>
      )}
      {msg && (
        <div style={{ marginBottom: 24, padding: '12px 16px', borderRadius: 12, fontSize: 13, background: 'rgba(92,224,210,0.1)', border: '1px solid rgba(92,224,210,0.3)', color: 'var(--refi-teal)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{msg}</span>
          <button onClick={() => setMsg('')} style={{ background: 'none', border: 'none', color: 'var(--refi-teal)', cursor: 'pointer', fontSize: 16, padding: '0 4px' }}>&times;</button>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 32, borderBottom: '1px solid var(--border-subtle)' }}>
        {(['documents', 'upload', 'contracts', 'compare'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '10px 16px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace",
            letterSpacing: '0.05em', textTransform: 'uppercase', background: 'none', border: 'none',
            cursor: 'pointer', transition: 'color 0.2s', marginBottom: -1,
            color: tab === t ? 'var(--refi-teal)' : 'var(--text-secondary)',
            borderBottom: tab === t ? '2px solid var(--refi-teal)' : '2px solid transparent',
          }}>
            {t === 'upload' ? '+ UPLOAD' : t === 'compare' ? '⇄ COMPARE' : t.toUpperCase()}
          </button>
        ))}
      </div>

      {/* ═══ DOCUMENTS TAB ═══ */}
      {tab === 'documents' && (
        <div>
          {/* Search + filter */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <input type="text" value={searchFilter} onChange={e => setSearchFilter(e.target.value)}
              placeholder="Search by title, tag, or type..."
              style={{ flex: 1, fontSize: 13, padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)' }} />
            <button onClick={() => setShowTestSearch(!showTestSearch)}
              style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", background: showTestSearch ? 'var(--bg-tertiary)' : 'transparent', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-secondary)', cursor: 'pointer' }}>
              {showTestSearch ? 'CLOSE SEARCH' : 'RAG SEARCH'}
            </button>
          </div>

          {/* Test RAG Search panel */}
          {showTestSearch && (
            <div style={{ marginBottom: 20, padding: 16, background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 14 }}>
              <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 10 }}>
                Query the knowledge base to see what Groot retrieves. Supports tag filtering.
              </p>
              <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                <input value={testSearchQuery} onChange={e => setTestSearchQuery(e.target.value)}
                  placeholder="e.g. What is REFINET?"
                  style={{ flex: 1, fontSize: 13, padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)' }}
                  onKeyDown={e => e.key === 'Enter' && runTestSearch()} />
                <button onClick={runTestSearch}
                  style={{ padding: '10px 16px', fontSize: 12, whiteSpace: 'nowrap', background: 'var(--refi-teal)', color: 'var(--text-inverse)', border: 'none', borderRadius: 10, cursor: 'pointer', opacity: isSearching ? 0.6 : 1 }}
                  disabled={isSearching}>
                  {isSearching ? 'Searching...' : 'Search'}
                </button>
              </div>
              <input value={searchTags} onChange={e => setSearchTags(e.target.value)}
                placeholder="Filter by tags (comma-separated, e.g. defi, staking)"
                style={{ width: '100%', fontSize: 12, padding: '8px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 8, color: 'var(--text-secondary)', boxSizing: 'border-box', marginBottom: 12 }} />
              {searchResults.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {searchResults.map((r, i) => (
                    <div key={r.chunk_id || i} style={{ padding: 12, background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                            {r.document_title}
                          </span>
                          {r.doc_type && <DocTypeBadge type={r.doc_type} />}
                          <CategoryBadge cat={r.category} />
                        </div>
                        <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", color: 'var(--refi-teal)' }}>
                          score: {r.score.toFixed(3)}
                        </span>
                      </div>
                      {r.tags && r.tags.length > 0 && (
                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
                          {r.tags.slice(0, 6).map(tag => <TagBadge key={tag} tag={tag} />)}
                        </div>
                      )}
                      <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {r.content.substring(0, 300)}{r.content.length > 300 ? '...' : ''}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Document List */}
          {filteredDocs.length === 0 && docs.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 14 }}>
              <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>No documents yet.</p>
              <button onClick={() => setTab('upload')} style={{ marginTop: 16, padding: '10px 20px', fontSize: 13, background: 'var(--refi-teal)', color: 'var(--text-inverse)', border: 'none', borderRadius: 10, cursor: 'pointer' }}>
                Upload First Document
              </button>
            </div>
          ) : filteredDocs.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
              No documents match &quot;{searchFilter}&quot;
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {filteredDocs.map((d) => {
                const isExpanded = expandedDocId === d.id
                return (
                  <div key={d.id} style={{ padding: '16px 20px', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 14, cursor: 'pointer', transition: 'border-color 0.2s' }}
                    onClick={() => setExpandedDocId(isExpanded ? null : d.id)}>
                    {/* Title row */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>{d.title}</span>
                          <CategoryBadge cat={d.category} />
                          {d.doc_type && <DocTypeBadge type={d.doc_type} />}
                          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s', display: 'inline-block' }}>▼</span>
                        </div>
                        <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: 0 }}>
                          {d.chunk_count} chunks
                          {d.page_count ? ` · ${d.page_count} pages` : ''}
                          {' · '}{d.source_filename || 'manual upload'}
                          {' · '}{new Date(d.created_at).toLocaleDateString()}
                        </p>
                        {/* Tags row */}
                        {d.tags && d.tags.length > 0 && (
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 6 }}>
                            {d.tags.slice(0, 8).map(tag => <TagBadge key={tag} tag={tag} />)}
                            {d.tags.length > 8 && <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>+{d.tags.length - 8} more</span>}
                          </div>
                        )}
                      </div>
                      {/* Actions */}
                      <div style={{ display: 'flex', gap: 6, flexShrink: 0, marginLeft: 12 }}>
                        <SmallBtn label={retaggingId === d.id ? '...' : 'Re-tag'} color="var(--refi-teal)"
                          onClick={(e) => { e.stopPropagation(); retagDoc(d) }} />
                        <SmallBtn label="Edit" color="var(--refi-teal)"
                          onClick={(e) => { e.stopPropagation(); startEdit(d) }} />
                        <SmallBtn label="Remove" color="#F87171"
                          onClick={(e) => { e.stopPropagation(); deleteDoc(d.id) }} />
                      </div>
                    </div>
                    {/* Edit form */}
                    {editingDocId === d.id && (
                      <div style={{ marginTop: 12 }} onClick={e => e.stopPropagation()}>
                        <input value={editTitle} onChange={e => setEditTitle(e.target.value)}
                          style={{ width: '100%', fontSize: 13, padding: '8px 12px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 8, color: 'var(--text-primary)', marginBottom: 8, boxSizing: 'border-box' }} />
                        <textarea rows={8} value={editContent} onChange={e => setEditContent(e.target.value)}
                          style={{ width: '100%', fontSize: 12, fontFamily: "'JetBrains Mono', monospace", padding: '8px 12px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 8, color: 'var(--text-primary)', lineHeight: 1.6, resize: 'none', marginBottom: 8, boxSizing: 'border-box' }} />
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button onClick={() => saveEdit(d)} style={{ padding: '6px 14px', fontSize: 12, background: 'var(--refi-teal)', color: 'var(--text-inverse)', border: 'none', borderRadius: 8, cursor: 'pointer' }}>Save</button>
                          <button onClick={() => setEditingDocId(null)} style={{ padding: '6px 14px', fontSize: 12, background: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', borderRadius: 8, cursor: 'pointer' }}>Cancel</button>
                        </div>
                      </div>
                    )}
                    {/* Expanded preview */}
                    {isExpanded && editingDocId !== d.id && (
                      <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {d.content
                          ? d.content.substring(0, 400) + (d.content.length > 400 ? '...' : '')
                          : 'No preview available.'}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ═══ UPLOAD TAB ═══ */}
      {tab === 'upload' && (
        <div style={{ padding: 24, background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 14 }}>
          <div style={{ marginBottom: 20 }}>
            <h3 style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>Upload Document</h3>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0 }}>
              Upload any file — PDF, DOCX, XLSX, CSV, TXT, Markdown, JSON, Solidity. Auto-parsed, auto-tagged, auto-categorized.
            </p>
          </div>

          {/* Drop zone */}
          <div ref={dropZoneRef} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
            style={{
              padding: '28px 20px', borderRadius: 12, textAlign: 'center', transition: 'all 0.2s', marginBottom: 16, cursor: 'pointer',
              border: isDragging ? '2px dashed var(--refi-teal)' : '2px dashed var(--border-default)',
              background: isDragging ? 'var(--refi-teal-glow)' : 'var(--bg-input)',
            }}
            onClick={() => fileInputRef.current?.click()}>
            <input ref={fileInputRef} type="file" style={{ display: 'none' }}
              accept={SUPPORTED_EXTS.join(',')} onChange={handleBrowse} />
            {uploadFile ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                <span style={{ fontSize: 20 }}>📄</span>
                <span style={{ fontSize: 13, fontFamily: "'JetBrains Mono', monospace", color: 'var(--refi-teal)' }}>
                  {uploadFile.name}
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                  ({(uploadFile.size / 1024).toFixed(0)} KB)
                </span>
                <button onClick={(e) => { e.stopPropagation(); setUploadFile(null); setUploadTitle('') }}
                  style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 14, padding: '2px 6px' }}>
                  &times;
                </button>
              </div>
            ) : (
              <div>
                <p style={{ fontSize: 24, marginBottom: 8 }}>{isDragging ? '📥' : '📁'}</p>
                <p style={{ fontSize: 13, color: isDragging ? 'var(--refi-teal)' : 'var(--text-secondary)', margin: '0 0 4px 0' }}>
                  {isDragging ? 'Drop file here' : 'Drag & drop or click to browse'}
                </p>
                <p style={{ fontSize: 11, color: 'var(--text-tertiary)', margin: 0 }}>
                  PDF, DOCX, XLSX, CSV, TXT, MD, JSON, SOL — max 50MB
                </p>
              </div>
            )}
          </div>

          {/* Title */}
          <input value={uploadTitle} onChange={e => setUploadTitle(e.target.value)}
            placeholder="Document title (optional — auto-generated from filename)"
            style={{ width: '100%', fontSize: 13, padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)', marginBottom: 12, boxSizing: 'border-box' }} />

          {/* Category */}
          <select value={uploadCategory} onChange={e => setUploadCategory(e.target.value)}
            style={{ width: '100%', fontSize: 13, padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)', marginBottom: 12, boxSizing: 'border-box' }}>
            <option value="">Auto-detect category</option>
            <option value="about">About REFINET</option>
            <option value="product">Product Documentation</option>
            <option value="docs">Technical Docs</option>
            <option value="blockchain">Blockchain / DLT</option>
            <option value="contract">Smart Contracts</option>
            <option value="faq">FAQ</option>
          </select>

          {/* Manual text fallback (only shown when no file selected) */}
          {!uploadFile && (
            <textarea value={uploadContent} onChange={e => setUploadContent(e.target.value)}
              placeholder="Or paste text content here..."
              rows={10}
              style={{ width: '100%', fontSize: 13, fontFamily: "'JetBrains Mono', monospace", padding: '12px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)', resize: 'none', lineHeight: 1.6, marginBottom: 16, boxSizing: 'border-box' }} />
          )}

          {/* Upload progress */}
          {isUploading && (
            <div style={{ marginBottom: 12, height: 4, borderRadius: 2, background: 'var(--border-subtle)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: '70%', borderRadius: 2, background: 'var(--refi-teal)', animation: 'upload-progress 1.5s ease-in-out infinite' }} />
              <style>{`@keyframes upload-progress { 0% { width: 20%; margin-left: 0; } 50% { width: 60%; margin-left: 20%; } 100% { width: 20%; margin-left: 80%; } }`}</style>
            </div>
          )}

          {/* Footer */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: uploadFile ? 16 : 0 }}>
            <span style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>
              {uploadFile ? `File: ${uploadFile.name} (${(uploadFile.size / 1024).toFixed(0)} KB)` :
                uploadContent ? `~${Math.ceil(uploadContent.length / 4)} tokens · ~${Math.ceil(uploadContent.length / 1600)} chunks` :
                  'No content yet'}
            </span>
            <button onClick={doUpload}
              style={{
                padding: '10px 20px', fontSize: 13, background: 'var(--refi-teal)', color: 'var(--text-inverse)',
                border: 'none', borderRadius: 10, cursor: (!uploadFile && !uploadContent) || isUploading ? 'not-allowed' : 'pointer',
                opacity: (!uploadFile && !uploadContent) || isUploading ? 0.5 : 1,
              }}
              disabled={(!uploadFile && !uploadContent) || isUploading}>
              {isUploading ? 'Processing...' : 'Upload & Process'}
            </button>
          </div>
        </div>
      )}

      {/* ═══ CONTRACTS TAB ═══ */}
      {tab === 'contracts' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Add contract form */}
          <div style={{ padding: 20, background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 14 }}>
            <h3 style={{ fontWeight: 600, fontSize: 14, marginBottom: 16 }}>Add Contract (CAG)</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
              <input value={contractName} onChange={e => setContractName(e.target.value)} placeholder="Contract name"
                style={{ fontSize: 13, padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)' }} />
              <select value={contractChain} onChange={e => setContractChain(e.target.value)}
                style={{ fontSize: 13, padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)' }}>
                <option value="ethereum">◆ Ethereum</option><option value="base">🔵 Base</option>
                <option value="arbitrum">🔶 Arbitrum</option><option value="polygon">🟣 Polygon</option>
              </select>
            </div>
            <input value={contractAddress} onChange={e => setContractAddress(e.target.value)} placeholder="Contract address (optional)"
              style={{ width: '100%', fontSize: 13, fontFamily: "'JetBrains Mono', monospace", padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)', marginBottom: 12, boxSizing: 'border-box' }} />
            <textarea value={contractDesc} onChange={e => setContractDesc(e.target.value)} placeholder="What does this contract do?" rows={3}
              style={{ width: '100%', fontSize: 13, padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)', resize: 'none', marginBottom: 12, boxSizing: 'border-box' }} />
            <textarea value={contractLogic} onChange={e => setContractLogic(e.target.value)} placeholder="Logic summary for Groot (optional)" rows={2}
              style={{ width: '100%', fontSize: 13, padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)', resize: 'none', marginBottom: 16, boxSizing: 'border-box' }} />
            <button onClick={addContract}
              style={{ padding: '10px 20px', fontSize: 13, background: 'var(--refi-teal)', color: 'var(--text-inverse)', border: 'none', borderRadius: 10, cursor: (!contractName || !contractDesc) ? 'not-allowed' : 'pointer', opacity: (!contractName || !contractDesc) ? 0.5 : 1 }}
              disabled={!contractName || !contractDesc}>
              Add Contract
            </button>
          </div>

          {/* Contract list */}
          {contracts.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <h3 style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>Registered Contracts</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {contracts.map(c => (
                  <div key={c.id} style={{ padding: 16, background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 14 }}>{CHAIN_ICONS[c.chain] || '⬡'}</span>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{c.name}</span>
                      <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", padding: '2px 8px', borderRadius: 999, background: 'var(--refi-teal-glow)', color: 'var(--refi-teal)' }}>{c.chain}</span>
                    </div>
                    {c.address && <p style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", margin: '0 0 4px 0', color: 'var(--text-tertiary)' }}>{c.address}</p>}
                    <p style={{ fontSize: 13, margin: 0, color: 'var(--text-secondary)' }}>{c.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ COMPARE TAB ═══ */}
      {tab === 'compare' && (
        <div style={{ padding: 24, background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 14 }}>
          <h3 style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>Compare Documents</h3>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 16px 0' }}>
            Compare two documents by semantic similarity, keyword overlap, and tag overlap.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <select value={compareA} onChange={e => setCompareA(e.target.value)}
              style={{ fontSize: 13, padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)' }}>
              <option value="">Select document A...</option>
              {docs.map(d => <option key={d.id} value={d.id}>{d.title}</option>)}
            </select>
            <select value={compareB} onChange={e => setCompareB(e.target.value)}
              style={{ fontSize: 13, padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 10, color: 'var(--text-primary)' }}>
              <option value="">Select document B...</option>
              {docs.map(d => <option key={d.id} value={d.id}>{d.title}</option>)}
            </select>
          </div>

          <button onClick={runCompare}
            style={{ padding: '10px 20px', fontSize: 13, background: 'var(--refi-teal)', color: 'var(--text-inverse)', border: 'none', borderRadius: 10, cursor: (!compareA || !compareB || compareA === compareB) ? 'not-allowed' : 'pointer', opacity: (!compareA || !compareB || compareA === compareB || isComparing) ? 0.5 : 1, marginBottom: 20 }}
            disabled={!compareA || !compareB || compareA === compareB || isComparing}>
            {isComparing ? 'Comparing...' : 'Compare'}
          </button>

          {/* Results */}
          {compareResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Score cards */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                <ScoreCard label="Semantic Similarity" score={compareResult.semantic_similarity} />
                <ScoreCard label="Keyword Overlap" score={compareResult.keyword_overlap.score} />
                <ScoreCard label="Tag Overlap" score={compareResult.tag_overlap.score} />
              </div>

              {/* Details */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {/* Shared keywords */}
                <div style={{ padding: 12, background: 'var(--bg-input)', borderRadius: 10, border: '1px solid var(--border-subtle)' }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>SHARED KEYWORDS</p>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {compareResult.keyword_overlap.shared_keywords.slice(0, 12).map(k =>
                      <TagBadge key={k} tag={k} />
                    )}
                    {compareResult.keyword_overlap.shared_keywords.length === 0 &&
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>None</span>}
                  </div>
                </div>
                {/* Shared tags */}
                <div style={{ padding: 12, background: 'var(--bg-input)', borderRadius: 10, border: '1px solid var(--border-subtle)' }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>SHARED TAGS</p>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {compareResult.tag_overlap.shared_tags.map(t =>
                      <TagBadge key={t} tag={t} />
                    )}
                    {compareResult.tag_overlap.shared_tags.length === 0 &&
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>None</span>}
                  </div>
                </div>
              </div>

              {/* Structure comparison */}
              <div style={{ padding: 12, background: 'var(--bg-input)', borderRadius: 10, border: '1px solid var(--border-subtle)' }}>
                <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>STRUCTURE</p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
                  <div>
                    <span style={{ color: 'var(--text-tertiary)' }}>Doc A:</span>{' '}
                    <span style={{ color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace" }}>
                      {(compareResult.structural_diff.length_a / 1000).toFixed(1)}K chars · {compareResult.structural_diff.chunk_count_a} chunks
                    </span>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-tertiary)' }}>Doc B:</span>{' '}
                    <span style={{ color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace" }}>
                      {(compareResult.structural_diff.length_b / 1000).toFixed(1)}K chars · {compareResult.structural_diff.chunk_count_b} chunks
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ── Micro-components ──────────────────────────────────────────── */

function CategoryBadge({ cat }: { cat: string }) {
  const color = CATEGORY_COLORS[cat] || 'var(--refi-teal)'
  return (
    <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", padding: '2px 8px', borderRadius: 999, background: `${color}18`, color, border: `1px solid ${color}30` }}>
      {cat}
    </span>
  )
}

function DocTypeBadge({ type }: { type: string }) {
  return (
    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '2px 6px', borderRadius: 4, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      {DOCTYPE_LABELS[type] || type}
    </span>
  )
}

function TagBadge({ tag }: { tag: string }) {
  return (
    <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(92,224,210,0.08)', color: 'var(--refi-teal)', border: '1px solid rgba(92,224,210,0.15)' }}>
      {tag}
    </span>
  )
}

function SmallBtn({ label, color, onClick }: { label: string; color: string; onClick: (e: React.MouseEvent) => void }) {
  return (
    <button onClick={onClick}
      style={{ fontSize: 12, padding: '6px 12px', borderRadius: 8, color, border: '1px solid var(--border-default)', background: 'transparent', cursor: 'pointer', whiteSpace: 'nowrap' }}>
      {label}
    </button>
  )
}

function ScoreCard({ label, score }: { label: string; score: number }) {
  const pct = Math.round(score * 100)
  const color = pct > 70 ? '#4ADE80' : pct > 40 ? '#FBBF24' : '#F87171'
  return (
    <div style={{ padding: 16, background: 'var(--bg-input)', borderRadius: 10, border: '1px solid var(--border-subtle)', textAlign: 'center' }}>
      <div style={{ fontSize: 28, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color, marginBottom: 4 }}>
        {pct}%
      </div>
      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>
        {label}
      </div>
    </div>
  )
}
