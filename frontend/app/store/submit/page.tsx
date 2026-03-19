'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

const CATEGORIES = ['dapp', 'agent', 'tool', 'template', 'dataset', 'api-service', 'digital-asset']
const PRICE_TYPES = ['free', 'one-time', 'subscription']
const LICENSE_TYPES = ['open', 'single-use', 'multi-use', 'enterprise']

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  draft: { bg: 'rgba(148,163,184,0.15)', text: '#94a3b8' },
  submitted: { bg: 'rgba(96,165,250,0.15)', text: '#60a5fa' },
  automated_review: { bg: 'rgba(251,191,36,0.15)', text: '#fbbf24' },
  in_review: { bg: 'rgba(168,85,247,0.15)', text: '#a855f7' },
  changes_requested: { bg: 'rgba(251,146,60,0.15)', text: '#fb923c' },
  approved: { bg: 'rgba(74,222,128,0.15)', text: '#4ade80' },
  rejected: { bg: 'rgba(248,113,113,0.15)', text: '#f87171' },
  published: { bg: 'rgba(74,222,128,0.15)', text: '#4ade80' },
}

export default function SubmitPage() {
  const [token, setToken] = useState('')
  const [tab, setTab] = useState<'new' | 'my'>('new')
  const [submissions, setSubmissions] = useState<any[]>([])
  const [selectedSub, setSelectedSub] = useState<any>(null)
  const [msg, setMsg] = useState('')

  // New submission form
  const [form, setForm] = useState({
    name: '', description: '', category: 'dapp', chain: '', version: '1.0.0',
    readme: '', icon_url: '', price_type: 'free', price_amount: '0',
    price_token: '', license_type: 'open', external_url: '', tags: '',
  })
  const [artifactFile, setArtifactFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setToken(localStorage.getItem('refinet_token') || '')
  }, [])

  const headers: Record<string, string> = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }

  const loadSubmissions = async () => {
    if (!token) return
    try {
      const resp = await fetch(`${API_URL}/apps/submissions`, { headers })
      if (resp.ok) {
        const data = await resp.json()
        setSubmissions(data.submissions || [])
      }
    } catch {}
  }

  const loadDetail = async (id: string) => {
    if (!token) return
    try {
      const resp = await fetch(`${API_URL}/apps/submissions/${id}`, { headers })
      if (resp.ok) setSelectedSub(await resp.json())
    } catch {}
  }

  useEffect(() => {
    if (token && tab === 'my') loadSubmissions()
  }, [token, tab])

  const handleCreate = async () => {
    setSubmitting(true)
    setMsg('')
    const body: any = {
      name: form.name, description: form.description, category: form.category,
      version: form.version, price_type: form.price_type,
      price_amount: parseFloat(form.price_amount) || 0, license_type: form.license_type,
    }
    if (form.chain) body.chain = form.chain
    if (form.readme) body.readme = form.readme
    if (form.icon_url) body.icon_url = form.icon_url
    if (form.price_token) body.price_token = form.price_token
    if (form.external_url) body.external_url = form.external_url
    if (form.tags) body.tags = form.tags.split(',').map((t: string) => t.trim()).filter(Boolean)

    try {
      // 1. Create submission
      const resp = await fetch(`${API_URL}/apps/submissions`, {
        method: 'POST', headers, body: JSON.stringify(body),
      })
      const data = await resp.json()
      if (!resp.ok) { setMsg(data.detail || 'Create failed'); setSubmitting(false); return }

      const subId = data.id

      // 2. Upload artifact if provided
      if (artifactFile) {
        const formData = new FormData()
        formData.append('file', artifactFile)
        const uploadResp = await fetch(`${API_URL}/apps/submissions/${subId}/artifact`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        })
        if (!uploadResp.ok) {
          const err = await uploadResp.json()
          setMsg(`Created but artifact upload failed: ${err.detail}`)
          setSubmitting(false)
          return
        }
      }

      // 3. Submit for review
      if (artifactFile) {
        const submitResp = await fetch(`${API_URL}/apps/submissions/${subId}/submit`, {
          method: 'POST', headers,
        })
        const submitData = await submitResp.json()
        setMsg(submitData.message || 'Submitted for review!')
      } else {
        setMsg('Draft created. Upload a ZIP artifact then submit for review.')
      }

      setForm({ name: '', description: '', category: 'dapp', chain: '', version: '1.0.0', readme: '', icon_url: '', price_type: 'free', price_amount: '0', price_token: '', license_type: 'open', external_url: '', tags: '' })
      setArtifactFile(null)
      if (fileRef.current) fileRef.current.value = ''
      setTab('my')
      loadSubmissions()
    } catch (e: any) {
      setMsg(e.message)
    }
    setSubmitting(false)
  }

  const handleWithdraw = async (id: string) => {
    const resp = await fetch(`${API_URL}/apps/submissions/${id}`, { method: 'DELETE', headers })
    if (resp.ok) { loadSubmissions(); setSelectedSub(null) }
  }

  const handleAddNote = async (id: string, content: string) => {
    await fetch(`${API_URL}/apps/submissions/${id}/notes`, {
      method: 'POST', headers, body: JSON.stringify({ content }),
    })
    loadDetail(id)
  }

  if (!token) {
    return (
      <div className="max-w-2xl mx-auto py-20 px-6 text-center">
        <h1 className="text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Submit to App Store</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Sign in to submit your app for review.</p>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto py-8 px-6">
      <div className="mb-6">
        <Link href="/store" className="text-xs" style={{ color: 'var(--text-tertiary)', textDecoration: 'none' }}>Store</Link>
        <span className="text-xs mx-1" style={{ color: 'var(--text-tertiary)' }}>/</span>
        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Submit</span>
      </div>

      <h1 className="text-2xl font-bold mb-2" style={{ letterSpacing: '-0.02em' }}>Submit to App Store</h1>
      <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
        Upload your code for review. Our team will test it in an isolated sandbox before approving.
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-6" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        {(['new', 'my'] as const).map(t => (
          <button key={t} onClick={() => { setTab(t); setSelectedSub(null) }}
            className="px-4 py-2 text-xs font-mono"
            style={{ color: tab === t ? 'var(--refi-teal)' : 'var(--text-tertiary)', borderBottom: tab === t ? '2px solid var(--refi-teal)' : '2px solid transparent' }}>
            {t === 'new' ? 'NEW SUBMISSION' : 'MY SUBMISSIONS'}
          </button>
        ))}
      </div>

      {msg && (
        <div className="mb-4 px-3 py-2 rounded text-xs" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>{msg}</div>
      )}

      {/* New Submission Form */}
      {tab === 'new' && (
        <div className="card p-5" style={{ border: '1px solid var(--border-default)' }}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>App Name *</label>
              <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                className="w-full px-2 py-1.5 text-sm rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }} />
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Category *</label>
              <select value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))}
                className="w-full px-2 py-1.5 text-sm rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Version</label>
              <input value={form.version} onChange={e => setForm(p => ({ ...p, version: e.target.value }))}
                className="w-full px-2 py-1.5 text-sm rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }} />
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Chain</label>
              <input value={form.chain} onChange={e => setForm(p => ({ ...p, chain: e.target.value }))} placeholder="ethereum, base, etc."
                className="w-full px-2 py-1.5 text-sm rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }} />
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Price Type</label>
              <select value={form.price_type} onChange={e => setForm(p => ({ ...p, price_type: e.target.value }))}
                className="w-full px-2 py-1.5 text-sm rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
                {PRICE_TYPES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Price (USD)</label>
              <input type="number" value={form.price_amount} onChange={e => setForm(p => ({ ...p, price_amount: e.target.value }))}
                className="w-full px-2 py-1.5 text-sm rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }} />
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Tags (comma-separated)</label>
              <input value={form.tags} onChange={e => setForm(p => ({ ...p, tags: e.target.value }))}
                className="w-full px-2 py-1.5 text-sm rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }} />
            </div>
            <div>
              <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>License</label>
              <select value={form.license_type} onChange={e => setForm(p => ({ ...p, license_type: e.target.value }))}
                className="w-full px-2 py-1.5 text-sm rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}>
                {LICENSE_TYPES.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          </div>

          <div className="mb-3">
            <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>Description</label>
            <textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} rows={2}
              className="w-full px-2 py-1.5 text-sm rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none', resize: 'vertical' }} />
          </div>

          <div className="mb-4">
            <label className="text-[10px] block mb-1" style={{ color: 'var(--text-tertiary)' }}>README (Markdown)</label>
            <textarea value={form.readme} onChange={e => setForm(p => ({ ...p, readme: e.target.value }))} rows={4}
              className="w-full px-2 py-1.5 text-sm rounded font-mono" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none', resize: 'vertical' }} />
          </div>

          {/* Artifact Upload */}
          <div className="mb-4 p-4 rounded-lg" style={{ border: '2px dashed var(--border-default)', background: 'var(--bg-secondary)' }}>
            <label className="text-xs block mb-2" style={{ color: 'var(--text-secondary)' }}>
              Upload Code Artifact (ZIP) *
            </label>
            <p className="text-[10px] mb-2" style={{ color: 'var(--text-tertiary)' }}>
              Upload a ZIP file containing your source code. It will be tested in an isolated sandbox.
            </p>
            <input ref={fileRef} type="file" accept=".zip" onChange={e => setArtifactFile(e.target.files?.[0] || null)}
              className="text-xs" style={{ color: 'var(--text-secondary)' }} />
            {artifactFile && (
              <p className="text-[10px] mt-1 font-mono" style={{ color: 'var(--refi-teal)' }}>
                {artifactFile.name} ({(artifactFile.size / 1024).toFixed(0)} KB)
              </p>
            )}
          </div>

          <button onClick={handleCreate} disabled={submitting || !form.name || !form.category}
            className="px-4 py-2 text-sm font-semibold rounded-lg"
            style={{
              background: (!form.name || submitting) ? 'var(--bg-tertiary)' : 'var(--refi-teal)',
              color: (!form.name || submitting) ? 'var(--text-tertiary)' : '#000',
              cursor: (!form.name || submitting) ? 'not-allowed' : 'pointer',
            }}>
            {submitting ? 'Submitting...' : artifactFile ? 'Submit for Review' : 'Save as Draft'}
          </button>
        </div>
      )}

      {/* My Submissions */}
      {tab === 'my' && !selectedSub && (
        <div>
          {submissions.length === 0 ? (
            <div className="text-center py-12" style={{ color: 'var(--text-tertiary)' }}>
              <p className="text-sm mb-2">No submissions yet.</p>
              <button onClick={() => setTab('new')} className="text-xs" style={{ color: 'var(--refi-teal)', background: 'none', border: 'none', cursor: 'pointer' }}>
                Create your first submission
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {submissions.map((s: any) => (
                <div key={s.id} className="card p-4 flex items-center justify-between cursor-pointer"
                  style={{ border: '1px solid var(--border-subtle)' }}
                  onClick={() => loadDetail(s.id)}
                  onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--refi-teal)')}
                  onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{s.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                        style={{ background: (STATUS_COLORS[s.status] || STATUS_COLORS.draft).bg, color: (STATUS_COLORS[s.status] || STATUS_COLORS.draft).text }}>
                        {s.status.replace(/_/g, ' ')}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>
                        {s.category}
                      </span>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                      v{s.version} · {s.submission_type} · {s.created_at ? new Date(s.created_at).toLocaleDateString() : ''}
                      {s.artifact_filename && <span> · {s.artifact_filename}</span>}
                    </p>
                  </div>
                  <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>View</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Submission Detail */}
      {tab === 'my' && selectedSub && (
        <div>
          <button onClick={() => setSelectedSub(null)} className="text-xs mb-4" style={{ color: 'var(--refi-teal)', background: 'none', border: 'none', cursor: 'pointer' }}>
            Back to list
          </button>

          <div className="card p-5 mb-4" style={{ border: '1px solid var(--border-default)' }}>
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{selectedSub.name}</h2>
              <span className="text-[10px] px-2 py-0.5 rounded font-mono"
                style={{ background: (STATUS_COLORS[selectedSub.status] || STATUS_COLORS.draft).bg, color: (STATUS_COLORS[selectedSub.status] || STATUS_COLORS.draft).text }}>
                {selectedSub.status.replace(/_/g, ' ')}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-4">
              {[
                ['Category', selectedSub.category],
                ['Version', selectedSub.version],
                ['Type', selectedSub.submission_type],
                ['Price', selectedSub.price_type === 'free' ? 'Free' : `$${selectedSub.price_amount}`],
              ].map(([k, v]) => (
                <div key={k as string}>
                  <span style={{ color: 'var(--text-tertiary)' }}>{k}: </span>
                  <span style={{ color: 'var(--text-primary)' }}>{v}</span>
                </div>
              ))}
            </div>

            {selectedSub.artifact_filename && (
              <div className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
                Artifact: <span className="font-mono" style={{ color: 'var(--refi-teal)' }}>{selectedSub.artifact_filename}</span>
                {selectedSub.artifact_size_bytes && <span> ({(selectedSub.artifact_size_bytes / 1024).toFixed(0)} KB)</span>}
                {selectedSub.artifact_hash && <span className="text-[9px] ml-2" style={{ color: 'var(--text-tertiary)' }}>SHA256: {selectedSub.artifact_hash.slice(0, 16)}...</span>}
              </div>
            )}

            {/* Automated Scan */}
            {selectedSub.automated_scan_result && (
              <div className="mb-3 p-3 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                <div className="text-xs font-mono mb-1" style={{ color: 'var(--text-tertiary)' }}>AUTOMATED SCAN</div>
                <span className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  style={{
                    background: selectedSub.automated_scan_status === 'passed' ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)',
                    color: selectedSub.automated_scan_status === 'passed' ? '#4ade80' : '#f87171',
                  }}>
                  {selectedSub.automated_scan_status}
                </span>
                <div className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
                  {selectedSub.automated_scan_result.file_count} files scanned ·
                  {selectedSub.automated_scan_result.critical_count} critical ·
                  {selectedSub.automated_scan_result.warning_count} warnings
                </div>
              </div>
            )}

            {selectedSub.rejection_reason && (
              <div className="p-3 rounded mb-3" style={{ background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.2)' }}>
                <div className="text-xs font-semibold mb-1" style={{ color: '#f87171' }}>Rejection Reason</div>
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{selectedSub.rejection_reason}</p>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 mt-3">
              {selectedSub.status === 'draft' && (
                <button onClick={() => { /* would navigate to upload flow */ }}
                  className="px-3 py-1.5 text-xs rounded" style={{ background: 'var(--refi-teal)', color: '#000', cursor: 'pointer' }}>
                  Upload Artifact & Submit
                </button>
              )}
              {['draft', 'submitted', 'changes_requested'].includes(selectedSub.status) && (
                <button onClick={() => handleWithdraw(selectedSub.id)}
                  className="px-3 py-1.5 text-xs rounded" style={{ background: 'rgba(248,113,113,0.15)', color: '#f87171', border: 'none', cursor: 'pointer' }}>
                  Withdraw
                </button>
              )}
            </div>
          </div>

          {/* Notes / Review Thread */}
          {selectedSub.notes && selectedSub.notes.length > 0 && (
            <div className="mb-4">
              <h3 className="text-xs font-mono font-semibold mb-2 uppercase" style={{ color: 'var(--text-tertiary)' }}>Review Thread</h3>
              <div className="space-y-2">
                {selectedSub.notes.map((n: any) => (
                  <div key={n.id} className="card p-3" style={{ border: '1px solid var(--border-subtle)', borderLeft: n.note_type === 'request_changes' ? '3px solid #fb923c' : n.note_type === 'rejection' ? '3px solid #f87171' : n.note_type === 'approval' ? '3px solid #4ade80' : '3px solid var(--border-subtle)' }}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{n.author_username || 'System'}</span>
                      <span className="text-[9px] px-1 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>{n.note_type}</span>
                      <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{n.created_at ? new Date(n.created_at).toLocaleString() : ''}</span>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{n.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
