'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useAccount, useConnect, useSignMessage, useDisconnect, Connector } from 'wagmi'
import { API_URL } from '@/lib/config'
import WalletOnboarding from '@/components/WalletOnboarding'

type AuthStep = 'connect' | 'onboarding' | 'complete'
type AuthTab = 'connect' | 'create'

interface ChainInfo {
  chain_id: number
  name: string
  short_name: string
  currency: string
  is_testnet: boolean
}

const DEFAULT_CHAINS: ChainInfo[] = [
  { chain_id: 1, name: 'Ethereum', short_name: 'eth', currency: 'ETH', is_testnet: false },
  { chain_id: 137, name: 'Polygon', short_name: 'matic', currency: 'MATIC', is_testnet: false },
  { chain_id: 42161, name: 'Arbitrum One', short_name: 'arb1', currency: 'ETH', is_testnet: false },
  { chain_id: 10, name: 'Optimism', short_name: 'oeth', currency: 'ETH', is_testnet: false },
  { chain_id: 8453, name: 'Base', short_name: 'base', currency: 'ETH', is_testnet: false },
  { chain_id: 11155111, name: 'Sepolia', short_name: 'sep', currency: 'SEP', is_testnet: true },
]

// Chain icons (minimal SVG representations)
const CHAIN_ICONS: Record<number, string> = {
  1: '⟠',      // Ethereum
  137: '⬡',    // Polygon
  42161: '◆',   // Arbitrum
  10: '◉',      // Optimism
  8453: '◈',    // Base
  11155111: '⟠', // Sepolia
}

// Wallet brand colors and icons
const WALLET_BRANDS: Record<string, { color: string; icon: React.ReactNode }> = {
  metamask: {
    color: '#F6851B',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path d="M21.3 2L13.1 8.2l1.5-3.6L21.3 2z" fill="#E2761B" stroke="#E2761B" strokeWidth="0.1"/>
        <path d="M2.7 2l8.1 6.3-1.4-3.7L2.7 2zM18.4 17.1l-2.2 3.3 4.6 1.3 1.3-4.5-3.7-.1zM1.9 17.2l1.3 4.5 4.6-1.3-2.2-3.3-3.7.1z" fill="#E4761B" stroke="#E4761B" strokeWidth="0.1"/>
        <path d="M7.5 10.7l-1.3 2 4.6.2-.2-5-3.1 2.8zM16.5 10.7l-3.2-2.9-.1 5.1 4.6-.2-1.3-2zM7.8 20.4l2.8-1.4-2.4-1.9-.4 3.3zM13.4 19l2.8 1.4-.4-3.3-2.4 1.9z" fill="#E4761B" stroke="#E4761B" strokeWidth="0.1"/>
      </svg>
    ),
  },
  coinbase: {
    color: '#0052FF',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="6" fill="#0052FF"/>
        <path d="M12 4.5a7.5 7.5 0 100 15 7.5 7.5 0 000-15zm-2.25 5.25h4.5a.75.75 0 01.75.75v3a.75.75 0 01-.75.75h-4.5a.75.75 0 01-.75-.75v-3a.75.75 0 01.75-.75z" fill="white"/>
      </svg>
    ),
  },
  walletconnect: {
    color: '#3B99FC',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="6" fill="#3B99FC"/>
        <path d="M7.2 9.6c2.6-2.6 6.9-2.6 9.5 0l.3.3a.3.3 0 010 .5l-1.1 1a.2.2 0 01-.2 0l-.5-.4a5 5 0 00-6.6 0l-.5.4a.2.2 0 01-.2 0l-1.1-1a.3.3 0 010-.5l.4-.3zm11.7 2.2l1 .9a.3.3 0 010 .5l-4.4 4.3a.4.4 0 01-.5 0l-3.1-3a.1.1 0 00-.1 0l-3.1 3a.4.4 0 01-.5 0L3.8 13.2a.3.3 0 010-.5l1-.9a.4.4 0 01.5 0l3.1 3a.1.1 0 00.1 0l3.1-3a.4.4 0 01.5 0l3.1 3a.1.1 0 00.1 0l3.1-3a.4.4 0 01.5 0z" fill="white"/>
      </svg>
    ),
  },
  dcent: {
    color: '#00D4AA',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="6" fill="#00D4AA"/>
        <path d="M12 5a7 7 0 100 14 7 7 0 000-14zm0 2a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm-3 5h6v1a3 3 0 01-6 0v-1z" fill="white"/>
      </svg>
    ),
  },
  trezor: {
    color: '#14854F',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="6" fill="#14854F"/>
        <path d="M12 4l-6 3v5c0 4.4 2.6 8.5 6 10 3.4-1.5 6-5.6 6-10V7l-6-3zm0 2.5l4 2v4c0 3.3-1.8 6.4-4 7.5-2.2-1.1-4-4.2-4-7.5v-4l4-2z" fill="white"/>
      </svg>
    ),
  },
  ledger: {
    color: '#000000',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="6" fill="#000"/>
        <path d="M5 5h5v14H5V5zm9 0h5v5h-5V5zm0 9h5v5h-5v-5z" fill="white"/>
      </svg>
    ),
  },
  default: {
    color: 'var(--refi-teal)',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="2" y="6" width="20" height="14" rx="3"/>
        <path d="M16 14a2 2 0 100-4 2 2 0 000 4z"/>
        <path d="M2 10h20"/>
      </svg>
    ),
  },
}

function getWalletBrand(connector: Connector) {
  const id = connector.id.toLowerCase()
  const name = connector.name.toLowerCase()
  if (id.includes('metamask') || id === 'io.metamask' || name.includes('metamask')) return WALLET_BRANDS.metamask
  if (id.includes('coinbase') || name.includes('coinbase')) return WALLET_BRANDS.coinbase
  if (id.includes('walletconnect') || name.includes('walletconnect')) return WALLET_BRANDS.walletconnect
  if (id.includes('dcent') || name.includes("d'cent") || name.includes('dcent')) return WALLET_BRANDS.dcent
  if (id.includes('trezor') || name.includes('trezor')) return WALLET_BRANDS.trezor
  if (id.includes('ledger') || name.includes('ledger')) return WALLET_BRANDS.ledger
  return WALLET_BRANDS.default
}

function getWalletDisplayName(connector: Connector): string {
  const name = connector.name
  if (name === 'Injected') return 'Browser Wallet'
  return name
}

export default function AuthFlow({ onComplete }: { onComplete?: (token: string) => void }) {
  const router = useRouter()
  const prefetchedNonce = useRef<{ nonce: string } | null>(null)

  const { address, isConnected } = useAccount()
  const { connectors, connect, isPending: isConnecting } = useConnect()
  const { signMessageAsync } = useSignMessage()
  const { disconnect } = useDisconnect()

  const [tab, setTab] = useState<AuthTab>('connect')
  const [step, setStep] = useState<AuthStep>('connect')
  const [error, setError] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [signing, setSigning] = useState(false)
  const [chainId, setChainId] = useState(1)
  const [chainName, setChainName] = useState('Ethereum')
  const [supportedChainsList, setSupportedChainsList] = useState<ChainInfo[]>(DEFAULT_CHAINS)
  const [showTestnets, setShowTestnets] = useState(false)

  // Prefetch chains and nonce
  useEffect(() => {
    fetch(`${API_URL}/auth/chains`)
      .then((r) => r.json())
      .then((data) => {
        if (data.chains?.length) setSupportedChainsList(data.chains)
      })
      .catch(() => {})

    fetch(`${API_URL}/auth/siwe/nonce`)
      .then((r) => r.json())
      .then((data) => { prefetchedNonce.current = data })
      .catch(() => {})
  }, [])

  // Auto-proceed to SIWE signing when wallet connects
  useEffect(() => {
    if (isConnected && address && connecting) {
      handleSIWESign(address)
    }
  }, [isConnected, address, connecting])

  const handleChainSelect = (id: number) => {
    const chain = supportedChainsList.find((c) => c.chain_id === id)
    setChainId(id)
    setChainName(chain?.name || `Chain ${id}`)
  }

  const handleConnect = useCallback((connector: Connector) => {
    setError('')
    setConnecting(true)
    try {
      connect({ connector })
    } catch (e: any) {
      setError(e.message || 'Connection failed')
      setConnecting(false)
    }
  }, [connect])

  const handleSIWESign = async (walletAddress: string) => {
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

      const signature = await signMessageAsync({ message })

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
      setError(e.message)
      setConnecting(false)
      setSigning(false)
    }
  }

  const isBusy = connecting || signing || isConnecting

  // Deduplicate connectors by name (wagmi can register duplicates)
  const seen = new Set<string>()
  const uniqueConnectors = connectors.filter((c) => {
    const key = c.name.toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })

  // All connectors are available — WalletConnect is now supported for
  // mobile wallets, hardware wallets (DCENT, Trezor, Ledger), and QR code scanning
  const walletConnectors = uniqueConnectors

  const mainnetChains = supportedChainsList.filter((c) => !c.is_testnet)
  const testnetChains = supportedChainsList.filter((c) => c.is_testnet)

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
            {/* Network Selector */}
            <div className="auth-section">
              <div className="auth-section-header">
                <label className="auth-label">Select Network</label>
                {testnetChains.length > 0 && (
                  <button
                    className="auth-testnet-toggle"
                    onClick={() => setShowTestnets(!showTestnets)}
                  >
                    {showTestnets ? 'Hide' : 'Show'} Testnets
                  </button>
                )}
              </div>
              <div className="auth-chain-grid">
                {mainnetChains.map((chain) => (
                  <button
                    key={chain.chain_id}
                    onClick={() => handleChainSelect(chain.chain_id)}
                    disabled={isBusy}
                    className={`auth-chain-btn ${chainId === chain.chain_id ? 'auth-chain-btn-active' : ''}`}
                  >
                    <span className="auth-chain-icon">{CHAIN_ICONS[chain.chain_id] || '●'}</span>
                    <span>{chain.name}</span>
                  </button>
                ))}
                {showTestnets && testnetChains.map((chain) => (
                  <button
                    key={chain.chain_id}
                    onClick={() => handleChainSelect(chain.chain_id)}
                    disabled={isBusy}
                    className={`auth-chain-btn auth-chain-btn-testnet ${chainId === chain.chain_id ? 'auth-chain-btn-active' : ''}`}
                  >
                    <span className="auth-chain-icon">{CHAIN_ICONS[chain.chain_id] || '●'}</span>
                    <span>{chain.name}</span>
                    <span className="auth-testnet-badge">testnet</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Wallet List */}
            <div className="auth-section">
              <label className="auth-label">Choose Wallet</label>
              <div className="auth-wallet-list">
                {walletConnectors.map((connector) => {
                  const brand = getWalletBrand(connector)
                  const displayName = getWalletDisplayName(connector)
                  return (
                    <button
                      key={connector.uid}
                      onClick={() => handleConnect(connector)}
                      disabled={isBusy}
                      className="auth-wallet-btn"
                    >
                      <div className="auth-wallet-icon" style={{ color: brand.color }}>
                        {brand.icon}
                      </div>
                      <div className="auth-wallet-info">
                        <span className="auth-wallet-name">{displayName}</span>
                        <span className="auth-wallet-detail">
                          {connector.id === 'injected' ? 'Browser extension' :
                           connector.id.includes('walletConnect') ? 'QR code · Mobile · Hardware wallets' :
                           connector.id.includes('coinbase') ? 'Extension & mobile app' :
                           'Direct connection'}
                        </span>
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

                {walletConnectors.length === 0 && (
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
