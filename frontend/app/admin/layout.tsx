'use client'

import { useState, useEffect, createContext, useContext } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import Link from 'next/link'
import { API_URL } from '@/lib/config'

/* ─── Admin Auth Context ─── */
interface AdminCtx {
  token: string
  headers: Record<string, string>
}

const AdminContext = createContext<AdminCtx>({ token: '', headers: {} })
export function useAdmin() { return useContext(AdminContext) }

/* ─── Sidebar nav definition ─── */
const NAV_SECTIONS = [
  {
    label: 'Overview',
    items: [
      { key: 'overview', label: 'Dashboard', href: '/admin', icon: 'grid' },
      { key: 'onboarding', label: 'Onboarding', href: '/admin/onboarding', icon: 'users-plus' },
      { key: 'downloads', label: 'Downloads', href: '/admin/downloads', icon: 'download' },
    ],
  },
  {
    label: 'Management',
    items: [
      { key: 'users', label: 'Users', href: '/admin/users', icon: 'users' },
      { key: 'reviews', label: 'Reviews', href: '/admin/reviews', icon: 'clipboard' },
      { key: 'store', label: 'App Store', href: '/admin/store', icon: 'package' },
    ],
  },
  {
    label: 'Infrastructure',
    items: [
      { key: 'providers', label: 'AI Providers', href: '/admin/providers', icon: 'cpu' },
      { key: 'wallets', label: 'Wallets', href: '/admin/wallets', icon: 'wallet' },
      { key: 'networks', label: 'Networks', href: '/admin/networks', icon: 'globe' },
      { key: 'infra', label: 'Nodes', href: '/admin/infra', icon: 'server' },
      { key: 'mcp', label: 'MCP Servers', href: '/admin/mcp', icon: 'plug' },
    ],
  },
  {
    label: 'Security',
    items: [
      { key: 'audit', label: 'Audit Log', href: '/admin/audit', icon: 'shield' },
      { key: 'secrets', label: 'Secrets', href: '/admin/secrets', icon: 'lock' },
      { key: 'visibility', label: 'Tab Visibility', href: '/admin/visibility', icon: 'eye' },
    ],
  },
]

/* ─── SVG icon map ─── */
function NavIcon({ name, size = 16 }: { name: string; size?: number }) {
  const s = { width: size, height: size, strokeWidth: 1.5, stroke: 'currentColor', fill: 'none', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  const icons: Record<string, React.ReactNode> = {
    grid: <svg {...s} viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>,
    'users-plus': <svg {...s} viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>,
    download: <svg {...s} viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
    users: <svg {...s} viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
    clipboard: <svg {...s} viewBox="0 0 24 24"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/></svg>,
    package: <svg {...s} viewBox="0 0 24 24"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>,
    cpu: <svg {...s} viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>,
    wallet: <svg {...s} viewBox="0 0 24 24"><rect x="1" y="5" width="22" height="16" rx="2"/><path d="M1 10h22"/><circle cx="18" cy="15" r="1"/></svg>,
    globe: <svg {...s} viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>,
    server: <svg {...s} viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>,
    plug: <svg {...s} viewBox="0 0 24 24"><path d="M12 22v-5"/><path d="M9 8V1h6v7"/><path d="M4 12a4 4 0 0 0 4 4h8a4 4 0 0 0 4-4V8H4z"/></svg>,
    shield: <svg {...s} viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
    lock: <svg {...s} viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>,
    eye: <svg {...s} viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>,
    'arrow-left': <svg {...s} viewBox="0 0 24 24"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>,
    menu: <svg {...s} viewBox="0 0 24 24"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>,
  }
  return <>{icons[name] || null}</>
}

/* ─── Admin Layout ─── */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const [token, setToken] = useState('')
  const [authState, setAuthState] = useState<'loading' | 'authenticated' | 'not_authenticated' | 'session_expired' | 'forbidden'>('loading')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileOpen, setMobileOpen] = useState(false)

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }

  // Auth check on mount
  useEffect(() => {
    const t = localStorage.getItem('refinet_token') || ''
    if (!t) {
      setAuthState('not_authenticated')
      return
    }
    setToken(t)

    // Verify token is valid and user has admin role
    fetch(`${API_URL}/admin/stats`, {
      headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' },
    }).then(resp => {
      if (resp.ok) {
        setAuthState('authenticated')
      } else if (resp.status === 401) {
        setAuthState('session_expired')
      } else if (resp.status === 403) {
        setAuthState('forbidden')
      } else {
        setAuthState('session_expired')
      }
    }).catch(() => {
      setAuthState('session_expired')
    })
  }, [])

  // Close mobile menu on route change
  useEffect(() => { setMobileOpen(false) }, [pathname])

  // Loading state
  if (authState === 'loading') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="text-center">
          <div className="w-8 h-8 rounded-lg mx-auto mb-3 flex items-center justify-center" style={{ background: 'var(--refi-teal-glow)' }}>
            <span style={{ color: 'var(--refi-teal)', fontWeight: 700, fontSize: 14 }}>R</span>
          </div>
          <p className="text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>Verifying admin access...</p>
        </div>
      </div>
    )
  }

  // Auth error states
  if (authState !== 'authenticated') {
    const isAuthError = authState === 'not_authenticated' || authState === 'session_expired'
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="max-w-md text-center px-6">
          <div className="w-12 h-12 rounded-xl mx-auto mb-4 flex items-center justify-center" style={{ background: isAuthError ? 'var(--refi-teal-glow)' : 'rgba(248,113,113,0.1)' }}>
            <NavIcon name={isAuthError ? 'lock' : 'shield'} size={24} />
          </div>
          <h1 className="text-xl font-bold mb-2" style={{ letterSpacing: '-0.02em', color: isAuthError ? 'var(--text-primary)' : 'var(--error, #f87171)' }}>
            {authState === 'not_authenticated' ? 'Authentication Required' : authState === 'session_expired' ? 'Session Expired' : 'Access Denied'}
          </h1>
          <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {authState === 'not_authenticated'
              ? 'Sign in with your wallet to access the admin dashboard. SIWE authentication is required.'
              : authState === 'session_expired'
              ? 'Your session has expired or is invalid. Please sign in again with your wallet.'
              : 'Your wallet does not have admin privileges. Contact the platform owner for access.'}
          </p>
          {isAuthError && (
            <a
              href="/login"
              className="inline-block px-6 py-3 text-sm font-semibold rounded-lg transition-colors"
              style={{ background: 'var(--refi-teal)', color: '#000', textDecoration: 'none' }}
            >
              Sign In with Wallet
            </a>
          )}
          <div className="mt-4">
            <Link href="/dashboard" className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              Back to Dashboard
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const isActive = (href: string) => {
    if (href === '/admin') return pathname === '/admin' || pathname === '/admin/'
    return pathname.startsWith(href)
  }

  return (
    <AdminContext.Provider value={{ token, headers }}>
      <div style={{ display: 'flex', minHeight: '100vh' }}>
        {/* Mobile overlay */}
        {mobileOpen && (
          <div
            onClick={() => setMobileOpen(false)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 40 }}
            className="lg:hidden"
          />
        )}

        {/* Sidebar */}
        <aside
          style={{
            width: sidebarOpen ? 240 : 56,
            minHeight: '100vh',
            background: 'var(--bg-secondary)',
            borderRight: '1px solid var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            transition: 'width 0.2s ease',
            position: 'fixed',
            top: 0,
            left: 0,
            bottom: 0,
            zIndex: 50,
            transform: mobileOpen ? 'translateX(0)' : undefined,
          }}
          className={`hidden lg:flex ${mobileOpen ? '!flex' : ''}`}
        >
          {/* Header */}
          <div style={{ padding: sidebarOpen ? '16px 16px 12px' : '16px 8px 12px', borderBottom: '1px solid var(--border-subtle)' }}>
            <div className="flex items-center justify-between">
              {sidebarOpen ? (
                <Link href="/admin" style={{ textDecoration: 'none' }} className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'var(--refi-teal-glow)' }}>
                    <span style={{ color: 'var(--refi-teal)', fontWeight: 800, fontSize: 12 }}>R</span>
                  </div>
                  <div>
                    <div className="text-xs font-bold" style={{ color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>REFINET</div>
                    <div className="text-[9px] font-mono" style={{ color: 'var(--text-tertiary)' }}>ADMIN PANEL</div>
                  </div>
                </Link>
              ) : (
                <Link href="/admin" style={{ textDecoration: 'none' }}>
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center mx-auto" style={{ background: 'var(--refi-teal-glow)' }}>
                    <span style={{ color: 'var(--refi-teal)', fontWeight: 800, fontSize: 12 }}>R</span>
                  </div>
                </Link>
              )}
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="hidden lg:flex items-center justify-center"
                style={{ width: 24, height: 24, background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}
              >
                <NavIcon name="menu" size={14} />
              </button>
            </div>
          </div>

          {/* Nav */}
          <nav style={{ flex: 1, overflowY: 'auto', padding: sidebarOpen ? '8px 8px' : '8px 4px' }}>
            {NAV_SECTIONS.map(section => (
              <div key={section.label} style={{ marginBottom: 16 }}>
                {sidebarOpen && (
                  <div className="text-[9px] font-mono uppercase px-2 mb-1" style={{ color: 'var(--text-tertiary)', letterSpacing: '0.08em' }}>
                    {section.label}
                  </div>
                )}
                {section.items.map(item => {
                  const active = isActive(item.href)
                  return (
                    <Link
                      key={item.key}
                      href={item.href}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: sidebarOpen ? '7px 10px' : '7px 0',
                        justifyContent: sidebarOpen ? 'flex-start' : 'center',
                        borderRadius: 6,
                        textDecoration: 'none',
                        color: active ? 'var(--refi-teal)' : 'var(--text-secondary)',
                        background: active ? 'var(--refi-teal-glow, rgba(92,224,210,0.08))' : 'transparent',
                        fontSize: 12,
                        fontWeight: active ? 600 : 400,
                        transition: 'all 0.15s ease',
                        marginBottom: 2,
                      }}
                      title={!sidebarOpen ? item.label : undefined}
                    >
                      <NavIcon name={item.icon} size={15} />
                      {sidebarOpen && <span>{item.label}</span>}
                    </Link>
                  )
                })}
              </div>
            ))}
          </nav>

          {/* Footer */}
          <div style={{ padding: sidebarOpen ? '12px 16px' : '12px 8px', borderTop: '1px solid var(--border-subtle)' }}>
            <Link
              href="/dashboard"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                justifyContent: sidebarOpen ? 'flex-start' : 'center',
                fontSize: 11,
                color: 'var(--text-tertiary)',
                textDecoration: 'none',
              }}
            >
              <NavIcon name="arrow-left" size={14} />
              {sidebarOpen && <span>Back to App</span>}
            </Link>
          </div>
        </aside>

        {/* Main content */}
        <main style={{ flex: 1, marginLeft: sidebarOpen ? 240 : 56, transition: 'margin-left 0.2s ease' }} className="lg:ml-0">
          {/* Mobile header */}
          <div className="lg:hidden flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <button
              onClick={() => setMobileOpen(true)}
              style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
            >
              <NavIcon name="menu" size={20} />
            </button>
            <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>Admin Panel</span>
            <div style={{ width: 20 }} />
          </div>

          <div style={{ padding: '24px 24px 48px', maxWidth: 1200, margin: '0 auto' }}>
            {children}
          </div>
        </main>
      </div>
    </AdminContext.Provider>
  )
}
