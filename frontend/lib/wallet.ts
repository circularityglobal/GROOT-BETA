/**
 * REFINET Cloud — Native Wallet Configuration
 * Pure wagmi setup for multi-wallet SIWE authentication.
 * No WalletConnect dependency — direct browser wallet injection only.
 * Supports: MetaMask, Coinbase Wallet, Brave, Phantom, and all EIP-6963 injected wallets.
 */

import { http, createConfig, createStorage, cookieStorage } from 'wagmi'
import { mainnet, polygon, arbitrum, optimism, base, sepolia } from 'wagmi/chains'
import { injected, coinbaseWallet } from 'wagmi/connectors'

// Chains supported by REFINET Cloud SIWE authentication
export const supportedChains = [mainnet, polygon, arbitrum, optimism, base, sepolia] as const

// Create wagmi config with native connectors only (no WalletConnect)
export const wagmiConfig = createConfig({
  chains: supportedChains,
  connectors: [
    injected({
      shimDisconnect: true,
    }),
    coinbaseWallet({
      appName: 'REFINET Cloud',
      appLogoUrl: typeof window !== 'undefined'
        ? `${window.location.origin}/refi-logo.png`
        : '/refi-logo.png',
    }),
  ],
  storage: createStorage({
    storage: typeof window !== 'undefined' ? cookieStorage : undefined,
  }),
  ssr: true,
  transports: {
    [mainnet.id]: http(),
    [polygon.id]: http(),
    [arbitrum.id]: http(),
    [optimism.id]: http(),
    [base.id]: http(),
    [sepolia.id]: http(),
  },
})
