# REFINET Cloud — Claude Code Prompt Library
# Post-Deployment UI Refinement Prompts
#
# How to use: Open the groot/ folder in VSCode with Claude Code.
# Copy any prompt below and give it to Claude Code.
# Each prompt is self-contained and targets a specific refinement.

---

## PROMPT 01 — Master Brand Alignment

```
I need you to audit and refine the REFINET Cloud frontend to perfectly match our brand identity.

Our brand DNA comes from the REFINET logo: three organic leaves in a circular formation with a teal/cyan gradient (#5CE0D2 → #7EECD8 → #A8F0E6) on a deep black background.

The design system is already in frontend/app/globals.css using CSS custom properties. Review every component and ensure:

1. The teal gradient (#5CE0D2 → #7EECD8) is used consistently for:
   - Primary CTAs and interactive elements
   - Accent text (section labels, status indicators)
   - Focus rings and glow effects
   - The Groot chat widget button

2. The dark theme uses:
   - --bg-primary: #050505 (near-black, not pure black)
   - --bg-secondary: #0C0C0C
   - --bg-elevated: #1A1A1A (cards)
   - Borders should be barely visible: #1C1C1C → #262626

3. The light theme uses:
   - Teal shifts to a deeper shade: #0D9488 → #0F766E
   - Backgrounds shift to warm whites: #FAFAFA, #F5F5F5
   - Cards get a subtle glass effect with white/75% opacity

4. Typography:
   - Display/headings: 'Instrument Serif' for the editorial, premium feel
   - Body text: 'DM Sans' for clean readability
   - Code/mono: 'JetBrains Mono'

5. The REFINET logo (public/refi-logo.png) should appear in:
   - The navbar (already there)
   - The Groot chat widget header
   - The landing page hero
   - The favicon

Review all files in frontend/app/ and frontend/components/ and make targeted fixes. Do not restructure — only refine colors, spacing, and typography to match the brand.
```

---

## PROMPT 02 — Google-Level Simplicity

```
The REFINET Cloud landing page at frontend/app/page.tsx needs to feel as clean and effortless as google.com, but with the depth and polish of claude.ai.

Current state: it has a hero, feature cards, constraints section, and code snippet. 

Refinements needed:

1. Hero section: reduce visual noise. The headline and two CTA buttons should breathe. Remove the scroll indicator. The logo should float gently (already has animate-float). The status pill is good — keep it minimal.

2. Whitespace: increase vertical padding between sections from py-28 to py-32. Increase max-width of the hero text area. Let the design breathe.

3. Cards: they currently have hover states. Make the hover more subtle — just a slight border color shift, no shadow jump. The glass effect should be barely noticeable.

4. Code snippet section: wrap the code in a properly styled code block with a copy button. Add syntax highlighting using CSS classes, not inline styles. The background should match --bg-secondary.

5. Footer: keep it ultra-minimal. Logo + 3 links + license. No decoration.

6. Animations: the stagger class already handles sequential fade-in. Verify the timing feels natural — 50ms between children. Don't add more animations. Restraint is the design.

The goal: someone visits this page and immediately understands what REFINET Cloud is, feels the quality, and clicks "Talk to Groot" — all within 5 seconds.
```

---

## PROMPT 03 — Claude-Quality Chat Interface

```
The Groot chat widget at frontend/components/GrootChat/index.tsx is the most important UI component. It needs to feel as polished as Claude's chat interface.

Current state: floating button bottom-right, opens a 400px-wide panel with messages and input.

Refinements:

1. The floating button:
   - Keep the pulse-glow animation
   - Use the REFINET logo (refi-logo.png) inside the button instead of a generic chat icon
   - Size: 56px circle
   - On hover: scale to 1.1 with a stronger glow

2. The chat panel:
   - Width: 420px on desktop, full-width minus 24px padding on mobile
   - Height: 600px max, 85vh on mobile
   - Border radius: 20px (matching modern chat apps)
   - The open animation (animate-slide-up) should feel natural — ease-out, 350ms

3. Messages:
   - User messages: teal background (var(--refi-teal)) with dark text
   - Assistant messages: transparent background with a subtle left border (2px teal)
   - Remove the bubble-style rounded corners on assistant messages — use flat left-aligned
   - Add a small "Groot" label with the logo before assistant messages
   - The streaming cursor (▌) should blink in teal

4. Input area:
   - The textarea should auto-resize up to 3 lines
   - The send button should be a circle with an arrow icon
   - Add "Powered by BitNet · Sovereign AI" at the bottom in 10px text

5. The full chat page (frontend/app/chat/page.tsx):
   - This should be a full-screen chat experience, not just the widget
   - Center the messages in a max-w-3xl container
   - Add suggested prompts at the top: "What is REFINET?", "How does the API work?", "Tell me about sovereign computing"

Make these changes to both the widget component and the full chat page.
```

---

## PROMPT 04 — Dark/Light Theme Polish

```
The theme system in frontend/app/globals.css has dark and light CSS variables already defined. The ThemeProvider at frontend/components/ThemeProvider/ handles toggling.

Audit the entire frontend for theme consistency:

1. Every color must use CSS custom properties — search for any hardcoded hex values in .tsx files and replace them with var(--property-name) references.

2. Dark theme refinements:
   - The background gradient on the hero should use radial-gradient with var(--refi-teal-glow) at 12% opacity
   - Borders should be nearly invisible: var(--border-subtle) at #1C1C1C
   - The glass effect (.glass class) should use rgba(255,255,255,0.03) backdrop-blur(16px)
   - Cards should NOT have visible borders in dark mode — use rgba(255,255,255,0.04) border

3. Light theme refinements:
   - The teal should shift to deeper: #0D9488 (already in CSS vars)
   - Card backgrounds should be white with a very subtle shadow: 0 1px 3px rgba(0,0,0,0.06)
   - The glass effect in light mode: rgba(255,255,255,0.75) backdrop-blur(12px)
   - Borders should be #E5E5E5 (already set)

4. Transition: all theme-dependent properties should transition smoothly at 300ms when toggling. The body already has transition set — verify all components respect it.

5. The theme toggle button in the navbar should:
   - Use a sun icon for dark mode (switch to light)
   - Use a moon icon for light mode (switch to dark)
   - Animate the icon swap with a 200ms fade

Test by toggling the theme and checking: landing page, chat, dashboard, settings, admin, knowledge pages.
```

---

## PROMPT 05 — Dashboard & Settings Upgrade

```
The dashboard (frontend/app/dashboard/page.tsx) and settings (frontend/app/settings/page.tsx) pages need to match the quality of the landing page and chat.

Dashboard refinements:
1. Stats cards: use a 2x2 grid on mobile, 4-column on desktop. Each card should have:
   - A subtle teal icon (not emoji)
   - The stat value in large text (text-3xl font-bold)
   - The label in small text below
   - A very subtle teal glow on hover

2. API keys section: show key prefix, name, usage bar (requests_today / daily_limit as a visual progress bar using var(--refi-teal)), and a copy button for the prefix.

3. Devices section: show device name, type badge (iot/plc/dlt colored differently), status dot (green/red), and telemetry count.

4. Add a "Recent Activity" section showing the last 5 usage records.

Settings refinements:
1. The auth flow (AuthFlow component) is already good. Keep it.
2. Account section: clean two-column layout with labels and values
3. Add a "Knowledge" link for admins that goes to /knowledge/
4. The "Create Key" flow should show the key in a copiable code block with a prominent "Copy" button and a warning that it won't be shown again.
```

---

## PROMPT 06 — Mobile Responsiveness

```
Audit all pages for mobile responsiveness. The target is iPhone 14 Pro (393px) to iPad (1024px).

Rules:
1. The navbar should collapse to a hamburger menu on mobile (<768px):
   - Logo stays visible
   - Theme toggle stays visible
   - Nav links collapse into a slide-down menu

2. The Groot chat widget should be full-width on mobile (max-w-[calc(100vw-24px)])

3. The landing page hero should:
   - Reduce heading from text-7xl to text-4xl on mobile
   - Stack CTAs vertically on mobile
   - Reduce section padding from py-32 to py-16

4. Cards should be single-column on mobile, 2-column on tablet, 3-column on desktop

5. The dashboard stats grid: 2 columns on mobile, 4 on desktop

6. The admin panel table should scroll horizontally on mobile

7. All input fields should be 100% width on mobile

8. Touch targets: all buttons and links should be minimum 44px tap target

Use Tailwind responsive prefixes (sm:, md:, lg:) consistently.
```

---

## PROMPT 07 — Admin Knowledge Base UI

```
The knowledge management page at frontend/app/knowledge/page.tsx needs refinement:

1. Document upload:
   - Add drag-and-drop file upload support for .txt and .md files
   - When a file is dropped, read its content and populate the textarea
   - Show a file icon with the filename when a file is loaded
   - Add a progress indicator during upload

2. Document list:
   - Show a search/filter bar at the top
   - Category badges should be color-coded:
     - about: teal
     - product: blue
     - docs: purple
     - blockchain: orange
     - contract: yellow
     - faq: green
   - Each document card should expand to show a preview of the first chunk

3. Contract definitions:
   - Show a chain logo/icon (Ethereum diamond, Base logo, etc.) next to each chain
   - The ABI field should be a collapsible JSON viewer
   - Add a "Test Search" button that queries the knowledge base and shows what Groot would find

4. Add this page to the navbar for admin users, and link it from the admin panel.
```

---

## PROMPT 08 — Layer Zero Aesthetic Feel

```
The "Layer Zero" aesthetic is about making the infrastructure feel like a living network layer — not a dashboard, not a SaaS app, but the underlying fabric of a decentralized system.

Apply this aesthetic through:

1. Subtle grid pattern background:
   - Add a very faint dot grid to the hero section background
   - Use CSS: background-image: radial-gradient(circle, var(--border-subtle) 1px, transparent 1px); background-size: 24px 24px;
   - Opacity: 0.3 in dark mode, 0.15 in light mode

2. Connection lines between sections:
   - Add thin vertical connector lines between the hero and features section
   - Use an SVG line with a gradient from transparent → teal → transparent

3. Status indicators:
   - The status pill on the landing page should pulse gently
   - Add a small "Network Status" indicator in the footer showing: nodes connected, inference latency, uptime

4. Typography:
   - Section labels ("What is REFINET Cloud", "Non-negotiable constraints") should use uppercase tracking-widest letter-spacing in 12px monospace
   - These labels should have a teal color

5. The overall impression should be: this is infrastructure, not an app. It's always on, always running, always connected. The UI is a window into the network.

Apply these changes to the landing page first, then consider if any apply to the dashboard.
```

---

## PROMPT 09 — Accessibility & Performance

```
Run an accessibility and performance audit on the REFINET Cloud frontend:

1. Accessibility:
   - All interactive elements need aria-labels
   - Color contrast must meet WCAG AA (4.5:1 for body text, 3:1 for large text)
   - Check our teal (#5CE0D2) on dark backgrounds — it should pass
   - Focus indicators must be visible (the focus-glow class handles this)
   - All images need alt text
   - The theme toggle needs aria-label="Switch to light/dark theme"
   - Keyboard navigation: Tab through the entire app and verify focus order

2. Performance:
   - The landing page should load in under 2 seconds on 3G
   - Defer font loading with display=swap (already in the Google Fonts URL)
   - The Groot chat widget should lazy-load — don't initialize the WebSocket/fetch until the button is clicked
   - Images should use next/image with proper sizing (but we're using static export, so use standard img with width/height)
   - Minimize JavaScript: the chat SSE parser should be lightweight

3. SEO:
   - The layout.tsx metadata is already set
   - Add OpenGraph meta tags for social sharing
   - Add a robots.txt and sitemap.xml to the public/ directory
```

---

## PROMPT 10 — Seed Knowledge for Groot

```
Create a script at scripts/seed_knowledge.py that seeds the initial knowledge base for Groot.

The script should use the admin API to upload these documents:

1. "What is REFINET Cloud" — Explain REFINET Cloud as a sovereign AI platform with zero cost, 3-layer auth, and universal connectivity. Cover the BitNet LLM, the OpenAI-compatible API, and the device/agent connectivity.

2. "REFINET Products" — Describe QuickCast (autonomous podcast/YouTube publishing), AgentOS (AI agent platform), and CIFI Wizards (gamified learning platform with blockchain identity).

3. "Groot AI Assistant" — Explain what Groot is, how it works (BitNet + RAG), and what it can help with.

4. "Getting Started" — How to create an account, complete 3-layer auth, get an API key, and make your first inference call.

5. "Device Connectivity" — How to register IoT devices, PLCs, and DLT nodes. Include example telemetry payloads and webhook events.

6. "Regenerative Finance" — Explain ReFi principles, how REFINET applies them, and the vision for a post-subscription internet.

7. "Sovereign Infrastructure" — Explain why REFINET runs on its own hardware, why data sovereignty matters, and how the dual-database architecture works.

Each document should be 500-1000 words. The script should be idempotent (skip already-uploaded docs using content hash dedup).

Usage: python3 scripts/seed_knowledge.py --api-url https://api.refinet.io --token {admin_jwt}
```

---

## HOW TO USE THESE PROMPTS

1. Get REFINET Cloud running locally:
   ```
   cd groot
   pip install -r requirements.txt
   cp .env.example .env
   # Generate secrets and fill .env
   uvicorn api.main:app --reload --port 8000
   ```

2. Open the groot/ folder in VSCode with Claude Code

3. Start with PROMPT 01 (brand alignment) — this sets the foundation

4. Work through prompts in order, or pick the ones most relevant to your current priority

5. After each prompt, verify the changes in the browser at localhost:3000

6. PROMPT 10 (seed knowledge) should be run after deployment to give Groot its initial knowledge base

Each prompt is designed to be given directly to Claude Code as-is. They reference the exact file paths and CSS properties in the codebase.
