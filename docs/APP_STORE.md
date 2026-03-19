# REFINET App Store — Technical Documentation

## Overview

The REFINET App Store is a digital marketplace for DApps, AI agents, smart contracts, MCPs, tools, templates, datasets, API services, and other digital assets. It follows an Apple/Google-style review pipeline where developers submit code, admins test it in isolated Docker sandboxes, and approved submissions are published to the store.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        REFINET App Store                         │
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────────┐  │
│  │ Frontend  │───▶│  FastAPI      │───▶│  SQLite (WAL mode)     │  │
│  │ Next.js   │    │  Routes       │    │  public.db + internal  │  │
│  └──────────┘    └──────┬───────┘    └────────────────────────┘  │
│                         │                                        │
│                  ┌──────▼───────┐    ┌────────────────────────┐  │
│                  │  Services     │───▶│  Docker Sandboxes       │  │
│                  │  (business    │    │  (network-isolated)     │  │
│                  │   logic)      │    │  (read-only FS)         │  │
│                  └──────────────┘    └────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Database Models

### public.db (user-facing)

**AppListing** — Published store entries
- Identity: `id`, `slug` (username/app-name), `owner_id`
- Content: `name`, `description`, `readme` (markdown), `icon_url`, `screenshots`, `tags`
- Classification: `category`, `chain`, `version`
- Pricing: `price_type` (free/one-time/subscription), `price_amount`, `price_token`, `license_type`
- Delivery: `download_url`, `external_url`
- Source links: `registry_project_id`, `dapp_build_id`, `agent_id`
- Metrics: `install_count`, `download_count`, `rating_avg`, `rating_count`
- Flags: `is_published`, `is_verified`, `is_featured`, `is_active`, `listed_by_admin`

**AppReview** — User ratings (1-5 stars + optional comment)
- Unique constraint: one review per user per app
- Rating recalculated atomically after each review

**AppInstall** — Tracks installations per user
- Soft-delete pattern: `uninstalled_at` = null means active
- Install counts use atomic SQL increments (race-condition safe)

**AppSubmission** — Review pipeline entries
- Status: `draft → submitted → automated_review → in_review → changes_requested → approved → rejected → published`
- Artifact: `artifact_path`, `artifact_hash` (SHA-256), `artifact_size_bytes`
- Review: `reviewer_id`, `review_started_at`, `review_completed_at`, `rejection_reason`
- Automated scan: `automated_scan_status`, `automated_scan_result` (JSON)

**SubmissionNote** — Review thread (admin ↔ developer)
- Types: `comment`, `request_changes`, `approval`, `rejection`, `system`

### internal.db (admin-only, never exposed)

**SandboxEnvironment** — Docker container tracking
- `container_id`, `container_name`, `image_tag`, `port`, `access_url`
- `network_isolated`, `resource_limits` (JSON)
- `expires_at` (auto-destroy after 4 hours)

---

## Categories

| Category | Description |
|----------|-------------|
| `dapp` | Complete decentralized applications |
| `agent` | AI agents with inference capabilities |
| `tool` | Developer utilities and SDKs |
| `template` | Starter kits and boilerplate |
| `dataset` | Curated data packages |
| `api-service` | Hosted API endpoints |
| `digital-asset` | Any other digital product |

## Pricing Models

| Type | Description |
|------|-------------|
| `free` | No cost |
| `one-time` | Single purchase (USD or token) |
| `subscription` | Recurring monthly (USD or token) |

## License Types

| Type | Description |
|------|-------------|
| `open` | Open source / freely distributable |
| `single-use` | One installation per purchase |
| `multi-use` | Unlimited installations per purchase |
| `enterprise` | Custom terms for organizations |

---

## Submission & Review Pipeline

### Developer Flow

```
1. Create Submission
   POST /apps/submissions
   Body: { name, category, description, version, price_type, ... }
   Returns: submission object in "draft" status

2. Upload Code Artifact (ZIP)
   POST /apps/submissions/{id}/artifact
   Body: multipart/form-data with ZIP file
   Validates: ZIP integrity, 100MB max, zip bomb check (500MB decompressed max)

3. Submit for Review
   POST /apps/submissions/{id}/submit
   Triggers: automated static analysis scan
   Status: draft → submitted → automated_review → submitted

4. Monitor Status
   GET /apps/submissions         (list all my submissions)
   GET /apps/submissions/{id}    (detail with review notes)

5. If Changes Requested
   Upload new artifact, then re-submit
   Status: changes_requested → submitted

6. If Approved
   App automatically published to store with is_verified=true

7. Withdraw (cancel anytime before approval)
   DELETE /apps/submissions/{id}
```

### Admin Review Flow

```
1. View Submission Queue
   GET /admin/submissions                    (all submissions)
   GET /admin/submissions?status=submitted   (pending review)
   GET /admin/submissions/stats              (pipeline statistics)

2. Claim a Submission
   PUT /admin/submissions/{id}/claim
   Status: submitted → in_review

3. Launch Sandbox (isolated Docker container)
   POST /admin/submissions/{id}/sandbox
   Returns: { access_url, port, sandbox_id, expires_at }
   Container runs on http://localhost:91XX

4. Test the Code in Sandbox
   - Visit access_url in browser
   - Check sandbox logs: GET /admin/submissions/{id}/sandbox/logs
   - Check sandbox status: GET /admin/submissions/{id}/sandbox

5. Add Review Notes
   POST /admin/submissions/{id}/notes
   Body: { content: "...", note_type: "comment" }

6. Decision
   a) APPROVE → PUT /admin/submissions/{id}/approve
      Auto-publishes to App Store, marks as verified
   b) REQUEST CHANGES → PUT /admin/submissions/{id}/request-changes
      Body: { reason: "..." }
      Developer can fix and resubmit
   c) REJECT → PUT /admin/submissions/{id}/reject
      Body: { reason: "..." }
      Final — developer must create new submission

7. Destroy Sandbox (auto-destroys after 4 hours)
   DELETE /admin/submissions/{id}/sandbox
```

### Automated Scan

On submission, the system automatically scans the ZIP artifact for:

| Pattern | Severity | Description |
|---------|----------|-------------|
| `subprocess.call/run/Popen` | warning | Process execution |
| `os.system()` | warning | Shell command execution |
| `eval()` / `exec()` | warning | Dynamic code execution |
| `__import__()` | warning | Dynamic import |
| `open(.*/etc/` | warning | Sensitive file access |
| `rm -rf` | warning | Destructive shell command |
| `DROP TABLE` | warning | SQL destruction |
| `private_key` | warning | Possible key exposure |
| `BEGIN RSA/EC PRIVATE KEY` | warning | Private key literal |
| `.env` files | critical | Environment files with secrets |

Scan results are stored as JSON and shown to the admin reviewer. The admin makes the final decision regardless of scan outcome.

---

## Sandbox Security

### Container Isolation

| Control | Setting |
|---------|---------|
| Network | `--network refinet_sandbox_isolated` (Docker `--internal` — no internet) |
| Filesystem | `--read-only` with 50MB tmpfs at `/tmp` |
| Privileges | `--security-opt no-new-privileges` |
| Capabilities | `--cap-drop ALL` |
| Processes | `--pids-limit 100` |
| CPU | Clamped to 0.1–2.0 cores |
| Memory | Clamped to 128–4096 MB |
| Lifetime | 4-hour auto-expiry + manual destroy |
| Dockerfile | User-provided Dockerfiles are ALWAYS overwritten — only platform-generated Dockerfiles execute |

### Zip Safety

| Check | Protection |
|-------|-----------|
| Zip slip | Every entry path validated with `os.path.realpath()` — blocks `../` traversal |
| Zip bomb | Total decompressed size calculated before extraction — 500MB limit |
| ZIP validity | `testzip()` CRC validation before accepting |
| Size limit | 100MB compressed upload limit |
| Hash integrity | SHA-256 computed on upload, stored for verification |

---

## App Store Browse & Install

### Public Endpoints (no auth required)

| Endpoint | Description |
|----------|-------------|
| `GET /apps` | Browse/search with filters (category, chain, price_type, query) and sorting (installs, rating, recent, name, price) |
| `GET /apps/featured` | Featured + trending apps (admin-curated first, then top-rated) |
| `GET /apps/categories` | List all valid categories, price types, license types |
| `GET /apps/{owner/name}` | Full app detail with readme + recent reviews |

### Authenticated Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /apps` | Publish directly (admin-only path, bypasses review) |
| `GET /apps/installed` | User's installed apps |
| `POST /apps/{slug}/install` | Install an app |
| `POST /apps/{slug}/uninstall` | Uninstall an app |
| `POST /apps/{slug}/review` | Submit/update a review (1-5 stars + comment) |

### Migration Endpoints (import existing assets)

| Endpoint | Description |
|----------|-------------|
| `POST /apps/migrate/dapp` | Import a DApp build into the store |
| `POST /apps/migrate/agent` | Import an agent registration into the store |
| `POST /apps/migrate/registry` | Import a registry project into the store |

---

## Admin Store Management

| Endpoint | Description |
|----------|-------------|
| `GET /admin/apps` | List all apps (including unpublished/inactive) |
| `GET /admin/apps/stats` | Store analytics: totals, category breakdown, pricing breakdown, top apps |
| `POST /admin/apps/publish` | Admin publishes a product directly (platform-listed, auto-verified, auto-featured) |
| `PUT /admin/apps/{id}/verify` | Toggle verified badge |
| `PUT /admin/apps/{id}/feature` | Toggle featured status |
| `PUT /admin/apps/{id}/status` | Activate/deactivate an app |

---

## Frontend Pages

| Path | Description |
|------|-------------|
| `/store` | Browse page — search, filter by category, sort, pagination, featured section |
| `/store/{slug}` | Detail page — install/uninstall, download, reviews, screenshots, readme, metadata |
| `/store/submit` | Submission form — create submission, upload ZIP, track status, view review notes |
| `/admin` → REVIEWS tab | Review queue, claim submissions, launch sandboxes, approve/reject, add notes |
| `/admin` → APP STORE tab | Manage listings, publish products, verify/feature/deactivate, view stats |

---

## Security Model

### Authentication
- JWT bearer tokens (via SIWE wallet sign-in)
- API keys (prefix `rf_`) for programmatic access
- Admin operations require admin role in internal.db or X-Admin-Secret header

### Authorization
- Developers can only modify their own submissions and apps
- Admin operations are role-gated through `_require_admin()`
- All admin actions are logged to the append-only `AdminAuditLog`
- Download routes require authentication (no anonymous artifact access)

### Input Validation
- URLs validated: only `http://` and `https://` schemes accepted (blocks `javascript:`, `file:///`, `data:`, SSRF)
- Container names: strict `^[a-zA-Z0-9][a-zA-Z0-9_.-]*$` pattern
- Resource limits: clamped to safe ranges server-side regardless of input
- Search queries: capped at 500 characters, pagination capped at page 1000
- File uploads: 100MB compressed, 500MB decompressed, ZIP validation

### Data Integrity
- Install/uninstall counts use atomic SQL `UPDATE ... SET count = count ± 1` (no race conditions)
- Rating averages recalculated from actual review data after each update
- Submission artifacts hashed with SHA-256 on upload
- Transaction rollback on partial failures

---

## Event Bus Integration

The app store emits events for real-time updates via the in-process EventBus:

| Event | Trigger |
|-------|---------|
| `appstore.app.published` | New app published |
| `appstore.app.updated` | Existing app updated |
| `appstore.app.installed` | User installs an app |
| `appstore.app.uninstalled` | User uninstalls an app |
| `appstore.app.reviewed` | User submits/updates a review |
| `appstore.app.verified` | Admin verifies an app |
| `appstore.app.featured` | Admin features an app |
| `appstore.app.status_changed` | Admin activates/deactivates an app |
| `appstore.product.listed` | Admin publishes a platform product |

These events can be subscribed to by webhooks and WebSocket connections for real-time notifications.
