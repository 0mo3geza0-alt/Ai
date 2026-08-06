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
                         TeamBody, MemberBody, TeamMemberBody, ApiKeyBody,
                         VerifyEmailBody, ResendCodeBody)
from auth.oauth import exchange_session
from auth import email_service
from auth import anti_fraud
from core.logging import logger
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


CODE_TTL_MIN = int(os.environ.get("VERIFICATION_CODE_TTL_MIN", "15"))
RESEND_COOLDOWN_SEC = int(os.environ.get("RESEND_COOLDOWN_SEC", "60"))


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def _generate_and_send_code(db, user: dict) -> None:
    """Create a 6-digit code, store its hash on the user, and email it."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    verification = {
        "code_hash": _hash_code(code),
        "expires_at": utcnow() + timedelta(minutes=CODE_TTL_MIN),
        "attempts": 0,
        "last_sent": utcnow(),
    }
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"verification": verification}})
    try:
        await email_service.send_verification_email(user["email"], user.get("name", ""), code)
    except Exception as e:
        logger.error(f"Failed to send verification email to {user['email']}: {e}")
        raise HTTPException(status_code=502,
                            detail="تعذّر إرسال بريد التفعيل حالياً. يرجى المحاولة بعد قليل.")


# ----------------------------------------------------------------- auth
@router.post("/auth/register")
async def register(body: RegisterBody, request: Request):
    db = get_db()
    email = body.email.lower()

    # 1) block disposable / temporary email providers
    if anti_fraud.is_disposable_email(email):
        raise HTTPException(status_code=400,
                            detail="عذراً، لا نقبل عناوين البريد المؤقتة. يرجى استخدام بريد إلكتروني حقيقي.")

    existing = await db.users.find_one({"email": email})
    if existing:
        if existing.get("email_verified"):
            raise HTTPException(status_code=400, detail="Email already registered")
        # Unverified account already exists -> update details and resend a fresh code
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"name": body.name, "password_hash": sec.hash_password(body.password)}},
        )
        existing = await db.users.find_one({"_id": existing["_id"]})
        await _generate_and_send_code(db, existing)
        return {"requires_verification": True, "email": email,
                "message": "أرسلنا كود تفعيل جديد إلى بريدك."}

    # 2) enforce per-IP / per-device account limits (verified accounts only)
    ip = anti_fraud.get_client_ip(request)
    device = anti_fraud.get_device_fingerprint(request)
    await anti_fraud.check_account_limits(db, ip, device)

    # 3) create the UNVERIFIED user (no tokens, no org until verified)
    doc = {"email": email, "name": body.name,
           "password_hash": sec.hash_password(body.password),
           "global_role": "user", "auth_provider": "local",
           "email_verified": False, "signup_ip": ip, "signup_device": device,
           "created_at": utcnow()}
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    await _generate_and_send_code(db, doc)
    return {"requires_verification": True, "email": email,
            "message": "أرسلنا كود تفعيل إلى بريدك الإلكتروني."}


@router.post("/auth/verify-email")
async def verify_email(body: VerifyEmailBody, response: Response):
    db = get_db()
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="لم يتم العثور على الحساب.")
    if user.get("email_verified"):
        # already verified -> just log them in
        tokens = await _issue_tokens(db, user)
        _set_cookies(response, tokens)
        return {"user": serialize_user(user), "token": tokens["access"],
                "refresh_token": tokens["refresh"]}

    vr = user.get("verification")
    if not vr:
        raise HTTPException(status_code=400, detail="لا يوجد كود تفعيل. يرجى طلب كود جديد.")
    if vr.get("attempts", 0) >= 5:
        raise HTTPException(status_code=429,
                            detail="عدد كبير من المحاولات الخاطئة. يرجى طلب كود جديد.")
    expires_at = vr.get("expires_at")
    if expires_at and utcnow() > expires_at:
        raise HTTPException(status_code=400, detail="انتهت صلاحية الكود. يرجى طلب كود جديد.")
    if _hash_code(body.code.strip()) != vr.get("code_hash"):
        await db.users.update_one({"_id": user["_id"]}, {"$inc": {"verification.attempts": 1}})
        raise HTTPException(status_code=400, detail="الكود غير صحيح. يرجى المحاولة مرة أخرى.")

    # success -> mark verified, drop the verification record, create personal org
    await db.users.update_one({"_id": user["_id"]},
                              {"$set": {"email_verified": True},
                               "$unset": {"verification": ""}})
    if not user.get("default_org_id"):
        await _create_personal_org(db, str(user["_id"]), user.get("name", email))
    user = await db.users.find_one({"_id": user["_id"]})
    tokens = await _issue_tokens(db, user)
    _set_cookies(response, tokens)
    return {"user": serialize_user(user), "token": tokens["access"],
            "refresh_token": tokens["refresh"]}


@router.post("/auth/resend-code")
async def resend_code(body: ResendCodeBody):
    db = get_db()
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    # generic response to avoid account enumeration
    generic = {"ok": True, "message": "إذا كان الحساب موجوداً وغير مفعّل، فقد أرسلنا كوداً جديداً."}
    if not user or user.get("email_verified"):
        return generic
    vr = user.get("verification") or {}
    last_sent = vr.get("last_sent")
    if last_sent and (utcnow() - last_sent).total_seconds() < RESEND_COOLDOWN_SEC:
        wait = int(RESEND_COOLDOWN_SEC - (utcnow() - last_sent).total_seconds())
        raise HTTPException(status_code=429,
                            detail=f"يرجى الانتظار {wait} ثانية قبل طلب كود جديد.")
    await _generate_and_send_code(db, user)
    return generic


@router.post("/auth/login")
async def login(body: LoginBody, response: Response):
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not user.get("password_hash") or not sec.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("suspended"):
        raise HTTPException(status_code=403, detail="Your account has been suspended. Please contact support.")
    if user.get("auth_provider", "local") == "local" and not user.get("email_verified", False):
        # trigger a fresh code so the user can complete verification immediately
        try:
            await _generate_and_send_code(db, user)
        except Exception:
            pass
        raise HTTPException(status_code=403,
                            detail={"code": "email_not_verified",
                                    "msg": "يرجى تفعيل بريدك الإلكتروني أولاً. أرسلنا لك كوداً جديداً."})
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
               "global_role": "user", "auth_provider": "google", "email_verified": True,
               "created_at": utcnow()}
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
