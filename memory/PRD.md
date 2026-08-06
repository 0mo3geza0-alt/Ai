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
### Update (2025-07) — Video removed + Live Voice Conversation ✅ verified
- Restored app after GitHub import: rebuilt missing `backend/.env` & `frontend/.env` (MONGO_URL, DB_NAME, JWT_SECRET, EMERGENT_LLM_KEY, REACT_APP_BACKEND_URL). Admin: admin@aiplatform.com / admin12345.
- REMOVED all video generation (gateway `generate_video`/VIDEO_ENDPOINT, studio `/generate/video`, VideoBody, video cost, intent-router `video` action, admin video stat, and all frontend video UI). Backend tested 5/5.
- ADDED Feature 1 "Live Voice Conversation" INSIDE chat: `POST /api/orgs/{org}/chat/sessions/{sid}/voice-chat {message, voice}` -> concise spoken reply + inline base64 MP3 (not saved as creation), persists turns, spends 1 chat credit, VibeVerse identity enforced. Frontend uses browser Web Speech API (STT) + plays TTS; animated voice overlay in Chat.js. Backend tested 7/7.
- Voice/voiceover also still works via unified chat intent (kind='voice') and `/generate/audio` (real TTS via Emergent key).
- Remaining chosen roadmap for this session: (2) Chat-with-files RAG, (3) Prompt Gallery, (4) Remix, (5) Agent Marketplace + scheduling (scheduling prioritized per user).


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

## Phase 11 — Video quality + Downloads + Stripe Billing (2026-06 update) ✅ verified (backend 5/5 pytest, frontend E2E 100%)
- **Video model upgraded**: `llm/gateway.py` VIDEO_ENDPOINT → `fal-ai/minimax/hailuo-02/standard/text-to-video` (was `ltx-video`). `generate_video(prompt, duration="6")` now sends `prompt_optimizer=True` for far better prompt adherence + quality; timeout raised to 600s. Verified via live gateway call (returns real mp4).
- **Download-to-device** buttons added for generated media:
  - `Creations.js`: `download-<id>` button (fetch blob → `<a download>`), correct extension per kind.
  - `Create.js` studio: `image-download-link`, `video-download-link`, `music-download-link` (+ existing audio).
  - Public `SharePage.js`: `share-download-btn` so anyone opening a shared link can save the file to their phone.
- **Stripe subscription billing** (Flow A claimable sandbox, test mode; GB + digital SaaS → Stripe Tax fallback since sandbox is managed-payments-ineligible):
  - `billing/setup_stripe.py`: catalog (Pro $19/mo, $180/yr; Business $49/mo, $470/yr) + `PLAN_BY_LOOKUP` (pro→10k credits, business→50k) + `ensure_tax_settings` (GB head office). Idempotent, runs on startup.
  - `billing/router.py`: `GET /api/billing/plans`, `POST /api/billing/orgs/{oid}/checkout` (customer_email prefill, managed_payments→automatic_tax fallback), `GET /api/billing/status/{sid}` (webhook-fallback flips DB + upgrades org inline), `POST /api/stripe/webhook`.
  - Frontend: `Billing.js` (plan cards + monthly/yearly toggle + Stripe redirect), `PaymentSuccess.js` (polls status), `PaymentCancel.js`; routes `/app/billing`, `/payment/success`, `/payment/cancel`; sidebar `Billing` nav + clickable credits badge.
  - Env: `STRIPE_SECRET_KEY/PUBLISHABLE_KEY/ACCOUNT_ID/WEBHOOK_SECRET/MODE` in backend/.env. Test card 4242 4242 4242 4242.
  - **Billing model**: platform OWNER pays Emergent (Universal Key); end-users pay the owner via Stripe. On paid, org `plan`+`credits` upgrade. E2E verified: fresh user free→Pro (10k credits) via real test-mode payment.
- Pytest: `/app/backend/tests/test_billing.py` (5/5).

## Phase 12 — Full Admin Panel (2026-06 update) ✅ verified (backend 13/13 pytest, frontend 100%)
- **Account suspension** (full): `auth/deps.py get_current_user` + `auth/router.py` login/oauth reject `suspended` users with 403; suspending clears the user's `sessions` so existing tokens die. `serialize_user` exposes `suspended`.
- **Admin endpoints** (`admin_api.py`, global-admin only):
  - `PATCH /api/admin/users/{id}/suspend {suspended}` (self-suspend blocked, sessions cleared).
  - `POST /api/admin/credits/grant-all {add_credits}` — bulk add/deduct credits to every org (floor 0).
  - `PATCH /api/admin/organizations/{id}` — set/add/deduct credits (floored) + plan free/pro/business.
  - `/users` now returns `suspended`.
- **Admin UI** (`Admin.js`, rebuilt, tabbed): Overview stats (incl. video/music), Users (search + role Select + Suspend/Reactivate + 2-step Delete), Organizations (grant-to-all + search + plan Select + credit Add/Deduct/Set with live credit pill). Non-admin sees `admin-denied`.
- Pytest: `/app/backend/tests/test_admin_panel.py` (13/13).
- Note: deleting a user does not cascade-delete their auto-created org (informational).

## Phase 13 — Admin panel v2 (2026-06 update) ✅ verified (backend 6/6 new + 13/13 regression, frontend 100%)
- **Delete cleanup (cascade)**: `admin_api.delete_user` now removes the user's owned orgs + all data scoped to them (creations, projects, artifacts, chat, api_keys, agents, memories, teams, payment_transactions) and the user's own footprint (memberships, sessions, creations, keys). Returns `orgs_removed`.
- **Admin activity log**: `admin_activity` collection + `_log()` helper. Every suspend/reactivate, role change, org credit/plan update, grant-all, delete, and monthly-reset is recorded (actor_email, action, target_label, detail, created_at). `GET /api/admin/activity` (last 300, newest first). UI: new **Activity** tab.
- **Auto monthly reset**: `billing/monthly_reset.py` — `apply_monthly_reset(force)` sets each org's credits to `PLAN_CREDITS[plan]` (free 200 / pro 10k / business 50k) + `last_reset_month`. Startup backfills current month (no wipe on deploy) then hourly loop refills on calendar rollover. Manual trigger `POST /api/admin/credits/monthly-reset` + **"Refill to plan"** button in the Orgs tab.
- Pytest: `/app/backend/tests/test_admin_v2.py` (6/6).

## Phase 14 — Unified multimodal "AI Studio" chat (2026-06 update) ✅ verified (backend 6/6, frontend 100%)
- **Merged Create Studio into the chat** (ChatGPT-style). Removed the Create Studio page/route/nav (`Create.js` deleted, `/app/create` → redirect to chat); chat nav renamed **"AI Studio"**.
- **Intent router**: `gateway.route_intent` (fast `gemini-3-flash-preview`) classifies each message → `chat|image|video|voice|document|code|webapp` + extracted prompt + friendly reply.
- **Unified endpoint** `POST /api/orgs/{oid}/chat/sessions/{sid}/agent`: generates the right modality and returns `{action, kind, content, media}`; messages persist `kind`+`media`. Image/voice/document/code inline; **video & webapp run as background jobs** (poll `/creations/{cid}/status`) to avoid the ~60s ingress timeout on long generations.
- **Webapp/games/sites**: generates ONE self-contained HTML doc → stored as a creation → rendered as a **live iframe preview** in chat with Open (full screen) + Download.
- **Frontend `Chat.js`** rewritten: markdown (react-markdown@9), code block + Copy, inline image/voice/video with Download, webapp live preview, suggestion chips, loading states, session CRUD.
- Pytest: `/app/backend/tests/test_unified_agent.py` (6/6).

## Phase 15 — Chat power-ups: attachments, streaming, regenerate, app-edit (2026-06) ✅ verified (backend 11/11, frontend 100%, regenerate bug fixed)
- **File/Image attachments**: `POST /api/orgs/{oid}/uploads` (multipart, ≤15MB) + `GET /uploads/{uid}/file`. Chat paperclip uploads → attachment chip. Image → vision (describe) or **image edit** (nano banana with source image); non-image file (pdf/txt/csv) folded in as context via `gateway.describe_media`. User bubble shows the image thumbnail.
- **Streaming replies**: SSE `POST .../agent/stream` (events start/delta*/done, `X-Accel-Buffering: no`); `gateway.stream_chat` streams tokens (supports image/file). Frontend fetch ReadableStream appends deltas live.
- **Regenerate & variations**: button under each assistant message re-runs the preceding user prompt (preserves the original attachment — drop bug fixed).
- **Edit the app**: follow-ups like "make the header blue" re-route to webapp and rebuild using the previous app's HTML as context (`_last_webapp_html`).
- Refactor: non-chat gen extracted to `_run_action`; `edit_image`/`describe_media`/`stream_chat` added; `route_intent(has_image,has_file)` + app-edit hint.
- Pytest: `/app/backend/tests/test_streaming_uploads.py` (5/5).

## Ownership & billing model (clarified to user, 2026-06)
- Owner owns 100% of the code/IP. Owner pays Emergent via Universal Key for all real generations (image/video/voice cost real money — in-app "credits" are just an owner-controlled meter). End-users pay the owner via Stripe.
