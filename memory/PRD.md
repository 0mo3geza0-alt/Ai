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

## Env-adapted / deferred (honest status)
- Next.js→CRA React; Celery/Redis→async + Mongo; Postgres→Mongo; Qdrant→(future) Mongo vector; K8s/Helm→artifacts in /app/infra.
- **Not built (need external keys / not runnable here):** real Video & Music generation (need fal.ai etc.), voice-cloning (ElevenLabs), Stripe billing (credits are in-app), live browser-automation module, full plugin marketplace, real K8s deploy. Chat is non-streaming (reliable) rather than SSE.
