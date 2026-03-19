'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

export default function ProjectsPage() {
  const [projects, setProjects] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [username, setUsername] = useState('')

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    if (!token) { window.location.href = '/settings/'; return }

    const headers = { Authorization: `Bearer ${token}` }

    fetch(`${API_URL}/auth/me`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(profile => {
        if (!profile) { setLoading(false); return }
        setUsername(profile.username)
        return fetch(`${API_URL}/registry/users/${profile.username}/projects`, { headers })
          .then(r => r.ok ? r.json() : [])
          .then(data => {
            setProjects(Array.isArray(data) ? data : [])
            setLoading(false)
          })
      })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '60vh' }}>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)', fontSize: 13 }} className="animate-pulse">
          Loading projects...
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto py-10 px-6 space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ letterSpacing: '-0.03em' }}>
            My <span style={{ color: 'var(--refi-teal)' }}>Projects</span>
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            {projects.length > 0
              ? `${projects.length} project${projects.length !== 1 ? 's' : ''} in your collection`
              : 'Build, publish, and manage your smart contract projects'}
          </p>
        </div>
        {projects.length > 0 && (
          <Link href="/registry/new/" className="btn-primary !py-2 !px-5 !text-sm !rounded-lg" style={{ textDecoration: 'none' }}>
            + New Project
          </Link>
        )}
      </div>

      {/* Projects Grid */}
      {projects.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project: any) => (
            <ProjectCard key={project.id} project={project} username={username} />
          ))}
        </div>
      ) : (
        <GettingStartedGuide />
      )}
    </div>
  )
}

/* ─── Project Card ─── */

const CHAIN_COLORS: Record<string, string> = {
  ethereum: '#627EEA', base: '#0052FF', arbitrum: '#28A0F0',
  polygon: '#8247E5', solana: '#14F195', 'multi-chain': 'var(--refi-teal)',
}
const CATEGORY_COLORS: Record<string, string> = {
  defi: '#F59E0B', token: '#8B5CF6', governance: '#EC4899', bridge: '#06B6D4',
  utility: '#6B7280', oracle: '#F97316', nft: '#EF4444', dao: '#10B981',
  sdk: '#3B82F6', library: '#6366F1',
}

function ProjectCard({ project, username }: { project: any; username: string }) {
  return (
    <Link
      href={`/registry/${project.slug}/`}
      className="card block"
      style={{ padding: 20, textDecoration: 'none', transition: 'all 0.2s' }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 0 20px var(--refi-teal-glow)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
    >
      <div className="flex items-start justify-between mb-2">
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--refi-teal)' }}>
          {project.owner_username || username}/{project.name}
        </div>
        <div className="flex items-center gap-3" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          <span className="flex items-center gap-1">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" /></svg>
            {project.stars_count || 0}
          </span>
        </div>
      </div>

      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12, lineHeight: 1.5 }}>
        {project.description
          ? project.description.length > 120 ? project.description.slice(0, 120) + '...' : project.description
          : 'No description'}
      </p>

      <div className="flex items-center gap-2 flex-wrap">
        {project.chain && (
          <span style={{
            fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
            padding: '2px 6px', borderRadius: 4,
            background: `${CHAIN_COLORS[project.chain] || '#6B7280'}20`,
            color: CHAIN_COLORS[project.chain] || '#6B7280',
            fontWeight: 600, textTransform: 'uppercase',
          }}>
            {project.chain}
          </span>
        )}
        {project.category && (
          <span style={{
            fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
            padding: '2px 6px', borderRadius: 4,
            background: `${CATEGORY_COLORS[project.category] || '#6B7280'}20`,
            color: CATEGORY_COLORS[project.category] || '#6B7280',
            fontWeight: 600,
          }}>
            {project.category}
          </span>
        )}
        {project.visibility && (
          <span style={{
            fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
            padding: '2px 6px', borderRadius: 4,
            background: project.visibility === 'public' ? 'rgba(16,185,129,0.12)' : 'rgba(107,114,128,0.12)',
            color: project.visibility === 'public' ? '#10B981' : '#6B7280',
            fontWeight: 600, textTransform: 'uppercase',
          }}>
            {project.visibility}
          </span>
        )}
      </div>
    </Link>
  )
}

/* ─── Getting Started Guide ─── */
function GettingStartedGuide() {
  const steps = [
    {
      number: '01',
      title: 'Create a Project',
      description: 'Give your project a name, choose the target chain, and set a category. This creates your project namespace in the registry.',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 5v14M5 12h14"/>
        </svg>
      ),
    },
    {
      number: '02',
      title: 'Upload Your ABIs',
      description: 'Add smart contract ABIs so GROOT can understand your contracts. ABIs are automatically parsed to expose functions and events.',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
      ),
    },
    {
      number: '03',
      title: 'Add SDKs & Logic',
      description: 'Attach generated SDKs and execution logic to your project. These make your contracts callable by any AI agent through MCP.',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
        </svg>
      ),
    },
    {
      number: '04',
      title: 'Publish & Discover',
      description: 'Make your project public so the community can discover, star, and fork it. Your contracts become part of GROOT\'s brain.',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
        </svg>
      ),
    },
  ]

  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      {/* Hero section */}
      <div className="card" style={{
        padding: '40px 32px',
        textAlign: 'center',
        background: 'linear-gradient(135deg, var(--bg-elevated) 0%, rgba(92,224,210,0.04) 100%)',
        border: '1px solid var(--border-subtle)',
        marginBottom: 32,
      }}>
        <div style={{
          width: 56, height: 56, borderRadius: 16, margin: '0 auto 20px',
          background: 'rgba(92,224,210,0.1)',
          border: '1px solid rgba(92,224,210,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, letterSpacing: '-0.02em' }}>
          Ship Your First Project
        </h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: 480, margin: '0 auto 24px' }}>
          Projects are how you organize and publish smart contracts on REFINET.
          Create one to make your contracts discoverable by AI agents through MCP.
        </p>
        <Link
          href="/registry/new/"
          className="btn-primary !py-2.5 !px-8 !text-sm !rounded-lg"
          style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 8 }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 5v14M5 12h14"/>
          </svg>
          Create Your First Project
        </Link>
      </div>

      {/* Steps */}
      <div style={{ position: 'relative' }}>
        {/* Vertical connector line */}
        <div style={{
          position: 'absolute', left: 27, top: 40, bottom: 40, width: 1,
          background: 'linear-gradient(to bottom, var(--refi-teal), transparent)',
          opacity: 0.2,
        }} />

        <div className="space-y-4">
          {steps.map((step) => (
            <div
              key={step.number}
              className="card"
              style={{
                padding: '20px 24px',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 16,
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'rgba(92,224,210,0.3)'
                e.currentTarget.style.boxShadow = '0 0 20px rgba(92,224,210,0.05)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--border-subtle)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <div style={{
                width: 40, height: 40, borderRadius: 12, flexShrink: 0,
                background: 'rgba(92,224,210,0.08)',
                border: '1px solid rgba(92,224,210,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                position: 'relative', zIndex: 1,
              }}>
                {step.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div className="flex items-center gap-2 mb-1">
                  <span style={{
                    fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
                    color: 'var(--refi-teal)', fontWeight: 700, letterSpacing: '0.05em',
                  }}>
                    STEP {step.number}
                  </span>
                </div>
                <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 4px' }}>
                  {step.title}
                </h3>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer tip */}
      <div style={{
        marginTop: 32, padding: '16px 20px', borderRadius: 10,
        background: 'rgba(92,224,210,0.04)',
        border: '1px solid rgba(92,224,210,0.1)',
        display: 'flex', alignItems: 'flex-start', gap: 12,
      }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 1 }}>
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
        </svg>
        <div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Pro tip:</strong> You can also explore the{' '}
            <Link href="/explore/" style={{ color: 'var(--refi-teal)', textDecoration: 'none' }}
              onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
              onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
            >
              Registry
            </Link>
            {' '}to discover and fork existing projects as a starting point.
          </p>
        </div>
      </div>
    </div>
  )
}
