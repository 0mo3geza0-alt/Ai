"""Stripe billing backend tests: plans catalog, checkout session, status polling."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASS = "admin12345"


@pytest.fixture(scope="module")
def admin_ctx():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    token = data["token"]
    orgs = requests.get(f"{BASE_URL}/api/orgs", headers={"Authorization": f"Bearer {token}"}, timeout=30).json()
    org_id = orgs[0]["id"] if isinstance(orgs, list) else orgs.get("orgs", [{}])[0].get("id")
    return {"token": token, "org_id": org_id}


@pytest.fixture(scope="module")
def new_user_ctx():
    """Register a new user (free org) for the E2E upgrade scenario."""
    email = f"TEST_billing_{int(time.time())}@t.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "test1234", "name": "Billing Test"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    token = data["token"]
    orgs = requests.get(f"{BASE_URL}/api/orgs", headers={"Authorization": f"Bearer {token}"}, timeout=30).json()
    orgs_list = orgs if isinstance(orgs, list) else orgs.get("orgs", [])
    return {"token": token, "org_id": orgs_list[0]["id"], "email": email}


class TestBillingPlans:
    def test_list_plans_returns_three(self):
        r = requests.get(f"{BASE_URL}/api/billing/plans", timeout=30)
        assert r.status_code == 200
        plans = r.json()["plans"]
        assert len(plans) == 3
        ids = {p["id"] for p in plans}
        assert ids == {"free", "pro", "business"}
        pro = next(p for p in plans if p["id"] == "pro")
        assert pro["monthly"] == 19 and pro["yearly"] == 180
        assert pro["monthly_lookup"] == "pro_monthly"
        assert pro["yearly_lookup"] == "pro_yearly"
        biz = next(p for p in plans if p["id"] == "business")
        assert biz["monthly"] == 49 and biz["yearly"] == 470


class TestBillingCheckout:
    def test_checkout_creates_stripe_session(self, new_user_ctx):
        headers = {"Authorization": f"Bearer {new_user_ctx['token']}"}
        r = requests.post(
            f"{BASE_URL}/api/billing/orgs/{new_user_ctx['org_id']}/checkout",
            json={"lookup_key": "pro_monthly", "origin_url": BASE_URL},
            headers=headers, timeout=60,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "checkout_url" in d and d["checkout_url"].startswith("https://checkout.stripe.com/")
        assert "session_id" in d and d["session_id"].startswith("cs_")
        # cache session_id for the status test
        pytest.session_id = d["session_id"]

    def test_status_pending_before_payment(self):
        sid = getattr(pytest, "session_id", None)
        assert sid, "prior checkout test must have run"
        r = requests.get(f"{BASE_URL}/api/billing/status/{sid}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["session_id"] == sid
        assert d["lookup_key"] == "pro_monthly"
        assert d["payment_status"] in ("pending", "unpaid", "no_payment_required")

    def test_checkout_rejects_unknown_lookup(self, admin_ctx):
        headers = {"Authorization": f"Bearer {admin_ctx['token']}"}
        r = requests.post(
            f"{BASE_URL}/api/billing/orgs/{admin_ctx['org_id']}/checkout",
            json={"lookup_key": "not_a_plan", "origin_url": BASE_URL},
            headers=headers, timeout=30,
        )
        assert r.status_code == 400

    def test_status_404_for_unknown_session(self):
        r = requests.get(f"{BASE_URL}/api/billing/status/cs_unknown_xyz", timeout=30)
        assert r.status_code == 404
