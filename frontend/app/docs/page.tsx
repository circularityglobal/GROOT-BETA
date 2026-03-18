'use client'

import { API_URL } from '@/lib/config'

export default function DocsPage() {
  return (
    <div className="max-w-4xl mx-auto py-12 px-6">
      <h1 className="text-3xl font-bold mb-4" style={{ letterSpacing: '-0.02em' }}>API Documentation</h1>
      <p className="mb-8" style={{ color: 'var(--text-secondary)' }}>
        REFINET Cloud exposes an OpenAI-compatible API. Use your existing SDK — just change the base URL.
      </p>

      <Section title="Quick Start">
        <CodeBlock code={`from openai import OpenAI

client = OpenAI(
    base_url="${API_URL}/v1",
    api_key="rf_your_key_here"
)

response = client.chat.completions.create(
    model="bitnet-b1.58-2b",
    messages=[{"role": "user", "content": "Hello, Groot"}],
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content, end="")`} />
      </Section>

      <Section title="Authentication">
        <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
          Sign in with your Ethereum wallet (SIWE). No registration required — connect your wallet and you&apos;re in.
          Optionally add email/password and TOTP 2FA in Settings.
        </p>
        <EndpointList endpoints={[
          { method: 'GET', path: '/auth/siwe/nonce', desc: 'Get SIWE nonce (public)' },
          { method: 'POST', path: '/auth/siwe/verify', desc: 'Verify wallet signature → full JWT + auto-create account' },
          { method: 'POST', path: '/auth/token/refresh', desc: 'Rotate refresh token' },
          { method: 'GET', path: '/auth/me', desc: 'Current user profile' },
          { method: 'PUT', path: '/auth/me', desc: 'Update username or email' },
          { method: 'POST', path: '/auth/settings/password', desc: 'Set email + password (optional)' },
          { method: 'POST', path: '/auth/login', desc: 'Password login (if password set)' },
          { method: 'POST', path: '/auth/login/totp', desc: 'Complete password login with TOTP' },
          { method: 'POST', path: '/auth/settings/totp/setup', desc: 'Enable TOTP 2FA (optional)' },
          { method: 'POST', path: '/auth/settings/totp/verify', desc: 'Verify TOTP setup code' },
        ]} />
      </Section>

      <Section title="Inference (OpenAI-compatible)">
        <EndpointList endpoints={[
          { method: 'GET', path: '/v1/models', desc: 'List available models (no auth)' },
          { method: 'POST', path: '/v1/chat/completions', desc: 'Chat completion (stream or non-stream)' },
        ]} />
      </Section>

      <Section title="Devices">
        <EndpointList endpoints={[
          { method: 'POST', path: '/devices/register', desc: 'Register IoT/PLC/DLT device' },
          { method: 'GET', path: '/devices', desc: 'List your devices' },
          { method: 'POST', path: '/devices/{id}/telemetry', desc: 'Ingest telemetry' },
          { method: 'GET', path: '/devices/{id}/telemetry', desc: 'Query telemetry' },
          { method: 'POST', path: '/devices/{id}/command', desc: 'Send command to device' },
        ]} />
      </Section>

      <Section title="Webhooks">
        <EndpointList endpoints={[
          { method: 'POST', path: '/webhooks/subscribe', desc: 'Register webhook URL + events' },
          { method: 'GET', path: '/webhooks', desc: 'List subscriptions' },
          { method: 'POST', path: '/webhooks/{id}/test', desc: 'Send test event' },
        ]} />
      </Section>

      <Section title="Knowledge Base & Document Ingestion">
        <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
          Upload any document (PDF, DOCX, XLSX, CSV, TXT, MD, JSON, SOL) — auto-parsed, auto-tagged for LLM search, auto-categorized. Compare documents by semantic similarity.
        </p>
        <EndpointList endpoints={[
          { method: 'POST', path: '/knowledge/documents', desc: 'Upload document (JSON body with title + content)' },
          { method: 'POST', path: '/knowledge/documents/upload', desc: 'Upload file (multipart — PDF, DOCX, XLSX, CSV, etc.)' },
          { method: 'GET', path: '/knowledge/documents', desc: 'List all documents with tags, type, page count' },
          { method: 'DELETE', path: '/knowledge/documents/{id}', desc: 'Remove document from knowledge base' },
          { method: 'GET', path: '/knowledge/documents/{id}/tags', desc: 'Get auto-generated semantic tags for document' },
          { method: 'POST', path: '/knowledge/documents/{id}/retag', desc: 'Re-generate tags for existing document' },
          { method: 'POST', path: '/knowledge/documents/compare', desc: 'Compare two documents (semantic + keyword + tags)' },
          { method: 'GET', path: '/knowledge/search?q=&tags=', desc: 'Search knowledge base (hybrid RAG with tag filtering)' },
          { method: 'POST', path: '/knowledge/contracts', desc: 'Add contract definition for CAG' },
          { method: 'GET', path: '/knowledge/contracts', desc: 'List contract definitions' },
        ]} />
        <p className="text-xs mt-4" style={{ color: 'var(--text-tertiary)' }}>
          Supported file types: PDF (PyMuPDF), DOCX (python-docx), XLSX (openpyxl), CSV, TXT, Markdown, JSON/ABI, Solidity. All parsing is sovereign — zero external API calls.
        </p>
      </Section>

      <Section title="MCP Tools (Document)">
        <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
          These tools are available to GROOT and external AI agents via all 6 MCP protocols (REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks).
        </p>
        <EndpointList endpoints={[
          { method: 'TOOL', path: 'search_documents', desc: 'Search knowledge base with natural language + tag filtering' },
          { method: 'TOOL', path: 'compare_documents', desc: 'Compare two documents by similarity and structure' },
          { method: 'TOOL', path: 'get_document_tags', desc: 'Get auto-generated semantic tags for a document' },
        ]} />
      </Section>

      <Section title="Interactive Docs">
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Full interactive API documentation is available at{' '}
          <a href={`${API_URL}/docs`} style={{ color: 'var(--refi-teal)' }} className="hover:underline font-mono" target="_blank" rel="noopener noreferrer">
            {API_URL}/docs
          </a>{' '}
          (Swagger UI) and{' '}
          <a href={`${API_URL}/redoc`} style={{ color: 'var(--refi-teal)' }} className="hover:underline font-mono" target="_blank" rel="noopener noreferrer">
            {API_URL}/redoc
          </a>{' '}
          (ReDoc).
        </p>
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-12">
      <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--refi-teal)', letterSpacing: '-0.02em' }}>{title}</h2>
      {children}
    </section>
  )
}

function CodeBlock({ code }: { code: string }) {
  return (
    <div className="relative">
      <button
        className="absolute top-3 right-3 px-2.5 py-1 rounded-md text-[11px] font-mono transition-colors"
        style={{ color: 'var(--text-tertiary)', border: '1px solid var(--border-subtle)' }}
        onClick={() => navigator.clipboard?.writeText(code)}
      >
        Copy
      </button>
      <pre className="card p-5 overflow-x-auto mb-6">
        <code className="text-sm font-mono leading-relaxed" style={{ color: 'var(--text-primary)' }}>{code}</code>
      </pre>
    </div>
  )
}

function EndpointList({ endpoints }: { endpoints: { method: string; path: string; desc: string }[] }) {
  return (
    <div className="space-y-2">
      {endpoints.map((e, i) => (
        <div key={i} className="flex items-start sm:items-center gap-4 py-2 flex-col sm:flex-row" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
          <span className={`font-mono text-xs font-bold w-12 ${
            e.method === 'GET' ? 'text-green-400' :
            e.method === 'POST' ? 'text-blue-400' :
            e.method === 'PUT' ? 'text-yellow-400' :
            e.method === 'DELETE' ? 'text-red-400' : ''
          }`}>{e.method}</span>
          <span className="font-mono text-sm" style={{ color: 'var(--text-primary)' }}>{e.path}</span>
          <span className="text-xs sm:ml-auto" style={{ color: 'var(--text-tertiary)' }}>{e.desc}</span>
        </div>
      ))}
    </div>
  )
}
