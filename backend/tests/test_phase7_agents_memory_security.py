"""Phase 7 backend tests: Agents / Memory / Security (audit-logs)."""
import os, time, uuid, pytest, requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "admin@aiplatform.com", "password": "admin12345"}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()


def _register(email, password):
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": password, "name": "T"}, timeout=30)
    r.raise_for_status()
    return r.json()


@pytest.fixture(scope="module")
def admin_ctx():
    d = _login(**ADMIN)
    return {"token": d["token"], "user": d["user"], "org_id": d["user"]["default_org_id"]}


@pytest.fixture(scope="module")
def user_ctx():
    email = f"phase7_{uuid.uuid4().hex[:8]}@t.com"
    d = _register(email, "test1234")
    return {"token": d["token"], "user": d["user"], "org_id": d["user"]["default_org_id"], "email": email}


def H(t): return {"Authorization": f"Bearer {t}"}


# ------------------------------- Memory ------------------------------
class TestMemory:
    def test_add_list_search_delete(self, admin_ctx):
        oid = admin_ctx["org_id"]; h = H(admin_ctx["token"])
        text = f"TEST_mem The Eiffel tower is in Paris {uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/orgs/{oid}/memories", json={"text": text, "tags": ["TEST_"]}, headers=h, timeout=60)
        assert r.status_code == 200, r.text
        mid = r.json()["id"]; assert r.json()["dim"] == 384

        lr = requests.get(f"{API}/orgs/{oid}/memories", headers=h, timeout=30)
        assert lr.status_code == 200
        assert any(m["id"] == mid for m in lr.json())

        sr = requests.post(f"{API}/orgs/{oid}/memories/search",
                           json={"query": "Where is the Eiffel tower?", "limit": 5}, headers=h, timeout=60)
        assert sr.status_code == 200
        res = sr.json()["results"]
        assert isinstance(res, list) and len(res) > 0
        assert all("score" in x for x in res)
        assert any(x["id"] == mid for x in res)

        dr = requests.delete(f"{API}/orgs/{oid}/memories/{mid}", headers=h, timeout=30)
        assert dr.status_code == 200
        # verify gone
        lr2 = requests.get(f"{API}/orgs/{oid}/memories", headers=h, timeout=30)
        assert not any(m["id"] == mid for m in lr2.json())


# ------------------------------- Agents ------------------------------
class TestAgents:
    def test_crud_and_run(self, admin_ctx):
        oid = admin_ctx["org_id"]; h = H(admin_ctx["token"])
        body = {
            "name": f"TEST_Bot_{uuid.uuid4().hex[:6]}",
            "description": "A helpful test bot",
            "role": "assistant",
            "system_prompt": "You answer briefly (<=20 words).",
            "tools": ["memory"],
            "knowledge": ["The secret code is BLUE-42.", "Our company name is Nexus."],
            "color": "#A855F7",
        }
        r = requests.post(f"{API}/orgs/{oid}/agents", json=body, headers=h, timeout=60)
        assert r.status_code == 200, r.text
        agent = r.json(); aid = agent["id"]
        assert agent["name"] == body["name"]
        assert agent["knowledge_count"] == 2
        assert "memory" in agent["tools"]

        # list
        lr = requests.get(f"{API}/orgs/{oid}/agents", headers=h, timeout=30)
        assert lr.status_code == 200
        assert any(a["id"] == aid for a in lr.json())

        # run
        rr = requests.post(f"{API}/orgs/{oid}/agents/{aid}/run",
                           json={"input": "What is the secret code?"}, headers=h, timeout=120)
        assert rr.status_code == 200, rr.text
        rj = rr.json()
        assert "output" in rj and len(rj["output"]) > 0
        assert "credits" in rj

        # runs history
        hist = requests.get(f"{API}/orgs/{oid}/agents/{aid}/runs", headers=h, timeout=30)
        assert hist.status_code == 200
        assert len(hist.json()) >= 1

        # patch
        body2 = {**body, "description": "updated desc", "knowledge": ["Only one line now."]}
        pr = requests.patch(f"{API}/orgs/{oid}/agents/{aid}", json=body2, headers=h, timeout=60)
        assert pr.status_code == 200
        assert pr.json()["description"] == "updated desc"
        assert pr.json()["knowledge_count"] == 1

        # delete
        dr = requests.delete(f"{API}/orgs/{oid}/agents/{aid}", headers=h, timeout=30)
        assert dr.status_code == 200

    def test_team_run(self, admin_ctx):
        oid = admin_ctx["org_id"]; h = H(admin_ctx["token"])
        ids = []
        for name, role, prompt in [
            ("TEST_Researcher", "researcher", "You research briefly."),
            ("TEST_Writer", "writer", "You write concise summaries."),
        ]:
            r = requests.post(f"{API}/orgs/{oid}/agents", headers=h, timeout=60,
                              json={"name": f"{name}_{uuid.uuid4().hex[:4]}", "role": role,
                                    "system_prompt": prompt, "tools": [], "knowledge": []})
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])

        tr = requests.post(f"{API}/orgs/{oid}/agents/team/run",
                           json={"goal": "Give 3 bullet facts about the moon.", "agent_ids": ids},
                           headers=h, timeout=180)
        assert tr.status_code == 200, tr.text
        j = tr.json()
        assert "output" in j and len(j["output"]) > 0
        assert isinstance(j.get("steps"), list) and len(j["steps"]) >= 1

        for aid in ids:
            requests.delete(f"{API}/orgs/{oid}/agents/{aid}", headers=h, timeout=30)


# ------------------------------- Security ------------------------------
class TestSecurity:
    def test_admin_overview_and_logs(self, admin_ctx):
        h = H(admin_ctx["token"])
        r = requests.get(f"{API}/admin/security/overview", headers=h, timeout=30)
        assert r.status_code == 200
        j = r.json()
        for k in ("total_events", "blocked_events", "error_events", "by_method", "rate_limit"):
            assert k in j
        assert "limit" in j["rate_limit"] and "window_seconds" in j["rate_limit"]

        r2 = requests.get(f"{API}/admin/audit-logs?limit=20", headers=h, timeout=30)
        assert r2.status_code == 200
        assert isinstance(r2.json(), list)

        r3 = requests.get(f"{API}/admin/audit-logs?blocked=true&limit=5", headers=h, timeout=30)
        assert r3.status_code == 200

    def test_non_admin_blocked(self, user_ctx):
        h = H(user_ctx["token"])
        r = requests.get(f"{API}/admin/audit-logs", headers=h, timeout=30)
        assert r.status_code == 403
        r2 = requests.get(f"{API}/admin/security/overview", headers=h, timeout=30)
        assert r2.status_code == 403
