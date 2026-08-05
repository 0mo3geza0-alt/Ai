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

## Remaining (phase by phase — see ROADMAP.md)
- P0 next: **Phase 4 — Tool Framework** (Plugin SDK + sandboxed Python/Terminal/Browser/Git/REST/DB tools + registry)
- Then: 5 Memory → 6 Planning → 7 Multi-Agent → 8 Browser → 9 LLM Gateway → 10 Frontend → 11 Infra → 12 Security → 13 Testing → 14 Production.

## Note on expanded vision (2026-08-05)
User later described a broader "AI Creation Platform" (websites/apps/images/video/audio/docs/coding/research/automation/plugins/agent-builder/model-gateway/billing). This is a superset that maps onto the existing phased roadmap. Env constraints: Next.js→CRA React, Celery/Redis/Postgres/Qdrant/K8s→Mongo + self-host artifacts. Awaiting user's pick of next runnable milestone.
