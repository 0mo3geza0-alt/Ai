"""Tests for the unified multimodal AI Studio agent endpoint."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"


@pytest.fixture(scope="module")
def auth():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    token = data["token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    # find admin org
    orgs = s.get(f"{BASE_URL}/api/orgs", timeout=30).json()
    assert orgs, "No orgs"
    # prefer Admin Org
    org = next((o for o in orgs if "admin" in (o.get("name") or "").lower()), orgs[0])
    return {"session": s, "org_id": org["id"], "user": data["user"]}


@pytest.fixture(scope="module")
def session_id(auth):
    s = auth["session"]
    r = s.post(f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions", json={"title": "TEST_unified"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _agent(auth, sid, msg, timeout=90):
    s = auth["session"]
    t0 = time.time()
    r = s.post(f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions/{sid}/agent",
               json={"message": msg}, timeout=timeout)
    elapsed = time.time() - t0
    return r, elapsed


# ---------------- CHAT (plain) ----------------
def test_agent_plain_chat(auth, session_id):
    r, _ = _agent(auth, session_id, "What is the capital of France?")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["action"] == "chat"
    assert d["kind"] == "text"
    assert d["content"] and "paris" in d["content"].lower()


# ---------------- CODE ----------------
def test_agent_code(auth, session_id):
    r, _ = _agent(auth, session_id, "Write a Python function to reverse a string")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["action"] == "code"
    assert d["kind"] == "code"
    assert d["media"] and d["media"].get("language")
    assert "def " in d["content"] or "```" in d["content"]


# ---------------- IMAGE ----------------
def test_agent_image(auth, session_id):
    r, _ = _agent(auth, session_id, "Generate an image of a mountain lake at sunrise")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["action"] == "image"
    assert d["kind"] == "image"
    assert d["media"] and d["media"].get("url")
    # fetch the image
    s = auth["session"]
    img = s.get(f"{BASE_URL}{d['media']['url']}", timeout=60)
    assert img.status_code == 200
    assert img.headers.get("content-type", "").startswith("image/")
    assert len(img.content) > 500


# ---------------- WEBAPP (backgrounded) ----------------
def test_agent_webapp_backgrounded_and_completes(auth, session_id):
    r, elapsed = _agent(auth, session_id, "Build a simple landing page for a bakery", timeout=45)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["action"] == "webapp"
    assert d["kind"] == "webapp"
    assert d["media"]["status"] == "processing"
    assert d["media"].get("cid")
    # Must return quickly (well under ingress ~60s)
    assert elapsed < 40, f"webapp /agent took {elapsed:.1f}s — must be backgrounded"

    cid = d["media"]["cid"]
    s = auth["session"]
    status = None
    final = None
    for _ in range(60):  # up to ~2min
        time.sleep(3)
        sr = s.get(f"{BASE_URL}/api/orgs/{auth['org_id']}/creations/{cid}/status", timeout=30)
        assert sr.status_code == 200, sr.text
        final = sr.json()
        status = final.get("status")
        if status in ("done", "failed"):
            break
    assert status == "done", f"webapp did not complete: {final}"
    assert final.get("url")
    # Fetch the HTML
    hr = s.get(f"{BASE_URL}{final['url']}", timeout=30)
    assert hr.status_code == 200
    assert "text/html" in hr.headers.get("content-type", "")
    assert "<" in hr.text and "html" in hr.text.lower()


# ---------------- Messages persistence carries kind+media ----------------
def test_messages_carry_kind_and_media(auth, session_id):
    s = auth["session"]
    r = s.get(f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions/{session_id}/messages", timeout=30)
    assert r.status_code == 200
    msgs = r.json()
    assert any(m.get("kind") == "image" and m.get("media") for m in msgs), "image kind/media missing in history"
    assert any(m.get("kind") == "code" for m in msgs), "code kind missing"
    assert any(m.get("kind") == "webapp" for m in msgs), "webapp kind missing"


# ---------------- Sessions CRUD ----------------
def test_sessions_list_and_delete(auth):
    s = auth["session"]
    # Create then delete a temp session
    c = s.post(f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions", json={"title": "TEST_todelete"}, timeout=30)
    assert c.status_code == 200
    sid = c.json()["id"]
    lst = s.get(f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions", timeout=30).json()
    assert any(x["id"] == sid for x in lst)
    d = s.delete(f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions/{sid}", timeout=30)
    assert d.status_code == 200
    lst2 = s.get(f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions", timeout=30).json()
    assert not any(x["id"] == sid for x in lst2)
