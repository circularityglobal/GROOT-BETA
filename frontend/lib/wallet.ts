/**
 * REFINET Cloud — Extensible Wallet Configuration
 * Supports: Native (injected), Coinbase Wallet, WalletConnect, and admin-configured providers.
 * Hardware wallets (DCENT, Trezor, Ledger) connect via WalletConnect bridge.
 *
 * IMPORTANT: wagmiConfig is created at module scope. All code paths must be
 * SSR-safe and must never throw — a crash here kills the entire app.
 */

import { http, createConfig, createStorage, cookieStorage } from 'wagmi'
import { defineChain } from 'viem'
import { mainnet, polygon, arbitrum, optimism, base, sepolia, avalancheFuji } from 'wagmi/chains'
import { injected, coinbaseWallet } from 'wagmi/connectors'

// XDC Network (Mainnet) — chain ID 50
export const xdc = defineChain({
  id: 50,
  name: 'XDC Network',
  nativeCurrency: { name: 'XDC', symbol: 'XDC', decimals: 18 },
  rpcUrls: {
    default: { http: ['https://rpc.xinfin.network'] },
  },
  blockExplorers: {
    default: { name: 'XDC Explorer', url: 'https://explorer.xinfin.network' },
  },
})

// Chains supported by REFINET Cloud SIWE authentication
// XDC mainnet is primary, Avalanche Fuji for testing
export const supportedChains = [xdc, avalancheFuji, mainnet, polygon, arbitrum, optimism, base, sepolia] as const

// Default chain for SIWE auth — Avalanche Fuji for testing, XDC for production
export const DEFAULT_CHAIN_ID = 43113 // Avalanche Fuji (testing)
// export const DEFAULT_CHAIN_ID = 50 // XDC Network (production)

/**
 * Wallet provider configuration — stored in localStorage by admin dashboard.
 * Admins can toggle providers and set WalletConnect projectId.
 */
export interface WalletProviderConfig {
  injected: boolean
  coinbaseWallet: boolean
  walletConnect: boolean
  walletConnectProjectId: string
}

const DEFAULT_PROVIDER_CONFIG: WalletProviderConfig = {
  injected: true,
  coinbaseWallet: true,
  walletConnect: true,
  walletConnectProjectId: '',
}

/**
 * Load wallet provider configuration from localStorage (set by admin dashboard).
 * Falls back to defaults if not configured. Never throws.
 */
export function getProviderConfig(): WalletProviderConfig {
  if (typeof window === 'undefined') return DEFAULT_PROVIDER_CONFIG
  try {
    const stored = localStorage.getItem('refinet_wallet_providers')
    if (stored) {
      const parsed = JSON.parse(stored)
      return { ...DEFAULT_PROVIDER_CONFIG, ...parsed }
    }
  } catch {
    // Corrupted localStorage — reset to defaults
  }
  return DEFAULT_PROVIDER_CONFIG
}

/**
 * Save wallet provider configuration (called by admin dashboard).
 */
export function saveProviderConfig(config: Partial<WalletProviderConfig>): void {
  if (typeof window === 'undefined') return
  const current = getProviderConfig()
  const merged = { ...current, ...config }
  localStorage.setItem('refinet_wallet_providers', JSON.stringify(merged))
}

/**
 * Build wagmi connectors. Must be SSR-safe and never throw.
 * WalletConnect is loaded lazily only when projectId is configured.
 */
function buildConnectors() {
  const config = getProviderConfig()
  const connectors: any[] = []

  try {
    // Injected wallets (MetaMask, Brave, Phantom, all EIP-6963)
    if (config.injected) {
      connectors.push(
        injected({ shimDisconnect: true })
      )
    }

    // Coinbase Wallet — direct SDK, no external deps
    if (config.coinbaseWallet) {
      connectors.push(
        coinbaseWallet({
          appName: 'REFINET Cloud',
          appLogoUrl: typeof window !== 'undefined'
            ? `${window.location.origin}/refi-logo.png`
            : '/refi-logo.png',
        })
      )
    }

    // WalletConnect v2 — lazy import to avoid SSR crashes and missing-dep crashes.
    if (config.walletConnect && config.walletConnectProjectId && typeof window !== 'undefined') {
      try {
        const { walletConnect } = require('wagmi/connectors')
        connectors.push(
          walletConnect({
            projectId: config.walletConnectProjectId,
            metadata: {
              name: 'REFINET Cloud',
              description: 'Sovereign AI Infrastructure — Your Keys, Your Data',
              url: window.location.origin,
              icons: [`${window.location.origin}/refi-logo.png`],
            },
            showQrModal: true,
          })
        )
      } catch {
        console.warn('[REFINET] WalletConnect connector unavailable — install @walletconnect/ethereum-provider to enable')
      }
    }
  } catch {
    return [injected({ shimDisconnect: true })]
  }

  if (connectors.length === 0) {
    connectors.push(injected({ shimDisconnect: true }))
  }

  return connectors
}

// Create wagmi config
function createWagmiConfig() {
  try {
    return createConfig({
      chains: supportedChains,
      connectors: buildConnectors(),
      storage: createStorage({
        storage: typeof window !== 'undefined' ? cookieStorage : undefined,
      }),
      ssr: true,
      transports: {
        [xdc.id]: http(),
        [avalancheFuji.id]: http(),
        [mainnet.id]: http(),
        [polygon.id]: http(),
        [arbitrum.id]: http(),
        [optimism.id]: http(),
        [base.id]: http(),
        [sepolia.id]: http(),
      },
    })
  } catch (e) {
    console.error('[REFINET] Failed to create wagmi config, using minimal fallback:', e)
    return createConfig({
      chains: supportedChains,
      connectors: [injected({ shimDisconnect: true })],
      storage: createStorage({
        storage: typeof window !== 'undefined' ? cookieStorage : undefined,
      }),
      ssr: true,
      transports: {
        [xdc.id]: http(),
        [avalancheFuji.id]: http(),
        [mainnet.id]: http(),
        [polygon.id]: http(),
        [arbitrum.id]: http(),
        [optimism.id]: http(),
        [base.id]: http(),
        [sepolia.id]: http(),
      },
    })
  }
}

export const wagmiConfig = createWagmiConfig()

/**
 * Wallet provider metadata for display in the UI.
 */
export const WALLET_PROVIDER_INFO = {
  injected: {
    name: 'Browser Wallets',
    description: 'MetaMask, Brave, Phantom, and all injected wallets',
    alwaysAvailable: true,
  },
  coinbaseWallet: {
    name: 'Coinbase Wallet',
    description: 'Coinbase Wallet browser extension and mobile app',
    alwaysAvailable: true,
  },
  walletConnect: {
    name: 'WalletConnect',
    description: 'Mobile wallets, DCENT, Trezor, Ledger, and 300+ wallets via QR code',
    alwaysAvailable: false,
    requiresConfig: 'walletConnectProjectId',
  },
} as const
