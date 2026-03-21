'use client'

import { useState, useEffect } from 'react'
import { API_URL } from '@/lib/config'
import { useAdmin } from '../layout'
import { PageHeader, LoadingState } from '../shared'

export default function AdminWallets() {
  const { headers } = useAdmin()

  return (
    <div>
      <PageHeader title="Wallets" subtitle="GROOT wallet, pending actions, and wallet provider configuration" />
      <div className="space-y-6">
        <GrootWalletPanel headers={headers} />
        <PendingActionsPanel headers={headers} />
        <WalletProviderPanel />
      </div>
    </div>
  )
}

/* ─── GROOT Wallet Panel ─── */
function GrootWalletPanel({ headers }: { headers: Record<string, string> }) {
  const [wallet, setWallet] = useState<any>(null)
  const [balances, setBalances] = useState<Record<string, any>>({})
  const [transactions, setTransactions] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [balanceChain, setBalanceChain] = useState('base')

  useEffect(() => {
    fetch(`${API_URL}/admin/wallet`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { setWallet(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const fetchBalance = async (chain: string) => {
    try {
      const resp = await fetch(`${API_URL}/admin/wallet/balance/${chain}`, { headers })
      if (resp.ok) { const data = await resp.json(); setBalances(prev => ({ ...prev, [chain]: data })) }
    } catch {}
  }
  const fetchTransactions = async () => {
    try {
      const resp = await fetch(`${API_URL}/admin/wallet/transactions?limit=20`, { headers })
      if (resp.ok) setTransactions(await resp.json())
    } catch {}
  }

  if (loading) return <div className="card p-6" style={{ border: '1px solid var(--border-subtle)' }}><p style={{ color: 'var(--text-muted)' }}>Loading GROOT wallet...</p></div>
  if (!wallet) return (
    <div className="card p-6" style={{ border: '1px solid var(--border-subtle)' }}>
      <h3 style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>GROOT Wallet</h3>
      <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
        GROOT wallet not initialized. Run <code style={{ background: 'var(--bg-subtle)', padding: '2px 6px', borderRadius: 4 }}>python scripts/init_groot_wallet.py</code>
      </p>
    </div>
  )

  return (
    <div className="card p-6" style={{ border: '1px solid var(--border-subtle)' }}>
      <h3 style={{ fontWeight: 700, fontSize: 16, marginBottom: 12 }}>GROOT Wallet (The Wizard)</h3>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13 }}>
        <div><span style={{ color: 'var(--text-muted)' }}>Address:</span> <code style={{ color: 'var(--refi-teal)' }}>{wallet.address}</code></div>
        <div><span style={{ color: 'var(--text-muted)' }}>Chain ID:</span> {wallet.chain_id}</div>
        <div><span style={{ color: 'var(--text-muted)' }}>Threshold:</span> {wallet.threshold}-of-{wallet.share_count} SSS</div>
        <div><span style={{ color: 'var(--text-muted)' }}>Created:</span> {wallet.created_at?.slice(0, 10)}</div>
      </div>
      <div style={{ marginTop: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
        <select value={balanceChain} onChange={e => setBalanceChain(e.target.value)}
          style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px', fontSize: 12 }}>
          {['base', 'ethereum', 'sepolia', 'polygon', 'arbitrum', 'optimism'].map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button onClick={() => fetchBalance(balanceChain)}
          style={{ background: 'var(--refi-teal)', color: '#000', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer' }}>
          Check Balance
        </button>
        <button onClick={fetchTransactions}
          style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer' }}>
          Load Transactions
        </button>
      </div>
      {Object.entries(balances).map(([chain, bal]: [string, any]) => (
        <div key={chain} style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
          {chain}: <span style={{ color: '#4ade80', fontWeight: 600 }}>{bal.balance_eth} ETH</span>
        </div>
      ))}
      {transactions && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
            Deployments: {transactions.deployments?.length || 0} | Pending Actions: {transactions.pending_actions?.length || 0}
          </p>
          {transactions.deployments?.slice(0, 5).map((d: any) => (
            <div key={d.id} style={{ fontSize: 11, color: 'var(--text-muted)', padding: '2px 0' }}>
              {d.chain} | {d.contract_address?.slice(0, 14)}... | {d.ownership_status} | {d.created_at?.slice(0, 10)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ─── Pending Actions Panel ─── */
function PendingActionsPanel({ headers }: { headers: Record<string, string> }) {
  const [actions, setActions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [note, setNote] = useState('')

  const fetchActions = async () => {
    try {
      const resp = await fetch(`${API_URL}/pipeline/admin/pending-actions?status=pending`, { headers })
      if (resp.ok) setActions(await resp.json())
    } catch {}
    setLoading(false)
  }
  useEffect(() => { fetchActions() }, [])

  const approve = async (id: string) => {
    await fetch(`${API_URL}/pipeline/admin/pending-actions/${id}/approve`, { method: 'POST', headers, body: JSON.stringify({ note }) })
    setNote(''); fetchActions()
  }
  const reject = async (id: string) => {
    await fetch(`${API_URL}/pipeline/admin/pending-actions/${id}/reject`, { method: 'POST', headers, body: JSON.stringify({ note: note || 'Rejected by admin' }) })
    setNote(''); fetchActions()
  }

  return (
    <div className="card p-6" style={{ border: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ fontWeight: 700, fontSize: 16 }}>Pending Actions (Tier 2 Approvals)</h3>
        <button onClick={fetchActions}
          style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer' }}>
          Refresh
        </button>
      </div>
      {loading && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading...</p>}
      {!loading && actions.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No pending actions. GROOT is idle.</p>}
      {actions.map((a: any) => (
        <div key={a.id} style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12, marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontWeight: 600, fontSize: 13 }}>{a.action_type}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>{a.target_chain}</span>
              {a.target_address && <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>{a.target_address?.slice(0, 14)}...</span>}
            </div>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{a.created_at?.slice(0, 16)}</span>
          </div>
          {a.payload && (
            <details style={{ marginTop: 6 }}>
              <summary style={{ fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer' }}>Payload</summary>
              <pre style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, background: 'var(--bg-subtle)', padding: 8, borderRadius: 4, overflow: 'auto' }}>
                {JSON.stringify(a.payload, null, 2)}
              </pre>
            </details>
          )}
          <div style={{ marginTop: 8, display: 'flex', gap: 6, alignItems: 'center' }}>
            <input value={note} onChange={e => setNote(e.target.value)} placeholder="Note (optional)"
              style={{ flex: 1, background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px', fontSize: 11 }} />
            <button onClick={() => approve(a.id)}
              style={{ background: '#22c55e', color: 'white', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
              Approve
            </button>
            <button onClick={() => reject(a.id)}
              style={{ background: '#ef4444', color: 'white', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ─── Wallet Provider Panel ─── */
function WalletProviderPanel() {
  const [config, setConfig] = useState({ injected: true, coinbaseWallet: true, walletConnect: true, walletConnectProjectId: '' })
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    try {
      const stored = localStorage.getItem('refinet_wallet_providers')
      if (stored) { const parsed = JSON.parse(stored); setConfig(prev => ({ ...prev, ...parsed })) }
    } catch {}
  }, [])

  const handleSave = () => {
    localStorage.setItem('refinet_wallet_providers', JSON.stringify(config))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const providers = [
    { key: 'injected' as const, name: 'Browser Wallets (Injected)', desc: 'MetaMask, Brave Wallet, Phantom, and all EIP-6963 compatible browser extensions', alwaysOn: true },
    { key: 'coinbaseWallet' as const, name: 'Coinbase Wallet', desc: 'Coinbase Wallet browser extension and mobile app via direct SDK', alwaysOn: false },
    { key: 'walletConnect' as const, name: 'WalletConnect v2', desc: 'Mobile wallets (Trust, Rainbow, Argent), hardware wallets (DCENT, Trezor, Ledger), and 300+ wallets via QR code', alwaysOn: false, requiresConfig: true },
  ]

  return (
    <div className="card p-6" style={{ border: '1px solid var(--border-subtle)' }}>
      <h3 className="text-base font-bold mb-1" style={{ color: 'var(--text-primary)' }}>Wallet Providers</h3>
      <p className="text-xs mb-4" style={{ color: 'var(--text-tertiary)' }}>Configure which wallet connection methods are available on the login page.</p>

      <div className="space-y-3 mb-4">
        {providers.map(p => (
          <div key={p.key} className="p-3 rounded-lg" style={{ border: `1px solid ${config[p.key] ? 'var(--refi-teal)' : 'var(--border-subtle)'}`, opacity: config[p.key] ? 1 : 0.7 }}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{p.name}</div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{p.desc}</div>
              </div>
              <label className="flex items-center cursor-pointer">
                <input type="checkbox" checked={config[p.key]} disabled={p.alwaysOn}
                  onChange={e => setConfig(prev => ({ ...prev, [p.key]: e.target.checked }))} className="sr-only" />
                <div className="w-10 h-5 rounded-full transition-colors relative"
                  style={{ background: config[p.key] ? 'var(--refi-teal)' : 'var(--bg-tertiary)' }}>
                  <div className="absolute top-0.5 w-4 h-4 rounded-full transition-transform"
                    style={{ background: 'white', transform: config[p.key] ? 'translateX(22px)' : 'translateX(2px)' }} />
                </div>
              </label>
            </div>
            {p.requiresConfig && config.walletConnect && (
              <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                <label className="text-[10px] block mb-1 font-mono" style={{ color: 'var(--text-tertiary)' }}>WALLETCONNECT PROJECT ID</label>
                <input type="text" value={config.walletConnectProjectId}
                  onChange={e => setConfig(prev => ({ ...prev, walletConnectProjectId: e.target.value }))}
                  placeholder="Get from cloud.walletconnect.com"
                  className="w-full px-2 py-1.5 text-xs rounded font-mono"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'var(--text-primary)', outline: 'none' }} />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button onClick={handleSave} className="px-4 py-2 text-xs font-semibold rounded-lg"
          style={{ background: 'var(--refi-teal)', color: '#000', cursor: 'pointer' }}>
          Save Configuration
        </button>
        {saved && <span className="text-xs" style={{ color: 'var(--success)' }}>Saved</span>}
        {config.walletConnect && !config.walletConnectProjectId && (
          <span className="text-xs" style={{ color: '#fbbf24' }}>WalletConnect requires a project ID</span>
        )}
      </div>
    </div>
  )
}
