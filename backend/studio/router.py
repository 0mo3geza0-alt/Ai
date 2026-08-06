import uuid
import json
import os
import base64
import tempfile
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from bson import ObjectId
from pydantic import BaseModel

from core.db import get_db
from core.base_models import utcnow
from core.logging import logger
from auth.deps import require_permission, get_current_user
from workspace.storage import put_object, get_object, APP_NAME
from llm import gateway

router = APIRouter(prefix="/api")

COST = {"chat": 1, "document": 1, "code": 2, "image": 5, "audio": 3, "music": 8, "research": 2}


# ----------------------------------------------------------------- schemas
class ChatSessionBody(BaseModel):
    title: str = "New chat"


class ChatSendBody(BaseModel):
    message: str
    provider: str | None = None
    model: str | None = None


class Attachment(BaseModel):
    path: str
    mime: str
    kind: str = "file"          # image | file
    name: str | None = None
    url: str | None = None


class AgentBody(BaseModel):
    message: str
    attachment: Attachment | None = None


class DocBody(BaseModel):
    prompt: str
    mode: str = "report"          # report | presentation | article
    provider: str | None = None
    model: str | None = None


class CodeBody(BaseModel):
    prompt: str
    language: str = "python"
    provider: str | None = None
    model: str | None = None
    project_id: str | None = None  # optionally save as artifact


class ImageBody(BaseModel):
    prompt: str
    variations: int = 1
    modifier: str | None = None   # none | no-background | upscale | photorealistic | anime | 3d


class MusicBody(BaseModel):
    prompt: str
    seconds: int = 30


class ResearchBody(BaseModel):
    query: str


IMAGE_MODIFIERS = {
    "no-background": "isolated on a plain transparent white background, product cutout, no scenery",
    "upscale": "ultra high resolution, 4k, sharp details, professionally enhanced",
    "photorealistic": "photorealistic, cinematic lighting, DSLR photo, highly detailed",
    "anime": "anime illustration style, vibrant colors, clean linework",
    "3d": "3d rendered, octane render, soft studio lighting",
}


class AudioBody(BaseModel):
    text: str
    voice: str = "alloy"
    model: str = "tts-1"


class VoiceChatBody(BaseModel):
    message: str
    voice: str = "nova"
    agent: str | None = None      # voice-agent id (personality + default voice)
    adult_ok: bool = False        # user confirmed 18+ for adult agents
    dialect: str | None = None    # egyptian | gulf | levantine | standard


class VoiceSampleBody(BaseModel):
    agent: str | None = None
    voice: str | None = None
    text: str | None = None


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


async def _spend(db, org_id: str, kind: str):
    """Race-safe: only debit when balance >= cost (atomic conditional update)."""
    cost = COST[kind]
    updated = await db.organizations.find_one_and_update(
        {"_id": ObjectId(org_id), "credits": {"$gte": cost}},
        {"$inc": {"credits": -cost}},
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=402, detail="Not enough credits. Upgrade the organization plan.")
    return updated.get("credits", 0)


async def _refund(db, org_id: str, kind: str):
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$inc": {"credits": COST[kind]}})


async def _log_creation(db, org_id, user_id, kind, title, prompt, content="", storage_path=None, content_type=None, meta=None):
    doc = {"org_id": org_id, "user_id": user_id, "kind": kind, "title": title, "prompt": prompt,
           "content": content, "storage_path": storage_path, "content_type": content_type,
           "status": "done", "meta": meta or {}, "created_at": utcnow()}
    res = await db.creations.insert_one(doc)
    return str(res.inserted_id)


# ----------------------------------------------------------------- model gateway
@router.get("/models")
async def list_models(current_user: dict = Depends(get_current_user)):
    return {"text": gateway.MODELS, "image": {"gemini": ["nano-banana"]}, "voices": gateway.TTS_VOICES}


# ----------------------------------------------------------------- chat
@router.get("/orgs/{org_id}/chat/sessions")
async def chat_sessions(org_id: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    s = await db.chat_sessions.find({"org_id": org_id}).sort("updated_at", -1).to_list(200)
    return [{"id": str(x["_id"]), "title": x.get("title"), "updated_at": _iso(x.get("updated_at")),
             "pinned_doc": x.get("pinned_doc")} for x in s]


@router.post("/orgs/{org_id}/chat/sessions")
async def chat_create_session(org_id: str, body: ChatSessionBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    doc = {"org_id": org_id, "user_id": ctx["user"]["id"], "title": body.title,
           "created_at": utcnow(), "updated_at": utcnow()}
    res = await db.chat_sessions.insert_one(doc)
    return {"id": str(res.inserted_id), "title": body.title}


@router.delete("/orgs/{org_id}/chat/sessions/{sid}")
async def chat_delete_session(org_id: str, sid: str, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    await db.chat_sessions.delete_one({"_id": ObjectId(sid), "org_id": org_id})
    await db.chat_messages.delete_many({"session_id": sid})
    return {"ok": True}


@router.get("/orgs/{org_id}/chat/sessions/{sid}/messages")
async def chat_messages(org_id: str, sid: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    msgs = await db.chat_messages.find({"session_id": sid}).sort("created_at", 1).to_list(1000)
    return [{"role": m["role"], "content": m["content"], "kind": m.get("kind", "text"),
             "media": m.get("media"), "created_at": _iso(m["created_at"])} for m in msgs]


@router.post("/orgs/{org_id}/chat/sessions/{sid}/document")
async def pin_document(org_id: str, sid: str, body: Attachment, ctx: dict = Depends(require_permission("file:write"))):
    """Pin a document to a chat session so every following question is answered using it as context."""
    db = get_db()
    session = await db.chat_sessions.find_one({"_id": ObjectId(sid), "org_id": org_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    doc = {"path": body.path, "mime": body.mime, "kind": "file", "name": body.name, "url": body.url}
    await db.chat_sessions.update_one({"_id": ObjectId(sid)}, {"$set": {"pinned_doc": doc, "updated_at": utcnow()}})
    return {"ok": True, "pinned_doc": doc}


@router.delete("/orgs/{org_id}/chat/sessions/{sid}/document")
async def unpin_document(org_id: str, sid: str, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    await db.chat_sessions.update_one({"_id": ObjectId(sid), "org_id": org_id}, {"$unset": {"pinned_doc": ""}})
    return {"ok": True}


@router.post("/orgs/{org_id}/chat/sessions/{sid}/send")
async def chat_send(org_id: str, sid: str, body: ChatSendBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    session = await db.chat_sessions.find_one({"_id": ObjectId(sid), "org_id": org_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    remaining = await _spend(db, org_id, "chat")
    hist = await db.chat_messages.find({"session_id": sid}).sort("created_at", 1).to_list(1000)
    context = "".join(f"{m['role']}: {m['content']}\n" for m in hist)
    try:
        reply = await gateway.generate_text(
            session_id=sid,
            system="You are a helpful, knowledgeable AI assistant. Reply in the user's language. Use markdown for code and lists.",
            prompt=f"user: {body.message}", provider=body.provider, model=body.model, history=context)
    except Exception as e:
        await _refund(db, org_id, "chat")
        raise HTTPException(status_code=502, detail=f"AI error: {e}")
    ts = utcnow()
    await db.chat_messages.insert_many([
        {"session_id": sid, "org_id": org_id, "role": "user", "content": body.message, "created_at": ts},
        {"session_id": sid, "org_id": org_id, "role": "assistant", "content": reply, "created_at": ts},
    ])
    upd = {"updated_at": ts}
    if session.get("title", "New chat") == "New chat":
        upd["title"] = body.message[:40]
    await db.chat_sessions.update_one({"_id": ObjectId(sid)}, {"$set": upd})
    return {"reply": reply, "credits": remaining, "title": upd.get("title", session.get("title"))}


def _asset_url(org_id: str, cid: str) -> str:
    return f"/api/orgs/{org_id}/creations/{cid}/file"


WEBAPP_SYSTEM = (
    "You are a world-class, award-winning creative front-end engineer and digital designer "
    "(Awwwards / FWA caliber). You build COMPLETE, self-contained, single-file HTML apps, games "
    "and websites that look stunning and feel premium — far beyond generic AI output.\n\n"
    "OUTPUT FORMAT: Return ONE full, valid HTML5 document with all CSS in an inline <style> and all "
    "JS in inline <script> tags. Output ONLY the HTML inside a single ```html code block — no prose.\n\n"
    "You MAY load these trusted CDNs when they elevate the result:\n"
    "- Three.js (https://cdnjs.cloudflare.com/ajax/libs/three/r128/three.min.js) for 3D/WebGL scenes, "
    "particles, immersive animated hero backgrounds.\n"
    "- GSAP 3 + ScrollTrigger (https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js and "
    ".../gsap/3.12.5/ScrollTrigger.min.js) for buttery animations and scroll storytelling.\n"
    "- Tailwind CDN (https://cdn.tailwindcss.com) for fast, consistent styling.\n"
    "- Google Fonts for expressive typography.\n\n"
    "DESIGN BAR — make every output a 'wow':\n"
    "- Bold, intentional typography with strong hierarchy and a characterful display font.\n"
    "- A cohesive modern color system (tasteful gradients + one accent, strong contrast); dark aesthetic "
    "by default unless the user asks otherwise.\n"
    "- Rich micro-interactions: hover states, animated on-scroll reveals, smooth transitions, magnetic/"
    "glow buttons, subtle custom cursor where fitting.\n"
    "- Depth & polish: glassmorphism, soft shadows, glow, grain/noise, layered gradients — tasteful, not gaudy.\n"
    "- For hero / landing / immersive / 3D / game requests, add a REAL Three.js scene or canvas animation "
    "as a centerpiece.\n"
    "- Fully responsive & mobile-first, smooth on phones. Respect prefers-reduced-motion.\n"
    "- Semantic, accessible HTML (keyboard focus, alt text). Performant: requestAnimationFrame, cleanup, no jank.\n"
    "- Write real, contextual copy — never leave lorem-ipsum-only placeholders.\n\n"
    "Deliver a finished, production-quality experience that clearly outshines typical AI results and runs "
    "immediately in a browser with no build step."
)


async def _run_webapp_job(org_id: str, cid: str, prompt: str, edit_html: str | None = None):
    db = get_db()
    try:
        if edit_html:
            gen_prompt = (f"Here is the current app's full HTML:\n```html\n{edit_html}\n```\n\n"
                          f"Apply this change: {prompt}\nReturn the COMPLETE updated HTML document.")
        else:
            gen_prompt = prompt
        raw = await gateway.generate_text(session_id=uuid.uuid4().hex, system=WEBAPP_SYSTEM, prompt=gen_prompt)
        html = gateway.strip_fences(raw)
        path = f"{APP_NAME}/{org_id}/creations/{uuid.uuid4().hex}.html"
        await asyncio.to_thread(put_object, path, html.encode("utf-8"), "text/html")
        await db.creations.update_one({"_id": ObjectId(cid)},
                                      {"$set": {"status": "done", "storage_path": path,
                                                "content_type": "text/html", "content": html}})
    except Exception as e:
        await _refund(db, org_id, "code")
        await db.creations.update_one({"_id": ObjectId(cid)}, {"$set": {"status": "failed", "error": str(e)[:200]}})


async def _fetch_attachment(attachment):
    """Download an attachment from storage -> (image_b64, file_path, file_mime)."""
    if not attachment:
        return None, None, None
    data, _ = await asyncio.to_thread(get_object, attachment.path)
    if attachment.kind == "image":
        return base64.b64encode(data).decode(), None, None
    ext = os.path.splitext(attachment.name or "")[1] or ".bin"
    fd, tmp = tempfile.mkstemp(suffix=ext)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return None, tmp, attachment.mime


async def _last_webapp_html(db, sid):
    msgs = await db.chat_messages.find({"session_id": sid, "kind": "webapp"}).sort("created_at", -1).to_list(20)
    for m in msgs:
        cid = (m.get("media") or {}).get("cid")
        if cid:
            c = await db.creations.find_one({"_id": ObjectId(cid), "status": "done"})
            if c and c.get("content"):
                return c["content"]
    return None


async def _run_action(db, org_id, user_id, sid, action, prompt, lang, reply,
                      img_b64=None, file_path=None, file_mime=None):
    """Run a non-chat generation. Returns (kind, content, media). Raises HTTPException on failure."""
    has_att = bool(img_b64 or file_path)
    # For non-image actions, fold the attachment into the prompt as textual context.
    if has_att and action != "image":
        try:
            desc = await gateway.describe_media("Describe this attachment in detail so it can be used as context.",
                                                img_b64, file_path, file_mime)
            prompt = f"{prompt}\n\n[Context extracted from the user's attachment]:\n{desc}"
        except Exception:
            pass

    if action == "image":
        await _spend(db, org_id, "image")
        try:
            if img_b64:
                mime, data = await gateway.edit_image(prompt, img_b64)
            else:
                mime, data = await gateway.generate_image(prompt)
            ext = "png" if "png" in mime else "jpg"
            path = f"{APP_NAME}/{org_id}/creations/{uuid.uuid4().hex}.{ext}"
            put_object(path, data, mime)
        except Exception as e:
            await _refund(db, org_id, "image"); raise HTTPException(status_code=502, detail=f"Image error: {e}")
        cid = await _log_creation(db, org_id, user_id, "image", prompt[:60], prompt, storage_path=path, content_type=mime)
        return "image", (reply or ("Here's your edited image:" if img_b64 else "Here's your image:")), \
               {"type": "image", "url": _asset_url(org_id, cid), "cid": cid, "status": "done"}

    if action == "voice":
        await _spend(db, org_id, "audio")
        try:
            audio = await gateway.generate_audio(prompt, "nova")
            path = f"{APP_NAME}/{org_id}/creations/{uuid.uuid4().hex}.mp3"
            put_object(path, audio, "audio/mpeg")
        except Exception as e:
            await _refund(db, org_id, "audio"); raise HTTPException(status_code=502, detail=f"Voice error: {e}")
        cid = await _log_creation(db, org_id, user_id, "audio", prompt[:60], prompt, storage_path=path, content_type="audio/mpeg")
        return "voice", (reply or "Here's your voiceover:"), \
               {"type": "voice", "url": _asset_url(org_id, cid), "cid": cid, "status": "done"}

    if action == "document":
        await _spend(db, org_id, "document")
        try:
            doc = await gateway.generate_text(session_id=uuid.uuid4().hex,
                system="You are an expert writer. Write clear, well-structured long-form content in markdown.", prompt=prompt)
        except Exception as e:
            await _refund(db, org_id, "document"); raise HTTPException(status_code=502, detail=f"AI error: {e}")
        cid = await _log_creation(db, org_id, user_id, "document", prompt[:60], prompt, content=doc)
        return "document", doc, {"type": "document", "cid": cid, "status": "done"}

    if action == "code":
        await _spend(db, org_id, "code")
        language = lang or "python"
        system = (f"You are an expert {language} engineer. Output production-ready {language} code only, "
                  f"inside a single fenced code block, with brief inline comments. No prose.")
        try:
            code = await gateway.generate_text(session_id=uuid.uuid4().hex, system=system, prompt=prompt)
        except Exception as e:
            await _refund(db, org_id, "code"); raise HTTPException(status_code=502, detail=f"AI error: {e}")
        cid = await _log_creation(db, org_id, user_id, "code", prompt[:60], prompt, content=code, meta={"language": language})
        return "code", code, {"type": "code", "language": language, "cid": cid, "status": "done"}

    if action == "webapp":
        await _spend(db, org_id, "code")
        edit_html = await _last_webapp_html(db, sid)
        cid = await _log_creation(db, org_id, user_id, "webapp", prompt[:60], prompt, meta={"status": "processing"})
        await db.creations.update_one({"_id": ObjectId(cid)}, {"$set": {"status": "processing"}})
        asyncio.create_task(_run_webapp_job(org_id, cid, prompt, edit_html=edit_html))
        return "webapp", (reply or ("Updating your app…" if edit_html else "Building your app — this takes a few seconds…")), \
               {"type": "webapp", "cid": cid, "status": "processing",
                "status_url": f"/api/orgs/{org_id}/creations/{cid}/status", "url": _asset_url(org_id, cid)}

    return "text", (reply or ""), None


CHAT_SYSTEM = "You are a helpful, knowledgeable AI assistant. Reply in the user's language. Use markdown for code and lists."


# ----------------------------------------------------------------- unified agent (multimodal chat)
@router.post("/orgs/{org_id}/chat/sessions/{sid}/agent")
async def chat_agent(org_id: str, sid: str, body: AgentBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    session = await db.chat_sessions.find_one({"_id": ObjectId(sid), "org_id": org_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    user_id = ctx["user"]["id"]
    att = body.attachment
    await db.chat_messages.insert_one({"session_id": sid, "org_id": org_id, "role": "user",
                                       "content": body.message, "kind": "text",
                                       "media": ({"type": att.kind, "url": att.url, "name": att.name} if att else None),
                                       "created_at": utcnow()})
    hist = await db.chat_messages.find({"session_id": sid}).sort("created_at", 1).to_list(1000)
    context = "".join(f"{m['role']}: {m.get('content', '')}\n" for m in hist[-12:])
    # If no attachment on this message but a document is pinned to the session, use it as context.
    effective_att = att
    if not effective_att and session.get("pinned_doc"):
        try: effective_att = Attachment(**session["pinned_doc"])
        except Exception: effective_att = None
    img_b64, file_path, file_mime = await _fetch_attachment(effective_att)
    route = await gateway.route_intent(body.message, context, has_image=bool(img_b64), has_file=bool(file_path))
    action, prompt, lang, reply = route["action"], route["prompt"], route["language"], route["reply"]

    if action == "chat":
        await _spend(db, org_id, "chat")
        try:
            content = await gateway.generate_text(session_id=sid, system=CHAT_SYSTEM,
                prompt=f"user: {body.message}", history=context) if not (img_b64 or file_path) else \
                await gateway.describe_media(body.message, img_b64, file_path, file_mime)
        except Exception as e:
            await _refund(db, org_id, "chat"); raise HTTPException(status_code=502, detail=f"AI error: {e}")
        kind, media = "text", None
    else:
        kind, content, media = await _run_action(db, org_id, user_id, sid, action, prompt, lang, reply, img_b64, file_path, file_mime)

    a_ts = utcnow()
    adoc = {"session_id": sid, "org_id": org_id, "role": "assistant",
            "content": content, "kind": kind, "media": media, "created_at": a_ts}
    res = await db.chat_messages.insert_one(adoc)
    upd = {"updated_at": a_ts}
    if session.get("title", "New chat") == "New chat":
        upd["title"] = body.message[:40]
    await db.chat_sessions.update_one({"_id": ObjectId(sid)}, {"$set": upd})
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    return {"id": str(res.inserted_id), "role": "assistant", "content": content, "kind": kind,
            "media": media, "action": action, "credits": org.get("credits", 0) if org else 0,
            "title": upd.get("title", session.get("title"))}


# ----------------------------------------------------------------- chat file/image upload
@router.post("/orgs/{org_id}/uploads")
async def upload_attachment(org_id: str, file: UploadFile = File(...), ctx: dict = Depends(require_permission("file:write"))):
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 15MB)")
    mime = file.content_type or "application/octet-stream"
    kind = "image" if mime.startswith("image/") else "file"
    ext = os.path.splitext(file.filename or "")[1] or ""
    path = f"{APP_NAME}/{org_id}/uploads/{uuid.uuid4().hex}{ext}"
    try:
        await asyncio.to_thread(put_object, path, data, mime)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upload failed: {e}")
    db = get_db()
    res = await db.uploads.insert_one({"org_id": org_id, "user_id": ctx["user"]["id"], "storage_path": path,
                                       "mime": mime, "kind": kind, "name": file.filename, "created_at": utcnow()})
    uid = str(res.inserted_id)
    return {"id": uid, "path": path, "mime": mime, "kind": kind, "name": file.filename,
            "url": f"/api/orgs/{org_id}/uploads/{uid}/file"}


@router.get("/orgs/{org_id}/uploads/{uid}/file")
async def serve_upload(org_id: str, uid: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    u = await db.uploads.find_one({"_id": ObjectId(uid), "org_id": org_id})
    if not u:
        raise HTTPException(status_code=404, detail="Upload not found")
    data, ctype = await asyncio.to_thread(get_object, u["storage_path"])
    return Response(content=data, media_type=ctype)


# ----------------------------------------------------------------- unified agent (streaming SSE)
@router.post("/orgs/{org_id}/chat/sessions/{sid}/agent/stream")
async def chat_agent_stream(org_id: str, sid: str, body: AgentBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    session = await db.chat_sessions.find_one({"_id": ObjectId(sid), "org_id": org_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    user_id = ctx["user"]["id"]
    att = body.attachment
    await db.chat_messages.insert_one({"session_id": sid, "org_id": org_id, "role": "user",
                                       "content": body.message, "kind": "text",
                                       "media": ({"type": att.kind, "url": att.url, "name": att.name} if att else None),
                                       "created_at": utcnow()})
    hist = await db.chat_messages.find({"session_id": sid}).sort("created_at", 1).to_list(1000)
    context = "".join(f"{m['role']}: {m.get('content', '')}\n" for m in hist[-12:])
    # If no attachment on this message but a document is pinned to the session, use it as context.
    effective_att = att
    if not effective_att and session.get("pinned_doc"):
        try: effective_att = Attachment(**session["pinned_doc"])
        except Exception: effective_att = None
    img_b64, file_path, file_mime = await _fetch_attachment(effective_att)
    route = await gateway.route_intent(body.message, context, has_image=bool(img_b64), has_file=bool(file_path))
    action, prompt, lang, reply = route["action"], route["prompt"], route["language"], route["reply"]

    async def sse(obj):
        return f"data: {json.dumps(obj)}\n\n"

    async def event_stream():
        nonlocal action
        yield await sse({"type": "start", "action": action})
        try:
            if action == "chat":
                try:
                    await _spend(db, org_id, "chat")
                except HTTPException as he:
                    yield await sse({"type": "error", "detail": he.detail}); return
                acc = ""
                try:
                    async for delta in gateway.stream_chat(sid, CHAT_SYSTEM, f"user: {body.message}", context,
                                                           image_b64=img_b64, file_path=file_path, file_mime=file_mime):
                        acc += delta
                        yield await sse({"type": "delta", "content": delta})
                except Exception as e:
                    await _refund(db, org_id, "chat")
                    yield await sse({"type": "error", "detail": f"AI error: {e}"}); return
                kind, content, media = "text", acc, None
            else:
                try:
                    kind, content, media = await _run_action(db, org_id, user_id, sid, action, prompt, lang, reply,
                                                             img_b64, file_path, file_mime)
                except HTTPException as he:
                    yield await sse({"type": "error", "detail": he.detail}); return

            a_ts = utcnow()
            adoc = {"session_id": sid, "org_id": org_id, "role": "assistant",
                    "content": content, "kind": kind, "media": media, "created_at": a_ts}
            res = await db.chat_messages.insert_one(adoc)
            upd = {"updated_at": a_ts}
            if session.get("title", "New chat") == "New chat":
                upd["title"] = body.message[:40]
            await db.chat_sessions.update_one({"_id": ObjectId(sid)}, {"$set": upd})
            org = await db.organizations.find_one({"_id": ObjectId(org_id)})
            yield await sse({"type": "done", "message": {"id": str(res.inserted_id), "role": "assistant",
                            "content": content, "kind": kind, "media": media},
                            "action": action, "credits": org.get("credits", 0) if org else 0,
                            "title": upd.get("title", session.get("title"))})
        finally:
            if file_path:
                try: os.remove(file_path)
                except Exception: pass

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})



# ----------------------------------------------------------------- document generator
@router.post("/orgs/{org_id}/generate/document")
async def gen_document(org_id: str, body: DocBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    prompts = {
        "report": f"Write a detailed, well-structured professional report in markdown about:\n\n{body.prompt}",
        "presentation": f"Create a slide-by-slide presentation outline in markdown (use '## Slide N: title' headings with bullet points) about:\n\n{body.prompt}",
        "article": f"Write an engaging, SEO-friendly article in markdown about:\n\n{body.prompt}",
    }
    instruction = prompts.get(body.mode, prompts["report"])
    remaining = await _spend(db, org_id, "document")
    try:
        content = await gateway.generate_text(session_id=uuid.uuid4().hex,
                                               system="You are an expert writer and business analyst.",
                                               prompt=instruction, provider=body.provider, model=body.model)
    except Exception as e:
        await _refund(db, org_id, "document")
        raise HTTPException(status_code=502, detail=f"AI error: {e}")
    cid = await _log_creation(db, org_id, ctx["user"]["id"], "document", body.prompt[:60], body.prompt,
                              content=content, meta={"mode": body.mode})
    return {"id": cid, "content": content, "credits": remaining}


# ----------------------------------------------------------------- coding agent
@router.post("/orgs/{org_id}/generate/code")
async def gen_code(org_id: str, body: CodeBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    remaining = await _spend(db, org_id, "code")
    system = (f"You are an expert {body.language} engineer. Output production-ready {body.language} code only, "
              f"inside a single fenced code block, with brief inline comments. No prose before or after.")
    try:
        content = await gateway.generate_text(session_id=uuid.uuid4().hex, system=system,
                                              prompt=body.prompt, provider=body.provider, model=body.model)
    except Exception as e:
        await _refund(db, org_id, "code")
        raise HTTPException(status_code=502, detail=f"AI error: {e}")
    cid = await _log_creation(db, org_id, ctx["user"]["id"], "code", body.prompt[:60], body.prompt,
                              content=content, meta={"language": body.language})
    # optionally save into a project as an artifact
    if body.project_id:
        proj = await db.projects.find_one({"_id": ObjectId(body.project_id), "org_id": org_id})
        if proj:
            await db.artifacts.insert_one({"project_id": body.project_id, "org_id": org_id,
                                           "name": body.prompt[:40], "type": f"code/{body.language}",
                                           "content": content, "created_by": ctx["user"]["id"], "created_at": utcnow()})
    return {"id": cid, "content": content, "credits": remaining, "saved_to_project": bool(body.project_id)}


# ----------------------------------------------------------------- image studio
@router.post("/orgs/{org_id}/generate/image")
async def gen_image(org_id: str, body: ImageBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    n = max(1, min(body.variations, 4))
    prompt = body.prompt
    if body.modifier and body.modifier in IMAGE_MODIFIERS:
        prompt = f"{body.prompt}, {IMAGE_MODIFIERS[body.modifier]}"
    results = []
    for _ in range(n):
        remaining = await _spend(db, org_id, "image")
        try:
            mime, data = await gateway.generate_image(prompt)
        except Exception as e:
            await _refund(db, org_id, "image")
            raise HTTPException(status_code=502, detail=f"AI error: {e}")
        ext = "png" if "png" in mime else "jpg"
        path = f"{APP_NAME}/{org_id}/creations/{uuid.uuid4().hex}.{ext}"
        try:
            put_object(path, data, mime)
        except Exception as e:
            await _refund(db, org_id, "image")
            raise HTTPException(status_code=502, detail=f"Storage error: {e}")
        cid = await _log_creation(db, org_id, ctx["user"]["id"], "image", body.prompt[:60], body.prompt,
                                  storage_path=path, content_type=mime, meta={"modifier": body.modifier})
        results.append({"id": cid, "url": f"/api/orgs/{org_id}/creations/{cid}/file"})
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    return {"images": results, "credits": org.get("credits", 0)}


# ----------------------------------------------------------------- media background job
async def _run_media_job(org_id: str, cid: str, kind: str, fn, ext: str):
    db = get_db()
    try:
        data, mime = await asyncio.to_thread(fn)
        path = f"{APP_NAME}/{org_id}/creations/{uuid.uuid4().hex}.{ext}"
        await asyncio.to_thread(put_object, path, data, mime)
        await db.creations.update_one({"_id": ObjectId(cid)},
                                      {"$set": {"status": "done", "storage_path": path, "content_type": mime}})
    except Exception as e:
        await _refund(db, org_id, kind)
        await db.creations.update_one({"_id": ObjectId(cid)}, {"$set": {"status": "failed", "error": str(e)[:200]}})


@router.post("/orgs/{org_id}/generate/music")
async def gen_music(org_id: str, body: MusicBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    remaining = await _spend(db, org_id, "music")
    cid = await _log_creation(db, org_id, ctx["user"]["id"], "music", body.prompt[:60], body.prompt, meta={"status": "processing"})
    await db.creations.update_one({"_id": ObjectId(cid)}, {"$set": {"status": "processing"}})
    asyncio.create_task(_run_media_job(org_id, cid, "music", lambda: gateway.generate_music(body.prompt, body.seconds), "wav"))
    return {"id": cid, "status": "processing", "credits": remaining}


@router.get("/orgs/{org_id}/creations/{cid}/status")
async def creation_status(org_id: str, cid: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    c = await db.creations.find_one({"_id": ObjectId(cid), "org_id": org_id})
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    status = c.get("status", "done")
    out = {"id": cid, "status": status, "kind": c["kind"]}
    if status == "done" and c.get("storage_path"):
        out["url"] = f"/api/orgs/{org_id}/creations/{cid}/file"
    if status == "failed":
        out["error"] = c.get("error")
    return out


# ----------------------------------------------------------------- research agent (web + citations)
@router.post("/orgs/{org_id}/generate/research")
async def gen_research(org_id: str, body: ResearchBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    remaining = await _spend(db, org_id, "research")
    sources = await asyncio.to_thread(gateway.web_search, body.query, 6)
    src_block = "\n".join(f"[{i+1}] {s['title']} — {s['url']}\n{s['snippet']}" for i, s in enumerate(sources)) or "No web results found."
    system = "You are a meticulous research analyst. Write a concise report in markdown with an overview, key findings as bullet points, and a 'Sources' section listing the numbered sources. Cite sources inline like [1], [2]. Only use the provided sources; if insufficient, say so."
    try:
        content = await gateway.generate_text(session_id=uuid.uuid4().hex, system=system,
                                              prompt=f"Question: {body.query}\n\nWeb sources:\n{src_block}")
    except Exception as e:
        await _refund(db, org_id, "research")
        raise HTTPException(status_code=502, detail=f"AI error: {e}")
    cid = await _log_creation(db, org_id, ctx["user"]["id"], "research", body.query[:60], body.query,
                              content=content, meta={"sources": sources})
    return {"id": cid, "content": content, "sources": sources, "credits": remaining}


# ----------------------------------------------------------------- audio / voiceover
@router.post("/orgs/{org_id}/generate/audio")
async def gen_audio(org_id: str, body: AudioBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    remaining = await _spend(db, org_id, "audio")
    try:
        data = await gateway.generate_audio(body.text, voice=body.voice, model=body.model)
    except Exception as e:
        await _refund(db, org_id, "audio")
        raise HTTPException(status_code=502, detail=f"AI error: {e}")
    path = f"{APP_NAME}/{org_id}/creations/{uuid.uuid4().hex}.mp3"
    try:
        put_object(path, data, "audio/mpeg")
    except Exception as e:
        await _refund(db, org_id, "audio")
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")
    cid = await _log_creation(db, org_id, ctx["user"]["id"], "audio", body.text[:60], body.text,
                              storage_path=path, content_type="audio/mpeg", meta={"voice": body.voice})
    return {"id": cid, "url": f"/api/orgs/{org_id}/creations/{cid}/file", "credits": remaining}


# ----------------------------------------------------------------- live voice conversation (inside chat)
VOICE_CHAT_SYSTEM = (
    "You are having a spoken, real-time voice conversation. Reply the way a person would speak out loud: "
    "natural, warm and concise (usually 1-3 short sentences). Do NOT use markdown, bullet points, code blocks, "
    "emojis or headings — just plain spoken sentences. Always answer in the SAME language the user spoke in. "
    "If the user asks for something long, give a short spoken summary and offer to type out the details."
)


@router.get("/voice-agents")
async def list_voice_agents(current_user: dict = Depends(get_current_user)):
    """Selectable AI voice companions for onboarding + voice mode."""
    return {"agents": [gateway.voice_agent_public(a) for a in gateway.VOICE_AGENTS],
            "voices": gateway.TTS_VOICES}


@router.post("/orgs/{org_id}/voice-sample")
async def voice_sample(org_id: str, body: VoiceSampleBody, ctx: dict = Depends(require_permission("file:read"))):
    """A short spoken preview of an agent/voice (not charged, not saved)."""
    agent = gateway.VOICE_AGENTS_BY_ID.get(body.agent) if body.agent else None
    voice = (body.voice or (agent or {}).get("voice") or "nova")
    speed = (agent or {}).get("speed", 1.0)
    name = (agent or {}).get("name", "your assistant")
    text = (body.text or "").strip() or f"Hey there, I'm {name}. This is how I sound — let's create something amazing together."
    try:
        audio = await gateway.generate_audio(text[:220], voice=voice, speed=speed)
        return {"audio": base64.b64encode(audio).decode("ascii"), "mime": "audio/mpeg"}
    except Exception as e:
        logger.error("Voice sample failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not generate voice sample")


@router.post("/orgs/{org_id}/chat/sessions/{sid}/voice-chat")
async def voice_chat(org_id: str, sid: str, body: VoiceChatBody, ctx: dict = Depends(require_permission("file:write"))):
    """One spoken conversational turn: store user text, generate a concise reply + TTS audio (base64).
    Audio is returned inline (not saved as a creation) to keep the voice conversation lightweight."""
    db = get_db()
    session = await db.chat_sessions.find_one({"_id": ObjectId(sid), "org_id": org_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Empty message")
    user_id = ctx["user"]["id"]

    # Resolve the chosen voice companion (personality + voice + speed).
    agent = gateway.VOICE_AGENTS_BY_ID.get(body.agent) if body.agent else None
    if agent and agent.get("adult"):
        confirmed = body.adult_ok or bool((ctx["user"].get("preferences") or {}).get("adult_confirmed"))
        if not confirmed:
            raise HTTPException(status_code=403, detail="Age confirmation (18+) required for this companion.")
    system = (VOICE_CHAT_SYSTEM + "\n\n" + gateway.VOICE_EXPRESSION_GUIDE
              + gateway.dialect_directive(body.dialect)
              + (("\n\n" + agent["persona"]) if agent else ""))
    voice = body.voice or (agent or {}).get("voice") or "nova"
    base_speed = (agent or {}).get("speed", 1.0)

    await db.chat_messages.insert_one({"session_id": sid, "org_id": org_id, "role": "user",
                                       "content": msg, "kind": "text", "media": None, "created_at": utcnow()})
    hist = await db.chat_messages.find({"session_id": sid}).sort("created_at", 1).to_list(1000)
    context = "".join(f"{m['role']}: {m.get('content', '')}\n" for m in hist[-12:])

    remaining = await _spend(db, org_id, "chat")
    try:
        reply = await gateway.generate_text(session_id=sid, system=system,
                                             prompt=msg, history=context)
    except Exception as e:
        await _refund(db, org_id, "chat")
        raise HTTPException(status_code=502, detail=f"AI error: {e}")
    reply = (reply or "").strip() or "Sorry, I didn't catch that."
    # Auto-detect the emotional mood the model chose and speak it with matching pace for realism.
    mood, reply = gateway.extract_mood(reply)
    speed = gateway.emotion_speed(mood, base_speed)

    audio_b64 = None
    try:
        audio = await gateway.generate_audio(reply, voice=voice, speed=speed)
        audio_b64 = base64.b64encode(audio).decode("ascii")
    except Exception as e:
        logger.error("Voice-chat TTS failed: %s", e)

    await db.chat_messages.insert_one({"session_id": sid, "org_id": org_id, "role": "assistant",
                                       "content": reply, "kind": "text", "media": None, "created_at": utcnow()})
    if not session.get("title") or session.get("title") == "New chat":
        await db.chat_sessions.update_one({"_id": ObjectId(sid)}, {"$set": {"title": msg[:40]}})

    return {"reply": reply, "audio": audio_b64, "mime": "audio/mpeg", "mood": mood, "credits": remaining}



# ----------------------------------------------------------------- creations history
@router.get("/orgs/{org_id}/creations")
async def list_creations(org_id: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    items = await db.creations.find({"org_id": org_id}).sort("created_at", -1).to_list(500)
    out = []
    for i in items:
        d = {"id": str(i["_id"]), "kind": i["kind"], "title": i.get("title"), "prompt": i.get("prompt"),
             "content": i.get("content", ""), "meta": i.get("meta", {}), "status": i.get("status", "done"),
             "created_at": _iso(i.get("created_at"))}
        if i.get("storage_path"):
            d["url"] = f"/api/orgs/{org_id}/creations/{str(i['_id'])}/file"
        out.append(d)
    return out


@router.get("/orgs/{org_id}/creations/{cid}/file")
async def creation_file(org_id: str, cid: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    c = await db.creations.find_one({"_id": ObjectId(cid), "org_id": org_id})
    if not c or not c.get("storage_path"):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data, ctype = get_object(c["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")
    return Response(content=data, media_type=c.get("content_type", ctype))


# ----------------------------------------------------------------- usage / billing
@router.get("/orgs/{org_id}/usage")
async def usage(org_id: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    counts = {}
    for k in ["document", "code", "image", "audio", "chat"]:
        counts[k] = await db.creations.count_documents({"org_id": org_id, "kind": k})
    counts["chat"] = await db.chat_messages.count_documents({"org_id": org_id, "role": "user"})
    return {"credits": org.get("credits", 0), "plan": org.get("plan", "free"), "counts": counts}


@router.post("/orgs/{org_id}/upgrade")
async def upgrade(org_id: str, ctx: dict = Depends(require_permission("member:manage"))):
    db = get_db()
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"plan": "pro", "credits": 10000}})
    return {"plan": "pro", "credits": 10000}


# ----------------------------------------------------------------- streaming chat (SSE, real token streaming)
@router.post("/orgs/{org_id}/chat/sessions/{sid}/stream")
async def chat_stream(org_id: str, sid: str, body: ChatSendBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    session = await db.chat_sessions.find_one({"_id": ObjectId(sid), "org_id": org_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    remaining = await _spend(db, org_id, "chat")
    hist = await db.chat_messages.find({"session_id": sid}).sort("created_at", 1).to_list(1000)
    context = "".join(f"{m['role']}: {m['content']}\n" for m in hist)

    async def event_stream():
        reply = ""
        try:
            async for delta in gateway.stream_text(
                session_id=sid,
                system="You are a helpful, knowledgeable AI assistant. Reply in the user's language. Use markdown for code and lists.",
                prompt=f"user: {body.message}", provider=body.provider, model=body.model, history=context):
                reply += delta
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        except Exception as e:
            await _refund(db, org_id, "chat")
            yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"
            return
        ts = utcnow()
        await db.chat_messages.insert_many([
            {"session_id": sid, "org_id": org_id, "role": "user", "content": body.message, "created_at": ts},
            {"session_id": sid, "org_id": org_id, "role": "assistant", "content": reply, "created_at": ts},
        ])
        upd = {"updated_at": ts}
        if session.get("title", "New chat") == "New chat":
            upd["title"] = body.message[:40]
        await db.chat_sessions.update_one({"_id": ObjectId(sid)}, {"$set": upd})
        yield f"data: {json.dumps({'done': True, 'credits': remaining, 'title': upd.get('title', session.get('title'))})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


# ----------------------------------------------------------------- share / export
@router.post("/orgs/{org_id}/creations/{cid}/share")
async def share_creation(org_id: str, cid: str, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    c = await db.creations.find_one({"_id": ObjectId(cid), "org_id": org_id})
    if not c:
        raise HTTPException(status_code=404, detail="Creation not found")
    token = c.get("share_token") or uuid.uuid4().hex
    await db.creations.update_one({"_id": c["_id"]}, {"$set": {"share_token": token}})
    return {"token": token, "path": f"/share/{token}"}


_EXPORT_MIME = {"md": "text/markdown", "txt": "text/plain", "html": "text/html"}


@router.get("/orgs/{org_id}/creations/{cid}/export")
async def export_creation(org_id: str, cid: str, format: str = "md", ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    c = await db.creations.find_one({"_id": ObjectId(cid), "org_id": org_id})
    if not c:
        raise HTTPException(status_code=404, detail="Creation not found")
    if c["kind"] not in ("document", "code", "research"):
        raise HTTPException(status_code=400, detail="Only text creations can be exported")
    fmt = format if format in _EXPORT_MIME else "md"
    content = c.get("content", "")
    if fmt == "html":
        content = f"<!doctype html><html><head><meta charset='utf-8'><title>{c.get('title')}</title></head><body><pre>{content}</pre></body></html>"
    return Response(content=content.encode("utf-8"), media_type=_EXPORT_MIME[fmt],
                    headers={"Content-Disposition": f'attachment; filename="creation-{cid}.{fmt}"'})


# ----------------------------------------------------------------- public (shared) — no auth
@router.get("/public/creations/{token}")
async def public_creation(token: str):
    db = get_db()
    c = await db.creations.find_one({"share_token": token})
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    d = {"kind": c["kind"], "title": c.get("title"), "prompt": c.get("prompt"),
         "content": c.get("content", ""), "created_at": _iso(c.get("created_at"))}
    if c.get("storage_path"):
        d["url"] = f"/api/public/creations/{token}/file"
    return d


@router.get("/public/creations/{token}/file")
async def public_creation_file(token: str):
    db = get_db()
    c = await db.creations.find_one({"share_token": token})
    if not c or not c.get("storage_path"):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        data, ctype = get_object(c["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")
    return Response(content=data, media_type=c.get("content_type", ctype))


@router.get("/public/gallery")
async def public_gallery(kind: str = "all", limit: int = 60):
    db = get_db()
    q = {"share_token": {"$exists": True}, "status": {"$ne": "processing"}}
    if kind != "all":
        q["kind"] = kind
    items = await db.creations.find(q).sort("created_at", -1).to_list(min(limit, 120))
    out = []
    for i in items:
        d = {"kind": i["kind"], "title": i.get("title"), "prompt": i.get("prompt"),
             "content": (i.get("content", "") or "")[:400], "token": i.get("share_token"),
             "created_at": _iso(i.get("created_at"))}
        if i.get("storage_path"):
            d["url"] = f"/api/public/creations/{i['share_token']}/file"
        out.append(d)
    return out
