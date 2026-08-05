import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from bson import ObjectId
from pydantic import BaseModel

from core.db import get_db
from core.base_models import utcnow
from auth.deps import require_permission, get_current_user
from workspace.storage import put_object, get_object, APP_NAME
from llm import gateway

router = APIRouter(prefix="/api")

COST = {"chat": 1, "document": 1, "code": 2, "image": 5, "audio": 3}


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


class AudioBody(BaseModel):
    text: str
    voice: str = "alloy"
    model: str = "tts-1"


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


async def _spend(db, org_id: str, kind: str):
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    credits = org.get("credits", 0)
    cost = COST[kind]
    if credits < cost:
        raise HTTPException(status_code=402, detail="Not enough credits. Upgrade the organization plan.")
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$inc": {"credits": -cost}})
    return credits - cost


async def _refund(db, org_id: str, kind: str):
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$inc": {"credits": COST[kind]}})


async def _log_creation(db, org_id, user_id, kind, title, prompt, content="", storage_path=None, content_type=None, meta=None):
    doc = {"org_id": org_id, "user_id": user_id, "kind": kind, "title": title, "prompt": prompt,
           "content": content, "storage_path": storage_path, "content_type": content_type,
           "meta": meta or {}, "created_at": utcnow()}
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
    results = []
    for _ in range(n):
        remaining = await _spend(db, org_id, "image")
        try:
            mime, data = await gateway.generate_image(body.prompt)
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
                                  storage_path=path, content_type=mime)
        results.append({"id": cid, "url": f"/api/orgs/{org_id}/creations/{cid}/file"})
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    return {"images": results, "credits": org.get("credits", 0)}


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
             "content": i.get("content", ""), "meta": i.get("meta", {}), "created_at": _iso(i.get("created_at"))}
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
