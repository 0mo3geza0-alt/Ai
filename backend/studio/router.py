import uuid
import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from bson import ObjectId
from pydantic import BaseModel

from core.db import get_db
from core.base_models import utcnow
from auth.deps import require_permission, get_current_user
from workspace.storage import put_object, get_object, APP_NAME
from llm import gateway

router = APIRouter(prefix="/api")

COST = {"chat": 1, "document": 1, "code": 2, "image": 5, "audio": 3, "video": 15, "music": 8, "research": 2}


# ----------------------------------------------------------------- schemas
class ChatSessionBody(BaseModel):
    title: str = "New chat"


class ChatSendBody(BaseModel):
    message: str
    provider: str | None = None
    model: str | None = None


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


class VideoBody(BaseModel):
    prompt: str


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
    return [{"id": str(x["_id"]), "title": x.get("title"), "updated_at": _iso(x.get("updated_at"))} for x in s]


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
    return [{"role": m["role"], "content": m["content"], "created_at": _iso(m["created_at"])} for m in msgs]


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


# ----------------------------------------------------------------- video (fal.ai, background job)
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


@router.post("/orgs/{org_id}/generate/video")
async def gen_video(org_id: str, body: VideoBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    remaining = await _spend(db, org_id, "video")
    cid = await _log_creation(db, org_id, ctx["user"]["id"], "video", body.prompt[:60], body.prompt, meta={"status": "processing"})
    await db.creations.update_one({"_id": ObjectId(cid)}, {"$set": {"status": "processing"}})
    asyncio.create_task(_run_media_job(org_id, cid, "video", lambda: gateway.generate_video(body.prompt), "mp4"))
    return {"id": cid, "status": "processing", "credits": remaining}


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


# ----------------------------------------------------------------- streaming chat (SSE)
@router.post("/orgs/{org_id}/chat/sessions/{sid}/stream")
async def chat_stream(org_id: str, sid: str, body: ChatSendBody, ctx: dict = Depends(require_permission("file:write"))):
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

    async def event_stream():
        buf = ""
        for word in reply.split(" "):
            buf += word + " "
            yield f"data: {json.dumps({'delta': word + ' '})}\n\n"
            await asyncio.sleep(0.02)
        yield f"data: {json.dumps({'done': True, 'credits': remaining, 'title': upd.get('title', session.get('title'))})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ----------------------------------------------------------------- share / export
@router.post("/orgs/{org_id}/creations/{cid}/share")
async def share_creation(org_id: str, cid: str, ctx: dict = Depends(require_permission("file:read"))):
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
