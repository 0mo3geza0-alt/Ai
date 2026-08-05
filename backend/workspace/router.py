import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from bson import ObjectId

from core.db import get_db
from core.base_models import utcnow
from auth.deps import require_permission
from workspace.models import ProjectBody, ArtifactBody
from workspace.storage import put_object, get_object, APP_NAME

router = APIRouter(prefix="/api")


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _project(p: dict) -> dict:
    return {"id": str(p["_id"]), "org_id": p["org_id"], "name": p["name"],
            "description": p.get("description", ""), "created_by": p.get("created_by"),
            "created_at": _iso(p.get("created_at")), "updated_at": _iso(p.get("updated_at"))}


def _file(f: dict) -> dict:
    return {"id": str(f["_id"]), "project_id": f["project_id"], "file_key": f["file_key"],
            "name": f["name"], "version": f["version"], "content_type": f.get("content_type"),
            "size": f.get("size"), "current": f.get("current", True),
            "created_by": f.get("created_by"), "created_at": _iso(f.get("created_at"))}


def _artifact(a: dict) -> dict:
    return {"id": str(a["_id"]), "project_id": a["project_id"], "name": a["name"],
            "type": a.get("type"), "content": a.get("content", ""),
            "created_at": _iso(a.get("created_at"))}


async def _get_project(db, org_id, pid):
    p = await db.projects.find_one({"_id": ObjectId(pid), "org_id": org_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


# ----------------------------------------------------------------- projects
@router.post("/orgs/{org_id}/projects")
async def create_project(org_id: str, body: ProjectBody, ctx: dict = Depends(require_permission("project:create"))):
    db = get_db()
    doc = {"org_id": org_id, "name": body.name, "description": body.description,
           "created_by": ctx["user"]["id"], "created_at": utcnow(), "updated_at": utcnow()}
    res = await db.projects.insert_one(doc); doc["_id"] = res.inserted_id
    return _project(doc)


@router.get("/orgs/{org_id}/projects")
async def list_projects(org_id: str, ctx: dict = Depends(require_permission("project:read"))):
    db = get_db()
    projects = await db.projects.find({"org_id": org_id}).sort("updated_at", -1).to_list(500)
    return [_project(p) for p in projects]


@router.get("/orgs/{org_id}/projects/{pid}")
async def get_project(org_id: str, pid: str, ctx: dict = Depends(require_permission("project:read"))):
    db = get_db()
    return _project(await _get_project(db, org_id, pid))


@router.put("/orgs/{org_id}/projects/{pid}")
async def update_project(org_id: str, pid: str, body: ProjectBody, ctx: dict = Depends(require_permission("project:update"))):
    db = get_db()
    await _get_project(db, org_id, pid)
    await db.projects.update_one({"_id": ObjectId(pid)},
                                 {"$set": {"name": body.name, "description": body.description, "updated_at": utcnow()}})
    return _project(await _get_project(db, org_id, pid))


@router.delete("/orgs/{org_id}/projects/{pid}")
async def delete_project(org_id: str, pid: str, ctx: dict = Depends(require_permission("project:delete"))):
    db = get_db()
    await _get_project(db, org_id, pid)
    await db.projects.delete_one({"_id": ObjectId(pid)})
    await db.wsfiles.delete_many({"project_id": pid})
    await db.artifacts.delete_many({"project_id": pid})
    return {"ok": True}


# ----------------------------------------------------------------- files + versions
@router.post("/orgs/{org_id}/projects/{pid}/files")
async def upload_file(org_id: str, pid: str, file: UploadFile = File(...),
                      ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    await _get_project(db, org_id, pid)
    file_key = file.filename
    prev = await db.wsfiles.find({"project_id": pid, "file_key": file_key}).sort("version", -1).to_list(1)
    version = (prev[0]["version"] + 1) if prev else 1
    ext = file_key.split(".")[-1] if "." in file_key else "bin"
    path = f"{APP_NAME}/{org_id}/{pid}/{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    try:
        result = put_object(path, data, file.content_type or "application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")
    await db.wsfiles.update_many({"project_id": pid, "file_key": file_key}, {"$set": {"current": False}})
    doc = {"project_id": pid, "org_id": org_id, "file_key": file_key, "name": file_key,
           "version": version, "storage_path": result["path"],
           "content_type": file.content_type or "application/octet-stream",
           "size": result.get("size", len(data)), "current": True,
           "created_by": ctx["user"]["id"], "created_at": utcnow()}
    res = await db.wsfiles.insert_one(doc); doc["_id"] = res.inserted_id
    await db.projects.update_one({"_id": ObjectId(pid)}, {"$set": {"updated_at": utcnow()}})
    return _file(doc)


@router.get("/orgs/{org_id}/projects/{pid}/files")
async def list_files(org_id: str, pid: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    files = await db.wsfiles.find({"project_id": pid, "current": True}).sort("created_at", -1).to_list(1000)
    return [_file(f) for f in files]


@router.get("/orgs/{org_id}/projects/{pid}/files/{file_id}/versions")
async def file_versions(org_id: str, pid: str, file_id: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    f = await db.wsfiles.find_one({"_id": ObjectId(file_id), "project_id": pid})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    versions = await db.wsfiles.find({"project_id": pid, "file_key": f["file_key"]}).sort("version", -1).to_list(200)
    return [_file(v) for v in versions]


@router.get("/orgs/{org_id}/projects/{pid}/files/{file_id}/download")
async def download_file(org_id: str, pid: str, file_id: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    f = await db.wsfiles.find_one({"_id": ObjectId(file_id), "project_id": pid})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data, ctype = get_object(f["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")
    return Response(content=data, media_type=f.get("content_type", ctype),
                    headers={"Content-Disposition": f'attachment; filename="{f["name"]}"'})


# ----------------------------------------------------------------- artifacts
@router.post("/orgs/{org_id}/projects/{pid}/artifacts")
async def create_artifact(org_id: str, pid: str, body: ArtifactBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    await _get_project(db, org_id, pid)
    doc = {"project_id": pid, "org_id": org_id, "name": body.name, "type": body.type,
           "content": body.content, "created_by": ctx["user"]["id"], "created_at": utcnow()}
    res = await db.artifacts.insert_one(doc); doc["_id"] = res.inserted_id
    return _artifact(doc)


@router.get("/orgs/{org_id}/projects/{pid}/artifacts")
async def list_artifacts(org_id: str, pid: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    arts = await db.artifacts.find({"project_id": pid}).sort("created_at", -1).to_list(500)
    return [_artifact(a) for a in arts]
