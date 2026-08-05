from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Annotated

import jwt
import bcrypt
from bson import ObjectId
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, BeforeValidator, ConfigDict

from emergentintegrations.llm.chat import LlmChat, UserMessage

# ---------------------------------------------------------------- config
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']

TEXT_MODEL = ("openai", "gpt-5.6-terra")
IMAGE_MODEL = ("gemini", "gemini-3.1-flash-image-preview")

COST = {"chat": 1, "text": 1, "image": 5}
FREE_CREDITS = 100
PRO_CREDITS = 10000

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
api_router = APIRouter(prefix="/api")

# ---------------------------------------------------------------- helpers
def now_utc():
    return datetime.now(timezone.utc)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": now_utc() + timedelta(minutes=60), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": now_utc() + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=3600, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=604800, path="/")

def serialize_user(u: dict) -> dict:
    return {
        "id": str(u["_id"]),
        "email": u["email"],
        "name": u.get("name", ""),
        "role": u.get("role", "user"),
        "plan": u.get("plan", "free"),
        "credits": u.get("credits", 0),
        "created_at": u.get("created_at").isoformat() if isinstance(u.get("created_at"), datetime) else u.get("created_at"),
    }

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def spend_credits(user: dict, kind: str):
    cost = COST[kind]
    if user.get("credits", 0) < cost:
        raise HTTPException(status_code=402, detail="Not enough credits. Please upgrade your plan.")
    await db.users.update_one({"_id": user["_id"]}, {"$inc": {"credits": -cost}})
    return user["credits"] - cost

async def log_history(user_id, kind, prompt, result, meta=None):
    doc = {
        "user_id": str(user_id),
        "kind": kind,
        "prompt": prompt,
        "result": result,
        "meta": meta or {},
        "created_at": now_utc().isoformat(),
    }
    await db.history.insert_one(doc)

# ---------------------------------------------------------------- schemas
class RegisterBody(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)

class LoginBody(BaseModel):
    email: EmailStr
    password: str

class SessionBody(BaseModel):
    title: Optional[str] = "New chat"

class ChatSendBody(BaseModel):
    message: str

class TextBody(BaseModel):
    prompt: str
    mode: str = "article"  # article | rewrite | summarize

class ImageBody(BaseModel):
    prompt: str

class ProfileBody(BaseModel):
    name: str

class PasswordBody(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)

# ---------------------------------------------------------------- auth routes
@api_router.post("/auth/register")
async def register(body: RegisterBody, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "email": email, "name": body.name, "password_hash": hash_password(body.password),
        "role": "user", "plan": "free", "credits": FREE_CREDITS, "created_at": now_utc(),
    }
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    access = create_access_token(str(res.inserted_id), email)
    refresh = create_refresh_token(str(res.inserted_id))
    set_auth_cookies(response, access, refresh)
    return {"user": serialize_user(doc), "token": access}

@api_router.post("/auth/login")
async def login(body: LoginBody, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access = create_access_token(str(user["_id"]), email)
    refresh = create_refresh_token(str(user["_id"]))
    set_auth_cookies(response, access, refresh)
    return {"user": serialize_user(user), "token": access}

@api_router.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}

@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return serialize_user(user)

@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access = create_access_token(str(user["_id"]), user["email"])
        response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=3600, path="/")
        return {"token": access}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------------------------------------------------------- usage / billing
@api_router.get("/usage")
async def usage(user: dict = Depends(get_current_user)):
    uid = str(user["_id"])
    chat_count = await db.messages.count_documents({"user_id": uid, "role": "user"})
    text_count = await db.history.count_documents({"user_id": uid, "kind": "text"})
    image_count = await db.history.count_documents({"user_id": uid, "kind": "image"})
    return {
        "plan": user.get("plan", "free"),
        "credits": user.get("credits", 0),
        "max_credits": PRO_CREDITS if user.get("plan") == "pro" else FREE_CREDITS,
        "counts": {"chat": chat_count, "text": text_count, "image": image_count},
    }

@api_router.post("/billing/upgrade")
async def upgrade(user: dict = Depends(get_current_user)):
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"plan": "pro", "credits": PRO_CREDITS}})
    u = await db.users.find_one({"_id": user["_id"]})
    return serialize_user(u)

# ---------------------------------------------------------------- chat
@api_router.get("/chat/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    uid = str(user["_id"])
    sessions = await db.chat_sessions.find({"user_id": uid}).sort("updated_at", -1).to_list(200)
    return [{"id": str(s["_id"]), "title": s.get("title", "New chat"), "updated_at": s.get("updated_at")} for s in sessions]

@api_router.post("/chat/sessions")
async def create_session(body: SessionBody, user: dict = Depends(get_current_user)):
    doc = {"user_id": str(user["_id"]), "title": body.title or "New chat",
           "created_at": now_utc().isoformat(), "updated_at": now_utc().isoformat()}
    res = await db.chat_sessions.insert_one(doc)
    return {"id": str(res.inserted_id), "title": doc["title"], "updated_at": doc["updated_at"]}

@api_router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    await db.chat_sessions.delete_one({"_id": ObjectId(session_id), "user_id": str(user["_id"])})
    await db.messages.delete_many({"session_id": session_id})
    return {"ok": True}

@api_router.get("/chat/sessions/{session_id}/messages")
async def get_messages(session_id: str, user: dict = Depends(get_current_user)):
    msgs = await db.messages.find({"session_id": session_id, "user_id": str(user["_id"])}).sort("created_at", 1).to_list(1000)
    return [{"role": m["role"], "content": m["content"], "created_at": m["created_at"]} for m in msgs]

@api_router.post("/chat/sessions/{session_id}/send")
async def send_chat(session_id: str, body: ChatSendBody, user: dict = Depends(get_current_user)):
    uid = str(user["_id"])
    session = await db.chat_sessions.find_one({"_id": ObjectId(session_id), "user_id": uid})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    remaining = await spend_credits(user, "chat")

    history = await db.messages.find({"session_id": session_id}).sort("created_at", 1).to_list(1000)
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id,
                   system_message="You are a helpful, knowledgeable AI assistant. Answer clearly and reply in the same language the user uses.")
    chat.with_model(*TEXT_MODEL)
    # replay prior context
    context = ""
    for m in history:
        context += f"{m['role']}: {m['content']}\n"
    prompt = (context + f"user: {body.message}") if context else body.message

    try:
        reply = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logger.exception("chat error")
        await db.users.update_one({"_id": user["_id"]}, {"$inc": {"credits": COST["chat"]}})
        raise HTTPException(status_code=502, detail=f"AI error: {e}")

    ts = now_utc().isoformat()
    await db.messages.insert_many([
        {"session_id": session_id, "user_id": uid, "role": "user", "content": body.message, "created_at": ts},
        {"session_id": session_id, "user_id": uid, "role": "assistant", "content": reply, "created_at": ts},
    ])
    update = {"updated_at": ts}
    if session.get("title", "New chat") == "New chat":
        update["title"] = body.message[:40]
    await db.chat_sessions.update_one({"_id": ObjectId(session_id)}, {"$set": update})
    return {"reply": reply, "credits": remaining, "title": update.get("title", session.get("title"))}

# ---------------------------------------------------------------- text generation
@api_router.post("/text/generate")
async def generate_text(body: TextBody, user: dict = Depends(get_current_user)):
    remaining = await spend_credits(user, "text")
    prompts = {
        "article": f"Write a well-structured, engaging article about the following topic. Use the same language as the input.\n\nTopic: {body.prompt}",
        "rewrite": f"Rewrite and improve the following text keeping the same meaning and language. Make it clearer and more professional.\n\nText: {body.prompt}",
        "summarize": f"Summarize the following text into concise key points. Use the same language as the input.\n\nText: {body.prompt}",
    }
    instruction = prompts.get(body.mode, prompts["article"])
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"text-{secrets.token_hex(6)}",
                   system_message="You are an expert writer and editor.")
    chat.with_model(*TEXT_MODEL)
    try:
        result = await chat.send_message(UserMessage(text=instruction))
    except Exception as e:
        await db.users.update_one({"_id": user["_id"]}, {"$inc": {"credits": COST["text"]}})
        raise HTTPException(status_code=502, detail=f"AI error: {e}")
    await log_history(user["_id"], "text", body.prompt, result, {"mode": body.mode})
    return {"result": result, "credits": remaining}

# ---------------------------------------------------------------- image generation
@api_router.post("/image/generate")
async def generate_image(body: ImageBody, user: dict = Depends(get_current_user)):
    remaining = await spend_credits(user, "image")
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"img-{secrets.token_hex(6)}",
                   system_message="You are an AI image generator.")
    chat.with_model(*IMAGE_MODEL).with_params(modalities=["image", "text"])
    try:
        text, images = await chat.send_message_multimodal_response(UserMessage(text=body.prompt))
    except Exception as e:
        await db.users.update_one({"_id": user["_id"]}, {"$inc": {"credits": COST["image"]}})
        raise HTTPException(status_code=502, detail=f"AI error: {e}")
    if not images:
        await db.users.update_one({"_id": user["_id"]}, {"$inc": {"credits": COST["image"]}})
        raise HTTPException(status_code=502, detail="No image was generated. Try a different prompt.")
    img = images[0]
    data_url = f"data:{img['mime_type']};base64,{img['data']}"
    await log_history(user["_id"], "image", body.prompt, data_url, {})
    return {"image": data_url, "credits": remaining}

# ---------------------------------------------------------------- history
@api_router.get("/history")
async def get_history(user: dict = Depends(get_current_user)):
    items = await db.history.find({"user_id": str(user["_id"])}).sort("created_at", -1).to_list(500)
    return [{"id": str(i["_id"]), "kind": i["kind"], "prompt": i["prompt"],
             "result": i["result"], "meta": i.get("meta", {}), "created_at": i["created_at"]} for i in items]

@api_router.delete("/history/{item_id}")
async def delete_history(item_id: str, user: dict = Depends(get_current_user)):
    await db.history.delete_one({"_id": ObjectId(item_id), "user_id": str(user["_id"])})
    return {"ok": True}

# ---------------------------------------------------------------- account
@api_router.put("/account/profile")
async def update_profile(body: ProfileBody, user: dict = Depends(get_current_user)):
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"name": body.name}})
    u = await db.users.find_one({"_id": user["_id"]})
    return serialize_user(u)

@api_router.post("/account/password")
async def change_password(body: PasswordBody, user: dict = Depends(get_current_user)):
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    return {"ok": True}

@api_router.get("/")
async def root():
    return {"message": "AI Platform API"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@aiplatform.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin12345")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "email": admin_email, "name": "Admin", "password_hash": hash_password(admin_password),
            "role": "admin", "plan": "pro", "credits": PRO_CREDITS, "created_at": now_utc(),
        })
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
    logger.info("Startup complete")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
