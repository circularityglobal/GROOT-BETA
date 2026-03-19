# REFINET Cloud — Frontend

Next.js 14 single-page application with wallet-first authentication.

## Tech Stack

- **Framework:** Next.js 14 (App Router) + React 18
- **Language:** TypeScript 5.5
- **Styling:** Tailwind CSS 3.4 + custom globals.css
- **Web3:** ethers 6.13, viem 2.21, wagmi 2.14, WalletConnect
- **State:** @tanstack/react-query 5.60
- **Animation:** Framer Motion 12.38
- **Build:** Static export via `next export` → served by Nginx

## Development

```bash
npm install
npm run dev        # http://localhost:4000
```

**Environment files:**
- `.env.local` — Local development (API at localhost:8000)
- `.env.production` — Production (API at api.refinet.io)

Key variable: `NEXT_PUBLIC_API_URL` — Backend API base URL.

## Pages

| Path | Directory | Description |
|---|---|---|
| `/` | `app/page.tsx` | Landing page with GROOT chat widget |
| `/dashboard` | `app/dashboard/` | Main dashboard with platform overview |
| `/chat` | `app/chat/` | Full-screen GROOT chat interface |
| `/explore` | `app/explore/` | Browse contracts by category |
| `/registry` | `app/registry/` | Smart contract registry (GitHub-style) |
| `/repo` | `app/repo/` | Personal contract repository |
| `/knowledge` | `app/knowledge/` | Knowledge base management |
| `/store` | `app/store/` | App store (browse, install, submit) |
| `/projects` | `app/projects/` | Agent and automation projects |
| `/devices` | `app/devices/` | IoT device management |
| `/messages` | `app/messages/` | Wallet-to-wallet messaging |
| `/webhooks` | `app/webhooks/` | Webhook subscription management |
| `/network` | `app/network/` | P2P network visualization |
| `/settings` | `app/settings/` | User settings (wallet, auth, preferences) |
| `/admin` | `app/admin/` | Admin dashboard (users, roles, config) |
| `/docs` | `app/docs/` | Documentation viewer |
| `/u/[username]` | `app/u/` | Public user profiles |

## Components

| Component | Directory | Description |
|---|---|---|
| AuthFlow | `components/AuthFlow/` | SIWE wallet connection + JWT session |
| GrootChat | `components/GrootChat/` | AI chat widget with streaming SSE |
| SettingsModal | `components/SettingsModal/` | User preferences and account settings |
| WalletOnboarding | `components/WalletOnboarding/` | First-time wallet setup wizard |
| ThemeProvider | `components/ThemeProvider/` | Dark/light theme with system detection |
| AdminPanel | `components/AdminPanel/` | Admin operations UI |
| ApiKeyManager | `components/ApiKeyManager/` | API key CRUD |
| DeviceManager | `components/DeviceManager/` | Device registration and telemetry |
| WebhookManager | `components/WebhookManager/` | Webhook subscription management |
| ModelSelector | `components/ModelSelector/` | AI model picker (header dropdown) |
| DocsModal | `components/DocsModal/` | In-app documentation viewer |
| ErrorBoundary | `components/ErrorBoundary/` | React error boundary wrapper |
| MatrixRain | `components/MatrixRain/` | Visual effect for landing page |
| TerminalText | `components/TerminalText/` | Typing animation effect |
| HorizontalPanels | `components/HorizontalPanels/` | Swipeable panel layout |
| ui/ | `components/ui/` | Shared UI primitives |

## Auth Flow

1. User clicks "Connect Wallet" → MetaMask/WalletConnect prompt
2. Wallet signs SIWE message → `POST /auth/siwe/verify`
3. Backend returns JWT (access + refresh tokens)
4. All subsequent API calls include `Authorization: Bearer <jwt>`
5. Token refresh via `POST /auth/refresh`

**Implementation:** `components/AuthFlow/index.tsx` + `lib/wallet.ts`

## API Client

`lib/api.ts` exports a configured fetch wrapper:
```typescript
import { api } from '@/lib/api'
const response = await api.get('/agents')
const data = await api.post('/agents/register', { name: 'my-agent' })
```

Automatically includes JWT token from session storage.

## Styling

- Tailwind CSS with custom design tokens in `globals.css`
- CSS custom properties for theme colors (dark/light)
- Responsive: mobile-first with breakpoints at sm/md/lg/xl
- Font: system font stack (no custom fonts loaded)
