"""Phase 2 + Phase 3 backend tests: auth (JWT), orgs, teams, api-keys, RBAC, workspace (projects/files/versions/artifacts)."""
import os
import io
import uuid
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"


def _register(name="U"):
    email = f"test_{uuid.uuid4().hex[:10]}@user.com"
    r = requests.post(f"{API}/auth/register",
                      json={"name": name, "email": email, "password": "test1234"}, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    d = r.json()
    return {"email": email, "password": "test1234",
            "token": d["token"], "user": d["user"],
            "org_id": d["user"]["default_org_id"]}


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def userA():
    return _register("Alice")


@pytest.fixture(scope="module")
def userB():
    return _register("Bob")


# -------------------------------- health / auth
class TestHealthAuth:
    def test_health(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_register_creates_personal_org(self, userA):
        assert userA["user"]["email"] == userA["email"]
        assert userA["user"]["default_org_id"]
        assert isinstance(userA["token"], str) and len(userA["token"]) > 20

    def test_login_admin(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == ADMIN_EMAIL
        assert "token" in d

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_me_bearer(self, userA):
        r = requests.get(f"{API}/auth/me", headers=_headers(userA["token"]), timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == userA["email"]

    def test_me_no_auth_401(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401

    def test_duplicate_register(self, userA):
        r = requests.post(f"{API}/auth/register",
                          json={"name": "X", "email": userA["email"], "password": "test1234"}, timeout=15)
        assert r.status_code == 400

    def test_oauth_invalid_session(self):
        r = requests.post(f"{API}/auth/oauth/emergent",
                          json={"session_id": "invalid_xxx"}, timeout=30)
        assert r.status_code in (401, 400, 502)


# -------------------------------- orgs
class TestOrgs:
    def test_list_orgs(self, userA):
        r = requests.get(f"{API}/orgs", headers=_headers(userA["token"]), timeout=15)
        assert r.status_code == 200
        orgs = r.json()
        assert any(o["id"] == userA["org_id"] for o in orgs)
        assert any(o["role"] == "owner" for o in orgs)

    def test_get_org(self, userA):
        r = requests.get(f"{API}/orgs/{userA['org_id']}", headers=_headers(userA["token"]), timeout=15)
        assert r.status_code == 200
        assert r.json()["id"] == userA["org_id"]

    def test_non_member_forbidden(self, userA, userB):
        r = requests.get(f"{API}/orgs/{userA['org_id']}",
                         headers=_headers(userB["token"]), timeout=15)
        assert r.status_code == 403

    def test_add_member_nonexistent_email(self, userA):
        r = requests.post(f"{API}/orgs/{userA['org_id']}/members",
                         headers=_headers(userA["token"]),
                         json={"email": f"noone_{uuid.uuid4().hex[:6]}@nope.com", "role": "member"},
                         timeout=15)
        assert r.status_code == 404

    def test_add_member_success(self, userA, userB):
        r = requests.post(f"{API}/orgs/{userA['org_id']}/members",
                         headers=_headers(userA["token"]),
                         json={"email": userB["email"], "role": "member"}, timeout=15)
        assert r.status_code == 200, r.text
        # userB can now access userA's org
        r2 = requests.get(f"{API}/orgs/{userA['org_id']}", headers=_headers(userB["token"]), timeout=15)
        assert r2.status_code == 200

    def test_create_team(self, userA):
        r = requests.post(f"{API}/orgs/{userA['org_id']}/teams",
                         headers=_headers(userA["token"]),
                         json={"name": "Engineering"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["name"] == "Engineering"

    def test_list_members(self, userA):
        r = requests.get(f"{API}/orgs/{userA['org_id']}/members",
                        headers=_headers(userA["token"]), timeout=15)
        assert r.status_code == 200
        assert len(r.json()) >= 2  # owner + userB added earlier


# -------------------------------- projects + files + artifacts
@pytest.fixture(scope="module")
def project(userA):
    r = requests.post(f"{API}/orgs/{userA['org_id']}/projects",
                     headers=_headers(userA["token"]),
                     json={"name": "TEST_Proj", "description": "for tests"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


class TestProjects:
    def test_create_and_list(self, userA, project):
        assert project["name"] == "TEST_Proj"
        r = requests.get(f"{API}/orgs/{userA['org_id']}/projects",
                        headers=_headers(userA["token"]), timeout=15)
        assert r.status_code == 200
        assert any(p["id"] == project["id"] for p in r.json())

    def test_get_project(self, userA, project):
        r = requests.get(f"{API}/orgs/{userA['org_id']}/projects/{project['id']}",
                        headers=_headers(userA["token"]), timeout=15)
        assert r.status_code == 200
        assert r.json()["id"] == project["id"]


class TestFilesVersions:
    def test_upload_v1_then_v2_same_name(self, userA, project):
        files = {"file": ("notes.txt", io.BytesIO(b"version one content"), "text/plain")}
        r1 = requests.post(f"{API}/orgs/{userA['org_id']}/projects/{project['id']}/files",
                          headers=_headers(userA["token"]), files=files, timeout=60)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["version"] == 1
        assert d1["name"] == "notes.txt"
        assert d1["current"] is True

        files2 = {"file": ("notes.txt", io.BytesIO(b"version TWO content updated"), "text/plain")}
        r2 = requests.post(f"{API}/orgs/{userA['org_id']}/projects/{project['id']}/files",
                          headers=_headers(userA["token"]), files=files2, timeout=60)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["version"] == 2

        # list shows only current version
        r3 = requests.get(f"{API}/orgs/{userA['org_id']}/projects/{project['id']}/files",
                         headers=_headers(userA["token"]), timeout=15)
        assert r3.status_code == 200
        listing = [f for f in r3.json() if f["file_key"] == "notes.txt"]
        assert len(listing) == 1
        assert listing[0]["version"] == 2

        # versions endpoint shows both
        rv = requests.get(f"{API}/orgs/{userA['org_id']}/projects/{project['id']}/files/{d2['id']}/versions",
                         headers=_headers(userA["token"]), timeout=15)
        assert rv.status_code == 200
        versions = rv.json()
        assert len(versions) >= 2
        assert {v["version"] for v in versions} >= {1, 2}

        # download current version
        rd = requests.get(f"{API}/orgs/{userA['org_id']}/projects/{project['id']}/files/{d2['id']}/download",
                         headers=_headers(userA["token"]), timeout=30)
        assert rd.status_code == 200
        assert b"TWO" in rd.content


class TestArtifacts:
    def test_create_and_list(self, userA, project):
        r = requests.post(f"{API}/orgs/{userA['org_id']}/projects/{project['id']}/artifacts",
                         headers=_headers(userA["token"]),
                         json={"name": "readme", "type": "text", "content": "hello world"},
                         timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "readme"

        r2 = requests.get(f"{API}/orgs/{userA['org_id']}/projects/{project['id']}/artifacts",
                         headers=_headers(userA["token"]), timeout=15)
        assert r2.status_code == 200
        assert any(a["name"] == "readme" for a in r2.json())


# -------------------------------- api keys + RBAC
class TestApiKeysRBAC:
    def test_create_apikey_and_use(self, userA):
        r = requests.post(f"{API}/orgs/{userA['org_id']}/api-keys",
                         headers=_headers(userA["token"]),
                         json={"name": "ci-key", "scopes": ["project:read"]}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        secret = d.get("key")
        assert secret and secret.startswith("ak_"), f"secret missing/wrong: {d}"
        prefix = d["prefix"]

        # list contains prefix but no secret
        rl = requests.get(f"{API}/orgs/{userA['org_id']}/api-keys",
                         headers=_headers(userA["token"]), timeout=15)
        assert rl.status_code == 200
        keys = rl.json()
        assert any(k["prefix"] == prefix for k in keys)
        assert all("key" not in k for k in keys)

        # use api key for allowed read
        rk = requests.get(f"{API}/orgs/{userA['org_id']}/projects",
                         headers={"X-API-Key": secret}, timeout=15)
        assert rk.status_code == 200, rk.text

        # api key denied for create (needs project:create)
        rc = requests.post(f"{API}/orgs/{userA['org_id']}/projects",
                          headers={"X-API-Key": secret},
                          json={"name": "should-fail", "description": ""}, timeout=15)
        assert rc.status_code == 403

        # revoke
        rr = requests.delete(f"{API}/orgs/{userA['org_id']}/api-keys/{d['id']}",
                            headers=_headers(userA["token"]), timeout=15)
        assert rr.status_code == 200

        # after revoke -> 401 or 403
        r_after = requests.get(f"{API}/orgs/{userA['org_id']}/projects",
                              headers={"X-API-Key": secret}, timeout=15)
        assert r_after.status_code in (401, 403)

    def test_non_member_cannot_read_projects(self, userA):
        # userC not a member
        userC = _register("Carol")
        r = requests.get(f"{API}/orgs/{userA['org_id']}/projects",
                        headers=_headers(userC["token"]), timeout=15)
        assert r.status_code == 403
