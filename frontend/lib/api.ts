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

  // ── User Provider Keys (BYOK) ──────────────────────────────
  getProviderCatalog = () => this.get('/provider-keys/catalog')
  listUserProviderKeys = () => this.get('/provider-keys')
  saveUserProviderKey = (data: { provider_type: string; display_name: string; api_key: string; base_url?: string }) =>
    this.post('/provider-keys', data)
  deleteUserProviderKey = (id: string) => this.delete(`/provider-keys/${id}`)
  testUserProviderKey = (id: string) => this.post(`/provider-keys/${id}/test`, {})

  // ── Model Providers (Admin) ────────────────────────────────
  listModels = () => this.get('/v1/models')
  listProviders = () => this.get('/admin/providers')
  checkProviderHealth = () => this.get('/admin/providers/health')
  getProviderUsage = (period: string = 'day') => this.get(`/admin/providers/usage?period=${period}`)
  updateProviderConfig = (key: string, value: string) => this.post('/admin/providers/config', { key, value })

  // ── Wizard Pipeline (GROOT deploys using its wallet) ─────
  startWizardPipeline = (data: {
    source_code?: string; registry_project_id?: string;
    chain?: string; constructor_args?: any[];
    compiler_version?: string; new_owner?: string;
    brand?: { primary: string; background: string };
    contract_name?: string; is_public?: boolean;
  }) => this.post('/pipeline/start', data)

  startCompileTest = (data: { source_code?: string; abi?: any[]; bytecode?: string }) =>
    this.post('/pipeline/compile-test', data)

  startDeploy = (data: {
    source_code?: string; chain?: string; constructor_args?: any[];
    new_owner?: string; user_wallet_address?: string;
  }) => this.post('/pipeline/deploy', data)

  listPipelines = (limit = 20, offset = 0) =>
    this.get(`/pipeline/?limit=${limit}&offset=${offset}`)

  getPipeline = (id: string) => this.get(`/pipeline/${id}`)

  cancelPipeline = (id: string) => this.post(`/pipeline/${id}/cancel`, {})

  // ── Pipeline Admin: Pending Actions (Master Admin) ───────
  listPendingActions = (status = 'pending') =>
    this.get(`/pipeline/admin/pending-actions?status=${status}`)

  approveAction = (actionId: string, note?: string) =>
    this.post(`/pipeline/admin/pending-actions/${actionId}/approve`, { note })

  rejectAction = (actionId: string, note?: string) =>
    this.post(`/pipeline/admin/pending-actions/${actionId}/reject`, { note })

  // ── Deployments (GROOT-deployed contracts) ───────────────
  listDeployments = () => this.get('/deployments/')

  getDeployment = (id: string) => this.get(`/deployments/${id}`)

  transferOwnership = (id: string, newOwner: string) =>
    this.post(`/deployments/${id}/transfer`, { new_owner: newOwner })

  verifyOwner = (id: string) => this.get(`/deployments/${id}/verify-owner`)

  // ── DApp Factory ─────────────────────────────────────────
  listDappTemplates = () => this.get('/dapp/templates')

  buildDapp = (data: {
    template_name: string; contract_name: string;
    contract_address: string; chain: string; abi_json?: string;
  }) => this.post('/dapp/build', data)

  listDappBuilds = () => this.get('/dapp/builds')

  downloadDapp = (buildId: string) =>
    fetch(`${API_URL}/dapp/builds/${buildId}/download`, { headers: this.headers() })

  validateDapp = (buildId: string) => this.post(`/dapp/builds/${buildId}/validate`, {})

  getDappValidation = (buildId: string) => this.get(`/dapp/builds/${buildId}/validation`)

  // ── GROOT Wallet Admin (Master Admin only) ───────────────
  getGrootWallet = () => this.get('/admin/wallet')

  getGrootBalance = (chain: string) => this.get(`/admin/wallet/balance/${chain}`)

  getGrootTransactions = (limit = 50) => this.get(`/admin/wallet/transactions?limit=${limit}`)

  initiateGrootTransfer = (to: string, amountEth: string, chain = 'base') =>
    this.post('/admin/wallet/transfer', { to, amount_eth: amountEth, chain })

  // ── CAG: Contract-Augmented Generation ───────────────────
  // Query: search public SDKs
  cagQuery = (query: string, chain?: string, maxResults = 3) => {
    const params = new URLSearchParams({ q: query })
    if (chain) params.set('chain', chain)
    params.set('max_results', String(maxResults))
    return this.get(`/explore/search?${params}`)
  }

  // Execute: call view/pure functions on-chain (no gas, no approval)
  cagExecute = (contractAddress: string, chain: string, functionName: string, args: any[] = []) =>
    this.post('/explore/cag/execute', { contract_address: contractAddress, chain, function_name: functionName, args })

  // Act: request state-changing call (creates PendingAction for master_admin approval)
  cagAct = (contractAddress: string, chain: string, functionName: string, args: any[] = []) =>
    this.post('/explore/cag/act', { contract_address: contractAddress, chain, function_name: functionName, args })

  // ── Block Explorer ABI Fetch ─────────────────────────────
  fetchAbiFromExplorer = (address: string, chain: string) =>
    this.get(`/explore/fetch-abi?address=${address}&chain=${chain}`)

  // ── Dynamic Chain / Network Management ─────────────────
  listChains = () => this.get('/explore/chains')

  // Admin chain management (master_admin only)
  adminListChains = () => this.get('/admin/chains')
  adminAddChain = (data: {
    chain_id: number; name: string; short_name: string; rpc_url: string;
    currency?: string; explorer_url?: string; explorer_api_url?: string;
    icon_url?: string; is_testnet?: boolean;
  }) => this.post('/admin/chains', data)
  adminImportChainlist = (chainId: number) => this.post('/admin/chains/import', { chain_id: chainId })
  adminUpdateChain = (chainId: number, data: any) => this.put(`/admin/chains/${chainId}`, data)
  adminDeactivateChain = (chainId: number) => this.delete(`/admin/chains/${chainId}`)

  // ── Agents ──────────────────────────────────────────────────────
  registerAgent = (data: { name: string; description?: string; archetype?: string }) =>
    this.post('/agents/register', data)
  registerAgentWithManifest = (manifest: any) =>
    this.post('/agents/register-with-manifest', manifest)
  validateManifest = (manifest: any) =>
    this.post('/agents/validate-manifest', manifest)
  listAgents = () => this.get('/agents/')
  agentHeartbeat = (agentId: string) => this.post(`/agents/${agentId}/heartbeat`, {})
  getAgentConfig = (agentId: string) => this.get(`/agents/${agentId}/config`)
  updateAgentConfig = (agentId: string, config: any) =>
    this.put(`/agents/${agentId}/config`, config)
  getAgentSoul = (agentId: string) => this.get(`/agents/${agentId}/soul`)
  updateAgentSoul = (agentId: string, soul: string) =>
    this.post(`/agents/${agentId}/soul`, { soul_md: soul })
  runAgentTask = (agentId: string, task: string) =>
    this.post(`/agents/${agentId}/run`, { task })
  listAgentTasks = (agentId: string, status?: string) =>
    this.get(`/agents/${agentId}/tasks${status ? `?status=${status}` : ''}`)
  getAgentTask = (agentId: string, taskId: string) =>
    this.get(`/agents/${agentId}/tasks/${taskId}`)
  getAgentTaskSteps = (agentId: string, taskId: string) =>
    this.get(`/agents/${agentId}/tasks/${taskId}/steps`)
  cancelAgentTask = (agentId: string, taskId: string) =>
    this.post(`/agents/${agentId}/tasks/${taskId}/cancel`, {})
  delegateAgentTask = (agentId: string, data: { target_agent_id: string; subtask: string; source_task_id: string }) =>
    this.post(`/agents/${agentId}/delegate`, data)

  // ── Chain Watchers ──────────────────────────────────────────────
  createWatcher = (data: { contract_address: string; chain: string; events?: string[] }) =>
    this.post('/chain/watchers', data)
  listWatchers = () => this.get('/chain/watchers')
  deleteWatcher = (watcherId: string) => this.delete(`/chain/watchers/${watcherId}`)
  getWatcherEvents = (watcherId: string, limit = 50) =>
    this.get(`/chain/watchers/${watcherId}/events?limit=${limit}`)

  // ── Payments & Subscriptions ────────────────────────────────────
  getFeeSchedule = () => this.get('/payments/fee-schedule')
  checkout = (data: { item_type: string; item_id: string; chain?: string }) =>
    this.post('/payments/checkout', data)
  completePayment = (paymentId: string) =>
    this.post(`/payments/${paymentId}/complete`, {})
  paymentHistory = () => this.get('/payments/history')
  subscriptionStatus = () => this.get('/payments/subscriptions/status')
  upgradeSubscription = (tier: string) =>
    this.post('/payments/subscriptions/upgrade', { tier })
  adminRevenue = () => this.get('/payments/admin/revenue')
  adminRevenueSplits = () => this.get('/payments/admin/revenue-splits')

  // ── Broker Sessions ─────────────────────────────────────────────
  createBrokerSession = (data: { agent_id: string; service_type: string }) =>
    this.post('/broker/sessions', data)
  listBrokerSessions = () => this.get('/broker/sessions')
  getBrokerSession = (sessionId: string) => this.get(`/broker/sessions/${sessionId}`)
  completeBrokerSession = (sessionId: string) =>
    this.post(`/broker/sessions/${sessionId}/complete`, {})
  cancelBrokerSession = (sessionId: string) =>
    this.post(`/broker/sessions/${sessionId}/cancel`, {})
  getBrokerFees = (serviceType: string) => this.get(`/broker/fees/${serviceType}`)

  // ── Vector Memory ───────────────────────────────────────────────
  vectorMemoryHealth = () => this.get('/vector-memory/health')
  storeMemory = (data: { agent_id: string; content: string; metadata?: any }) =>
    this.post('/vector-memory/store', data)
  searchMemory = (data: { agent_id: string; query: string; limit?: number }) =>
    this.post('/vector-memory/search', data)
  getMemoryContext = (data: { agent_id: string; query: string }) =>
    this.post('/vector-memory/context', data)
  memoryStats = (agentId: string) => this.get(`/vector-memory/stats/${agentId}`)
  deleteMemory = (memoryId: string) => this.delete(`/vector-memory/${memoryId}`)

  // ── Scheduled Tasks (Admin) ─────────────────────────────────────
  listScheduledTasks = () => this.get('/admin/scheduled-tasks')
  createScheduledTask = (data: { name: string; cron: string; agent: string; task: string }) =>
    this.post('/admin/scheduled-tasks', data)
  updateScheduledTask = (taskId: string, data: any) =>
    this.put(`/admin/scheduled-tasks/${taskId}`, data)
  deleteScheduledTask = (taskId: string) => this.delete(`/admin/scheduled-tasks/${taskId}`)
  runScheduledTask = (taskId: string) =>
    this.post(`/admin/scheduled-tasks/${taskId}/run`, {})

  // ── Onboarding & Leads (Admin) ──────────────────────────────────
  getOnboardingStats = () => this.get('/admin/stats/onboarding')
  getLeads = () => this.get('/admin/leads')
}

export const api = new RefinetAPI()
export default api
