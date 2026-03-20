---
paths:
  - "frontend/**/*.tsx"
  - "frontend/**/*.ts"
---

# Frontend Development Rules

## Next.js Patterns
- All interactive pages need `'use client'` directive at top
- Pages live in `frontend/app/{route}/page.tsx` (App Router)
- Use `API_URL` from `@/lib/config` for all API calls
- Auth token: `localStorage.getItem('refinet_token')`

## Chain Selectors
- NEVER hardcode chain arrays — fetch dynamically from `/explore/chains`
- Use fallback arrays only as initial state before API response arrives
- Pattern:
```tsx
const [chains, setChains] = useState<string[]>(FALLBACK_CHAINS)
useEffect(() => {
  fetch(`${API_URL}/explore/chains`)
    .then(r => r.ok ? r.json() : [])
    .then(data => { if (data.length) setChains(data.map(c => c.short_name)) })
    .catch(() => {})
}, [])
```

## API Client
- All API methods live in `frontend/lib/api.ts` as methods on the `RefinetAPI` class
- Add new methods there, not inline in components
- Export: `export const api = new RefinetAPI()`

## Styling
- Tailwind CSS for layout and spacing
- Inline styles for dynamic values (colors from chain config, status badges)
- Color constants: `CHAIN_COLORS`, `STATUS_COLORS` at top of page files
- Dark theme: backgrounds use `#0A0A1B` (pages) and `#1A1A2E` (cards)
- Accent: `#FF6B00` (orange, REFINET brand)

## Admin Dashboard
- Tabs defined in `const tabs = [...]` array with union type for state
- Each tab has a separate panel component (e.g., `NetworksPanel`, `GrootWalletPanel`)
- Master admin features use JWT auth (never admin secret header from frontend)
