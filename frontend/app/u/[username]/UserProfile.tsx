'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'

function StarIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  )
}

function ForkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="2">
      <circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/>
      <path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9"/><line x1="12" y1="12" x2="12" y2="15"/>
    </svg>
  )
}

function ProjectCard({ project }: { project: any }) {
  return (
    <a
      href={`/registry/${project.slug}/`}
      className="card transition-all block"
      style={{ padding: 16, textDecoration: 'none' }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 0 20px var(--refi-teal-glow)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
    >
      <div className="flex items-start justify-between mb-1">
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--refi-teal)' }}>
          {project.name}
        </span>
        <div className="flex items-center gap-2" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
          <span className="flex items-center gap-1"><StarIcon />{project.stars_count}</span>
          <span className="flex items-center gap-1"><ForkIcon />{project.forks_count}</span>
        </div>
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8, lineHeight: 1.5 }}>
        {project.description ? (project.description.length > 100 ? project.description.slice(0, 100) + '...' : project.description) : 'No description'}
      </p>
      <div className="flex items-center gap-2">
        <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", padding: '1px 5px', borderRadius: 3, background: 'rgba(92,224,210,0.12)', color: 'var(--refi-teal)' }}>
          {project.chain}
        </span>
        <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", padding: '1px 5px', borderRadius: 3, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
          {project.category}
        </span>
      </div>
    </a>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 4, color: copied ? 'var(--success)' : 'var(--text-tertiary)' }}
    >
      {copied ? (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
      ) : (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      )}
    </button>
  )
}

export default function UserProfilePage({ params }: { params: { username: string } }) {
  const { username } = params
  const [profile, setProfile] = useState<any>(null)
  const [projects, setProjects] = useState<any[]>([])
  const [starredProjects, setStarredProjects] = useState<any[]>([])
  const [activeTab, setActiveTab] = useState('Projects')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('refinet_token')
    if (!token) { window.location.href = '/settings/'; return }

    Promise.all([
      fetch(`${API_URL}/registry/users/${username}`).then(r => r.ok ? r.json() : null),
      fetch(`${API_URL}/registry/users/${username}/projects`).then(r => r.ok ? r.json() : []),
      fetch(`${API_URL}/registry/users/${username}/stars`).then(r => r.ok ? r.json() : { items: [] }),
    ]).then(([prof, proj, stars]) => {
      setProfile(prof)
      setProjects(Array.isArray(proj) ? proj : [])
      setStarredProjects(stars?.items || [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [username])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <span className="animate-pulse" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)', fontSize: 14 }}>
          Loading profile...
        </span>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="max-w-3xl mx-auto py-20 px-6 text-center">
        <h1 className="text-2xl font-bold mb-4">User Not Found</h1>
        <p style={{ color: 'var(--text-secondary)' }}>The user "{username}" doesn't exist.</p>
      </div>
    )
  }

  const TIER_COLORS: Record<string, string> = {
    free: 'var(--text-tertiary)',
    developer: '#3B82F6',
    pro: '#8B5CF6',
    admin: '#F59E0B',
  }

  return (
    <div className="max-w-5xl mx-auto py-10 px-6 space-y-8">
      {/* Profile Header */}
      <div className="flex flex-col md:flex-row gap-6 items-start">
        {/* Avatar placeholder */}
        <div style={{
          width: 80, height: 80, borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--refi-teal), var(--refi-teal-dim))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 28, fontWeight: 700, color: 'var(--bg-primary)',
          flexShrink: 0,
        }}>
          {username[0]?.toUpperCase()}
        </div>

        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold" style={{ letterSpacing: '-0.02em' }}>{username}</h1>
            <span style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 10,
              background: `${TIER_COLORS[profile.tier] || 'var(--text-tertiary)'}20`,
              color: TIER_COLORS[profile.tier] || 'var(--text-tertiary)',
              fontFamily: "'JetBrains Mono', monospace", fontWeight: 600,
              textTransform: 'uppercase',
            }}>
              {profile.tier}
            </span>
          </div>

          {profile.eth_address && (
            <div className="flex items-center gap-1 mb-3">
              <span style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>
                {profile.eth_address.slice(0, 6)}...{profile.eth_address.slice(-4)}
              </span>
              <CopyButton text={profile.eth_address} />
            </div>
          )}

          {/* Stats */}
          <div className="flex items-center gap-6" style={{ fontSize: 13 }}>
            <div>
              <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{profile.project_count}</span>
              <span style={{ color: 'var(--text-tertiary)', marginLeft: 4 }}>projects</span>
            </div>
            <div>
              <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{profile.total_stars_received}</span>
              <span style={{ color: 'var(--text-tertiary)', marginLeft: 4 }}>stars received</span>
            </div>
            <div>
              <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{profile.stars_given}</span>
              <span style={{ color: 'var(--text-tertiary)', marginLeft: 4 }}>stars given</span>
            </div>
            {profile.joined_at && (
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                Joined {new Date(profile.joined_at).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Pinned Projects */}
      {profile.pinned_projects?.length > 0 && (
        <section>
          <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
            Pinned Projects
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {profile.pinned_projects.map((p: any) => <ProjectCard key={p.id} project={p} />)}
          </div>
        </section>
      )}

      {/* Tabs */}
      <div className="flex gap-1" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        {['Projects', 'Stars'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-4 py-2.5 text-[13px] font-medium transition-colors"
            style={{
              color: activeTab === tab ? 'var(--refi-teal)' : 'var(--text-secondary)',
              borderBottom: activeTab === tab ? '2px solid var(--refi-teal)' : '2px solid transparent',
              background: 'transparent', cursor: 'pointer',
            }}
          >
            {tab} ({tab === 'Projects' ? projects.length : starredProjects.length})
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'Projects' && (
          projects.length === 0 ? (
            <p style={{ color: 'var(--text-tertiary)', fontSize: 14, padding: '20px 0' }}>No public projects yet.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {projects.map((p: any) => <ProjectCard key={p.id} project={p} />)}
            </div>
          )
        )}

        {activeTab === 'Stars' && (
          starredProjects.length === 0 ? (
            <p style={{ color: 'var(--text-tertiary)', fontSize: 14, padding: '20px 0' }}>No starred projects yet.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {starredProjects.map((p: any) => <ProjectCard key={p.id} project={p} />)}
            </div>
          )
        )}
      </div>
    </div>
  )
}
