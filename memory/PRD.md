# NeuraForge — AI Platform (منصة ذكاء اصطناعي)

## Original Problem Statement
Integrated web platform where users use AI tools (chat, text generation, image generation) from one place, with accounts and subscriptions. Bilingual Arabic RTL + English LTR. Stack: React + FastAPI + MongoDB.

## User Choices
- All 3 AI tools in v1 (chat, text, image)
- Models: best mix -> gpt-5.6-terra (chat/text), gemini-3.1-flash-image-preview / Nano Banana (images) via EMERGENT_LLM_KEY
- Auth: JWT email/password
- Payments: none now (Pro upgrade is a mock endpoint)
- Bilingual: Arabic RTL + English LTR with switcher (Arabic default)

## Architecture
- Backend `/app/backend/server.py`: FastAPI, all routes under /api. Auth via JWT (httpOnly cookies + Bearer token fallback). MongoDB collections: users, chat_sessions, messages, history.
- Frontend `/app/frontend/src`: React + Tailwind + shadcn. AppContext = auth + i18n state. Bearer token stored in localStorage (works inside iframe where cookies blocked).
- AI via emergentintegrations LlmChat (EMERGENT_LLM_KEY).

## Credits
chat=1, text=1, image=5. Free=100, Pro=10000.

## Implemented (2026-08-05)
- JWT auth: register/login/logout/me/refresh; admin seeding.
- Landing page (hero + features bento + pricing), Arabic RTL default.
- Dashboard with sidebar nav, stats, quick actions.
- AI Chat with multi-session saved conversations.
- Text Studio (article/rewrite/summarize).
- Image Studio (text-to-image, base64 data-url).
- History (text + image ops) with filters + delete.
- Settings (profile, password, upgrade to Pro).
- Language switcher AR/EN with dir toggle.
- Fixed: 401 on authenticated AI calls in iframe -> Bearer token auth. Verified by testing agent (100% backend + frontend).

## Backlog / Remaining
- P1: Stripe real payments for Pro subscription
- P1: Object storage for generated images (currently base64 data-url in Mongo/history)
- P2: Streaming chat responses (SSE)
- P2: Password reset (forgot-password flow UI)
- P2: Image editing with reference image
- P2: Token expiry auto-refresh on 401
