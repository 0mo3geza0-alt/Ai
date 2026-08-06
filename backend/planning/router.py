"""Planning Engine — Phase 6 / Module.

Decompose a complex goal into ordered steps, execute each step (research / browse /
reason) building on previous results, then synthesize a final deliverable.
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import get_db
from core.base_models import utcnow
from core.credits import spend, refund
from auth.deps import require_permission
from llm import gateway
from tools import registry

router = APIRouter(prefix="/api")

COST_PLAN = 6
ACTIONS = {"research", "browse", "reason"}


class PlanBody(BaseModel):
    goal: str = Field(min_length=3, max_length=4000)
    provider: str | None = None
    model: str | None = None
    max_steps: int = Field(default=5, ge=1, le=8)


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _extract_json_array(text: str):
    t = (text or "").strip()
    if "```" in t:
        parts = t.split("```")
        for p in parts:
            p2 = p[4:] if p[:4].lower() == "json" else p
            if "[" in p2 and "]" in p2:
                t = p2
                break
    start, end = t.find("["), t.rfind("]")
    if start != -1 and end != -1 and end > start:
        t = t[start:end + 1]
    try:
        data = json.loads(t)
        return data if isinstance(data, list) else None
    except Exception:
        return None


async def _make_plan(goal: str, max_steps: int, provider, model):
    system = ("You are a meticulous planning engine. Decompose the user's GOAL into a short "
              "ordered list of concrete steps. For each step choose an action: "
              "'research' (needs a web search), 'browse' (needs to open a specific URL — put the URL in query), "
              "or 'reason' (pure reasoning/writing using prior results). "
              f"Use at most {max_steps} steps. Respond with STRICT JSON ONLY — an array of objects like "
              '[{"title":"...","action":"research|browse|reason","query":"search terms / URL / instruction"}]. '
              "No prose, no markdown.")
    raw = await gateway.generate_text(session_id=f"plan-{uuid.uuid4().hex}", system=system,
                                      prompt=f"GOAL:\n{goal}", provider=provider, model=model)
    plan = _extract_json_array(raw)
    cleaned = []
    for s in (plan or [])[:max_steps]:
        if not isinstance(s, dict):
            continue
        action = str(s.get("action", "reason")).lower()
        if action not in ACTIONS:
            action = "reason"
        cleaned.append({"title": str(s.get("title") or s.get("query") or "Step")[:200],
                        "action": action,
                        "query": str(s.get("query") or s.get("title") or goal)[:1000]})
    if not cleaned:
        cleaned = [{"title": "Solve the goal", "action": "reason", "query": goal}]
    return cleaned


async def _execute_step(goal: str, step: dict, prior: str, provider, model):
    action, query = step["action"], step["query"]
    tool_output, tool_used = "", None
    if action == "research":
        res = await registry.run_tool("web_search", query)
        results = res.get("results", [])
        tool_used = "web_search"
        tool_output = "\n".join(f"[{i+1}] {r['title']} — {r['url']}\n{r['snippet']}"
                                for i, r in enumerate(results)) or "(no results)"
    elif action == "browse":
        res = await registry.run_tool("browse", query)
        tool_used = "browse"
        if res.get("ok"):
            tool_output = f"URL: {res.get('url')}\nTitle: {res.get('title')}\n\n{res.get('text', '')}"
        else:
            tool_output = f"(failed to browse: {res.get('error')})"
    system = ("You are an expert executor working step-by-step toward a larger goal. "
              "Use the provided tool output and prior results. Be concise and factual. "
              "Reply in the user's language.")
    prompt = (f"GOAL:\n{goal}\n\nPRIOR RESULTS:\n{prior or '(none yet)'}\n\n"
              f"CURRENT STEP: {step['title']}\nInstruction: {query}\n"
              + (f"\nTOOL OUTPUT ({tool_used}):\n{tool_output}\n" if tool_used else "")
              + "\nProduce the result of THIS step only.")
    output = await gateway.generate_text(session_id=f"step-{uuid.uuid4().hex}", system=system,
                                         prompt=prompt, provider=provider, model=model)
    return {"title": step["title"], "action": action, "query": query,
            "tool_used": tool_used, "output": output}


@router.post("/orgs/{org_id}/plan/run")
async def run_plan(org_id: str, body: PlanBody,
                   ctx: dict = Depends(require_permission("file:write"))):
    db = get_db()
    remaining = await spend(db, org_id, COST_PLAN)
    try:
        plan = await _make_plan(body.goal, body.max_steps, body.provider, body.model)
        steps, prior = [], ""
        for step in plan:
            r = await _execute_step(body.goal, step, prior, body.provider, body.model)
            steps.append(r)
            prior += f"\n\n[{r['title']}]\n{r['output']}"
        synthesis = "\n\n".join(f"[{s['title']}]\n{s['output']}" for s in steps)
        final = await gateway.generate_text(
            session_id=f"synth-{uuid.uuid4().hex}",
            system=("You are the planner. Synthesize the step results into one cohesive, "
                    "well-structured final deliverable in markdown. Reply in the user's language."),
            prompt=f"GOAL:\n{body.goal}\n\nSTEP RESULTS:\n{synthesis}\n\nProduce the final answer.",
            provider=body.provider, model=body.model)
    except HTTPException:
        await refund(db, org_id, COST_PLAN)
        raise
    except Exception as e:
        await refund(db, org_id, COST_PLAN)
        raise HTTPException(status_code=502, detail=f"Planning error: {e}")

    doc = {"org_id": org_id, "user_id": ctx["user"]["id"], "goal": body.goal,
           "plan": plan, "steps": steps, "output": final, "created_at": utcnow()}
    res = await db.plan_runs.insert_one(doc)
    return {"id": str(res.inserted_id), "goal": body.goal, "plan": plan,
            "steps": steps, "output": final, "credits": remaining}


@router.get("/orgs/{org_id}/plan/runs")
async def list_plan_runs(org_id: str, ctx: dict = Depends(require_permission("file:read"))):
    db = get_db()
    docs = await db.plan_runs.find({"org_id": org_id}).sort("created_at", -1).to_list(50)
    return [{"id": str(d["_id"]), "goal": d.get("goal"), "plan": d.get("plan", []),
             "steps": d.get("steps", []), "output": d.get("output"),
             "created_at": _iso(d.get("created_at"))} for d in docs]
