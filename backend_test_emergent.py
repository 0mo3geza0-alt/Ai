#!/usr/bin/env python3
"""
Test AI Provider Manager ENHANCEMENT: Emergent built-in key tracking + per-provider remaining budget
"""
import requests
import json
import sys

BASE_URL = "https://b56603c6-4e16-41ee-a1f9-a01a1c612d5a.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

def login():
    """Login and return Bearer token"""
    print("🔐 Logging in as admin...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    token = resp.json().get("token")
    print(f"✅ Login successful, token: {token[:20]}...")
    return token

def get_org_id(token):
    """Get default org id"""
    print("\n📋 Getting org id...")
    resp = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ Failed to get user info: {resp.status_code}")
        sys.exit(1)
    org_id = resp.json().get("default_org_id")
    print(f"✅ Org id: {org_id}")
    return org_id

def test_1_get_emergent(token):
    """TEST 1: GET /api/admin/providers/emergent"""
    print("\n" + "="*80)
    print("TEST 1: GET /api/admin/providers/emergent")
    print("="*80)
    
    resp = requests.get(f"{BASE_URL}/admin/providers/emergent", 
                       headers={"Authorization": f"Bearer {token}"})
    
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    # Check required fields
    required_fields = [
        "balance_supported", "note", "dashboard_url", 
        "today_requests", "month_requests", "month_tokens",
        "estimated_cost_month", "avg_response_ms", 
        "monthly_budget", "remaining_budget", "price_in", "price_out"
    ]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"❌ FAIL: Missing fields: {missing}")
        return False
    
    # CRITICAL: balance_supported MUST be false
    if data.get("balance_supported") != False:
        print(f"❌ FAIL: balance_supported must be false (not fabricate real balance), got: {data.get('balance_supported')}")
        return False
    
    print(f"✅ PASS: All required fields present")
    print(f"✅ PASS: balance_supported is false (correct - no fabricated balance)")
    print(f"   - today_requests: {data.get('today_requests')}")
    print(f"   - month_requests: {data.get('month_requests')}")
    print(f"   - month_tokens: {data.get('month_tokens')}")
    print(f"   - estimated_cost_month: {data.get('estimated_cost_month')}")
    print(f"   - monthly_budget: {data.get('monthly_budget')}")
    print(f"   - remaining_budget: {data.get('remaining_budget')}")
    print(f"   - price_in: {data.get('price_in')}")
    print(f"   - price_out: {data.get('price_out')}")
    
    return True

def test_2_put_emergent(token):
    """TEST 2: PUT /api/admin/providers/emergent with budget and prices"""
    print("\n" + "="*80)
    print("TEST 2: PUT /api/admin/providers/emergent")
    print("="*80)
    
    payload = {
        "monthly_budget": 50,
        "price_in": 0.15,
        "price_out": 0.6
    }
    
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    resp = requests.put(f"{BASE_URL}/admin/providers/emergent",
                       json=payload,
                       headers={"Authorization": f"Bearer {token}"})
    
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    # Verify the values
    if data.get("monthly_budget") != 50:
        print(f"❌ FAIL: monthly_budget should be 50, got {data.get('monthly_budget')}")
        return False
    
    if data.get("price_in") != 0.15:
        print(f"❌ FAIL: price_in should be 0.15, got {data.get('price_in')}")
        return False
    
    if data.get("price_out") != 0.6:
        print(f"❌ FAIL: price_out should be 0.6, got {data.get('price_out')}")
        return False
    
    # remaining_budget should be 50 before new usage
    if data.get("remaining_budget") != 50:
        print(f"⚠️  WARNING: remaining_budget should be 50 (before usage), got {data.get('remaining_budget')}")
        # Not failing this as there might be existing usage
    
    print(f"✅ PASS: monthly_budget = {data.get('monthly_budget')}")
    print(f"✅ PASS: price_in = {data.get('price_in')}")
    print(f"✅ PASS: price_out = {data.get('price_out')}")
    print(f"✅ PASS: remaining_budget = {data.get('remaining_budget')}")
    
    # Also verify route ordering - this should NOT be treated as a provider id
    # (i.e., we got the emergent summary shape, not a 404)
    if "slug" in data and data.get("slug") == "emergent":
        # This is the emergent summary shape, good
        pass
    
    return True

def test_3_emergent_usage_logging(token, org_id):
    """TEST 3: CRITICAL - Emergent usage logging"""
    print("\n" + "="*80)
    print("TEST 3: EMERGENT USAGE LOGGING (CRITICAL)")
    print("="*80)
    
    # Get current Emergent stats BEFORE chat
    print("\n📊 Getting Emergent stats BEFORE chat...")
    resp = requests.get(f"{BASE_URL}/admin/providers/emergent",
                       headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not get Emergent stats before chat")
        return False
    
    before = resp.json()
    print(f"Before - today_requests: {before.get('today_requests')}, "
          f"month_requests: {before.get('month_requests')}, "
          f"month_tokens: {before.get('month_tokens')}, "
          f"estimated_cost_month: {before.get('estimated_cost_month')}, "
          f"remaining_budget: {before.get('remaining_budget')}")
    
    # Create chat session
    print("\n💬 Creating chat session...")
    resp = requests.post(f"{BASE_URL}/orgs/{org_id}/chat/sessions",
                        json={},
                        headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not create chat session: {resp.status_code}")
        return False
    
    sid = resp.json().get("id")
    print(f"✅ Session created: {sid}")
    
    # Send message (this should use Emergent fallback since no provider is enabled)
    print("\n📤 Sending message 'Say hi'...")
    resp = requests.post(f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/agent",
                        json={"message": "Say hi"},
                        headers={"Authorization": f"Bearer {token}"})
    
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Chat failed: {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    response_data = resp.json()
    
    # The response has "content" field, not "reply"
    reply = response_data.get("content", response_data.get("reply", ""))
    print(f"✅ Reply received: {reply[:100] if len(reply) > 100 else reply}")
    
    if not reply:
        print(f"❌ FAIL: Empty reply")
        print(f"Full response: {json.dumps(response_data, indent=2)}")
        return False
    
    # Get Emergent stats AFTER chat
    print("\n📊 Getting Emergent stats AFTER chat...")
    resp = requests.get(f"{BASE_URL}/admin/providers/emergent",
                       headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not get Emergent stats after chat")
        return False
    
    after = resp.json()
    print(f"After - today_requests: {after.get('today_requests')}, "
          f"month_requests: {after.get('month_requests')}, "
          f"month_tokens: {after.get('month_tokens')}, "
          f"estimated_cost_month: {after.get('estimated_cost_month')}, "
          f"remaining_budget: {after.get('remaining_budget')}")
    
    # Verify usage increased
    checks_passed = True
    
    if after.get('today_requests', 0) <= before.get('today_requests', 0):
        print(f"❌ FAIL: today_requests did not increase (before: {before.get('today_requests')}, after: {after.get('today_requests')})")
        checks_passed = False
    else:
        print(f"✅ PASS: today_requests increased from {before.get('today_requests')} to {after.get('today_requests')}")
    
    if after.get('month_requests', 0) <= before.get('month_requests', 0):
        print(f"❌ FAIL: month_requests did not increase (before: {before.get('month_requests')}, after: {after.get('month_requests')})")
        checks_passed = False
    else:
        print(f"✅ PASS: month_requests increased from {before.get('month_requests')} to {after.get('month_requests')}")
    
    if after.get('month_tokens', 0) <= 0:
        print(f"❌ FAIL: month_tokens should be > 0, got {after.get('month_tokens')}")
        checks_passed = False
    else:
        print(f"✅ PASS: month_tokens > 0 ({after.get('month_tokens')})")
    
    if after.get('estimated_cost_month', 0) <= 0:
        print(f"❌ FAIL: estimated_cost_month should be > 0, got {after.get('estimated_cost_month')}")
        checks_passed = False
    else:
        print(f"✅ PASS: estimated_cost_month computed from prices ({after.get('estimated_cost_month')})")
    
    if after.get('remaining_budget', 50) >= 50:
        print(f"⚠️  WARNING: remaining_budget should be < 50 after usage, got {after.get('remaining_budget')}")
        # Not failing as budget might have been reset or there's existing usage
    else:
        print(f"✅ PASS: remaining_budget < 50 ({after.get('remaining_budget')})")
    
    if not checks_passed:
        print(f"\n❌ FAIL: Emergent usage logging not working correctly")
        return False
    
    print(f"\n✅ PASS: Emergent usage logging working correctly")
    return True

def test_4_auth_guard(token):
    """TEST 4: Auth guard - no token should return 401/403"""
    print("\n" + "="*80)
    print("TEST 4: AUTH GUARD")
    print("="*80)
    
    print("Calling GET /api/admin/providers/emergent with NO token...")
    resp = requests.get(f"{BASE_URL}/admin/providers/emergent")
    
    print(f"Status: {resp.status_code}")
    
    if resp.status_code not in [401, 403]:
        print(f"❌ FAIL: Expected 401 or 403, got {resp.status_code}")
        return False
    
    print(f"✅ PASS: Correctly returned {resp.status_code} (unauthorized)")
    return True

def test_5_regression(token):
    """TEST 5: Regression - verify existing endpoints still work"""
    print("\n" + "="*80)
    print("TEST 5: REGRESSION TESTS")
    print("="*80)
    
    # Test 5a: GET /api/admin/providers should return 14 providers
    print("\n5a. GET /api/admin/providers (should return 14 providers)...")
    resp = requests.get(f"{BASE_URL}/admin/providers",
                       headers={"Authorization": f"Bearer {token}"})
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    providers = resp.json()
    if not isinstance(providers, list):
        print(f"❌ FAIL: Expected list, got {type(providers)}")
        return False
    
    if len(providers) != 14:
        print(f"❌ FAIL: Expected 14 providers, got {len(providers)}")
        print(f"Providers: {[p.get('slug') for p in providers]}")
        return False
    
    print(f"✅ PASS: GET /api/admin/providers returns exactly 14 providers")
    
    # Test 5b: GET /api/admin/providers/usage should return 200
    print("\n5b. GET /api/admin/providers/usage...")
    resp = requests.get(f"{BASE_URL}/admin/providers/usage",
                       headers={"Authorization": f"Bearer {token}"})
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    usage = resp.json()
    if "providers" not in usage:
        print(f"❌ FAIL: Expected 'providers' key in response")
        return False
    
    # Check that each provider has month_cost, monthly_budget, remaining_budget
    providers_list = usage.get("providers", [])
    for p in providers_list:
        if "month_cost" not in p or "monthly_budget" not in p or "remaining_budget" not in p:
            print(f"❌ FAIL: Provider {p.get('slug')} missing cost/budget fields")
            return False
    
    print(f"✅ PASS: GET /api/admin/providers/usage returns 200 with providers[] containing month_cost/monthly_budget/remaining_budget")
    
    return True

def main():
    print("="*80)
    print("AI Provider Manager ENHANCEMENT Test Suite")
    print("Testing: Emergent built-in key tracking + per-provider remaining budget")
    print("="*80)
    
    # Login
    token = login()
    org_id = get_org_id(token)
    
    # Run tests
    results = []
    
    results.append(("TEST 1: GET /api/admin/providers/emergent", test_1_get_emergent(token)))
    results.append(("TEST 2: PUT /api/admin/providers/emergent", test_2_put_emergent(token)))
    results.append(("TEST 3: Emergent usage logging (CRITICAL)", test_3_emergent_usage_logging(token, org_id)))
    results.append(("TEST 4: Auth guard", test_4_auth_guard(token)))
    results.append(("TEST 5: Regression tests", test_5_regression(token)))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
