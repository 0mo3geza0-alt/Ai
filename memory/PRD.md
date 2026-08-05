# Autonomous AI Agent Platform — PRD

## Original Problem Statement
Build a production-grade Autonomous AI Agent Platform following a 15-phase roadmap (Phase 0–14). Each phase must be independently runnable and tested before the next. Full roadmap: `/app/memory/ROADMAP.md`.

## Decisions
- New app **replacing** the previous NeuraForge app.
- Stack: **FastAPI + MongoDB + React** (Postgres/Redis/K8s delivered as self-host artifacts in `/app/infra`, not run in preview).
- LLM via Emergent Universal Key.

## Architecture
- `backend/core/`: config, logging, errors, db, base_models (PyObjectId/BaseDocument).
- `backend/server.py`: FastAPI, `/api/*` routes.
- `frontend/src/pages/Foundation.js`: boot/status screen + roadmap progress.
- `infra/`: Docker, docker-compose (artifacts).

## Implemented
### Phase 1 — Foundation (2026-08-05) ✅ verified
- Core config/logging/errors/db/base-model modules.
- `GET /api/health` (pings Mongo), `GET /api/version`, `GET /api/`.
- MongoDB connection + startup index creation.
- React foundation boot screen: live API/DB/version status + 14-phase roadmap tracker.
- Infra artifacts: Dockerfile.backend, Dockerfile.frontend, docker-compose.yml.

### Phase 2 — Authentication (2026-08-05) ✅ verified (21/21 backend, frontend 100%)
- JWT email/password (register/login/logout/me/refresh) + Emergent Google OAuth (both mint our JWT; Bearer via localStorage works in iframe).
- Organizations, memberships, teams, team members.
- RBAC roles: owner/admin/member/viewer with permission checks (`require_permission`).
- API keys (X-API-Key, scoped, hashed, revocable) with scope enforcement.
- Global admin seed. Brute-force/session tracking via `sessions` collection.

### Phase 3 — Workspace (2026-08-05) ✅ verified
- Projects CRUD (org-scoped, RBAC-guarded).
- File upload/download via Emergent Object Storage with automatic version history (same filename -> new version; current flag).
- Artifacts (text/code) per project.
- Frontend: DashboardLayout (sidebar + org switcher), Overview, Projects, ProjectDetail (upload/versions/download/artifacts), Organization (members/teams), ApiKeys, Settings.

### Phase 4+ — AI Creation Platform (Nexus) (2026-08-05) ✅ verified (backend 17/17, frontend 100%)
- **Model Gateway** (`llm/gateway.py`): OpenAI/Anthropic/Gemini via Emergent key with automatic fallback chain; `/api/models` lists providers/voices.
- **AI Chat**: org-scoped saved sessions + history/context memory, credit-metered.
- **AI Document Generator**: report/presentation/article (markdown).
- **AI Coding Agent**: language-specific code gen, optional save into a project as an artifact.
- **AI Image Studio**: Gemini Nano Banana, stored in object storage, served via `/creations/{id}/file`.
- **AI Audio/Voiceover**: OpenAI TTS (9 voices), mp3 stored + served.
- **Creations history** + **per-org Credits/Usage** (chat=1, doc=1, code=2, image=5, audio=3; free=200, pro=10000) + mock **upgrade**.
- **Admin panel** (`admin_api.py`): platform stats + users (global-admin only).
- Frontend: Chat, Create Studio (tabs: Document/Code/Image/Audio), Creations gallery, Admin, sidebar credits badge + org switcher.
- Fix applied: idempotent admin seed (role/org/membership/default_org_id); per-request image session id.

## Improvements round (2026-08-05) ✅ verified (backend 100%, frontend 95%)
Implemented user-requested items 2,3,4,5,6,7,9,11,12:
- (2) **Streaming Chat (SSE)** endpoint `/chat/.../stream` + fetch-reader consumer (note: server generates full reply then streams word-by-word — reliable, not token-level).
- (3) **Instant credit refresh** in sidebar after every generation.
- (4) **Race-safe credits**: atomic `findOneAndUpdate({credits:{$gte:cost}})` — no negative balances (verified with concurrent debits).
- (5) **AI Video** via `fal-ai/ltx-video` (Universal Key) — background job + status polling.
- (6) **AI Music** via `fal-ai/stable-audio` (Universal Key) — background job + polling. (True voice-cloning needs an ElevenLabs key — deferred.)
- (7) **Image modifiers/variations**: photorealistic / no-background / upscale / anime / 3d presets.
- (9) **Research Agent**: DuckDuckGo (no key) web sources + LLM report with inline citations & source links.
- (11) **Prompt templates**: quick-fill chips per Create tab.
- (12) **Share & Export**: public share links (`/share/{token}`, unauth) + export text creations as .md/.txt/.html.
- Credits: chat=1 doc=1 code=2 image=5 audio=3 video=15 music=8 research=2.
- Fixes: idempotent admin seed; per-request image session id; share() clipboard-safe toast in iframe; share gated to file:write.

## Known limitations / deferred
- Chat streaming is server-simulated (full reply then chunked), not SDK token streaming.
- Voice-cloning (ElevenLabs), real Stripe billing, browser-automation module, plugin marketplace, K8s deploy: not built (need keys / not runnable in preview).
- Video/music are slow (~1-3 min) — handled via async jobs + polling.

## Phase 7 — Agents / Memory / Security (2026-06 update) ✅ verified (backend 5/5 pytest, frontend ~90% Playwright)
- **AI Agent Builder UI** (`frontend/src/pages/Agents.js`): create/edit/delete custom agents (name, role, provider, system prompt, tools = web_search + memory-RAG, per-agent knowledge, color). Single-run with output + sources + run history; Team-run mode (manager AI delegates subtasks to selected agents and synthesizes a final result). Credits: agent=3, team=8.
- **Knowledge Base UI** (`frontend/src/pages/Memory.js`): add manual knowledge (text + tags), semantic vector search (fastembed dim=384, cosine) with relevance scores, delete. Agents recall knowledge via the memory RAG tool.
- **Security & Audit UI** (`frontend/src/pages/Security.js`, admin-only): overview stat cards (total/blocked/error/write events), rate-limit policy, audit-log table with All/Blocked/Errors filter. Sidebar Security + Admin links gated to `global_role==admin`.
- Routes wired in `App.js` (`/app/agents`, `/app/memory`, `/app/security`) + sidebar nav in `DashboardLayout.js`.
- **Fixes this session:**
  - Route-ordering bug: `/agents/team/run` was shadowed by `/agents/{aid}/run` (FastAPI matches in declaration order) → team routes moved above dynamic `{aid}` routes in `agents/router.py`.
  - Edit-agent knowledge wipe: edit form now prefills existing agent knowledge (fetched from memories filtered by `agent_id`) so saving no longer silently erases it.
- Backend routes: `/api/orgs/{oid}/agents[/{aid}[/run|/runs]|/team/run|/team/runs]`, `/api/orgs/{oid}/memories[/search]`, `/api/admin/security/overview`, `/api/admin/audit-logs`.
- Pytest suite: `/app/backend/tests/test_phase7_agents_memory_security.py`.
