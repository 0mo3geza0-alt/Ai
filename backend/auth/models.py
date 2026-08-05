from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class RegisterBody(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class OAuthBody(BaseModel):
    session_id: str


class RefreshBody(BaseModel):
    refresh_token: str


class OrgBody(BaseModel):
    name: str


class TeamBody(BaseModel):
    name: str


class MemberBody(BaseModel):
    email: EmailStr
    role: str = "member"


class TeamMemberBody(BaseModel):
    user_id: str


class ApiKeyBody(BaseModel):
    name: str
    scopes: List[str] = ["project:read", "file:read"]
