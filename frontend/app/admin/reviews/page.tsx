'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

export default function AdminReviews() {
  const { headers } = useAdmin()
  const [reviewSubs, setReviewSubs] = useState<any[]>([])
  const [reviewStats, setReviewStats] = useState<any>(null)
  const [selectedReview, setSelectedReview] = useState<any>(null)
  const [reviewNote, setReviewNote] = useState('')
  const [reviewMsg, setReviewMsg] = useState('')
  const [loading, setLoading] = useState(true)

  const loadReviewSubs = async (statusFilter?: string) => {
    const params = statusFilter ? `?status=${statusFilter}` : '?page_size=50'
    const resp = await fetch(`${API_URL}/admin/submissions${params}`, { headers })
    if (resp.ok) { const data = await resp.json(); setReviewSubs(data.submissions || []) }
    setLoading(false)
  }
  const loadReviewStats = async () => {
    const resp = await fetch(`${API_URL}/admin/submissions/stats`, { headers })
    if (resp.ok) setReviewStats(await resp.json())
  }
  const loadReviewDetail = async (id: string) => {
    const resp = await fetch(`${API_URL}/admin/submissions/${id}`, { headers })
    if (resp.ok) setSelectedReview(await resp.json())
  }
  const claimReview = async (id: string) => {
    setReviewMsg('')
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/claim`, { method: 'PUT', headers })
    const d = await resp.json(); setReviewMsg(d.message || d.detail || ''); loadReviewDetail(id); loadReviewSubs()
  }
  const approveReview = async (id: string) => {
    setReviewMsg('')
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/approve`, { method: 'PUT', headers, body: JSON.stringify({ note: reviewNote }) })
    const d = await resp.json(); setReviewMsg(d.message || d.detail || ''); if (resp.ok) { setSelectedReview(null); loadReviewSubs(); loadReviewStats() }
  }
  const rejectReview = async (id: string) => {
    if (!reviewNote) { setReviewMsg('Rejection reason required'); return }
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/reject`, { method: 'PUT', headers, body: JSON.stringify({ reason: reviewNote }) })
    const d = await resp.json(); setReviewMsg(d.message || d.detail || ''); if (resp.ok) { setSelectedReview(null); loadReviewSubs(); loadReviewStats() }
  }
  const requestChanges = async (id: string) => {
    if (!reviewNote) { setReviewMsg('Reason required'); return }
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/request-changes`, { method: 'PUT', headers, body: JSON.stringify({ reason: reviewNote }) })
    const d = await resp.json(); setReviewMsg(d.message || d.detail || ''); if (resp.ok) loadReviewDetail(id)
  }
  const provisionSandbox = async (id: string) => {
    setReviewMsg('')
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/sandbox`, { method: 'POST', headers, body: '{}' })
    const d = await resp.json(); setReviewMsg(d.access_url ? `Sandbox running at ${d.access_url}` : d.detail || d.error || 'Sandbox provisioned'); loadReviewDetail(id)
  }
  const destroySandbox = async (id: string) => {
    const resp = await fetch(`${API_URL}/admin/submissions/${id}/sandbox`, { method: 'DELETE', headers })
    const d = await resp.json(); setReviewMsg(d.message || d.detail || ''); loadReviewDetail(id)
  }
  const addAdminNote = async (id: string) => {
    if (!reviewNote) return
    await fetch(`${API_URL}/admin/submissions/${id}/notes`, { method: 'POST', headers, body: JSON.stringify({ content: reviewNote, note_type: 'comment' }) })
    setReviewNote(''); loadReviewDetail(id)
  }

  useEffect(() => {
    if (headers.Authorization === 'Bearer ') return
    loadReviewSubs()
    loadReviewStats()
  }, [headers.Authorization])

  if (loading) return <LoadingState label="Loading submissions..." />

  const SC: Record<string, string> = { draft: '#94a3b8', submitted: '#60a5fa', automated_review: '#fbbf24', in_review: '#a855f7', changes_requested: '#fb923c', approved: '#4ade80', rejected: '#f87171', published: '#4ade80' }

  return (
    <div>
      <PageHeader title="App Reviews" subtitle="Submission review pipeline" />

      {/* Stats */}
      {reviewStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Pending Review', value: reviewStats.pending_review, color: '#60a5fa' },
            { label: 'In Review', value: reviewStats.in_review, color: '#a855f7' },
            { label: 'Approved', value: reviewStats.approved, color: '#4ade80' },
            { label: 'Rejected', value: reviewStats.rejected, color: '#f87171' },
          ].map(s => (
            <div key={s.label} className="card p-4" style={{ border: '1px solid var(--border-subtle)' }}>
              <div className="text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>{s.label}</div>
              <div className="text-xl font-bold" style={{ color: s.color }}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {reviewMsg && <div className="mb-4 px-3 py-2 rounded text-xs" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>{reviewMsg}</div>}

      {/* Filter buttons */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {['all', 'submitted', 'in_review', 'changes_requested', 'approved', 'rejected'].map(f => (
          <button key={f} onClick={() => loadReviewSubs(f === 'all' ? undefined : f)}
            className="text-[10px] px-2 py-1 rounded font-mono" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>
            {f.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {!selectedReview ? (
        /* Submissions List */
        <div className="card overflow-hidden overflow-x-auto" style={{ border: '1px solid var(--border-subtle)' }}>
          {reviewSubs.length === 0 ? (
            <p className="text-sm p-6 text-center" style={{ color: 'var(--text-tertiary)' }}>No submissions found.</p>
          ) : (
            <table className="w-full text-sm min-w-[700px]">
              <thead style={{ background: 'var(--bg-elevated)' }}>
                <tr>
                  {['App', 'Category', 'Submitter', 'Status', 'Scan', 'Submitted', 'Actions'].map(h => (
                    <th key={h} className="text-left px-3 py-2.5 text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {reviewSubs.map((s: any) => (
                  <tr key={s.id} style={{ borderTop: '1px solid var(--border-subtle)' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                    <td className="px-3 py-2.5">
                      <div className="font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{s.name}</div>
                      <div className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>v{s.version} · {s.submission_type}</div>
                    </td>
                    <td className="px-3 py-2.5 text-xs">{s.category}</td>
                    <td className="px-3 py-2.5 text-xs" style={{ color: 'var(--text-secondary)' }}>@{s.submitter_username || '?'}</td>
                    <td className="px-3 py-2.5">
                      <span className="text-[9px] px-1.5 py-0.5 rounded font-mono" style={{ color: SC[s.status] || '#94a3b8' }}>
                        {s.status.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-[10px]">
                      {s.automated_scan_status === 'passed' ? <span style={{ color: '#4ade80' }}>passed</span>
                        : s.automated_scan_status === 'failed' ? <span style={{ color: '#f87171' }}>failed</span>
                        : <span style={{ color: 'var(--text-tertiary)' }}>{s.automated_scan_status || '-'}</span>}
                    </td>
                    <td className="px-3 py-2.5 text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                      {s.submitted_at ? new Date(s.submitted_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="px-3 py-2.5">
                      <button onClick={() => loadReviewDetail(s.id)} className="text-[10px] px-2 py-0.5 rounded"
                        style={{ background: 'var(--refi-teal)', color: '#000', border: 'none', cursor: 'pointer' }}>
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        /* Review Detail */
        <div>
          <button onClick={() => setSelectedReview(null)} className="text-xs mb-4" style={{ color: 'var(--refi-teal)', background: 'none', border: 'none', cursor: 'pointer' }}>
            Back to list
          </button>

          <div className="card p-5 mb-4" style={{ border: '1px solid var(--border-default)' }}>
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{selectedReview.name}</h2>
              <span className="text-[10px] px-2 py-0.5 rounded font-mono" style={{ color: SC[selectedReview.status] || '#94a3b8' }}>
                {selectedReview.status.replace(/_/g, ' ')}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
              {[['Submitter', `@${selectedReview.submitter_username}`], ['Category', selectedReview.category], ['Version', selectedReview.version], ['Price', selectedReview.price_type === 'free' ? 'Free' : `$${selectedReview.price_amount}`]].map(([k, v]) => (
                <div key={k as string}><span style={{ color: 'var(--text-tertiary)' }}>{k}: </span><span style={{ color: 'var(--text-primary)' }}>{v}</span></div>
              ))}
            </div>

            {selectedReview.description && <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>{selectedReview.description}</p>}

            {selectedReview.artifact_filename && (
              <div className="text-xs mb-3 font-mono" style={{ color: 'var(--text-secondary)' }}>
                Artifact: <span style={{ color: 'var(--refi-teal)' }}>{selectedReview.artifact_filename}</span>
                ({selectedReview.artifact_size_bytes ? `${(selectedReview.artifact_size_bytes / 1024).toFixed(0)} KB` : '?'})
                {selectedReview.artifact_hash && <span className="text-[9px] ml-1" style={{ color: 'var(--text-tertiary)' }}>SHA256: {selectedReview.artifact_hash.slice(0, 16)}...</span>}
              </div>
            )}

            {/* Scan Results */}
            {selectedReview.automated_scan_result && (
              <div className="p-3 mb-3 rounded text-xs" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)' }}>
                <div className="font-mono mb-1" style={{ color: 'var(--text-tertiary)' }}>AUTOMATED SCAN: <span style={{ color: selectedReview.automated_scan_status === 'passed' ? '#4ade80' : '#f87171' }}>{selectedReview.automated_scan_status}</span></div>
                <div style={{ color: 'var(--text-tertiary)' }}>{selectedReview.automated_scan_result.file_count} files · {selectedReview.automated_scan_result.critical_count} critical · {selectedReview.automated_scan_result.warning_count} warnings</div>
                {selectedReview.automated_scan_result.findings?.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {selectedReview.automated_scan_result.findings.slice(0, 10).map((f: any, i: number) => (
                      <div key={i} className="flex gap-2" style={{ color: f.severity === 'critical' ? '#f87171' : f.severity === 'warning' ? '#fbbf24' : 'var(--text-tertiary)' }}>
                        <span className="font-mono w-12">[{f.severity}]</span>
                        <span className="font-mono">{f.file}</span>
                        <span>{f.issue}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Admin Actions */}
            <div className="flex gap-2 flex-wrap mb-3">
              {selectedReview.status === 'submitted' && (
                <button onClick={() => claimReview(selectedReview.id)} className="px-3 py-1.5 text-xs rounded font-semibold"
                  style={{ background: 'var(--refi-teal)', color: '#000', cursor: 'pointer' }}>Claim for Review</button>
              )}
              {selectedReview.status === 'in_review' && (
                <>
                  <button onClick={() => provisionSandbox(selectedReview.id)} className="px-3 py-1.5 text-xs rounded"
                    style={{ background: 'rgba(168,85,247,0.15)', color: '#a855f7', border: 'none', cursor: 'pointer' }}>Launch Sandbox</button>
                  <button onClick={() => destroySandbox(selectedReview.id)} className="px-3 py-1.5 text-xs rounded"
                    style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>Destroy Sandbox</button>
                  <button onClick={() => approveReview(selectedReview.id)} className="px-3 py-1.5 text-xs rounded font-semibold"
                    style={{ background: 'rgba(74,222,128,0.15)', color: '#4ade80', border: 'none', cursor: 'pointer' }}>Approve & Publish</button>
                  <button onClick={() => requestChanges(selectedReview.id)} className="px-3 py-1.5 text-xs rounded"
                    style={{ background: 'rgba(251,146,60,0.15)', color: '#fb923c', border: 'none', cursor: 'pointer' }}>Request Changes</button>
                  <button onClick={() => rejectReview(selectedReview.id)} className="px-3 py-1.5 text-xs rounded"
                    style={{ background: 'rgba(248,113,113,0.15)', color: '#f87171', border: 'none', cursor: 'pointer' }}>Reject</button>
                </>
              )}
            </div>

            {/* Review Note Input */}
            {['in_review', 'submitted'].includes(selectedReview.status) && (
              <div className="flex gap-2">
                <input value={reviewNote} onChange={e => setReviewNote(e.target.value)} placeholder="Add review note / reason..."
                  className="flex-1 px-2 py-1.5 text-xs rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }} />
                <button onClick={() => addAdminNote(selectedReview.id)} className="px-3 py-1.5 text-xs rounded"
                  style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>Add Note</button>
              </div>
            )}
          </div>

          {/* Review Thread */}
          {selectedReview.notes?.length > 0 && (
            <div>
              <h3 className="text-xs font-mono mb-2 uppercase" style={{ color: 'var(--text-tertiary)' }}>Review Thread</h3>
              <div className="space-y-2">
                {selectedReview.notes.map((n: any) => (
                  <div key={n.id} className="card p-3" style={{ border: '1px solid var(--border-subtle)', borderLeft: n.note_type === 'request_changes' ? '3px solid #fb923c' : n.note_type === 'rejection' ? '3px solid #f87171' : n.note_type === 'approval' ? '3px solid #4ade80' : '3px solid var(--border-subtle)' }}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{n.author_username || 'System'}</span>
                      <span className="text-[9px] px-1 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>{n.note_type}</span>
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
