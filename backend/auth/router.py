import os
import uuid
import hashlib
import secrets
from datetime import timedelta
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from bson import ObjectId

from core.db import get_db
from core.base_models import utcnow
from auth import security as sec
from auth.models import (RegisterBody, LoginBody, OAuthBody, RefreshBody, OrgBody,
                         TeamBody, MemberBody, TeamMemberBody, ApiKeyBody)
from auth.oauth import exchange_session
from auth.deps import get_current_user, require_permission
from auth.rbac import ROLES
from auth.service import (serialize_user, serialize_org, serialize_team,
                          serialize_membership, serialize_api_key)

router = APIRouter(prefix="/api")


async def _create_personal_org(db, user_id: str, name: str) -> str:
    org = {"name": f"{name}'s Org", "owner_id": user_id, "created_at": utcnow(),
           "plan": "free", "credits": 200}
    res = await db.organizations.insert_one(org)
    oid = str(res.inserted_id)
    await db.memberships.insert_one({"org_id": oid, "user_id": user_id, "role": "owner",
                                     "created_at": utcnow()})
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"default_org_id": oid}})
    return oid


async def _issue_tokens(db, user: dict) -> dict:
    uid = str(user["_id"])
    jti = uuid.uuid4().hex
    access = sec.create_access_token(uid, user["email"], user.get("global_role", "user"))
    refresh = sec.create_refresh_token(uid, jti)
    await db.sessions.insert_one({"user_id": uid, "jti": jti,
                                  "expires_at": utcnow() + timedelta(days=sec.REFRESH_TTL_DAYS),
                                  "created_at": utcnow()})
    return {"access": access, "refresh": refresh}


def _set_cookies(response: Response, tokens: dict):
    response.set_cookie("access_token", tokens["access"], httponly=True, secure=True,
                        samesite="none", max_age=3600, path="/")
    response.set_cookie("refresh_token", tokens["refresh"], httponly=True, secure=True,
                        samesite="none", max_age=604800, path="/")


# ----------------------------------------------------------------- auth
@router.post("/auth/register")
async def register(body: RegisterBody, response: Response):
    db = get_db()
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {"email": email, "name": body.name, "password_hash": sec.hash_password(body.password),
           "global_role": "user", "auth_provider": "local", "created_at": utcnow()}
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    await _create_personal_org(db, str(res.inserted_id), body.name)
    doc = await db.users.find_one({"_id": res.inserted_id})
    tokens = await _issue_tokens(db, doc)
    _set_cookies(response, tokens)
    return {"user": serialize_user(doc), "token": tokens["access"], "refresh_token": tokens["refresh"]}


@router.post("/auth/login")
async def login(body: LoginBody, response: Response):
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not user.get("password_hash") or not sec.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("suspended"):
        raise HTTPException(status_code=403, detail="Your account has been suspended. Please contact support.")
    tokens = await _issue_tokens(db, user)
    _set_cookies(response, tokens)
    return {"user": serialize_user(user), "token": tokens["access"], "refresh_token": tokens["refresh"]}


@router.post("/auth/oauth/emergent")
async def oauth_emergent(body: OAuthBody, response: Response):
    db = get_db()
    profile = exchange_session(body.session_id)
    email = profile["email"].lower()
    user = await db.users.find_one({"email": email})
    if user and user.get("suspended"):
        raise HTTPException(status_code=403, detail="Your account has been suspended. Please contact support.")
    if not user:
        doc = {"email": email, "name": profile.get("name", email), "picture": profile.get("picture"),
               "global_role": "user", "auth_provider": "google", "created_at": utcnow()}
        res = await db.users.insert_one(doc)
        await _create_personal_org(db, str(res.inserted_id), doc["name"])
        user = await db.users.find_one({"_id": res.inserted_id})
    else:
        await db.users.update_one({"_id": user["_id"]},
                                  {"$set": {"picture": profile.get("picture"), "name": user.get("name") or profile.get("name")}})
        user = await db.users.find_one({"_id": user["_id"]})
    tokens = await _issue_tokens(db, user)
    _set_cookies(response, tokens)
    return {"user": serialize_user(user), "token": tokens["access"], "refresh_token": tokens["refresh"]}


@router.post("/auth/logout")
async def logout(response: Response, current_user: dict = Depends(get_current_user)):
    db = get_db()
    await db.sessions.delete_many({"user_id": current_user["id"]})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    return serialize_user(current_user)


@router.put("/auth/me/preferences")
async def update_preferences(body: dict, current_user: dict = Depends(get_current_user)):
    """Persist the user's chosen voice companion + voice + 18+ confirmation."""
    db = get_db()
    prefs = current_user.get("preferences") or {}
    if "voice_agent" in body:
        prefs["voice_agent"] = body.get("voice_agent")
    if "voice" in body:
        prefs["voice"] = body.get("voice")
    if "dialect" in body:
        prefs["dialect"] = body.get("dialect")
    if "adult_confirmed" in body:
        prefs["adult_confirmed"] = bool(body.get("adult_confirmed"))
    prefs["onboarded"] = True
    await db.users.update_one({"_id": current_user["_id"]}, {"$set": {"preferences": prefs}})
    current_user["preferences"] = prefs
    return serialize_user(current_user)


@router.post("/auth/refresh")
async def refresh(body: RefreshBody, request: Request, response: Response):
    db = get_db()
    token = body.refresh_token or request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = sec.decode_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    session = await db.sessions.find_one({"jti": payload["jti"]})
    if not session:
        raise HTTPException(status_code=401, detail="Session revoked")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    access = sec.create_access_token(str(user["_id"]), user["email"], user.get("global_role", "user"))
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=3600, path="/")
    return {"token": access}


# ----------------------------------------------------------------- orgs
@router.get("/orgs")
async def list_orgs(current_user: dict = Depends(get_current_user)):
    db = get_db()
    memberships = await db.memberships.find({"user_id": current_user["id"]}).to_list(200)
    out = []
    for m in memberships:
        org = await db.organizations.find_one({"_id": ObjectId(m["org_id"])})
        if org:
            d = serialize_org(org)
            d["role"] = m["role"]
            out.append(d)
    return out


@router.post("/orgs")
async def create_org(body: OrgBody, current_user: dict = Depends(get_current_user)):
    db = get_db()
    org = {"name": body.name, "owner_id": current_user["id"], "created_at": utcnow(),
           "plan": "free", "credits": 200}
    res = await db.organizations.insert_one(org)
    oid = str(res.inserted_id)
    await db.memberships.insert_one({"org_id": oid, "user_id": current_user["id"], "role": "owner",
                                     "created_at": utcnow()})
    org["_id"] = res.inserted_id
    d = serialize_org(org); d["role"] = "owner"
    return d


@router.get("/orgs/{org_id}")
async def get_org(org_id: str, ctx: dict = Depends(require_permission("project:read"))):
    db = get_db()
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    d = serialize_org(org); d["role"] = ctx["role"]
    return d


@router.get("/orgs/{org_id}/members")
async def list_members(org_id: str, ctx: dict = Depends(require_permission("project:read"))):
    db = get_db()
    members = await db.memberships.find({"org_id": org_id}).to_list(500)
    out = []
    for m in members:
        u = await db.users.find_one({"_id": ObjectId(m["user_id"])})
        out.append(serialize_membership(m, u))
    return out


@router.post("/orgs/{org_id}/members")
async def add_member(org_id: str, body: MemberBody, ctx: dict = Depends(require_permission("member:manage"))):
    db = get_db()
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {ROLES}")
    user = await db.users.find_one({"email": body.email.lower()})
    if not user:
        raise HTTPException(status_code=404, detail="User with that email not found")
    uid = str(user["_id"])
    if await db.memberships.find_one({"org_id": org_id, "user_id": uid}):
        raise HTTPException(status_code=400, detail="Already a member")
    m = {"org_id": org_id, "user_id": uid, "role": body.role, "created_at": utcnow()}
    res = await db.memberships.insert_one(m); m["_id"] = res.inserted_id
    return serialize_membership(m, user)


@router.delete("/orgs/{org_id}/members/{user_id}")
async def remove_member(org_id: str, user_id: str, ctx: dict = Depends(require_permission("member:manage"))):
    db = get_db()
    m = await db.memberships.find_one({"org_id": org_id, "user_id": user_id})
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if m["role"] == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the owner")
    await db.memberships.delete_one({"_id": m["_id"]})
    return {"ok": True}


# ----------------------------------------------------------------- teams
@router.get("/orgs/{org_id}/teams")
async def list_teams(org_id: str, ctx: dict = Depends(require_permission("project:read"))):
    db = get_db()
    teams = await db.teams.find({"org_id": org_id}).to_list(200)
    return [serialize_team(t) for t in teams]


@router.post("/orgs/{org_id}/teams")
async def create_team(org_id: str, body: TeamBody, ctx: dict = Depends(require_permission("team:manage"))):
    db = get_db()
    t = {"org_id": org_id, "name": body.name, "created_at": utcnow()}
    res = await db.teams.insert_one(t); t["_id"] = res.inserted_id
    return serialize_team(t)


@router.post("/orgs/{org_id}/teams/{team_id}/members")
async def add_team_member(org_id: str, team_id: str, body: TeamMemberBody,
                          ctx: dict = Depends(require_permission("team:manage"))):
    db = get_db()
    if not await db.memberships.find_one({"org_id": org_id, "user_id": body.user_id}):
        raise HTTPException(status_code=400, detail="User must be an org member first")
    if await db.team_members.find_one({"team_id": team_id, "user_id": body.user_id}):
        raise HTTPException(status_code=400, detail="Already on the team")
    await db.team_members.insert_one({"team_id": team_id, "org_id": org_id,
                                      "user_id": body.user_id, "created_at": utcnow()})
    return {"ok": True}


# ----------------------------------------------------------------- api keys
@router.get("/orgs/{org_id}/api-keys")
async def list_api_keys(org_id: str, ctx: dict = Depends(require_permission("apikey:manage"))):
    db = get_db()
    keys = await db.api_keys.find({"org_id": org_id}).to_list(200)
    return [serialize_api_key(k) for k in keys]


@router.post("/orgs/{org_id}/api-keys")
async def create_api_key(org_id: str, body: ApiKeyBody, ctx: dict = Depends(require_permission("apikey:manage"))):
    db = get_db()
    prefix = "ak_" + secrets.token_hex(4)
    secret = secrets.token_hex(24)
    doc = {"org_id": org_id, "user_id": ctx["user"]["id"], "name": body.name, "prefix": prefix,
           "key_hash": hashlib.sha256(secret.encode()).hexdigest(), "scopes": body.scopes,
           "revoked": False, "last_used": None, "created_at": utcnow()}
    res = await db.api_keys.insert_one(doc); doc["_id"] = res.inserted_id
    return serialize_api_key(doc, secret=f"{prefix}.{secret}")


@router.delete("/orgs/{org_id}/api-keys/{key_id}")
async def revoke_api_key(org_id: str, key_id: str, ctx: dict = Depends(require_permission("apikey:manage"))):
    db = get_db()
    await db.api_keys.update_one({"_id": ObjectId(key_id), "org_id": org_id}, {"$set": {"revoked": True}})
    return {"ok": True}
