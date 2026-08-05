import os
import bcrypt
import jwt
from datetime import timedelta
from core.base_models import utcnow

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
ACCESS_TTL_MIN = 60
REFRESH_TTL_DAYS = 7


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str, email: str, global_role: str) -> str:
    payload = {"sub": user_id, "email": email, "role": global_role,
               "type": "access", "exp": utcnow() + timedelta(minutes=ACCESS_TTL_MIN)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def create_refresh_token(user_id: str, jti: str) -> str:
    payload = {"sub": user_id, "jti": jti, "type": "refresh",
               "exp": utcnow() + timedelta(days=REFRESH_TTL_DAYS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
