"""Tool Framework & Browser Automation endpoints — Phases 4 & 8."""
import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.deps import require_permission, get_current_user
from tools import registry, browser

router = APIRouter(prefix="/api")


@router.get("/tools")
async def list_tools(_: dict = Depends(get_current_user)):
    """List the tools available to agents & the planning engine."""
    return {"tools": registry.TOOL_SPECS}


class BrowseBody(BaseModel):
    url: str = Field(min_length=3, max_length=2000)
    max_chars: int = Field(default=4000, ge=200, le=20000)


@router.post("/orgs/{org_id}/tools/browse")
async def browse_url(org_id: str, body: BrowseBody,
                     ctx: dict = Depends(require_permission("file:read"))):
    return await asyncio.to_thread(browser.browse, body.url, body.max_chars)


class CalcBody(BaseModel):
    expression: str = Field(min_length=1, max_length=500)


@router.post("/orgs/{org_id}/tools/calc")
async def calc(org_id: str, body: CalcBody,
               ctx: dict = Depends(require_permission("file:read"))):
    return {"result": registry.calculator(body.expression)}


class SearchToolBody(BaseModel):
    query: str = Field(min_length=1, max_length=500)


@router.post("/orgs/{org_id}/tools/web_search")
async def web_search_tool(org_id: str, body: SearchToolBody,
                          ctx: dict = Depends(require_permission("file:read"))):
    res = await registry.run_tool("web_search", body.query)
    return res
