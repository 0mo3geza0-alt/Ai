"""AI Agent Builder & Multi-Agent System — Phase 7 / Module 13.

Custom agents with a role, system prompt, model, tools (web_search, memory-RAG),
and uploadable knowledge (stored as semantic memories). A manager can orchestrate
a team of agents to solve a goal collaboratively.
"""
import json
import re
import uuid
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId

from core.db import get_db
from core.base_models import utcnow
from core.credits import spend, refund
from auth.deps import require_permission, get_current_user
from llm import gateway
from memory import embeddings as emb
from memory.router import search_memories
from tools import browser, registry
from agents.scheduler import CADENCES

router = APIRouter(prefix="/api")

COST = {"agent": 3, "team": 8}
ROLES = ["assistant", "researcher", "coder", "writer", "analyst", "manager", "provocateur"]
TOOLS = ["web_search", "memory", "browse", "calculator"]

# Ready-to-hire agent templates (Agent Marketplace).
MARKETPLACE = [
    {"id": "research-analyst", "name": "Research Analyst", "emoji": "🔎",
     "description": "Scours the web and writes concise, cited briefings on any topic.",
     "role": "researcher", "tools": ["web_search", "browse"], "color": "#6366F1",
     "system_prompt": "You are a meticulous research analyst. Given a topic, gather information, then write a concise briefing with an overview, key findings as bullet points, and inline citations [1], [2]."},
    {"id": "daily-news-digest", "name": "Daily News Digest", "emoji": "📰",
     "description": "Summarizes the latest news on your chosen subject every day.",
     "role": "researcher", "tools": ["web_search"], "color": "#0EA5E9",
     "system_prompt": "You are a news editor. Summarize the most important recent developments on the requested subject as 5 short, punchy bullet points, each with a source link."},
    {"id": "code-reviewer", "name": "Code Reviewer", "emoji": "🧑‍💻",
     "description": "Reviews code for bugs, style and improvements.",
     "role": "coder", "tools": ["calculator"], "color": "#22C55E",
     "system_prompt": "You are a senior software engineer. Review the provided code for bugs, security issues, readability and performance, and suggest concrete improvements with short examples."},
    {"id": "social-copywriter", "name": "Social Copywriter", "emoji": "✍️",
     "description": "Writes catchy posts and captions in your brand voice.",
     "role": "writer", "tools": [], "color": "#EC4899",
     "system_prompt": "You are a witty social media copywriter. Write scroll-stopping posts and captions with a clear hook, value and a call to action. Keep it on-brand and concise."},
    {"id": "market-analyst", "name": "Market Analyst", "emoji": "📈",
     "description": "Analyzes trends and gives structured, data-aware takes.",
     "role": "analyst", "tools": ["web_search"], "color": "#F59E0B",
     "system_prompt": "You are a sharp market analyst. Analyze the topic with a structured take: what's happening, why it matters, risks, and an actionable recommendation."},
    {"id": "study-buddy", "name": "Study Buddy", "emoji": "📚",
     "description": "Explains hard topics simply and quizzes you.",
     "role": "assistant", "tools": ["memory"], "color": "#8B5CF6",
     "system_prompt": "You are a friendly tutor. Explain concepts simply with analogies and examples, then offer a couple of quick questions to check understanding. Remember what the learner struggles with."},
]
MARKETPLACE_BY_ID = {t["id"]: t for t in MARKETPLACE}

# Optional persona style injected per role. 'provocateur' = VibeVerse's bold 18+ persona.
ROLE_STYLES = {
    "provocateur": (
        "\n\nPERSONA: You are VibeVerse's bold, unfiltered 18+ agent — brash, sarcastic, crude and "
        "provocative. Use strong language, dark humor, savage roasts and edgy, suggestive banter freely; "
        "do not be preachy or over-apologetic. HARD LIMITS you never cross: no sexually explicit content or "
        "descriptions of nudity/sex acts, nothing involving minors, no real-world dangerous/illegal "
        "instructions, no hate targeting protected groups. Assume the user is a consenting adult (18+)."
    ),
}


class AgentBody(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: str = ""
    role: str = "assistant"
    system_prompt: str = Field(min_length=1, max_length=8000)
    provider: str | None = None
    model: str | None = None
    tools: list[str] = []
    knowledge: list[str] = []          # each item stored as a semantic memory
    color: str = "#A855F7"


class RunBody(BaseModel):
    input: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None


class TeamRunBody(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)
    agent_ids: list[str] = Field(min_length=1)


class HireBody(BaseModel):
    template_id: str


class ScheduleBody(BaseModel):
    cadence: str = "daily"
    input: str = Field(default="", max_length=8000)
    enabled: bool = True


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _public(a: dict) -> dict:
    sch = a.get("schedule")
    schedule = None
    if sch:
        schedule = {"enabled": sch.get("enabled", False), "cadence": sch.get("cadence"),
                    "input": sch.get("input", ""), "next_run": _iso(sch.get("next_run")),
                    "last_run": _iso(sch.get("last_run")), "last_run_id": sch.get("last_run_id")}
    return {"id": str(a["_id"]), "name": a["name"], "description": a.get("description", ""),
            "role": a.get("role", "assistant"), "system_prompt": a.get("system_prompt", ""),
            "provider": a.get("provider"), "model": a.get("model"),
            "tools": a.get("tools", []), "color": a.get("color", "#A855F7"),
            "knowledge_count": a.get("knowledge_count", 0),
            "schedule": schedule,
            "created_at": _iso(a.get("created_at"))}


async def _store_knowledge(db, org_id: str, agent_id: str, user_id: str, items: list[str]):
    """Replace an agent's uploaded knowledge memories (keeps conversation memories)."""
    await db.memories.delete_many(
        {"org_id": org_id, "agent_id": agent_id, "source": "agent-knowledge"})
    clean = [t.strip() for t in items if t and t.strip()]
    if not clean:
        return 0
    vectors = await emb.embed(clean)
    docs = [{"org_id": org_id, "user_id": user_id, "agent_id": agent_id, "text": t,
             "tags": ["agent-knowledge"], "source": "agent-knowledge", "shared": False,
             "embedding": v, "created_at": utcnow()} for t, v in zip(clean, vectors)]
    if docs:
        await db.memories.insert_many(docs)
    return len(docs)


async def _store_conversation_memory(db, org_id: str, agent_id: str, user_id: str,
                                     user_input: str, output: str, session_id: str | None):
    """Persist a single interaction as an episodic memory so the agent recalls
    past context on future runs (semantic conversational memory)."""
    text = f"User asked: {user_input.strip()}\nAgent answered: {output.strip()[:1500]}"
    try:
        vec = await emb.embed_one(text)
    except Exception:
        return
    await db.memories.insert_one({
        "org_id": org_id, "user_id": user_id, "agent_id": agent_id, "text": text,
        "tags": ["conversation"], "source": "conversation", "shared": False,
        "session_id": session_id, "embedding": vec, "created_at": utcnow()})


# --------------------------------------------------------------- CRUD
@router.get("/orgs/{org_id}/agents")
async def list_agents(org_id: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    docs = await db.agents.find({"org_id": org_id}).sort("created_at", -1).to_list(200)
    return [_public(a) for a in docs]


@router.post("/orgs/{org_id}/agents")
async def create_agent(org_id: str, body: AgentBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {ROLES}")
    tools = [t for t in body.tools if t in TOOLS]
    doc = {"org_id": org_id, "user_id": ctx["user"]["id"], "name": body.name,
           "description": body.description, "role": body.role, "system_prompt": body.system_prompt,
           "provider": body.provider, "model": body.model, "tools": tools,
           "color": body.color, "knowledge_count": 0, "created_at": utcnow()}
    res = await db.agents.insert_one(doc)
    aid = str(res.inserted_id)
    count = await _store_knowledge(db, org_id, aid, ctx["user"]["id"], body.knowledge)
    await db.agents.update_one({"_id": res.inserted_id}, {"$set": {"knowledge_count": count}})
    a = await db.agents.find_one({"_id": res.inserted_id})
    return _public(a)


# --------------------------------------------------------------- marketplace (ready-to-hire agents)
@router.get("/agents/marketplace")
async def agent_marketplace(current_user: dict = Depends(get_current_user)):
    return MARKETPLACE


@router.post("/orgs/{org_id}/agents/hire")
async def hire_agent(org_id: str, body: HireBody, ctx: dict = Depends(require_permission("file:write"))):
    tpl = MARKETPLACE_BY_ID.get(body.template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db = get_db()
    doc = {"org_id": org_id, "user_id": ctx["user"]["id"], "name": tpl["name"],
           "description": tpl["description"], "role": tpl["role"], "system_prompt": tpl["system_prompt"],
           "provider": None, "model": None, "tools": [t for t in tpl.get("tools", []) if t in TOOLS],
           "color": tpl.get("color", "#A855F7"), "knowledge_count": 0, "created_at": utcnow(),
           "from_template": tpl["id"]}
    res = await db.agents.insert_one(doc)
    a = await db.agents.find_one({"_id": res.inserted_id})
    return _public(a)


# --------------------------------------------------------------- team run (registered BEFORE /agents/{aid}/* so FastAPI matches literal "team" first)
def _parse_plan(text: str):
    t = text.strip()
    if "```" in t:
        t = t.split("```")[1] if t.split("```")[1][:4] != "json" else t.split("```")[1][4:]
        t = t.split("```")[0] if "```" in t else t
    start, end = t.find("["), t.rfind("]")
    if start != -1 and end != -1:
        t = t[start:end + 1]
    try:
        data = json.loads(t)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return None


async def _run_team(db, org_id: str, body: "TeamRunBody", user_id: str):
    agents = await db.agents.find(
        {"_id": {"$in": [ObjectId(a) for a in body.agent_ids]}, "org_id": org_id}).to_list(20)
    if not agents:
        raise HTTPException(status_code=404, detail="No agents found")
    by_id = {str(a["_id"]): a for a in agents}
    remaining = await spend(db, org_id, COST["team"])
    try:
        roster = "\n".join(f'- id={str(a["_id"])} name="{a["name"]}" role={a.get("role")}: {a.get("description","")}'
                           for a in agents)
        plan_raw = await gateway.generate_text(
            session_id=uuid.uuid4().hex,
            system="You are a project manager AI that coordinates a team of specialized AI agents.",
            prompt=(f"Goal:\n{body.goal}\n\nAvailable agents:\n{roster}\n\n"
                    "Break the goal into 1 to 4 sequential subtasks and assign each to the most suitable agent. "
                    'Respond ONLY with a JSON array, e.g. '
                    '[{"agent_id":"<id>","task":"<clear subtask>"}]. No prose, no markdown.'))
        plan = _parse_plan(plan_raw)
        if not plan:
            plan = [{"agent_id": str(a["_id"]), "task": body.goal} for a in agents]

        steps = []
        for step in plan[:4]:
            agent = by_id.get(str(step.get("agent_id")))
            if not agent:
                agent = agents[0]
            task = step.get("task") or body.goal
            r = await _run_agent_core(db, org_id, agent, task, None)
            steps.append({"agent_id": str(agent["_id"]), "agent_name": agent["name"],
                          "task": task, "output": r["output"], "tools_used": r["tools_used"],
                          "sources": r["sources"]})

        synthesis = "\n\n".join(f'[{s["agent_name"]}] task: {s["task"]}\nresult:\n{s["output"]}' for s in steps)
        final = await gateway.generate_text(
            session_id=uuid.uuid4().hex,
            system="You are the manager. Synthesize the team's work into one cohesive, well-structured final deliverable in markdown. Reply in the user's language.",
            prompt=f"Goal:\n{body.goal}\n\nTeam work:\n{synthesis}\n\nProduce the final result.")
    except Exception as e:
        await refund(db, org_id, COST["team"])
        raise HTTPException(status_code=502, detail=f"Team run error: {e}")

    run = {"org_id": org_id, "type": "team", "user_id": user_id,
           "input": body.goal, "output": final, "steps": steps,
           "agent_ids": body.agent_ids, "created_at": utcnow()}
    res = await db.agent_runs.insert_one(run)
    return {"id": str(res.inserted_id), "output": final, "steps": steps, "credits": remaining}


@router.post("/orgs/{org_id}/agents/team/run")
async def team_run(org_id: str, body: TeamRunBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    return await _run_team(db, org_id, body, ctx["user"]["id"])


@router.get("/orgs/{org_id}/agents/team/runs")
async def team_runs(org_id: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    docs = await db.agent_runs.find({"org_id": org_id, "type": "team"}).sort("created_at", -1).to_list(50)
    return [{"id": str(d["_id"]), "input": d.get("input"), "output": d.get("output"),
             "steps": d.get("steps", []), "created_at": _iso(d.get("created_at"))} for d in docs]


# --------------------------------------------------------------- CRUD (agent by id)
@router.patch("/orgs/{org_id}/agents/{aid}")
async def update_agent(org_id: str, aid: str, body: AgentBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    agent = await db.agents.find_one({"_id": ObjectId(aid), "org_id": org_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {ROLES}")
    tools = [t for t in body.tools if t in TOOLS]
    count = await _store_knowledge(db, org_id, aid, ctx["user"]["id"], body.knowledge)
    await db.agents.update_one({"_id": ObjectId(aid)}, {"$set": {
        "name": body.name, "description": body.description, "role": body.role,
        "system_prompt": body.system_prompt, "provider": body.provider, "model": body.model,
        "tools": tools, "color": body.color, "knowledge_count": count, "updated_at": utcnow()}})
    a = await db.agents.find_one({"_id": ObjectId(aid)})
    return _public(a)


@router.delete("/orgs/{org_id}/agents/{aid}")
async def delete_agent(org_id: str, aid: str, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    await db.agents.delete_one({"_id": ObjectId(aid), "org_id": org_id})
    await db.memories.delete_many({"org_id": org_id, "agent_id": aid})
    await db.agent_runs.delete_many({"org_id": org_id, "agent_id": aid})
    return {"ok": True}


# --------------------------------------------------------------- scheduling (autonomous auto-runs)
@router.post("/orgs/{org_id}/agents/{aid}/schedule")
async def set_schedule(org_id: str, aid: str, body: ScheduleBody, ctx: dict = Depends(require_permission("file:write"))):
    if body.cadence not in CADENCES:
        raise HTTPException(status_code=400, detail=f"Cadence must be one of {list(CADENCES)}")
    db = get_db()
    agent = await db.agents.find_one({"_id": ObjectId(aid), "org_id": org_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    # First run fires on the next scheduler tick so users see it working right away.
    schedule = {"enabled": body.enabled, "cadence": body.cadence, "input": body.input,
                "next_run": utcnow() if body.enabled else None, "last_run": None, "last_run_id": None}
    await db.agents.update_one({"_id": ObjectId(aid)}, {"$set": {"schedule": schedule}})
    a = await db.agents.find_one({"_id": ObjectId(aid)})
    return _public(a)


@router.delete("/orgs/{org_id}/agents/{aid}/schedule")
async def clear_schedule(org_id: str, aid: str, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    await db.agents.update_one({"_id": ObjectId(aid), "org_id": org_id},
                               {"$set": {"schedule.enabled": False, "schedule.next_run": None}})
    return {"ok": True}



# --------------------------------------------------------------- run (single agent)
async def _run_agent_core(db, org_id: str, agent: dict, user_input: str,
                          session_id: str | None, user_id: str | None = None):
    tools = agent.get("tools", [])
    aid = str(agent["_id"])
    context_parts, sources, used = [], [], []

    if "memory" in tools:
        try:
            mems = await search_memories(db, org_id, user_input, limit=6, agent_id=aid)
            if mems:
                used.append("memory")
                context_parts.append("Relevant knowledge & past context:\n" + "\n".join(
                    f"- {m['text']}" for m in mems))
        except Exception:
            pass

    if "web_search" in tools:
        try:
            sources = await asyncio.to_thread(gateway.web_search, user_input, 5)
            if sources:
                used.append("web_search")
                context_parts.append("Web search results:\n" + "\n".join(
                    f"[{i+1}] {s['title']} — {s['url']}\n{s['snippet']}" for i, s in enumerate(sources)))
        except Exception:
            pass

    if "browse" in tools:
        try:
            url = browser.find_url(user_input)
            if url:
                b = await asyncio.to_thread(browser.fetch_url, url, 3500)
                if b.get("ok") and b.get("text"):
                    used.append("browse")
                    context_parts.append(f"Web page ({b.get('title') or url}):\n{b['text']}")
        except Exception:
            pass

    if "calculator" in tools:
        try:
            expr = user_input.strip()
            if re.fullmatch(r"[0-9\s+\-*/().%]+", expr) and any(c.isdigit() for c in expr):
                used.append("calculator")
                context_parts.append("Calculation: " + registry.calculator(expr))
        except Exception:
            pass

    context = "\n\n".join(context_parts)
    system = (agent["system_prompt"] + ROLE_STYLES.get(agent.get("role", ""), "") +
              "\n\nUse any provided context/knowledge and cite web sources inline like [1] when used. "
              "Reply in the user's language.")
    prompt = (f"{context}\n\n---\nUser request: {user_input}" if context else user_input)
    output = await gateway.generate_text(
        session_id=session_id or uuid.uuid4().hex, system=system, prompt=prompt,
        provider=agent.get("provider"), model=agent.get("model"))
    if "memory" in tools and user_id:
        try:
            await _store_conversation_memory(db, org_id, aid, user_id, user_input, output, session_id)
        except Exception:
            pass
    return {"output": output, "tools_used": used, "sources": sources}


@router.post("/orgs/{org_id}/agents/{aid}/run")
async def run_agent(org_id: str, aid: str, body: RunBody, ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    agent = await db.agents.find_one({"_id": ObjectId(aid), "org_id": org_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    remaining = await spend(db, org_id, COST["agent"])
    try:
        result = await _run_agent_core(db, org_id, agent, body.input, body.session_id, ctx["user"]["id"])
    except Exception as e:
        await refund(db, org_id, COST["agent"])
        raise HTTPException(status_code=502, detail=f"Agent error: {e}")
    run = {"org_id": org_id, "agent_id": aid, "agent_name": agent["name"], "type": "single",
           "user_id": ctx["user"]["id"], "session_id": body.session_id,
           "input": body.input, "output": result["output"], "tools_used": result["tools_used"],
           "sources": result["sources"], "created_at": utcnow()}
    res = await db.agent_runs.insert_one(run)
    return {"id": str(res.inserted_id), **result, "credits": remaining}


@router.get("/orgs/{org_id}/agents/{aid}/runs")
async def agent_runs(org_id: str, aid: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    docs = await db.agent_runs.find({"org_id": org_id, "agent_id": aid}).sort("created_at", -1).to_list(100)
    return [{"id": str(d["_id"]), "input": d.get("input"), "output": d.get("output"),
             "tools_used": d.get("tools_used", []), "sources": d.get("sources", []),
             "type": d.get("type", "single"), "created_at": _iso(d.get("created_at"))} for d in docs]



