'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { API_URL } from '@/lib/config'
import WalletOnboarding from '@/components/WalletOnboarding'

type AuthStep = 'connect' | 'onboarding' | 'complete'

interface ChainInfo {
  chain_id: number
  name: string
  short_name: string
  currency: string
  is_testnet: boolean
}

interface AuthState {
  step: AuthStep
  error: string
  connecting: boolean
  chainId: number
  chainName: string
  supportedChains: ChainInfo[]
}

const DEFAULT_CHAINS: ChainInfo[] = [
  { chain_id: 1, name: 'Ethereum', short_name: 'eth', currency: 'ETH', is_testnet: false },
  { chain_id: 137, name: 'Polygon', short_name: 'matic', currency: 'MATIC', is_testnet: false },
  { chain_id: 42161, name: 'Arbitrum One', short_name: 'arb1', currency: 'ETH', is_testnet: false },
  { chain_id: 10, name: 'Optimism', short_name: 'oeth', currency: 'ETH', is_testnet: false },
  { chain_id: 8453, name: 'Base', short_name: 'base', currency: 'ETH', is_testnet: false },
  { chain_id: 11155111, name: 'Sepolia', short_name: 'sep', currency: 'SEP', is_testnet: true },
]

export default function AuthFlow({ onComplete }: { onComplete?: (token: string) => void }) {
  const router = useRouter()
  const prefetchedNonce = useRef<{ nonce: string } | null>(null)

  const [state, setState] = useState<AuthState>({
    step: 'connect',
    error: '',
    connecting: false,
    chainId: 1,
    chainName: 'Ethereum',
    supportedChains: DEFAULT_CHAINS,
  })

  // Prefetch both chains and nonce in parallel on mount
  useEffect(() => {
    fetch(`${API_URL}/auth/chains`)
      .then((r) => r.json())
      .then((data) => {
        if (data.chains?.length) {
          setState((s) => ({ ...s, supportedChains: data.chains }))
        }
      })
      .catch(() => {})

    // Prefetch nonce so it's ready when user clicks connect
    fetch(`${API_URL}/auth/siwe/nonce`)
      .then((r) => r.json())
      .then((data) => { prefetchedNonce.current = data })
      .catch(() => {})
  }, [])

  const handleChainSelect = (chainId: number) => {
    const chain = state.supportedChains.find((c) => c.chain_id === chainId)
    setState((s) => ({
      ...s,
      chainId: chainId,
      chainName: chain?.name || `Chain ${chainId}`,
    }))
  }

  const handleSIWE = async () => {
    try {
      setState((s) => ({ ...s, error: '', connecting: true }))

      if (typeof window === 'undefined' || !(window as any).ethereum) {
        setState((s) => ({
          ...s,
          error: 'No Ethereum wallet detected. Install MetaMask to continue.',
          connecting: false,
        }))
        return
      }

      const ethereum = (window as any).ethereum

      // Request accounts and nonce in parallel
      const [accounts, nonceData] = await Promise.all([
        ethereum.request({ method: 'eth_requestAccounts' }),
        prefetchedNonce.current
          ? Promise.resolve(prefetchedNonce.current)
          : fetch(`${API_URL}/auth/siwe/nonce`).then((r) => {
              if (!r.ok) throw new Error('Failed to get nonce')
              return r.json()
            }),
      ])
      const address = accounts[0]
      // Clear prefetched nonce (single use)
      prefetchedNonce.current = null

      const domain = new URL(API_URL).host
      const now = new Date().toISOString()
      const message = [
        `${domain} wants you to sign in with your Ethereum account:`,
        address,
        '',
        'Sign in to REFINET Cloud. Your Ethereum address is used as a cryptographic key component.',
        '',
        `URI: https://${domain}`,
        'Version: 1',
        `Chain ID: ${state.chainId}`,
        `Nonce: ${nonceData.nonce}`,
        `Issued At: ${now}`,
      ].join('\n')

      const signature = await ethereum.request({
        method: 'personal_sign',
        params: [message, address],
      })

      const verifyResp = await fetch(`${API_URL}/auth/siwe/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          signature,
          nonce: nonceData.nonce,
          chain_id: state.chainId,
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
      setState((s) => ({ ...s, error: e.message, connecting: false }))
    }
  }

  // Open the wallet onboarding wizard
  const handleStartCreateWallet = () => {
    setState((s) => ({ ...s, step: 'onboarding', error: '' }))
  }

  const isBusy = state.connecting

  return (
    <>
      <div className="max-w-md mx-auto p-8">
        {state.error && (
          <div className="mb-6 p-3 bg-red-900/30 border border-red-800 rounded-lg text-sm text-red-300">
            {state.error}
          </div>
        )}

        {(state.step === 'connect' || state.step === 'onboarding') && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold mb-2" style={{ letterSpacing: '-0.02em' }}>
              Sign In with Ethereum
            </h2>
            <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
              Connect your existing wallet or create a free one instantly.
            </p>

            {/* Chain Selector */}
            <div className="mb-2">
              <label className="text-xs font-medium mb-2 block" style={{ color: 'var(--text-tertiary)' }}>
                Network
              </label>
              <div className="flex flex-wrap gap-2">
                {state.supportedChains
                  .filter((c) => !c.is_testnet)
                  .map((chain) => (
                    <button
                      key={chain.chain_id}
                      onClick={() => handleChainSelect(chain.chain_id)}
                      disabled={isBusy}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                      style={{
                        background: state.chainId === chain.chain_id ? 'var(--refi-teal-glow)' : 'var(--bg-secondary)',
                        color: state.chainId === chain.chain_id ? 'var(--refi-teal)' : 'var(--text-secondary)',
                        border: `1px solid ${state.chainId === chain.chain_id ? 'var(--refi-teal)' : 'var(--border-default)'}`,
                      }}
                    >
                      {chain.name}
                    </button>
                  ))}
                {state.supportedChains
                  .filter((c) => c.is_testnet)
                  .map((chain) => (
                    <button
                      key={chain.chain_id}
                      onClick={() => handleChainSelect(chain.chain_id)}
                      disabled={isBusy}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all opacity-60"
                      style={{
                        background: state.chainId === chain.chain_id ? 'var(--refi-teal-glow)' : 'var(--bg-secondary)',
                        color: state.chainId === chain.chain_id ? 'var(--refi-teal)' : 'var(--text-tertiary)',
                        border: `1px solid ${state.chainId === chain.chain_id ? 'var(--refi-teal)' : 'var(--border-default)'}`,
                      }}
                    >
                      {chain.name}
                    </button>
                  ))}
              </div>
            </div>

            {/* Option 1: Existing wallet */}
            <div className="card p-4 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              <p className="mb-2">Connect existing wallet:</p>
              <p>&#8226; Your wallet signs a one-time message (no transaction, no gas)</p>
              <p>&#8226; Your Ethereum address becomes your identity</p>
              <p>&#8226; Works across {state.supportedChains.filter((c) => !c.is_testnet).length} supported networks</p>
            </div>
            <button
              onClick={handleSIWE}
              disabled={isBusy}
              className="btn-primary w-full !py-3 !text-sm tracking-wider font-semibold"
              style={{ opacity: isBusy ? 0.7 : 1 }}
            >
              {state.connecting ? 'CONNECTING...' : `CONNECT WALLET ON ${state.chainName.toUpperCase()}`}
            </button>

            {/* Divider */}
            <div className="flex items-center gap-3 py-1">
              <div className="flex-1 h-px" style={{ background: 'var(--border-default)' }} />
              <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>OR</span>
              <div className="flex-1 h-px" style={{ background: 'var(--border-default)' }} />
            </div>

            {/* Option 2: Create free wallet — opens wizard */}
            <div className="card p-4 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              <p className="mb-2">No wallet? No problem:</p>
              <p>&#8226; Secured with Shamir Secret Sharing (3-of-5 threshold)</p>
              <p>&#8226; No downloads, no seed phrase to manage</p>
              <p>&#8226; Set up email recovery during onboarding</p>
            </div>
            <button
              onClick={handleStartCreateWallet}
              disabled={isBusy}
              className="w-full !py-3 !text-sm tracking-wider font-semibold rounded-lg border transition-colors"
              style={{
                opacity: isBusy ? 0.7 : 1,
                borderColor: 'var(--refi-teal)',
                color: 'var(--refi-teal)',
                background: 'transparent',
              }}
            >
              CREATE FREE WALLET
            </button>
          </div>
        )}

        {state.step === 'complete' && (
          <div className="text-center py-12">
            <div className="animate-pulse" style={{ color: 'var(--refi-teal)', fontSize: 13, fontFamily: "'JetBrains Mono', monospace" }}>
              Signing you in...
            </div>
          </div>
        )}
      </div>

      {/* Wallet Onboarding Wizard (modal overlay) */}
      {state.step === 'onboarding' && (
        <WalletOnboarding
          chainId={state.chainId}
          chainName={state.chainName}
          onComplete={(token) => {
            onComplete?.(token)
          }}
          onCancel={() => setState((s) => ({ ...s, step: 'connect' }))}
        />
      )}
    </>
  )
}
