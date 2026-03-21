'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { API_URL } from '@/lib/config'
import { DEFAULT_CHAIN_ID } from '@/lib/wallet'
import WalletOnboarding from '@/components/WalletOnboarding'

type AuthStep = 'connect' | 'onboarding' | 'complete'
type AuthTab = 'connect' | 'create'

// Detected wallet providers via EIP-6963 or window.ethereum
interface DetectedWallet {
  name: string
  icon: React.ReactNode
  color: string
  provider: any // EIP-1193 provider
}

// Default chain name for display
const CHAIN_NAMES: Record<number, string> = {
  50: 'XDC Network',
  43113: 'Avalanche Fuji',
}

// Real brand logos as accurate SVGs
const WALLET_ICONS: Record<string, { color: string; icon: React.ReactNode; desc: string }> = {
  metamask: {
    color: '#F6851B',
    desc: 'Browser extension',
    icon: (
      <svg width="28" height="28" viewBox="0 0 318.6 318.6" fill="none">
        <path d="M274.1 35.5l-99.5 73.9L193 65.8z" fill="#E2761B" stroke="#E2761B" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M44.4 35.5l98.7 74.6-17.5-44.3zm193.9 171.3l-26.5 40.6 56.7 15.6 16.3-55.3zm-204.4.9L50.1 263l56.7-15.6-26.5-40.6z" fill="#E4761B" stroke="#E4761B" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M103.6 138.2l-15.8 23.9 56.3 2.5-2-60.5zm111.3 0l-39.8-35L174 164.6l56.2-2.5zm-108 95L142.1 210l-34.1-26.6zm71.1-23.3l25.3 23.3-5.6-49.9z" fill="#E4761B" stroke="#E4761B" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M211.8 233.2l-25.3-23.3 2 16.8-.2 7.1zm-123.5 0l23.6.6-.2-7.1 2-16.8z" fill="#D7C1B3" stroke="#D7C1B3" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M112.6 193l-32.9-9.7 23.2-10.6zm93.4 0l9.7-20.3 23.3 10.6z" fill="#233447" stroke="#233447" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M88.3 233.2l14-40.6-26.5.8zm127.9-40.6l14 40.6 12.5-39.8zM230 162.1l-56.2 2.5 5.2 28.9 9.7-20.3 23.3 10.6zm-150.3 23.7l23.2-10.6 9.7 20.3 5.2-28.9-56.2-2.5z" fill="#CD6116" stroke="#CD6116" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M87.8 162.1l23.6 46-.8-22.9zm143.1 23.1l-.9 22.9 23.6-46zm-86.9-20.6l-5.2 28.9 6.6 34.1 1.5-44.9zm30.6 0l-2.9 18 1.2 45 6.7-34.1z" fill="#E4751F" stroke="#E4751F" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M186.2 193l-6.7 34.1 4.8 3.3 29.4-22.9.9-22.9zm-106.5-9.7l.8 22.9 29.4 22.9 4.8-3.3-6.6-34.1z" fill="#F6851B" stroke="#F6851B" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M88.3 233.2l23.6.6-.2-7.1 2-16.8-25.4 23.3zm141.9 0l-25.3-23.3 2 16.8-.2 7.1z" fill="#C0AD9E" stroke="#C0AD9E" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M274.1 35.5L193 65.8l18.6 43.5 56.2-2.5 15.8-23.9-40-24.7zm-229.7 0l40.1 24.7-15.8 23.9 56.2 2.5L143 22.8z" fill="#763D16" stroke="#763D16" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  rabby: {
    color: '#7084FF',
    desc: 'Multi-chain browser wallet',
    icon: (
      <svg width="28" height="28" viewBox="0 0 256 256" fill="none">
        <rect width="256" height="256" rx="48" fill="#7C85F2"/>
        <path d="M80 100c0-22 18-40 40-40h16c22 0 40 18 40 40v8c0 22-18 40-40 40h-16c-22 0-40-18-40-40v-8z" fill="white"/>
        <circle cx="112" cy="104" r="10" fill="#7C85F2"/>
        <circle cx="144" cy="104" r="10" fill="#7C85F2"/>
        <path d="M96 156c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16v24c0 8.8-7.2 16-16 16h-32c-8.8 0-16-7.2-16-16v-24z" fill="white"/>
      </svg>
    ),
  },
  coinbase: {
    color: '#0052FF',
    desc: 'Extension & mobile app',
    icon: (
      <svg width="28" height="28" viewBox="0 0 256 256" fill="none">
        <rect width="256" height="256" rx="48" fill="#0052FF"/>
        <circle cx="128" cy="128" r="80" fill="white"/>
        <rect x="104" y="104" width="48" height="48" rx="8" fill="#0052FF"/>
      </svg>
    ),
  },
  trust: {
    color: '#0500FF',
    desc: 'Multi-chain mobile wallet',
    icon: (
      <svg width="28" height="28" viewBox="0 0 256 256" fill="none">
        <rect width="256" height="256" rx="48" fill="#0500FF"/>
        <path d="M128 48c-36 0-64 16-64 16v72c0 48 64 72 64 72s64-24 64-72V64s-28-16-64-16z" fill="none" stroke="white" strokeWidth="16" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  phantom: {
    color: '#AB9FF2',
    desc: 'Multi-chain wallet',
    icon: (
      <svg width="28" height="28" viewBox="0 0 256 256" fill="none">
        <rect width="256" height="256" rx="48" fill="#AB9FF2"/>
        <path d="M72 148c0-44 36-80 80-80h24c11 0 20 9 20 20v72c0 11-9 20-20 20H96c-13.3 0-24-10.7-24-24v-8z" fill="white"/>
        <circle cx="112" cy="128" r="10" fill="#AB9FF2"/>
        <circle cx="148" cy="128" r="10" fill="#AB9FF2"/>
      </svg>
    ),
  },
  dcent: {
    color: '#00D4AA',
    desc: 'Biometric hardware wallet',
    icon: (
      <svg width="28" height="28" viewBox="0 0 256 256" fill="none">
        <rect width="256" height="256" rx="48" fill="#1A1A2E"/>
        <path d="M128 48L68 88v80l60 40 60-40V88l-60-40z" fill="none" stroke="#00D4AA" strokeWidth="12" strokeLinejoin="round"/>
        <circle cx="128" cy="128" r="24" fill="#00D4AA"/>
      </svg>
    ),
  },
  trezor: {
    color: '#00854D',
    desc: 'Hardware security wallet',
    icon: (
      <svg width="28" height="28" viewBox="0 0 256 256" fill="none">
        <rect width="256" height="256" rx="48" fill="#00854D"/>
        <path d="M128 56c-24 0-44 20-44 44v20h-8c-4.4 0-8 3.6-8 8v64c0 4.4 3.6 8 8 8h104c4.4 0 8-3.6 8-8v-64c0-4.4-3.6-8-8-8h-8v-20c0-24-20-44-44-44zm0 20c13.3 0 24 10.7 24 24v20H104v-20c0-13.3 10.7-24 24-24z" fill="white"/>
      </svg>
    ),
  },
  ledger: {
    color: '#000000',
    desc: 'Hardware security wallet',
    icon: (
      <svg width="28" height="28" viewBox="0 0 256 256" fill="none">
        <rect width="256" height="256" rx="48" fill="#000"/>
        <path d="M60 60h56v136H60V60z" fill="white"/>
        <path d="M140 60h56v56h-56V60z" fill="white"/>
        <path d="M140 140h56v56h-56v-56z" fill="white"/>
      </svg>
    ),
  },
  okx: {
    color: '#000000',
    desc: 'Multi-chain Web3 wallet',
    icon: (
      <svg width="28" height="28" viewBox="0 0 256 256" fill="none">
        <rect width="256" height="256" rx="48" fill="#000"/>
        <rect x="60" y="60" width="52" height="52" rx="4" fill="white"/>
        <rect x="144" y="60" width="52" height="52" rx="4" fill="white"/>
        <rect x="60" y="144" width="52" height="52" rx="4" fill="white"/>
        <rect x="102" y="102" width="52" height="52" rx="4" fill="white"/>
        <rect x="144" y="144" width="52" height="52" rx="4" fill="white"/>
      </svg>
    ),
  },
  brave: {
    color: '#FB542B',
    desc: 'Built-in browser wallet',
    icon: (
      <svg width="28" height="28" viewBox="0 0 256 256" fill="none">
        <rect width="256" height="256" rx="48" fill="#FB542B"/>
        <path d="M128 40L72 72l8 24-12 16 16 8-4 20 20 16v40l28 16 28-16v-40l20-16-4-20 16-8-12-16 8-24-56-32z" fill="white"/>
      </svg>
    ),
  },
  default: {
    color: 'var(--refi-teal)',
    desc: 'Direct connection',
    icon: (
      <svg width="28" height="28" viewBox="0 0 256 256" fill="none">
        <rect width="256" height="256" rx="48" fill="#1A1A2E"/>
        <rect x="40" y="72" width="176" height="112" rx="16" fill="none" stroke="#5CE0D2" strokeWidth="12"/>
        <circle cx="164" cy="128" r="16" fill="#5CE0D2"/>
        <path d="M40 104h176" stroke="#5CE0D2" strokeWidth="12"/>
      </svg>
    ),
  },
}

function getWalletIcon(name: string) {
  const n = name.toLowerCase()
  if (n.includes('metamask')) return WALLET_ICONS.metamask
  if (n.includes('rabby')) return WALLET_ICONS.rabby
  if (n.includes('coinbase')) return WALLET_ICONS.coinbase
  if (n.includes('trust')) return WALLET_ICONS.trust
  if (n.includes('phantom')) return WALLET_ICONS.phantom
  if (n.includes('dcent') || n.includes("d'cent")) return WALLET_ICONS.dcent
  if (n.includes('trezor')) return WALLET_ICONS.trezor
  if (n.includes('ledger')) return WALLET_ICONS.ledger
  if (n.includes('okx')) return WALLET_ICONS.okx
  if (n.includes('brave')) return WALLET_ICONS.brave
  return WALLET_ICONS.default
}

/**
 * Detect all available wallet providers.
 * Uses EIP-6963 (multi-wallet discovery) with fallback to window.ethereum.
 */
function detectWallets(): DetectedWallet[] {
  if (typeof window === 'undefined') return []

  const wallets: DetectedWallet[] = []
  const seen = new Set<string>()

  // Check for EIP-6963 providers (modern multi-wallet standard)
  const eip6963Providers = (window as any).__eip6963_providers || []
  for (const p of eip6963Providers) {
    const name = p.info?.name || 'Unknown Wallet'
    if (seen.has(name.toLowerCase())) continue
    seen.add(name.toLowerCase())
    const brand = getWalletIcon(name)
    wallets.push({ name, icon: brand.icon, color: brand.color, provider: p.provider })
  }

  // Detect provider name from EIP-1193 flags
  function identifyProvider(p: any): string {
    if (p.isRabby) return 'Rabby Wallet'
    if (p.isMetaMask) return 'MetaMask'
    if (p.isCoinbaseWallet) return 'Coinbase Wallet'
    if (p.isBraveWallet) return 'Brave Wallet'
    if (p.isTrust || p.isTrustWallet) return 'Trust Wallet'
    if (p.isPhantom) return 'Phantom'
    if (p.isDCENT) return "D'CENT"
    if (p.isOkxWallet || p.isOKExWallet) return 'OKX Wallet'
    if (p.isTrezor) return 'Trezor'
    if (p.isLedger || p.isLedgerConnect) return 'Ledger'
    return 'Browser Wallet'
  }

  // Fallback: check window.ethereum directly
  const eth = (window as any).ethereum
  if (eth) {
    // Check for multiple providers (MetaMask + Coinbase, etc.)
    if (eth.providers && Array.isArray(eth.providers)) {
      for (const p of eth.providers) {
        const name = identifyProvider(p)
        if (seen.has(name.toLowerCase())) continue
        seen.add(name.toLowerCase())
        const brand = getWalletIcon(name)
        wallets.push({ name, icon: brand.icon, color: brand.color, provider: p })
      }
    } else if (!seen.size) {
      const name = identifyProvider(eth)
      const brand = getWalletIcon(name)
      wallets.push({ name, icon: brand.icon, color: brand.color, provider: eth })
    }
  }

  return wallets
}

export default function AuthFlow({ onComplete }: { onComplete?: (token: string) => void }) {
  const router = useRouter()
  const prefetchedNonce = useRef<{ nonce: string } | null>(null)

  const [tab, setTab] = useState<AuthTab>('connect')
  const [step, setStep] = useState<AuthStep>('connect')
  const [error, setError] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [signing, setSigning] = useState(false)
  const [wallets, setWallets] = useState<DetectedWallet[]>([])
  const [connectedAddress, setConnectedAddress] = useState<string | null>(null)
  const activeProvider = useRef<any>(null)

  const chainId = DEFAULT_CHAIN_ID
  const chainName = CHAIN_NAMES[chainId] || `Chain ${chainId}`

  // Detect wallets + prefetch nonce on mount
  useEffect(() => {
    setWallets(detectWallets())

    // Listen for EIP-6963 announcements (wallets may announce after page load)
    const handler = () => setWallets(detectWallets())
    window.addEventListener('eip6963:announceProvider', handler)

    // Prefetch nonce for faster auth
    fetch(`${API_URL}/auth/siwe/nonce`)
      .then((r) => r.json())
      .then((data) => { prefetchedNonce.current = data })
      .catch(() => {})

    return () => window.removeEventListener('eip6963:announceProvider', handler)
  }, [])

  // Request EIP-6963 discovery
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('eip6963:requestProvider'))
    }
  }, [])

  const handleConnect = useCallback(async (wallet: DetectedWallet) => {
    setError('')
    setConnecting(true)
    activeProvider.current = wallet.provider

    try {
      // Request accounts via EIP-1193
      const accounts: string[] = await wallet.provider.request({
        method: 'eth_requestAccounts',
      })

      if (!accounts || accounts.length === 0) {
        throw new Error('No accounts returned — check your wallet')
      }

      const address = accounts[0]
      setConnectedAddress(address)

      // Try to switch to the target chain
      try {
        await wallet.provider.request({
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: `0x${chainId.toString(16)}` }],
        })
      } catch (switchErr: any) {
        // 4902 = chain not added — try adding it
        if (switchErr.code === 4902) {
          try {
            if (chainId === 43113) {
              await wallet.provider.request({
                method: 'wallet_addEthereumChain',
                params: [{
                  chainId: '0xa869',
                  chainName: 'Avalanche Fuji Testnet',
                  nativeCurrency: { name: 'AVAX', symbol: 'AVAX', decimals: 18 },
                  rpcUrls: ['https://api.avax-test.network/ext/bc/C/rpc'],
                  blockExplorerUrls: ['https://testnet.snowtrace.io/'],
                }],
              })
            } else if (chainId === 50) {
              await wallet.provider.request({
                method: 'wallet_addEthereumChain',
                params: [{
                  chainId: '0x32',
                  chainName: 'XDC Network',
                  nativeCurrency: { name: 'XDC', symbol: 'XDC', decimals: 18 },
                  rpcUrls: ['https://rpc.xinfin.network'],
                  blockExplorerUrls: ['https://explorer.xinfin.network/'],
                }],
              })
            }
          } catch {
            // User rejected chain add — proceed anyway, SIWE works cross-chain
          }
        }
        // Other switch errors are non-fatal — proceed with whatever chain the user is on
      }

      // Proceed to SIWE sign
      await handleSIWESign(address, wallet.provider)
    } catch (e: any) {
      if (e.code === 4001) {
        setError('Connection rejected — please try again')
      } else {
        setError(e.message || 'Connection failed')
      }
      setConnecting(false)
    }
  }, [chainId])

  const handleSIWESign = async (walletAddress: string, provider: any) => {
    try {
      setSigning(true)

      const nonceData = prefetchedNonce.current
        ? prefetchedNonce.current
        : await fetch(`${API_URL}/auth/siwe/nonce`).then((r) => {
            if (!r.ok) throw new Error('Failed to get nonce')
            return r.json()
          })
      prefetchedNonce.current = null

      const domain = new URL(API_URL).host
      const now = new Date().toISOString()
      const message = [
        `${domain} wants you to sign in with your Ethereum account:`,
        walletAddress,
        '',
        'Sign in to REFINET Cloud. Your Ethereum address is used as a cryptographic key component.',
        '',
        `URI: https://${domain}`,
        'Version: 1',
        `Chain ID: ${chainId}`,
        `Nonce: ${nonceData.nonce}`,
        `Issued At: ${now}`,
      ].join('\n')

      // Sign via EIP-1193 personal_sign
      const signature = await provider.request({
        method: 'personal_sign',
        params: [message, walletAddress],
      })

      const verifyResp = await fetch(`${API_URL}/auth/siwe/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          signature,
          nonce: nonceData.nonce,
          chain_id: chainId,
        }),
      })

      if (!verifyResp.ok) {
        const err = await verifyResp.json().catch(() => ({ detail: 'Verification failed' }))
        throw new Error(err.detail || 'Verification failed')
      }

      const data = await verifyResp.json()

      localStorage.setItem('refinet_token', data.access_token)
      localStorage.setItem('refinet_refresh', data.refresh_token)
      window.dispatchEvent(new Event('refinet-auth-change'))

      onComplete?.(data.access_token)
      router.push('/dashboard')
    } catch (e: any) {
      if (e.code === 4001) {
        setError('Signature rejected — please try again')
      } else {
        setError(e.message)
      }
      setConnecting(false)
      setSigning(false)
    }
  }

  const isBusy = connecting || signing

  return (
    <>
      <div className="auth-right-panel">
        {/* Logo & Header */}
        <div className="auth-header">
          <div className="auth-logo-row">
            <img src="/refi-logo.png" alt="REFINET" className="auth-logo" />
            <span className="auth-brand">
              REFINET<span className="auth-brand-accent"> Cloud</span>
            </span>
          </div>
          <h1 className="auth-title">Welcome back</h1>
          <p className="auth-subtitle">
            Connect your wallet to access sovereign AI infrastructure
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="auth-tabs">
          <button
            className={`auth-tab ${tab === 'connect' ? 'auth-tab-active' : ''}`}
            onClick={() => { setTab('connect'); setStep('connect'); setError('') }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="6" width="20" height="14" rx="3"/>
              <path d="M16 14a2 2 0 100-4 2 2 0 000 4z"/>
            </svg>
            Connect Wallet
          </button>
          <button
            className={`auth-tab ${tab === 'create' ? 'auth-tab-active' : ''}`}
            onClick={() => { setTab('create'); setError('') }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="16"/>
              <line x1="8" y1="12" x2="16" y2="12"/>
            </svg>
            Create Wallet
          </button>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="auth-error">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            <span>{error}</span>
            <button onClick={() => setError('')} className="auth-error-dismiss">&times;</button>
          </div>
        )}

        {/* ─── Connect Wallet Tab ─── */}
        {tab === 'connect' && step !== 'onboarding' && (
          <div className="auth-content">
            {/* Connected network indicator */}
            <div className="auth-section">
              <div className="auth-info-item" style={{ justifyContent: 'center', opacity: 0.6 }}>
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--success)' }} />
                <span style={{ fontSize: 11 }}>Connecting on {chainName}</span>
              </div>
            </div>

            {/* Wallet List */}
            <div className="auth-section">
              <label className="auth-label">Choose Wallet</label>
              <div className="auth-wallet-list">
                {wallets.map((wallet, i) => {
                  const brand = getWalletIcon(wallet.name)
                  return (
                    <button
                      key={`${wallet.name}-${i}`}
                      onClick={() => handleConnect(wallet)}
                      disabled={isBusy}
                      className="auth-wallet-btn"
                    >
                      <div className="auth-wallet-icon" style={{ color: brand.color }}>
                        {brand.icon}
                      </div>
                      <div className="auth-wallet-info">
                        <span className="auth-wallet-name">{wallet.name}</span>
                        <span className="auth-wallet-detail">{brand.desc}</span>
                      </div>
                      <div className="auth-wallet-arrow">
                        {isBusy ? (
                          <div className="auth-spinner" />
                        ) : (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <polyline points="9 18 15 12 9 6"/>
                          </svg>
                        )}
                      </div>
                    </button>
                  )
                })}

                {wallets.length === 0 && (
                  <div className="auth-empty-state">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ opacity: 0.4 }}>
                      <rect x="2" y="6" width="20" height="14" rx="3"/>
                      <path d="M16 14a2 2 0 100-4 2 2 0 000 4z"/>
                    </svg>
                    <p>No wallets detected</p>
                    <p className="auth-empty-hint">
                      Install <a href="https://metamask.io" target="_blank" rel="noopener noreferrer">MetaMask</a> or another browser wallet to continue
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Info */}
            <div className="auth-info">
              <div className="auth-info-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
                <span>Message signature only — no transaction, no gas fee</span>
              </div>
              <div className="auth-info-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
                <span>Your address becomes your sovereign identity</span>
              </div>
            </div>
          </div>
        )}

        {/* ─── Create Wallet Tab ─── */}
        {tab === 'create' && step !== 'onboarding' && (
          <div className="auth-content">
            <div className="auth-create-card">
              <div className="auth-create-icon">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="1.5">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <h3 className="auth-create-title">Sovereign Cloud Wallet</h3>
              <p className="auth-create-desc">
                Get started instantly with a secure, self-custodial wallet — no browser extension required.
              </p>
              <div className="auth-create-features">
                <div className="auth-feature">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  <span>Shamir Secret Sharing (3-of-5 threshold)</span>
                </div>
                <div className="auth-feature">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  <span>AES-256-GCM encrypted key storage</span>
                </div>
                <div className="auth-feature">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  <span>Email recovery — no seed phrase needed</span>
                </div>
                <div className="auth-feature">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--refi-teal)" strokeWidth="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  <span>Works across all supported networks</span>
                </div>
              </div>
              <button
                onClick={() => setStep('onboarding')}
                disabled={isBusy}
                className="auth-create-btn"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="16"/>
                  <line x1="8" y1="12" x2="16" y2="12"/>
                </svg>
                Create Free Wallet
              </button>
            </div>
          </div>
        )}

        {/* Signing overlay */}
        {signing && (
          <div className="auth-signing-overlay">
            <div className="auth-spinner-lg" />
            <p>Check your wallet to sign the authentication message...</p>
          </div>
        )}

        {/* Footer */}
        <div className="auth-footer">
          <span>Sovereign infrastructure — your keys, your data</span>
        </div>
      </div>

      {/* Wallet Onboarding Modal */}
      {step === 'onboarding' && (
        <WalletOnboarding
          chainId={chainId}
          chainName={chainName}
          onComplete={(token) => { onComplete?.(token) }}
          onCancel={() => { setStep('connect'); setTab('connect') }}
        />
      )}
    </>
  )
}
