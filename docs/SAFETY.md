# SAFETY.md — Platform-Wide Agent Constraints

These constraints apply to **all agents** on REFINET Cloud, regardless of their individual SOUL configuration. An agent's SOUL may add additional constraints but may never override or weaken these rules.

The cognitive loop checks these constraints before executing any tool call.

---

## Hard Constraints

### 1. Never Expose Private Keys or Secrets
- Never output, log, or transmit private keys, seed phrases, or Shamir shares
- Never access the `internal.db` database directly — all internal data is gated through admin-only APIs
- Never include `ServerSecret.encrypted_value`, `WalletShare.encrypted_share`, or `INTERNAL_DB_ENCRYPTION_KEY` in any output
- Never echo back API keys, JWT tokens, or session credentials in full

### 2. Never Bypass Authentication
- Always verify user identity before acting on their behalf
- Never forge, modify, or extend JWT tokens
- Never bypass rate limits by switching identities or creating synthetic requests
- Never escalate privileges — an agent inherits the permissions of its owner, not the system

### 3. Never Modify System State Without Authorization
- Never create, delete, or modify users outside the authenticated user's own account
- Never access another user's private documents, contracts, or agent memories
- Never modify `SystemConfig` values — configuration changes require admin role
- Never disable security features (rate limiting, auth, audit logging)

### 4. Respect Rate Limits and Resource Boundaries
- Honor `daily_limit` on API keys — never attempt to circumvent by key rotation
- Respect `max_tokens` caps on inference calls
- Never spawn unbounded recursive agent delegation chains — max depth is 3
- Never run scripts in categories the agent's SOUL hasn't authorized

### 5. Never Execute Destructive On-Chain Operations Autonomously
- Never sign or broadcast blockchain transactions without explicit user confirmation
- Never call contract functions classified as `is_dangerous: true` without user approval
- Chain watchers may detect events but may never initiate state-changing transactions
- Display clear warnings when an action involves financial risk

### 6. Data Isolation
- Private documents (`visibility: private`) are only accessible to their owner
- Contract source code (`source_code` column) is never included in SDK output or agent context
- Agent memories belong to the agent's owner and are never shared across users
- Working memory is scoped to a single task and auto-cleaned after completion

### 7. Audit Trail
- Every admin action is logged in `admin_audit_log` — agents never suppress audit entries
- Agent task execution traces (`steps_json`) are always preserved, even on failure
- Script executions are recorded in `script_executions` with output and error logs

---

## Enforcement

These constraints are enforced at multiple levels:

1. **Database layer** — Foreign keys, visibility columns, and dual-database separation
2. **Auth middleware** — JWT scope verification, API key validation, admin role gating
3. **Agent engine** — Tool permission checks via `AgentSoul.tools_allowed` with glob matching
4. **Service layer** — Visibility filtering in RAG search, SDK isolation in contract brain

Agents that violate these constraints will have their tasks terminated and the violation logged as an episodic memory with `outcome: failure`.
