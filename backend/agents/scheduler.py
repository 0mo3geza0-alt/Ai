"""Background scheduler for autonomous agent auto-runs.

A lightweight asyncio loop (no external dependency) that periodically fires any
agent whose schedule is due. Started from server startup, mirrors the existing
monthly_reset_loop pattern.
"""
import asyncio
from datetime import timedelta

from core.db import get_db
from core.base_models import utcnow
from core.logging import logger
from core.credits import spend, refund

# Human-friendly cadence -> interval in seconds.
CADENCES = {
    "5min": 300,
    "15min": 900,
    "hourly": 3600,
    "daily": 86400,
    "weekly": 604800,
}
AGENT_COST = 3
_TICK_SECONDS = 30


def interval_for(cadence: str) -> int:
    return CADENCES.get(cadence, CADENCES["daily"])


async def _run_due_agent(db, agent: dict):
    from agents.router import _run_agent_core  # lazy import to avoid circulars

    sch = agent.get("schedule") or {}
    org_id = agent["org_id"]
    aid = str(agent["_id"])
    now = utcnow()
    interval = interval_for(sch.get("cadence"))
    # Advance next_run FIRST so a slow run can't be double-fired on the next tick.
    await db.agents.update_one({"_id": agent["_id"]},
                               {"$set": {"schedule.next_run": now + timedelta(seconds=interval)}})
    try:
        await spend(db, org_id, AGENT_COST)
    except Exception:
        logger.info("Scheduled agent %s skipped — insufficient credits", aid)
        return
    task_input = (sch.get("input") or "").strip() or "Run your scheduled task and report the result."
    try:
        result = await _run_agent_core(db, org_id, agent, task_input, None, agent.get("user_id"))
    except Exception as e:
        await refund(db, org_id, AGENT_COST)
        logger.error("Scheduled agent %s run failed: %s", aid, e)
        return
    run = {"org_id": org_id, "agent_id": aid, "agent_name": agent.get("name"), "type": "scheduled",
           "user_id": agent.get("user_id"), "session_id": None, "input": task_input,
           "output": result["output"], "tools_used": result["tools_used"],
           "sources": result["sources"], "created_at": now}
    res = await db.agent_runs.insert_one(run)
    await db.agents.update_one({"_id": agent["_id"]},
                               {"$set": {"schedule.last_run": now, "schedule.last_run_id": str(res.inserted_id)}})
    logger.info("Scheduled agent %s auto-ran (run %s)", aid, str(res.inserted_id))


async def _tick():
    db = get_db()
    now = utcnow()
    due = await db.agents.find({"schedule.enabled": True,
                                "schedule.next_run": {"$lte": now}}).to_list(200)
    for agent in due:
        try:
            await _run_due_agent(db, agent)
        except Exception as e:
            logger.error("Scheduler error on agent %s: %s", agent.get("_id"), e)


async def scheduler_loop():
    logger.info("Agent scheduler loop started (tick=%ss)", _TICK_SECONDS)
    while True:
        await asyncio.sleep(_TICK_SECONDS)
        try:
            await _tick()
        except Exception as e:
            logger.error("Agent scheduler loop error: %s", e)
