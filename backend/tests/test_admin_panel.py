"""Admin panel API tests - covers admin access, user suspension/role/delete, org credits, grant-all, non-admin guard."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://github-extractor-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PW = "admin12345"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    return r


@pytest.fixture(scope="module")
def admin_token():
    r = _login(ADMIN_EMAIL, ADMIN_PW)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def throwaway_user():
    """Create a fresh non-admin user."""
    ts = int(time.time())
    email = f"TEST_admin_throwaway_{ts}@example.com"
    pw = "testpass123"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "TEST throwaway"}, timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return {"email": email, "password": pw, "token": data["token"], "id": data["user"]["id"]}


# ---------- ADMIN ACCESS ----------
class TestAdminAccess:
    def test_stats(self, admin_headers):
        r = requests.get(f"{API}/admin/stats", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ["users", "organizations", "projects", "api_keys", "chat_messages", "creations"]:
            assert k in d
        assert isinstance(d["creations"], dict)
        assert "video" in d["creations"] and "music" in d["creations"]

    def test_users_list_has_suspended_field(self, admin_headers):
        r = requests.get(f"{API}/admin/users", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list) and len(arr) > 0
        assert "suspended" in arr[0]
        assert "email" in arr[0] and "global_role" in arr[0]

    def test_orgs_list(self, admin_headers):
        r = requests.get(f"{API}/admin/organizations", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list) and len(arr) > 0
        assert "credits" in arr[0] and "plan" in arr[0]


# ---------- NON-ADMIN GUARD ----------
class TestNonAdminGuard:
    def test_non_admin_stats_403(self, throwaway_user):
        h = {"Authorization": f"Bearer {throwaway_user['token']}"}
        r = requests.get(f"{API}/admin/stats", headers=h, timeout=30)
        assert r.status_code == 403

    def test_non_admin_users_403(self, throwaway_user):
        h = {"Authorization": f"Bearer {throwaway_user['token']}"}
        r = requests.get(f"{API}/admin/users", headers=h, timeout=30)
        assert r.status_code == 403

    def test_non_admin_orgs_403(self, throwaway_user):
        h = {"Authorization": f"Bearer {throwaway_user['token']}"}
        r = requests.get(f"{API}/admin/organizations", headers=h, timeout=30)
        assert r.status_code == 403


# ---------- USER SUSPENSION (critical) ----------
class TestUserSuspension:
    def test_suspend_and_login_blocked_then_reactivate(self, admin_headers):
        # Create a fresh user just for this
        ts = int(time.time())
        email = f"TEST_suspend_{ts}@example.com"
        pw = "testpass123"
        reg = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "TEST suspend"}, timeout=30)
        assert reg.status_code in (200, 201)
        user_id = reg.json()["user"]["id"]
        old_token = reg.json()["token"]

        # Login should work first
        r0 = _login(email, pw)
        assert r0.status_code == 200

        # Suspend
        r = requests.patch(f"{API}/admin/users/{user_id}/suspend", json={"suspended": True}, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["suspended"] is True

        # Login now blocked (403)
        r2 = _login(email, pw)
        assert r2.status_code == 403, f"suspended login expected 403, got {r2.status_code}"

        # Existing token also rejected on /auth/me
        me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {old_token}"}, timeout=30)
        assert me.status_code == 403, f"suspended token expected 403 on /auth/me, got {me.status_code}"

        # Reactivate
        r3 = requests.patch(f"{API}/admin/users/{user_id}/suspend", json={"suspended": False}, headers=admin_headers, timeout=30)
        assert r3.status_code == 200
        assert r3.json()["suspended"] is False

        # Login works again
        r4 = _login(email, pw)
        assert r4.status_code == 200

        # Cleanup
        requests.delete(f"{API}/admin/users/{user_id}", headers=admin_headers, timeout=30)

    def test_admin_cannot_suspend_self(self, admin_headers, admin_token):
        me = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=30).json()
        r = requests.patch(f"{API}/admin/users/{me['id']}/suspend", json={"suspended": True}, headers=admin_headers, timeout=30)
        assert r.status_code == 400


# ---------- ROLE CHANGE ----------
class TestRoleChange:
    def test_role_change_and_admin_cannot_demote_self(self, admin_headers):
        # Create throwaway
        ts = int(time.time())
        email = f"TEST_role_{ts}@example.com"
        reg = requests.post(f"{API}/auth/register", json={"email": email, "password": "testpass123", "name": "R"}, timeout=30)
        uid = reg.json()["user"]["id"]

        r = requests.patch(f"{API}/admin/users/{uid}/role", json={"global_role": "admin"}, headers=admin_headers, timeout=30)
        assert r.status_code == 200 and r.json()["global_role"] == "admin"

        r2 = requests.patch(f"{API}/admin/users/{uid}/role", json={"global_role": "user"}, headers=admin_headers, timeout=30)
        assert r2.status_code == 200 and r2.json()["global_role"] == "user"

        # Verify via list
        arr = requests.get(f"{API}/admin/users", headers=admin_headers, timeout=30).json()
        found = [u for u in arr if u["id"] == uid]
        assert found and found[0]["global_role"] == "user"

        # Admin cannot demote self
        me = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=30).json()
        r3 = requests.patch(f"{API}/admin/users/{me['id']}/role", json={"global_role": "user"}, headers=admin_headers, timeout=30)
        assert r3.status_code == 400

        # Cleanup
        requests.delete(f"{API}/admin/users/{uid}", headers=admin_headers, timeout=30)


# ---------- USER DELETE ----------
class TestUserDelete:
    def test_delete_removes_user(self, admin_headers):
        ts = int(time.time())
        email = f"TEST_del_{ts}@example.com"
        reg = requests.post(f"{API}/auth/register", json={"email": email, "password": "testpass123", "name": "D"}, timeout=30)
        uid = reg.json()["user"]["id"]

        r = requests.delete(f"{API}/admin/users/{uid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200 and r.json().get("ok") is True

        # Verify user gone
        arr = requests.get(f"{API}/admin/users", headers=admin_headers, timeout=30).json()
        assert not any(u["id"] == uid for u in arr)

        # Login should now fail (401/403/404 acceptable)
        r2 = _login(email, "testpass123")
        assert r2.status_code in (401, 403, 404)

    def test_admin_cannot_delete_self(self, admin_headers):
        me = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=30).json()
        r = requests.delete(f"{API}/admin/users/{me['id']}", headers=admin_headers, timeout=30)
        assert r.status_code == 400


# ---------- ORG CREDITS ----------
class TestOrgCredits:
    def test_org_set_add_deduct_plan(self, admin_headers):
        # Pick a throwaway org: register a fresh user, then edit their auto-created org
        ts = int(time.time())
        email = f"TEST_org_{ts}@example.com"
        reg = requests.post(f"{API}/auth/register", json={"email": email, "password": "testpass123", "name": "O"}, timeout=30)
        uid = reg.json()["user"]["id"]
        utoken = reg.json()["token"]

        # Find the user's own org via /api/orgs
        my_orgs = requests.get(f"{API}/orgs", headers={"Authorization": f"Bearer {utoken}"}, timeout=30).json()
        assert my_orgs and len(my_orgs) > 0, f"no orgs for user: {my_orgs}"
        oid = my_orgs[0]["id"]

        # SET credits
        r = requests.patch(f"{API}/admin/organizations/{oid}", json={"credits": 1000}, headers=admin_headers, timeout=30)
        assert r.status_code == 200 and r.json()["credits"] == 1000

        # ADD
        r = requests.patch(f"{API}/admin/organizations/{oid}", json={"add_credits": 250}, headers=admin_headers, timeout=30)
        assert r.status_code == 200 and r.json()["credits"] == 1250

        # DEDUCT (negative), floor 0
        r = requests.patch(f"{API}/admin/organizations/{oid}", json={"add_credits": -100000}, headers=admin_headers, timeout=30)
        assert r.status_code == 200 and r.json()["credits"] == 0

        # PLAN change
        for plan in ["pro", "business", "free"]:
            r = requests.patch(f"{API}/admin/organizations/{oid}", json={"plan": plan}, headers=admin_headers, timeout=30)
            assert r.status_code == 200 and r.json()["plan"] == plan

        # Cleanup user (org may cascade or not; leave it for now)
        requests.delete(f"{API}/admin/users/{uid}", headers=admin_headers, timeout=30)


# ---------- GRANT-ALL ----------
class TestGrantAll:
    def test_grant_all_positive_then_deduct(self, admin_headers):
        # Baseline
        orgs_before = requests.get(f"{API}/admin/organizations", headers=admin_headers, timeout=30).json()
        total_before = sum(o["credits"] for o in orgs_before)
        count = len(orgs_before)

        r = requests.post(f"{API}/admin/credits/grant-all", json={"add_credits": 5}, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["updated"] == count and d["add_credits"] == 5

        orgs_after = requests.get(f"{API}/admin/organizations", headers=admin_headers, timeout=30).json()
        total_after = sum(o["credits"] for o in orgs_after)
        assert total_after == total_before + 5 * count

        # Now deduct 5 back
        r2 = requests.post(f"{API}/admin/credits/grant-all", json={"add_credits": -5}, headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        orgs_final = requests.get(f"{API}/admin/organizations", headers=admin_headers, timeout=30).json()
        # Each org will be floored at 0 so exact equality only if none hit 0. Verify no negative.
        assert all(o["credits"] >= 0 for o in orgs_final)
