# Autonomous AI Agent Platform — Master Engineering Roadmap

> **Status:** Planning deliverable. No implementation code yet.
> Implementation begins **phase by phase** after this roadmap is approved.
> Each milestone must be **independently runnable and testable** before the next begins.

---

## ⚠️ Platform Reality Check (read first)

This roadmap is written **production-grade / aspirational** exactly as requested (PostgreSQL, Redis, Kubernetes, Helm, Docker Compose, vLLM, etc.). The current Emergent managed runtime, however, has fixed infrastructure:

| Requested | Managed Runtime Reality | Adaptation Strategy |
|---|---|---|
| PostgreSQL | **MongoDB** (fixed via `MONGO_URL`) | Use MongoDB for all persistence. Postgres schemas below are expressed as Mongo collections. |
| Redis (queue/cache) | No external Redis | Use MongoDB-backed task queue + in-process cache. (Redis becomes a self-host add-on.) |
| Docker / Docker Compose / K8s / Helm / Nginx | Supervisor-managed single pod (backend:8001, frontend:3000) | Provide manifests as **deliverable artifacts** for self-hosting; they do not run inside the preview. |
| Playwright browser automation | Chromium available for controlled use | Runs server-side with strict timeouts/sandboxing. |
| Ollama / vLLM (local models) | Not hostable in preview | Use Emergent Universal LLM Key (OpenAI/Anthropic/Gemini). Local backends = self-host add-on. |

**Recommendation:** Build the platform on **FastAPI + MongoDB + React** (our stack), keep the abstractions clean so Postgres/Redis/K8s can be swapped in when self-hosted. Infra phases (11) produce manifests as artifacts.

Ask before Phase 1: *Do we build this as a NEW app (replacing NeuraForge), or as a separate module?*

---

# Phase 0 — Project Planning

**Purpose:** Establish the blueprint, standards, and success criteria for the whole platform.

### Deliverables
- This roadmap, coding standards, architecture diagrams, risk register, milestone acceptance criteria.

### Folder Structure (target monorepo)
```
/app
├── backend/
│   ├── core/            # config, logging, security, db, errors
│   ├── auth/            # jwt, oauth, rbac, sessions, api-keys
│   ├── workspace/       # projects, files, artifacts, versions
│   ├── tools/           # plugin sdk + built-in tools
│   ├── memory/          # conversation, semantic, vector, graph
│   ├── planning/        # planner, task graph, workflow, scheduler
│   ├── agents/          # registry + specialized agents
│   ├── browser/         # playwright automation
│   ├── llm/             # gateway, routing, providers
│   ├── observability/   # metrics, tracing, audit
│   └── server.py        # FastAPI entrypoint, /api router
├── frontend/
│   └── src/{pages,components,context,lib,hooks}
├── infra/               # docker, k8s, helm, nginx, ci (artifacts)
├── tests/               # unit, integration, e2e, load
└── memory/              # PRD, roadmap, credentials
```

### Technology Stack
- **Backend:** FastAPI (Python 3.11), Motor/MongoDB, PyJWT, bcrypt, Playwright, emergentintegrations (LLM), APScheduler.
- **Frontend:** React 19, Tailwind, shadcn/ui, framer-motion, react-router, TanStack Query.
- **AI:** Emergent Universal Key → GPT-5.6 / Claude Sonnet 5 / Gemini 3.1; vector search via MongoDB Atlas Vector or in-Mongo cosine fallback.
- **Infra artifacts:** Docker, Compose, K8s + Helm, Nginx, GitHub Actions.

### Coding Standards
- Backend: all routes `/api/*`; Pydantic v2 models; `PyObjectId`/`BaseDocument` pattern; `datetime.now(timezone.utc)`; env-only secrets; async everywhere.
- Frontend: functional components < 50 lines; `data-testid` on all interactive/info elements; logical CSS (ms-/me-); named exports for components, default for pages.
- Git: conventional commits; one phase = one reviewable slice.

### Architecture (text diagram)
```
React SPA ──HTTPS──> FastAPI /api
                        │
     ┌──────────────────┼─────────────────────────────┐
   Auth/RBAC        Orchestrator (Planner→Supervisor→Executor)
     │                  │
  Sessions/Keys     Agent Registry ── Coding/Research/Browser/Test/Review/Manager
     │                  │                    │
   MongoDB          Tool Registry ── Python/Terminal/Browser/Git/Docker/REST/DB
                        │
                    Memory (conv + vector + graph)  ── LLM Gateway ── {OpenAI,Anthropic,Gemini}
                        │
                    Observability (metrics/tracing/audit)
```

### Estimates (whole platform)
- Files: ~180–240 · REST APIs: ~90–120 · Mongo collections: ~28–34 · Background jobs: ~12 · Tests: ~250+.

### Dependencies
motor, pyjwt, bcrypt, authlib (oauth), playwright, apscheduler, httpx, numpy, emergentintegrations, tiktoken; frontend deps already present.

### Risk Analysis
| Risk | Impact | Mitigation |
|---|---|---|
| Arbitrary code/terminal tool = RCE | Critical | Sandboxed exec, allow-lists, resource caps, per-org isolation |
| No Redis/Postgres/K8s in preview | High | Mongo-backed queue/cache; infra as artifacts |
| LLM cost runaway | Med | Routing + budgets + caching |
| Long agent runs > request timeout | High | Background jobs + SSE/polling status |
| Vector search scale | Med | Atlas Vector or capped cosine fallback |

### Completion Criteria (Phase 0)
- [ ] Roadmap approved · [ ] Stack confirmed · [ ] New-vs-module decision made · [ ] Standards agreed.

---

# Phase 1 — Project Foundation
**Purpose:** Runnable skeleton with config, logging, health, DB, dev env.
- **Folder:** `backend/core/`, `frontend/src` base.
- **Files:** `core/config.py`, `core/db.py`, `core/logging.py`, `core/errors.py`, `core/base_models.py` (PyObjectId/BaseDocument), `server.py`, `frontend/App.js`, `lib/api.js`.
- **Classes/Interfaces:** `Settings`, `Database`, `BaseDocument`, `AppError`, `HealthStatus`.
- **DB tables (collections):** `system_meta`.
- **REST APIs:** `GET /api/health`, `GET /api/version`.
- **Background jobs:** startup index creation, DB ping heartbeat.
- **Dependencies:** motor, pydantic-settings.
- **Tests:** health returns 200; DB connects; config loads from env.
- **Size:** ~10 files, S.
- **Checklist:** [ ] `/api/health` green [ ] logs structured [ ] frontend shell loads [ ] infra artifacts stubbed (Dockerfile, compose) in `/infra`.

# Phase 2 — Authentication
**Purpose:** Identity, access control, multi-tenancy.
- **Folder:** `backend/auth/`.
- **Files:** `jwt.py`, `oauth.py`, `rbac.py`, `models.py`, `router.py`, `deps.py`, `api_keys.py`.
- **Classes:** `TokenService`, `OAuthProvider`, `RBACPolicy`, `User`, `Organization`, `Team`, `Session`, `ApiKey`.
- **DB tables:** `users`, `organizations`, `teams`, `memberships`, `sessions`, `api_keys`, `login_attempts`.
- **REST APIs:** register, login, logout, me, refresh, oauth callback, orgs CRUD, teams CRUD, members, roles, api-keys CRUD.
- **Background jobs:** admin seed, expired-session TTL, api-key usage rollup.
- **Dependencies:** pyjwt, bcrypt, authlib. **(Integration expert required before coding auth.)**
- **Tests:** register/login/refresh; RBAC allow/deny matrix; api-key auth; org isolation.
- **Size:** ~12 files, M.
- **Checklist:** [ ] JWT + Bearer works in iframe [ ] RBAC enforced [ ] org/team scoping [ ] api-keys usable.

# Phase 3 — Workspace
**Purpose:** Per-project files/artifacts with versioning.
- **Folder:** `backend/workspace/`.
- **Files:** `projects.py`, `files.py`, `artifacts.py`, `versions.py`, `storage.py`, `router.py`, `models.py`.
- **Classes:** `Project`, `WorkspaceFile`, `Artifact`, `FileVersion`, `StorageBackend` (object storage).
- **DB tables:** `projects`, `files`, `artifacts`, `file_versions`.
- **REST APIs:** projects CRUD, file upload/download, list tree, artifact CRUD, version history/restore.
- **Background jobs:** orphan-file GC, version pruning.
- **Dependencies:** object storage (integration expert), python-multipart.
- **Tests:** upload→download roundtrip; version restore; per-org access.
- **Size:** ~12 files, M.
- **Checklist:** [ ] upload/download [ ] versions [ ] artifacts linked to runs.

# Phase 4 — Tool Framework
**Purpose:** Safe, pluggable capabilities agents can call.
- **Folder:** `backend/tools/`.
- **Files:** `sdk.py`, `registry.py`, `sandbox.py`, `python_tool.py`, `terminal_tool.py`, `browser_tool.py`, `git_tool.py`, `docker_tool.py`, `rest_tool.py`, `db_tool.py`.
- **Classes/Interfaces:** `Tool` (ABC: `name/schema/run`), `ToolResult`, `ToolRegistry`, `Sandbox`.
- **DB tables:** `tools`, `tool_invocations`.
- **REST APIs:** list tools, invoke tool, invocation history.
- **Background jobs:** sandbox cleanup, invocation metrics.
- **Dependencies:** RestrictedPython/subprocess isolation, gitpython, httpx, docker sdk (self-host).
- **Tests:** each tool happy+error path; sandbox blocks disallowed ops; timeout enforced.
- **Size:** ~14 files, L. **Highest security risk phase.**
- **Checklist:** [ ] SDK stable [ ] registry dynamic [ ] sandbox verified [ ] all 7 tools pass.

# Phase 5 — Memory System
**Purpose:** Short + long-term + semantic recall with context building.
- **Folder:** `backend/memory/`.
- **Files:** `conversation.py`, `longterm.py`, `semantic.py`, `vector_store.py`, `graph.py`, `hybrid_search.py`, `ranking.py`, `context_builder.py`, `compression.py`.
- **Classes:** `ConversationMemory`, `VectorStore`, `KnowledgeGraph`, `HybridSearch`, `MemoryRanker`, `ContextBuilder`, `Compressor`.
- **DB tables:** `conversations`, `messages`, `memories`, `embeddings`, `graph_nodes`, `graph_edges`.
- **REST APIs:** memory search, add/list memories, graph query, context preview.
- **Background jobs:** embedding backfill, memory compaction/decay.
- **Dependencies:** embeddings via LLM gateway, numpy (cosine), Atlas Vector optional.
- **Tests:** semantic recall precision; hybrid rank order; compression retains key facts; token-budgeted context.
- **Size:** ~14 files, L.
- **Checklist:** [ ] vector search [ ] graph links [ ] context under token budget.

# Phase 6 — Planning Engine
**Purpose:** Turn goals into ordered, retryable task graphs.
- **Folder:** `backend/planning/`.
- **Files:** `planner.py`, `task_graph.py`, `workflow.py`, `queue.py`, `retry.py`, `scheduler.py`, `supervisor.py`, `executor.py`.
- **Classes:** `Planner`, `TaskGraph`/`TaskNode`, `WorkflowEngine`, `TaskQueue`(Mongo-backed), `RetryPolicy`, `Scheduler`, `Supervisor`, `Executor`.
- **DB tables:** `plans`, `tasks`, `task_runs`, `schedules`.
- **REST APIs:** create plan, get plan/graph, run/pause/cancel, task status stream (SSE).
- **Background jobs:** queue worker, scheduler tick, stuck-task reaper.
- **Dependencies:** apscheduler.
- **Tests:** DAG ordering + cycle detection; retry/backoff; cancel mid-run; scheduled trigger.
- **Size:** ~12 files, L.
- **Checklist:** [ ] plan→graph→execute [ ] retries [ ] live status.

# Phase 7 — Multi-Agent System
**Purpose:** Specialized cooperating agents under a manager.
- **Folder:** `backend/agents/`.
- **Files:** `registry.py`, `base_agent.py`, `coding.py`, `research.py`, `browser_agent.py`, `testing.py`, `reviewer.py`, `manager.py`, `messaging.py`, `collaboration.py`, `loader.py`.
- **Classes/Interfaces:** `Agent` (ABC), `AgentRegistry`, `Manager`, `MessageBus`, specialized agents.
- **DB tables:** `agents`, `agent_messages`, `agent_runs`.
- **REST APIs:** list agents, dispatch task, run transcript, agent metrics.
- **Background jobs:** message dispatcher, run finalizer.
- **Dependencies:** Phases 4–6 + LLM gateway.
- **Tests:** manager delegates correctly; agent-to-agent handoff; dynamic load; end-to-end coding task.
- **Size:** ~16 files, XL.
- **Checklist:** [ ] registry [ ] messaging [ ] collaboration [ ] dynamic loading.

# Phase 8 — Browser Automation
**Purpose:** Real web interaction for agents.
- **Folder:** `backend/browser/`.
- **Files:** `manager.py`, `session.py`, `actions.py`, `dom_parser.py`, `visual.py`, `auth_flows.py`.
- **Classes:** `BrowserManager`, `BrowserSession`, `DomParser`, `VisualAnalyzer`.
- **DB tables:** `browser_sessions`, `browser_artifacts`.
- **REST APIs:** open session, navigate/click/type, screenshot, download, close.
- **Background jobs:** idle-session cleanup.
- **Dependencies:** playwright + chromium; visual analysis via multimodal LLM.
- **Tests:** navigate+screenshot; login flow; multi-tab; download capture (strict timeouts).
- **Size:** ~8 files, L.
- **Checklist:** [ ] navigation [ ] screenshots [ ] cookies/auth [ ] DOM parse.

# Phase 9 — LLM Gateway
**Purpose:** Unified, routed, cost-aware model access.
- **Folder:** `backend/llm/`.
- **Files:** `gateway.py`, `providers/{openai,anthropic,gemini,ollama,vllm,openrouter}.py`, `router.py`, `streaming.py`, `tool_calling.py`, `fallback.py`, `cost.py`.
- **Classes/Interfaces:** `LLMProvider` (ABC), `Gateway`, `ModelRouter`, `CostOptimizer`, `FallbackChain`.
- **DB tables:** `llm_calls`, `model_costs`, `routing_rules`.
- **REST APIs:** chat/completion (stream), models list, usage/cost report.
- **Background jobs:** cost aggregation, provider health probe.
- **Dependencies:** emergentintegrations (universal key); Ollama/vLLM self-host optional.
- **Tests:** streaming; tool-calling; auto-route by task; fallback on failure; cost tally.
- **Size:** ~14 files, L.
- **Checklist:** [ ] 3 cloud providers [ ] streaming+tools [ ] routing+fallback+cost.

# Phase 10 — Frontend
**Purpose:** Full operator UI.
- **Folder:** `frontend/src/pages` + components.
- **Files/Pages:** Dashboard, Chat, Timeline, Workspace, Projects, MemoryViewer, TaskViewer, Logs, Settings, AdminPanel, plus `AgentRunStream`, `TaskGraphView`, `FileTree`.
- **State:** AppContext (auth/i18n), TanStack Query, SSE hooks.
- **REST APIs consumed:** all above.
- **Tests:** protected routing; live run stream; file upload UI; graph render; admin gating.
- **Size:** ~30 files, XL.
- **Checklist:** [ ] all pages [ ] live timeline [ ] responsive + RTL/LTR.

# Phase 11 — Infrastructure (artifacts)
**Purpose:** Self-host & deploy assets.
- **Folder:** `infra/`.
- **Files:** `Dockerfile.{backend,frontend}`, `docker-compose.yml`, `k8s/*.yaml`, `helm/`, `nginx.conf`, `.github/workflows/ci.yml`.
- **Jobs:** CI build/test/scan; CD deploy.
- **Dependencies:** GitHub Actions, monitoring (Prometheus/Grafana), tracing (OpenTelemetry).
- **Tests:** compose boots; CI green; helm lint.
- **Size:** ~20 files, M. **(Artifacts — not run in preview.)**
- **Checklist:** [ ] images build [ ] CI pipeline [ ] monitoring/alerts defined.

# Phase 12 — Security
**Purpose:** Harden the whole platform.
- **Folder:** `backend/core/security/`, `backend/observability/audit.py`.
- **Files:** `secrets.py`, `encryption.py`, `sandbox_policy.py`, `isolation.py`, `audit.py`, `rate_limit.py`, `scanner.py`.
- **Classes:** `SecretManager`, `Encryptor`, `AuditLogger`, `RateLimiter`, `SecurityScanner`.
- **DB tables:** `audit_logs`, `rate_limits`.
- **REST APIs:** audit query, security report.
- **Jobs:** audit retention, scheduled scans.
- **Tests:** encryption roundtrip; rate-limit trips; sandbox escape attempts blocked; audit completeness.
- **Size:** ~10 files, M.
- **Checklist:** [ ] secrets encrypted [ ] tenant isolation [ ] audit trail [ ] rate limiting.

# Phase 13 — Testing
**Purpose:** Full quality gate.
- **Folder:** `tests/{unit,integration,e2e,load}`.
- **Files:** suites per module + `conftest.py`, `locustfile.py`.
- **Tools:** pytest, playwright, locust, coverage.
- **Tests:** unit ≥80% core; integration cross-module; e2e agent task; load p95 thresholds; benchmark report.
- **Size:** ~40 files, L.
- **Checklist:** [ ] coverage gate [ ] e2e green [ ] load report [ ] benchmarks recorded.

# Phase 14 — Production
**Purpose:** Optimize, document, ship.
- **Folder:** `docs/`, `scripts/`.
- **Files:** `caching.py`, `perf.py`, `installer.sh`, `migrate.py`, `backup.py`, `recovery.py`, `docs/*`.
- **Classes:** `CacheLayer`, `Migrator`, `BackupManager`.
- **Jobs:** scheduled backups, cache warmers.
- **Tests:** migration up/down; backup+restore; cache hit-rate; perf regressions.
- **Size:** ~15 files, M.
- **Checklist (Production):** [ ] caching [ ] docs complete [ ] installer works [ ] backup/recovery verified [ ] go-live checklist signed.

---

## Global Completion Criteria
Every phase ships **working, tested code** verified by the testing agent, with acceptance checklist fully ticked, before the next phase starts.
