"""Memory System & semantic (vector) search — Phase 5 / Module 15."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId

from core.db import get_db
from core.base_models import utcnow
from auth.deps import require_permission
from memory import embeddings as emb

router = APIRouter(prefix="/api")


class MemoryBody(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    tags: list[str] = []
    source: str = "manual"


class SearchBody(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=6, ge=1, le=50)


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


async def search_memories(db, org_id: str, query: str, limit: int = 6, agent_id: str | None = None):
    """Reusable semantic search — used by the memory API and agent RAG."""
    qv = await emb.embed_one(query)
    q = {"org_id": org_id}
    if agent_id:
        q["$or"] = [{"agent_id": agent_id}, {"shared": True}]
    docs = await db.memories.find(q).to_list(3000)
    scored = []
    for d in docs:
        vec = d.get("embedding")
        if not vec:
            continue
        scored.append((emb.cosine(qv, vec), d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"id": str(d["_id"]), "text": d["text"], "tags": d.get("tags", []),
             "source": d.get("source", "manual"), "score": round(s, 4),
             "created_at": _iso(d.get("created_at"))} for s, d in scored[:limit]]


@router.post("/orgs/{org_id}/memories")
async def add_memory(org_id: str, body: MemoryBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    try:
        vector = await emb.embed_one(body.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding failed: {e}")
    doc = {"org_id": org_id, "user_id": ctx["user"]["id"], "text": body.text,
           "tags": body.tags, "source": body.source, "shared": True,
           "embedding": vector, "created_at": utcnow()}
    res = await db.memories.insert_one(doc)
    return {"id": str(res.inserted_id), "dim": len(vector)}


@router.get("/orgs/{org_id}/memories")
async def list_memories(org_id: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    docs = await db.memories.find({"org_id": org_id}).sort("created_at", -1).to_list(500)
    return [{"id": str(d["_id"]), "text": d["text"], "tags": d.get("tags", []),
             "source": d.get("source", "manual"), "agent_id": d.get("agent_id"),
             "created_at": _iso(d.get("created_at"))} for d in docs]


@router.post("/orgs/{org_id}/memories/search")
async def search(org_id: str, body: SearchBody, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    try:
        results = await search_memories(db, org_id, body.query, body.limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")
    return {"results": results}


@router.delete("/orgs/{org_id}/memories/{mid}")
async def delete_memory(org_id: str, mid: str, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    await db.memories.delete_one({"_id": ObjectId(mid), "org_id": org_id})
    return {"ok": True}
