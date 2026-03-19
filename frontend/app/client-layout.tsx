'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { ThemeProvider, useTheme } from '@/components/ThemeProvider'
import ErrorBoundary from '@/components/ErrorBoundary'
import { API_URL } from '@/lib/config'
import GrootChatWidget from '@/components/GrootChat'
import SettingsModal from '@/components/SettingsModal'
import DocsModal from '@/components/DocsModal'

// Wallet providers
import { WagmiProvider } from 'wagmi'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { wagmiConfig } from '@/lib/wallet'

// Singleton QueryClient — survives re-renders but not page reloads (which is correct)
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      // Don't refetch on window focus during development to reduce noise
      refetchOnWindowFocus: false,
    },
  },
})

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [hydrated, setHydrated] = useState(false)
  const pathname = usePathname()
  const mountedRef = useRef(false)

  useEffect(() => {
    // Guard against double-mount in React StrictMode
    if (mountedRef.current) return
    mountedRef.current = true

    // Clear stale wagmi connector state on fresh page load.
    // This prevents crashes when connectors change between page loads
    // (e.g., WalletConnect added/removed, connector IDs changed).
    try {
      const cookies = document.cookie.split(';')
      for (const cookie of cookies) {
        const name = cookie.split('=')[0].trim()
        if (name === 'wagmi.store') {
          // Parse the wagmi store cookie to check for stale state
          const val = decodeURIComponent(cookie.split('=').slice(1).join('='))
          try {
            const state = JSON.parse(val)
            // If the stored state references a connector that doesn't exist
            // in the current config, clear it to prevent reconnection crashes
            if (state?.state?.connections) {
              const connectorIds = wagmiConfig.connectors.map(c => c.id)
              const hasStaleConnector = Object.values(state.state.connections as Record<string, any>).some(
                (conn: any) => conn?.connector?.id && !connectorIds.includes(conn.connector.id)
              )
              if (hasStaleConnector) {
                document.cookie = 'wagmi.store=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
                console.warn('[REFINET] Cleared stale wagmi connector state')
              }
            }
          } catch {
            // Malformed cookie — clear it
            document.cookie = 'wagmi.store=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
          }
        }
      }
    } catch {
      // Cookie access failed — not critical
    }
  }, [])

  useEffect(() => {
    const checkAuth = () => {
      try {
        const token = localStorage.getItem('refinet_token')
        setIsLoggedIn(!!token)
      } catch {
        // localStorage blocked (incognito, storage full, etc.)
        setIsLoggedIn(false)
      }
    }

    checkAuth()
    setHydrated(true)

    const onStorage = () => checkAuth()
    window.addEventListener('storage', onStorage)
    window.addEventListener('refinet-auth-change', onStorage)

    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('refinet-auth-change', onStorage)
    }
  }, [])

  // Auth page (/settings/) gets full viewport — no nav, no padding
  const isAuthPage = pathname === '/settings' || pathname === '/settings/'

  // Don't render anything until hydrated — prevents SSR/CSR mismatch flash
  // that can cause layout thrash and component unmount/remount cycles
  if (!hydrated) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'var(--bg-primary, #0a0a0f)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <img
          src="/refi-logo.png"
          alt="Loading..."
          style={{ width: 32, height: 32, borderRadius: '50%', opacity: 0.6, animation: 'pulse 1.5s ease-in-out infinite' }}
          onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
        />
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <WagmiProvider config={wagmiConfig}>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider>
            {isLoggedIn ? (
              <AppShell>{children}</AppShell>
            ) : isAuthPage ? (
              <>{children}</>
            ) : (
              <>
                <PublicNavBar hydrated={hydrated} />
                <main className="pt-[48px]">{children}</main>
              </>
            )}
          </ThemeProvider>
        </QueryClientProvider>
      </WagmiProvider>
    </ErrorBoundary>
  )
}

/* ─── Authenticated App Shell ─── */
function AppShell({ children }: { children: React.ReactNode }) {
  const { theme, toggle } = useTheme()
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [docsOpen, setDocsOpen] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('refinet_sidebar_collapsed')
    if (saved === 'true') setCollapsed(true)
  }, [])

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false)
  }, [pathname])

  const toggleSidebar = useCallback(() => {
    setCollapsed(prev => {
      localStorage.setItem('refinet_sidebar_collapsed', String(!prev))
      return !prev
    })
  }, [])

  const isActive = (href: string) => {
    const clean = href.replace(/\/$/, '')
    if (clean === '/dashboard') return pathname === '/dashboard' || pathname === '/dashboard/'
    return pathname.startsWith(clean)
  }

  const handleLogout = async () => {
    // Revoke refresh tokens server-side before clearing local storage
    const token = localStorage.getItem('refinet_token')
    if (token) {
      try {
        await fetch(`${API_URL}/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
      } catch {} // Best-effort — still clear local tokens even if server unreachable
    }
    localStorage.removeItem('refinet_token')
    localStorage.removeItem('refinet_refresh')
    window.dispatchEvent(new Event('refinet-auth-change'))
    window.location.href = '/'
  }

  const sidebarWidth = collapsed ? 64 : 240

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      {/* ── Top Bar ── */}
      <header
        className="glass"
        style={{
          height: 48,
          minHeight: 48,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingLeft: 16,
          paddingRight: 16,
          borderBottom: '1px solid var(--border-subtle)',
          zIndex: 50,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Mobile hamburger */}
          <button
            className="md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: 4 }}
            aria-label="Toggle menu"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>

          <Link href="/dashboard/" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
            <img src="/refi-logo.png" alt="REFINET" style={{ width: 24, height: 24, borderRadius: '50%' }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '0.02em' }}>
              REFINET<span style={{ color: 'var(--refi-teal)' }}> Cloud</span>
            </span>
          </Link>
        </div>

        {/* Right icons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <TopBarIcon href="/explore/" label="Registry" active={isActive('/explore')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </TopBarIcon>

          <TopBarIcon href="/repo/" label="Repositories" active={isActive('/repo')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
            </svg>
          </TopBarIcon>

          <TopBarIcon href="/store/" label="App Store" active={isActive('/store')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 2L3 7v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7l-3-5z"/><line x1="3" y1="7" x2="21" y2="7"/><path d="M16 11a4 4 0 0 1-8 0"/>
            </svg>
          </TopBarIcon>

          <TopBarIcon href="/messages/" label="Messages" active={isActive('/messages')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
            </svg>
          </TopBarIcon>

          <TopBarIcon href="/network/" label="Network" active={isActive('/network')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
            </svg>
          </TopBarIcon>

          <div style={{ width: 1, height: 20, background: 'var(--border-subtle)', margin: '0 4px' }} />

          {/* Theme toggle */}
          <button
            onClick={toggle}
            style={{
              background: 'none', border: 'none', cursor: 'pointer', padding: 6, borderRadius: 6,
              color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>

          {/* Settings (opens modal) */}
          <button
            onClick={() => setSettingsOpen(true)}
            title="Settings"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: 32, height: 32, borderRadius: 6,
              color: settingsOpen ? 'var(--refi-teal)' : 'var(--text-tertiary)',
              background: settingsOpen ? 'var(--refi-teal-glow)' : 'transparent',
              border: 'none', cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={e => { if (!settingsOpen) { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.color = 'var(--text-secondary)' }}}
            onMouseLeave={e => { if (!settingsOpen) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-tertiary)' }}}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
          </button>

          {/* Logout */}
          <button
            onClick={handleLogout}
            title="Sign out"
            style={{
              background: 'none', border: 'none', cursor: 'pointer', padding: 6, borderRadius: 6,
              color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.color = 'var(--error)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-tertiary)' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
          </button>
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* ── Mobile overlay ── */}
        {mobileMenuOpen && (
          <div
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 40 }}
            className="md:hidden"
            onClick={() => setMobileMenuOpen(false)}
          />
        )}

        {/* ── Sidebar ── */}
        <aside
          className={mobileMenuOpen ? '' : 'hidden md:flex'}
          style={{
            width: mobileMenuOpen ? 240 : sidebarWidth,
            minWidth: mobileMenuOpen ? 240 : sidebarWidth,
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--bg-secondary)',
            borderRight: '1px solid var(--border-subtle)',
            transition: 'width 0.2s ease, min-width 0.2s ease',
            overflow: 'hidden',
            ...(mobileMenuOpen ? { position: 'fixed', top: 48, left: 0, bottom: 0, zIndex: 45 } : {}),
          }}
        >
          {/* Collapse toggle (desktop only) */}
          <div
            className="hidden md:flex"
            style={{
              padding: collapsed ? '12px 0' : '12px 12px',
              justifyContent: collapsed ? 'center' : 'flex-end',
            }}
          >
            <button
              onClick={toggleSidebar}
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: 4, borderRadius: 6,
                color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-tertiary)')}
            >
              {collapsed ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
              )}
            </button>
          </div>

          {/* Nav items */}
          <nav style={{ flex: 1, padding: '4px 8px', overflowY: 'auto' }}>
            <SidebarItem href="/dashboard/" icon={<DashboardIcon />} label="Dashboard" active={isActive('/dashboard')} collapsed={collapsed} />

            <div style={{ height: 4 }} />
            {!collapsed && (
              <div style={{ padding: '8px 12px 4px', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-tertiary)' }}>
                Core
              </div>
            )}

            <SidebarItem href="/chat/" icon={<ChatIcon />} label="Chat" active={isActive('/chat')} collapsed={collapsed} />
            <SidebarItem href="/devices/" icon={<DevicesIcon />} label="Devices" active={isActive('/devices')} collapsed={collapsed} />
            <SidebarItem href="/webhooks/" icon={<WebhooksIcon />} label="Webhooks" active={isActive('/webhooks')} collapsed={collapsed} />
            <SidebarItem href="/knowledge/" icon={<KnowledgeIcon />} label="Knowledge" active={isActive('/knowledge')} collapsed={collapsed} />

            <div style={{ height: 4 }} />
            {!collapsed && (
              <div style={{ padding: '8px 12px 4px', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-tertiary)' }}>
                Build
              </div>
            )}

            <SidebarItem href="/projects/" icon={<ProjectsIcon />} label="Projects" active={isActive('/projects')} collapsed={collapsed} />
            <SidebarItem href="/explore/" icon={<RegistryIcon />} label="Registry" active={isActive('/explore')} collapsed={collapsed} />
            <SidebarItem href="/store/" icon={<StoreIcon />} label="App Store" active={isActive('/store')} collapsed={collapsed} />
            <SidebarItem href="/repo/" icon={<RepoIcon />} label="Repositories" active={isActive('/repo')} collapsed={collapsed} />
            <SidebarButton icon={<DocsIcon />} label="API Docs" active={docsOpen} collapsed={collapsed} onClick={() => setDocsOpen(true)} />
          </nav>

          {/* Bottom section */}
          <div style={{ borderTop: '1px solid var(--border-subtle)', padding: '8px' }}>
            <SidebarItem href="/admin/" icon={<AdminIcon />} label="Admin" active={isActive('/admin')} collapsed={collapsed} />
          </div>
        </aside>

        {/* ── Main Content ── */}
        <main style={{ flex: 1, overflow: 'auto', background: 'var(--bg-primary)' }}>
          {children}
        </main>
      </div>

      {/* Groot floating chat widget */}
      <GrootChatWidget />

      {/* Settings modal */}
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />

      {/* Docs modal (GitBook-style) */}
      <DocsModal open={docsOpen} onClose={() => setDocsOpen(false)} />
    </div>
  )
}

/* ─── Public (pre-login) NavBar ─── */
function PublicNavBar({ hydrated }: { hydrated: boolean }) {
  const { theme, toggle } = useTheme()
  return (
    <nav className="fixed top-0 left-0 right-0 z-40 glass" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <div className="mx-auto max-w-6xl flex items-center justify-between px-5 h-12">
        <Link href="/" className="flex items-center gap-2.5 group" style={{ textDecoration: 'none' }}>
          <img src="/refi-logo.png" alt="REFINET" className="w-6 h-6 rounded-full group-hover:scale-110 transition-transform" />
          <span className="text-sm font-semibold tracking-wide" style={{ color: 'var(--text-primary)' }}>
            REFINET<span style={{ color: 'var(--refi-teal)' }}> Cloud</span>
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <button
            onClick={toggle}
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ color: 'var(--text-secondary)', background: 'none', border: 'none', cursor: 'pointer' }}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
          <Link href="/settings/" className="btn-primary !py-1.5 !px-4 !text-xs !rounded-lg" style={{ textDecoration: 'none' }}>
            Get Started
          </Link>
        </div>
      </div>
    </nav>
  )
}

/* ─── Sidebar Item (uses Next.js Link) ─── */
function SidebarItem({ href, icon, label, active, collapsed }: {
  href: string; icon: React.ReactNode; label: string; active: boolean; collapsed: boolean
}) {
  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: collapsed ? '8px 0' : '7px 12px',
        justifyContent: collapsed ? 'center' : 'flex-start',
        borderRadius: 8,
        fontSize: 13,
        fontWeight: active ? 600 : 400,
        color: active ? 'var(--refi-teal)' : 'var(--text-secondary)',
        background: active ? 'var(--refi-teal-glow)' : 'transparent',
        textDecoration: 'none',
        transition: 'all 0.15s ease',
        marginBottom: 2,
        position: 'relative',
      }}
      onMouseEnter={e => {
        if (!active) { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.color = 'var(--text-primary)' }
      }}
      onMouseLeave={e => {
        if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-secondary)' }
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 20, height: 20, flexShrink: 0 }}>
        {icon}
      </span>
      {!collapsed && <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>}
      {active && (
        <span style={{
          position: 'absolute',
          left: 0,
          top: '50%',
          transform: 'translateY(-50%)',
          width: 3,
          height: 16,
          borderRadius: '0 3px 3px 0',
          background: 'var(--refi-teal)',
        }} />
      )}
    </Link>
  )
}

/* ─── Sidebar Button (for modal triggers) ─── */
function SidebarButton({ icon, label, active, collapsed, onClick }: {
  icon: React.ReactNode; label: string; active: boolean; collapsed: boolean; onClick: () => void
}) {
  return (
    <button
      title={collapsed ? label : undefined}
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: collapsed ? '8px 0' : '7px 12px',
        justifyContent: collapsed ? 'center' : 'flex-start',
        borderRadius: 8,
        fontSize: 13,
        fontWeight: active ? 600 : 400,
        color: active ? 'var(--refi-teal)' : 'var(--text-secondary)',
        background: active ? 'var(--refi-teal-glow)' : 'transparent',
        border: 'none',
        cursor: 'pointer',
        transition: 'all 0.15s ease',
        marginBottom: 2,
        width: '100%',
        fontFamily: 'inherit',
      }}
      onMouseEnter={e => {
        if (!active) { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.color = 'var(--text-primary)' }
      }}
      onMouseLeave={e => {
        if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-secondary)' }
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 20, height: 20, flexShrink: 0 }}>
        {icon}
      </span>
      {!collapsed && <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>}
    </button>
  )
}

/* ─── Top Bar Icon Link (uses Next.js Link) ─── */
function TopBarIcon({ href, label, active, children }: { href: string; label: string; active: boolean; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      title={label}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        width: 32, height: 32, borderRadius: 6, textDecoration: 'none',
        color: active ? 'var(--refi-teal)' : 'var(--text-tertiary)',
        background: active ? 'var(--refi-teal-glow)' : 'transparent',
        transition: 'all 0.15s',
      }}
      onMouseEnter={e => { if (!active) { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.color = 'var(--text-secondary)' }}}
      onMouseLeave={e => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-tertiary)' }}}
    >
      {children}
    </Link>
  )
}

/* ─── Icons ─── */
function SunIcon() { return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg> }
function MoonIcon() { return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg> }

function DashboardIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg> }
function ChatIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> }
function DevicesIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2M9 2v2M15 20v2M9 20v2M2 15h2M2 9h2M20 15h2M20 9h2"/></svg> }
function WebhooksIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 16.98h1.67c1.47 0 2.68-1.2 2.68-2.68V7.35c0-1.47-1.2-2.68-2.68-2.68H4.33C2.87 4.67 1.67 5.87 1.67 7.35v6.95c0 1.47 1.2 2.68 2.68 2.68H6"/><polyline points="12 15 17 20 12 25"/></svg> }
function KnowledgeIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg> }
function ProjectsIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg> }
function RegistryIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg> }
function RepoIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg> }
function StoreIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 2L3 7v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7l-3-5z"/><line x1="3" y1="7" x2="21" y2="7"/><path d="M16 11a4 4 0 0 1-8 0"/></svg> }
function DocsIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg> }
function AdminIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> }
