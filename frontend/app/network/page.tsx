'use client'

import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '@/lib/config'

interface PeerInfo {
  user_id: string
  eth_address: string
  chain_id: number
  pseudo_ipv6: string
  subnet: string
  display_name: string | null
  ens_name: string | null
  status: string
  connected_at: string | null
}

interface Stats {
  total_peers: number
  online_peers: number
  offline_peers: number
  chain_distribution: Record<string, number>
  smtp_bridge_running: boolean
}

const CHAIN_NAMES: Record<number, string> = {
  1: 'Ethereum',
  137: 'Polygon',
  42161: 'Arbitrum',
  10: 'Optimism',
  8453: 'Base',
  11155111: 'Sepolia',
}

export default function NetworkPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [peers, setPeers] = useState<PeerInfo[]>([])
  const [myPeer, setMyPeer] = useState<PeerInfo | null>(null)
  const [connected, setConnected] = useState(false)
  const [chainFilter, setChainFilter] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    setToken(localStorage.getItem('refinet_token'))
  }, [])

  const getHeaders = useCallback((): Record<string, string> => {
    const t = localStorage.getItem('refinet_token')
    return t
      ? { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' }
      : { 'Content-Type': 'application/json' }
  }, [])

  const loadStats = useCallback(() => {
    fetch(`${API_URL}/p2p/stats`)
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {})
  }, [])

  const loadPeers = useCallback(() => {
    const t = localStorage.getItem('refinet_token')
    if (!t) return
    const h = { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' }
    const url = chainFilter
      ? `${API_URL}/p2p/gossip?chain_id=${chainFilter}`
      : `${API_URL}/p2p/gossip`
    fetch(url, { headers: h })
      .then((r) => r.json())
      .then((data) => {
        setPeers(data.peers || [])
        if (data.your_peer) {
          setMyPeer(data.your_peer)
          setConnected(true)
        }
      })
      .catch(() => {})
  }, [chainFilter])

  useEffect(() => {
    loadStats()
    loadPeers()
    const interval = setInterval(() => {
      loadStats()
      loadPeers()
      if (localStorage.getItem('refinet_token') && connected) {
        fetch(`${API_URL}/p2p/heartbeat`, { method: 'POST', headers: getHeaders() }).catch(() => {})
      }
    }, 30000)
    return () => clearInterval(interval)
  }, [loadStats, loadPeers, connected, getHeaders])

  const handleConnect = async (chainId: number) => {
    const t = localStorage.getItem('refinet_token')
    if (!t) return
    setError('')
    try {
      const r = await fetch(`${API_URL}/p2p/connect?chain_id=${chainId}`, {
        method: 'POST',
        headers: getHeaders(),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: 'Connection failed' }))
        throw new Error(err.detail)
      }
      const peer = await r.json()
      setMyPeer(peer)
      setConnected(true)
      loadStats()
      loadPeers()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleDisconnect = async () => {
    if (!localStorage.getItem('refinet_token')) return
    await fetch(`${API_URL}/p2p/disconnect`, { method: 'POST', headers: getHeaders() }).catch(() => {})
    setMyPeer(null)
    setConnected(false)
    loadStats()
    loadPeers()
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold" style={{ letterSpacing: '-0.02em' }}>
        P2P Network
      </h1>

      {error && (
        <div className="p-3 bg-red-900/30 border border-red-800 rounded-lg text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Online Peers', value: stats.online_peers },
            { label: 'Total Peers', value: stats.total_peers },
            { label: 'SMTP Bridge', value: stats.smtp_bridge_running ? 'Running' : 'Stopped' },
            { label: 'Chains Active', value: Object.keys(stats.chain_distribution).length },
          ].map((s, i) => (
            <div key={i} className="card p-3 text-center">
              <div className="text-2xl font-bold" style={{ color: 'var(--refi-teal)' }}>
                {s.value}
              </div>
              <div className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                {s.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* My Peer Status */}
      {token && (
        <div className="card p-4">
          <h3 className="text-sm font-bold mb-3">Your Node</h3>
          {myPeer ? (
            <div className="space-y-1 text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
              <p>Address: {myPeer.eth_address}</p>
              <p>IPv6: {myPeer.pseudo_ipv6}</p>
              <p>Subnet: {myPeer.subnet}</p>
              <p>
                Status:{' '}
                <span style={{ color: myPeer.status === 'online' ? 'var(--refi-teal)' : 'var(--text-tertiary)' }}>
                  {myPeer.status}
                </span>
              </p>
              <button
                onClick={handleDisconnect}
                className="mt-2 px-3 py-1 rounded text-xs border"
                style={{ borderColor: 'var(--border-primary)', color: 'var(--text-secondary)' }}
              >
                Disconnect
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                Connect to the P2P network on a chain:
              </p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(CHAIN_NAMES).map(([id, name]) => (
                  <button
                    key={id}
                    onClick={() => handleConnect(Number(id))}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                    style={{
                      background: 'var(--bg-secondary)',
                      color: 'var(--text-secondary)',
                      border: '1px solid var(--border-primary)',
                    }}
                  >
                    {name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Chain Filter */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
          Filter:
        </span>
        <button
          onClick={() => setChainFilter(null)}
          className="px-2 py-1 rounded text-xs"
          style={{
            background: chainFilter === null ? 'var(--refi-teal-glow)' : 'var(--bg-secondary)',
            color: chainFilter === null ? 'var(--refi-teal)' : 'var(--text-tertiary)',
          }}
        >
          All
        </button>
        {Object.entries(CHAIN_NAMES)
          .filter(([id]) => Number(id) < 100000)
          .map(([id, name]) => (
            <button
              key={id}
              onClick={() => setChainFilter(Number(id))}
              className="px-2 py-1 rounded text-xs"
              style={{
                background: chainFilter === Number(id) ? 'var(--refi-teal-glow)' : 'var(--bg-secondary)',
                color: chainFilter === Number(id) ? 'var(--refi-teal)' : 'var(--text-tertiary)',
              }}
            >
              {name}
            </button>
          ))}
      </div>

      {/* Peer List */}
      <div className="space-y-2">
        <h3 className="text-sm font-bold">
          Peers ({peers.length})
        </h3>
        {peers.length === 0 && (
          <p className="text-xs py-4 text-center" style={{ color: 'var(--text-tertiary)' }}>
            No peers discovered. Connect to see other online wallets.
          </p>
        )}
        {peers.map((p) => (
          <div
            key={p.user_id}
            className="card p-3 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <div
                className="w-2 h-2 rounded-full"
                style={{ background: p.status === 'online' ? 'var(--refi-teal)' : '#666' }}
              />
              <div>
                <div className="text-sm font-medium">
                  {p.ens_name || p.display_name || `${p.eth_address.slice(0, 10)}...`}
                </div>
                <div className="text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>
                  {p.pseudo_ipv6}
                </div>
              </div>
            </div>
            <div className="text-right text-xs" style={{ color: 'var(--text-tertiary)' }}>
              <div>{CHAIN_NAMES[p.chain_id] || `Chain ${p.chain_id}`}</div>
              <div className="font-mono">{p.subnet}</div>
            </div>
          </div>
        ))}
      </div>

      {/* SMTP Bridge */}
      {stats && (
        <div className="card p-4">
          <h3 className="text-sm font-bold mb-2">SMTP Bridge</h3>
          <div className="flex items-center gap-2 text-xs">
            <div
              className="w-2 h-2 rounded-full"
              style={{ background: stats.smtp_bridge_running ? 'var(--refi-teal)' : '#666' }}
            />
            <span style={{ color: 'var(--text-secondary)' }}>
              {stats.smtp_bridge_running ? 'Running — accepting inbound email' : 'Stopped'}
            </span>
          </div>
          {stats.smtp_bridge_running && (
            <p className="text-xs mt-2 font-mono" style={{ color: 'var(--text-tertiary)' }}>
              Listening on 127.0.0.1:8025
            </p>
          )}
        </div>
      )}
    </div>
  )
}
