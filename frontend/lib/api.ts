import { API_URL } from './config'

class RefinetAPI {
  private token: string | null = null

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('refinet_token')
    }
  }

  private headers(extra?: Record<string, string>): Record<string, string> {
    const h: Record<string, string> = { 'Content-Type': 'application/json' }
    if (this.token) h.Authorization = `Bearer ${this.token}`
    return { ...h, ...extra }
  }

  setToken(token: string) {
    this.token = token
    if (typeof window !== 'undefined') localStorage.setItem('refinet_token', token)
  }

  clearToken() {
    this.token = null
    if (typeof window !== 'undefined') {
      localStorage.removeItem('refinet_token')
      localStorage.removeItem('refinet_refresh')
    }
  }

  async get(path: string) {
    const resp = await fetch(`${API_URL}${path}`, { headers: this.headers() })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return resp.json()
  }

  async post(path: string, body: any) {
    const resp = await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(body),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return resp.json()
  }

  async put(path: string, body: any) {
    const resp = await fetch(`${API_URL}${path}`, {
      method: 'PUT',
      headers: this.headers(),
      body: JSON.stringify(body),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return resp.json()
  }

  async delete(path: string) {
    const resp = await fetch(`${API_URL}${path}`, {
      method: 'DELETE',
      headers: this.headers(),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return resp.json()
  }

  async uploadFile(path: string, file: File, fields?: Record<string, string>) {
    const form = new FormData()
    form.append('file', file)
    if (fields) {
      for (const [k, v] of Object.entries(fields)) {
        if (v) form.append(k, v)
      }
    }
    const h: Record<string, string> = {}
    if (this.token) h.Authorization = `Bearer ${this.token}`
    // Do NOT set Content-Type — browser sets multipart boundary
    const resp = await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: h,
      body: form,
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
      throw new Error(err.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
  }

  // Auth — SIWE is primary
  me = () => this.get('/auth/me')
  updateProfile = (data: { username?: string; email?: string }) =>
    this.put('/auth/me', data)

  // Auth — custodial wallet (no browser extension needed)
  createWallet = (chainId = 1) =>
    this.post('/auth/wallet/create', { chain_id: chainId })
  custodialLogin = (ethAddress: string) =>
    this.post('/auth/wallet/siwe', { eth_address: ethAddress })

  // Auth — optional password login
  login = (email: string, password: string) =>
    this.post('/auth/login', { email, password })
  setPassword = (email: string, password: string, username?: string) =>
    this.post('/auth/settings/password', { email, password, username })

  // Auth — optional TOTP
  setupTotp = () => this.post('/auth/settings/totp/setup', {})
  verifyTotp = (code: string) =>
    this.post('/auth/settings/totp/verify', { code })

  // Keys
  createKey = (name: string, scopes = 'inference:read', dailyLimit = 100) =>
    this.post('/keys', { name, scopes, daily_limit: dailyLimit })

  listKeys = () => this.get('/keys')
  revokeKey = (id: string) => this.delete(`/keys/${id}`)

  // Devices
  listDevices = () => this.get('/devices')
  registerDevice = (name: string, type: string, metadata?: any) =>
    this.post('/devices/register', { name, device_type: type, metadata })

  // Health
  health = () => fetch(`${API_URL}/health`).then((r) => r.json())

  // ── Registry ──────────────────────────────────────────────────

  // Projects
  listProjects = (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return this.get(`/registry/projects${qs}`)
  }
  getProject = (slug: string) => this.get(`/registry/projects/${slug}`)
  createProject = (data: any) => this.post('/registry/projects', data)
  updateProject = (slug: string, data: any) => this.put(`/registry/projects/${slug}`, data)
  deleteProject = (slug: string) => this.delete(`/registry/projects/${slug}`)
  trendingProjects = (limit = 10) => this.get(`/registry/projects/trending?limit=${limit}`)

  // Social
  toggleStar = (slug: string) => this.post(`/registry/projects/${slug}/star`, {})
  forkProject = (slug: string) => this.post(`/registry/projects/${slug}/fork`, {})

  // User profile
  getUserProfile = (username: string) => this.get(`/registry/users/${username}`)
  getUserProjects = (username: string) => this.get(`/registry/users/${username}/projects`)
  getUserStars = (username: string) => this.get(`/registry/users/${username}/stars`)

  // ABIs
  listABIs = (slug: string) => this.get(`/registry/projects/${slug}/abis`)
  addABI = (slug: string, data: any) => this.post(`/registry/projects/${slug}/abis`, data)
  getABI = (abiId: string) => this.get(`/registry/abis/${abiId}`)
  deleteABI = (abiId: string) => this.delete(`/registry/abis/${abiId}`)

  // SDKs
  listSDKs = (slug: string) => this.get(`/registry/projects/${slug}/sdks`)
  addSDK = (slug: string, data: any) => this.post(`/registry/projects/${slug}/sdks`, data)
  getSDK = (sdkId: string) => this.get(`/registry/sdks/${sdkId}`)
  deleteSDK = (sdkId: string) => this.delete(`/registry/sdks/${sdkId}`)

  // Execution Logic
  listLogic = (slug: string) => this.get(`/registry/projects/${slug}/logic`)
  addLogic = (slug: string, data: any) => this.post(`/registry/projects/${slug}/logic`, data)
  getLogic = (logicId: string) => this.get(`/registry/logic/${logicId}`)
  deleteLogic = (logicId: string) => this.delete(`/registry/logic/${logicId}`)

  // ── GROOT Brain: Contract Repository ────────────────────────────

  // Repo namespace
  initRepo = (data?: { bio?: string; website?: string }) =>
    this.post('/repo/init', data || {})
  getMyRepo = () => this.get('/repo/me')
  getPublicRepo = (username: string) => this.get(`/repo/@${username}`)

  // Contract management
  uploadContract = (data: {
    name: string; chain: string; language?: string; abi_json: string;
    source_code?: string; address?: string; description?: string; tags?: string[];
  }) => this.post('/repo/contracts', data)
  listContracts = (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return this.get(`/repo/contracts${qs}`)
  }
  getContract = (slug: string) => this.get(`/repo/contracts/${slug}/detail`)
  updateContract = (slug: string, data: any) => this.put(`/repo/contracts/${slug}`, data)
  archiveContract = (slug: string) => this.delete(`/repo/contracts/${slug}`)

  // Parsing & SDK
  parseContract = (slug: string) => this.post(`/repo/contracts/${slug}/parse`, {})
  getContractFunctions = (slug: string) => this.get(`/repo/contracts/${slug}/functions`)
  getContractEvents = (slug: string) => this.get(`/repo/contracts/${slug}/events`)
  getContractSDK = (slug: string) => this.get(`/repo/contracts/${slug}/sdk`)

  // Visibility & toggles
  toggleContractVisibility = (slug: string, isPublic: boolean) =>
    this.put(`/repo/contracts/${slug}/visibility`, { is_public: isPublic })
  toggleFunction = (slug: string, functionId: string, isEnabled: boolean) =>
    this.put(`/repo/contracts/${slug}/functions/${functionId}/toggle`, { is_sdk_enabled: isEnabled })

  // Explore public contracts
  exploreContracts = (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return this.get(`/explore/contracts${qs}`)
  }
  getPublicSDK = (contractId: string) => this.get(`/explore/contracts/${contractId}/sdk`)
  exploreChains = () => this.get('/explore/chains')
  searchContracts = (q: string, params?: Record<string, string>) => {
    const qs = new URLSearchParams({ q, ...params }).toString()
    return this.get(`/explore/search?${qs}`)
  }
  getUserContracts = (username: string) => this.get(`/explore/@${username}/contracts`)

  // ── Knowledge Base ────────────────────────────────────────────────

  // Documents
  listDocuments = () => this.get('/knowledge/documents')
  uploadDocument = (data: { title: string; content: string; category?: string; filename?: string }) =>
    this.post('/knowledge/documents', data)
  uploadDocumentFile = (file: File, title?: string, category?: string) =>
    this.uploadFile('/knowledge/documents/upload', file, {
      ...(title ? { title } : {}),
      ...(category ? { category } : {}),
    })
  deleteDocument = (docId: string) => this.delete(`/knowledge/documents/${docId}`)
  getDocumentTags = (docId: string) => this.get(`/knowledge/documents/${docId}/tags`)
  retagDocument = (docId: string) => this.post(`/knowledge/documents/${docId}/retag`, {})
  compareDocuments = (docIdA: string, docIdB: string) =>
    this.post('/knowledge/documents/compare', { doc_id_a: docIdA, doc_id_b: docIdB })

  // Document generation (BitNet-powered) — admin
  summarizeDocument = (docId: string) => this.post(`/knowledge/documents/${docId}/summarize`, {})
  generateFaq = (docId: string) => this.post(`/knowledge/documents/${docId}/generate-faq`, {})
  generateOverview = (docId: string) => this.post(`/knowledge/documents/${docId}/generate-overview`, {})

  // ── User Documents (private/public layer) ─────────────────────
  listMyDocuments = () => this.get('/knowledge/my/documents')
  uploadMyDocumentFile = (file: File, title?: string, category?: string, visibility = 'private') =>
    this.uploadFile('/knowledge/my/documents/upload', file, {
      ...(title ? { title } : {}),
      ...(category ? { category } : {}),
      visibility,
    })
  deleteMyDocument = (docId: string) => this.delete(`/knowledge/my/documents/${docId}`)
  toggleMyDocVisibility = (docId: string, visibility: 'private' | 'public') =>
    this.put(`/knowledge/my/documents/${docId}/visibility`, { visibility })
  retagMyDocument = (docId: string) => this.post(`/knowledge/my/documents/${docId}/retag`, {})
  summarizeMyDocument = (docId: string) => this.post(`/knowledge/my/documents/${docId}/summarize`, {})
  generateMyFaq = (docId: string) => this.post(`/knowledge/my/documents/${docId}/generate-faq`, {})
  generateMyOverview = (docId: string) => this.post(`/knowledge/my/documents/${docId}/generate-overview`, {})

  // URL ingestion
  ingestUrl = (url: string, title?: string, category?: string) =>
    this.post('/knowledge/documents/ingest-url', { url, title, category })
  ingestMyUrl = (url: string, title?: string, category?: string, visibility = 'private') =>
    this.post('/knowledge/my/documents/ingest-url', { url, title, category, visibility })

  // YouTube ingestion
  ingestYoutube = (url: string, title?: string) =>
    this.post('/knowledge/documents/ingest-youtube', { url, title })
  ingestMyYoutube = (url: string, title?: string, visibility = 'private') =>
    this.post('/knowledge/my/documents/ingest-youtube', { url, title, visibility })

  // Export
  exportDocumentUrl = (docId: string, format: 'md' | 'pdf') =>
    `${API_URL}/knowledge/documents/${docId}/export?format=${format}`
  exportMyDocumentUrl = (docId: string, format: 'md' | 'pdf') =>
    `${API_URL}/knowledge/my/documents/${docId}/export?format=${format}`

  // Timeline
  extractTimeline = (docId: string) => this.post(`/knowledge/documents/${docId}/timeline`, {})
  extractMyTimeline = (docId: string) => this.post(`/knowledge/my/documents/${docId}/timeline`, {})

  // Audio overview
  audioOverview = (docId: string) => this.post(`/knowledge/documents/${docId}/audio-overview`, {})
  audioMyOverview = (docId: string) => this.post(`/knowledge/my/documents/${docId}/audio-overview`, {})

  // Sharing
  shareDocument = (docId: string, sharedWithId: string, permission = 'read') =>
    this.post(`/knowledge/my/documents/${docId}/share`, { shared_with_id: sharedWithId, permission })
  listDocumentShares = (docId: string) => this.get(`/knowledge/my/documents/${docId}/shares`)
  revokeShare = (docId: string, shareId: string) =>
    this.delete(`/knowledge/my/documents/${docId}/shares/${shareId}`)
  listSharedWithMe = () => this.get('/knowledge/shared-with-me')

  // Search
  searchKnowledge = (q: string, params?: { category?: string; tags?: string }) => {
    const qs = new URLSearchParams({ q, ...params }).toString()
    return this.get(`/knowledge/search?${qs}`)
  }

  // Contracts (CAG)
  listKnowledgeContracts = (chain?: string) => {
    const qs = chain ? `?chain=${chain}` : ''
    return this.get(`/knowledge/contracts${qs}`)
  }
  addKnowledgeContract = (data: any) => this.post('/knowledge/contracts', data)
}

export const api = new RefinetAPI()
export default api
