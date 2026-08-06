"""Admin panel v2 tests - delete cleanup cascade, activity log, monthly reset."""
import os
import time
import pytest
import requests
from datetime import datetime

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://git-project-tool.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PW = "admin12345"


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _register_throwaway(prefix="del"):
    ts = int(time.time() * 1000)
    email = f"TEST_{prefix}_{ts}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "testpass123", "name": f"TEST {prefix}"}, timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.text}"
    d = r.json()
    return {"email": email, "id": d["user"]["id"], "token": d["token"]}


# ---------- DELETE CLEANUP CASCADE ----------
class TestDeleteCleanupCascade:
    def test_delete_user_removes_owned_org_and_memberships(self, admin_headers):
        u = _register_throwaway("cascade")
        # user's own orgs
        my_orgs = requests.get(f"{API}/orgs", headers={"Authorization": f"Bearer {u['token']}"}, timeout=30).json()
        assert len(my_orgs) >= 1
        owned_org_ids = [o["id"] for o in my_orgs]

        # DELETE user
        r = requests.delete(f"{API}/admin/users/{u['id']}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("orgs_removed", 0) >= 1, f"expected orgs_removed>=1, got {body}"

        # Verify user gone
        users = requests.get(f"{API}/admin/users", headers=admin_headers, timeout=30).json()
        assert not any(x["id"] == u["id"] for x in users)

        # Verify owned org(s) gone from admin org list
        orgs = requests.get(f"{API}/admin/organizations", headers=admin_headers, timeout=30).json()
        remaining_ids = {o["id"] for o in orgs}
        for oid in owned_org_ids:
            assert oid not in remaining_ids, f"owned org {oid} was not cleaned up"

    def test_admin_cannot_delete_self(self, admin_headers):
        me = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=30).json()
        r = requests.delete(f"{API}/admin/users/{me['id']}", headers=admin_headers, timeout=30)
        assert r.status_code == 400


# ---------- ADMIN ACTIVITY LOG ----------
class TestAdminActivityLog:
    def test_non_admin_403(self):
        u = _register_throwaway("actguard")
        h = {"Authorization": f"Bearer {u['token']}"}
        r = requests.get(f"{API}/admin/activity", headers=h, timeout=30)
        assert r.status_code == 403
        # cleanup
        # (skip - we'll leave it for other tests; delete via admin below is out of scope)

    def test_activity_records_all_action_types(self, admin_headers):
        # Create a user for actions
        u = _register_throwaway("act")
        uid = u["id"]

        # 1. suspend
        r1 = requests.patch(f"{API}/admin/users/{uid}/suspend", json={"suspended": True}, headers=admin_headers, timeout=30)
        assert r1.status_code == 200
        # reactivate to not leave suspended
        requests.patch(f"{API}/admin/users/{uid}/suspend", json={"suspended": False}, headers=admin_headers, timeout=30)

        # 2. role change
        r2 = requests.patch(f"{API}/admin/users/{uid}/role", json={"global_role": "admin"}, headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        requests.patch(f"{API}/admin/users/{uid}/role", json={"global_role": "user"}, headers=admin_headers, timeout=30)

        # 3. org credit update - find user's org
        my_orgs = requests.get(f"{API}/orgs", headers={"Authorization": f"Bearer {u['token']}"}, timeout=30).json()
        oid = my_orgs[0]["id"]
        r3 = requests.patch(f"{API}/admin/organizations/{oid}", json={"add_credits": 10}, headers=admin_headers, timeout=30)
        assert r3.status_code == 200

        # 4. grant-all
        r4 = requests.post(f"{API}/admin/credits/grant-all", json={"add_credits": 1}, headers=admin_headers, timeout=30)
        assert r4.status_code == 200
        requests.post(f"{API}/admin/credits/grant-all", json={"add_credits": -1}, headers=admin_headers, timeout=30)

        # 5. delete
        r5 = requests.delete(f"{API}/admin/users/{uid}", headers=admin_headers, timeout=30)
        assert r5.status_code == 200

        # Fetch activity
        r = requests.get(f"{API}/admin/activity", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        entries = r.json()
        assert isinstance(entries, list) and len(entries) > 0

        # required fields on first entry
        first = entries[0]
        for key in ["actor_email", "action", "target_label", "detail", "created_at"]:
            assert key in first, f"missing field {key} in activity entry: {first}"

        # newest first: created_at should be non-increasing
        # (be tolerant of same ms; just check first is >= second if 2+)
        if len(entries) >= 2:
            assert entries[0]["created_at"] >= entries[1]["created_at"]

        # verify each action type appears
        actions_found = {e["action"] for e in entries[:50]}
        for action in ["suspend", "role_change", "org_update", "grant_all", "delete"]:
            assert action in actions_found, f"action {action} not found in recent activity. found: {actions_found}"

        # actor_email should be admin
        assert first["actor_email"] == ADMIN_EMAIL


# ---------- MONTHLY RESET ----------
class TestMonthlyReset:
    def test_non_admin_403(self):
        u = _register_throwaway("mrguard")
        h = {"Authorization": f"Bearer {u['token']}"}
        r = requests.post(f"{API}/admin/credits/monthly-reset", headers=h, timeout=30)
        assert r.status_code == 403

    def test_reset_refills_to_plan_allowance(self, admin_headers):
        PLAN_CREDITS = {"free": 200, "pro": 10000, "business": 50000}
        # Register throwaway user, get their org
        u = _register_throwaway("mreset")
        my_orgs = requests.get(f"{API}/orgs", headers={"Authorization": f"Bearer {u['token']}"}, timeout=30).json()
        oid = my_orgs[0]["id"]

        # Set org to a weird credit value + free plan
        requests.patch(f"{API}/admin/organizations/{oid}", json={"plan": "free"}, headers=admin_headers, timeout=30)
        r = requests.patch(f"{API}/admin/organizations/{oid}", json={"credits": 7}, headers=admin_headers, timeout=30)
        assert r.status_code == 200 and r.json()["credits"] == 7

        # Call monthly reset
        rr = requests.post(f"{API}/admin/credits/monthly-reset", headers=admin_headers, timeout=60)
        assert rr.status_code == 200
        body = rr.json()
        assert "updated" in body
        assert body["updated"] >= 1

        # Verify our org's credits are refilled to plan allowance
        orgs = requests.get(f"{API}/admin/organizations", headers=admin_headers, timeout=30).json()
        target = next((o for o in orgs if o["id"] == oid), None)
        assert target is not None
        assert target["credits"] == PLAN_CREDITS[target["plan"]], f"expected {PLAN_CREDITS[target['plan']]}, got {target['credits']} for plan {target['plan']}"

        # last_reset_month should be current YYYY-MM (fetch raw from Mongo not exposed; check via admin org list if present)
        current_ym = datetime.utcnow().strftime("%Y-%m")
        if "last_reset_month" in target:
            assert target["last_reset_month"] == current_ym

        # cleanup
        requests.delete(f"{API}/admin/users/{u['id']}", headers=admin_headers, timeout=30)
