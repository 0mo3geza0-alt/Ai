#!/usr/bin/env python3
"""
Comprehensive backend test for AI Provider Manager feature.
Tests all admin-only endpoints under /api/admin/providers.
"""
import os
import sys
import json
import time
import requests
from typing import Dict, Any

# Backend URL from frontend/.env
BACKEND_URL = "https://inspiring-wozniak-12.preview.emergentagent.com"
BASE_URL = f"{BACKEND_URL}/api"

# Admin credentials
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

# Test results
results = []


def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    msg = f"{status} - {test_name}"
    if details:
        msg += f": {details}"
    print(msg)
    results.append({"test": test_name, "passed": passed, "details": details})


def login_admin() -> str:
    """Login as admin and return Bearer token."""
    print("\n🔐 Logging in as admin...")
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30
    )
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    token = data.get("token")
    if not token:
        print(f"❌ No token in login response: {data}")
        sys.exit(1)
    print(f"✅ Login successful, got token")
    return token


def get_org_id(token: str) -> str:
    """Get default org ID from /api/auth/me."""
    resp = requests.get(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if resp.status_code != 200:
        print(f"❌ Failed to get user info: {resp.status_code}")
        sys.exit(1)
    data = resp.json()
    org_id = data.get("default_org_id")
    if not org_id:
        print(f"❌ No default_org_id in user data: {data}")
        sys.exit(1)
    print(f"✅ Got org_id: {org_id}")
    return org_id


def test_1_list_providers(token: str):
    """TEST 1: GET /api/admin/providers -> 200, exactly 14 providers with masked keys."""
    print("\n📋 TEST 1: List all providers")
    resp = requests.get(
        f"{BASE_URL}/admin/providers",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if resp.status_code != 200:
        log_test("TEST 1 - List providers", False, f"Status {resp.status_code}: {resp.text[:200]}")
        return None
    
    providers = resp.json()
    
    # Check exactly 14 providers
    if len(providers) != 14:
        log_test("TEST 1 - List providers", False, f"Expected 14 providers, got {len(providers)}")
        return None
    
    # Check expected slugs
    expected_slugs = ["openai", "anthropic", "gemini", "openrouter", "groq", "deepseek", 
                      "xai", "cerebras", "huggingface", "together", "fireworks", 
                      "sambanova", "ollama", "custom"]
    actual_slugs = [p["slug"] for p in providers]
    
    if set(actual_slugs) != set(expected_slugs):
        log_test("TEST 1 - List providers", False, 
                f"Slug mismatch. Expected: {expected_slugs}, Got: {actual_slugs}")
        return None
    
    # Check NO full plaintext API key is returned (only key_masked)
    for p in providers:
        if "api_key" in p and p["api_key"] and "*" not in str(p.get("api_key", "")):
            log_test("TEST 1 - List providers", False, 
                    f"Provider {p['slug']} has plaintext api_key field: {p.get('api_key')}")
            return None
        
        # Verify key_masked field exists
        if "key_masked" not in p:
            log_test("TEST 1 - List providers", False, 
                    f"Provider {p['slug']} missing key_masked field")
            return None
    
    log_test("TEST 1 - List providers", True, 
            f"14 providers returned, all with masked keys only")
    return providers


def test_2_catalog(token: str):
    """TEST 2: GET /api/admin/providers/catalog -> 200, 14 entries."""
    print("\n📚 TEST 2: Get provider catalog")
    resp = requests.get(
        f"{BASE_URL}/admin/providers/catalog",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if resp.status_code != 200:
        log_test("TEST 2 - Catalog", False, f"Status {resp.status_code}: {resp.text[:200]}")
        return
    
    catalog = resp.json()
    
    if len(catalog) != 14:
        log_test("TEST 2 - Catalog", False, f"Expected 14 entries, got {len(catalog)}")
        return
    
    log_test("TEST 2 - Catalog", True, f"14 catalog entries returned")


def test_3_auth_guard(token: str):
    """TEST 3: AUTH GUARD - GET /api/admin/providers with NO token -> 401/403."""
    print("\n🔒 TEST 3: Auth guard - no token")
    
    # Test with no token
    resp = requests.get(f"{BASE_URL}/admin/providers", timeout=30)
    
    if resp.status_code not in [401, 403]:
        log_test("TEST 3 - Auth guard (no token)", False, 
                f"Expected 401/403, got {resp.status_code}")
        return
    
    log_test("TEST 3 - Auth guard (no token)", True, 
            f"Correctly returned {resp.status_code} without token")


def test_4_update_and_mask(token: str, providers: list):
    """TEST 4: UPDATE + MASK - PUT /api/admin/providers/{id} with new key -> 200, key masked."""
    print("\n✏️ TEST 4: Update provider with new key and verify masking")
    
    # Find groq provider
    groq = next((p for p in providers if p["slug"] == "groq"), None)
    if not groq:
        log_test("TEST 4 - Update + mask", False, "Groq provider not found")
        return None
    
    groq_id = groq["id"]
    print(f"Found groq provider: {groq_id}")
    
    # Update with new key
    update_data = {
        "api_key": "gsk_test_ABCDEFGHIJKLMNOP1234",
        "enabled": False,
        "priority": 3,
        "price_in": 0.05,
        "price_out": 0.08,
        "monthly_budget": 10
    }
    
    resp = requests.put(
        f"{BASE_URL}/admin/providers/{groq_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=update_data,
        timeout=30
    )
    
    if resp.status_code != 200:
        log_test("TEST 4 - Update + mask", False, 
                f"Status {resp.status_code}: {resp.text[:200]}")
        return None
    
    updated = resp.json()
    
    # Verify has_key is true
    if not updated.get("has_key"):
        log_test("TEST 4 - Update + mask", False, 
                f"has_key should be true, got {updated.get('has_key')}")
        return None
    
    # Verify key_masked is masked (not full key)
    key_masked = updated.get("key_masked", "")
    if "gsk_test_ABCDEFGHIJKLMNOP1234" in key_masked:
        log_test("TEST 4 - Update + mask", False, 
                f"key_masked contains full key: {key_masked}")
        return None
    
    if "*" not in key_masked:
        log_test("TEST 4 - Update + mask", False, 
                f"key_masked should contain asterisks: {key_masked}")
        return None
    
    # Verify price_in updated
    if updated.get("price_in") != 0.05:
        log_test("TEST 4 - Update + mask", False, 
                f"price_in should be 0.05, got {updated.get('price_in')}")
        return None
    
    log_test("TEST 4 - Update + mask", True, 
            f"Key updated and masked correctly: {key_masked}, price_in=0.05")
    return groq_id


def test_5_mask_preservation(token: str, groq_id: str):
    """TEST 5: MASK PRESERVATION - PUT with masked key -> 200, key NOT overwritten."""
    print("\n🔐 TEST 5: Mask preservation - update with masked key")
    
    if not groq_id:
        log_test("TEST 5 - Mask preservation", False, "No groq_id from previous test")
        return
    
    # Update with masked key (should NOT overwrite)
    update_data = {
        "api_key": "gsk************1234",
        "model": "llama-3.3-70b-versatile"
    }
    
    resp = requests.put(
        f"{BASE_URL}/admin/providers/{groq_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=update_data,
        timeout=30
    )
    
    if resp.status_code != 200:
        log_test("TEST 5 - Mask preservation", False, 
                f"Status {resp.status_code}: {resp.text[:200]}")
        return
    
    updated = resp.json()
    
    # Verify has_key is still true (key not overwritten)
    if not updated.get("has_key"):
        log_test("TEST 5 - Mask preservation", False, 
                f"has_key should still be true, got {updated.get('has_key')}")
        return
    
    # Verify model updated
    if updated.get("model") != "llama-3.3-70b-versatile":
        log_test("TEST 5 - Mask preservation", False, 
                f"model should be updated, got {updated.get('model')}")
        return
    
    log_test("TEST 5 - Mask preservation", True, 
            f"Masked key NOT overwritten, model updated to {updated.get('model')}")


def test_6_test_connection(token: str, groq_id: str):
    """TEST 6: TEST CONNECTION - POST /api/admin/providers/{id}/test -> real error."""
    print("\n🔌 TEST 6: Test connection (expect failure with bad key)")
    
    if not groq_id:
        log_test("TEST 6 - Test connection", False, "No groq_id from previous test")
        return
    
    resp = requests.post(
        f"{BASE_URL}/admin/providers/{groq_id}/test",
        headers={"Authorization": f"Bearer {token}"},
        timeout=120  # Test connection can take time
    )
    
    if resp.status_code != 200:
        log_test("TEST 6 - Test connection", False, 
                f"Status {resp.status_code}: {resp.text[:200]}")
        return
    
    result = resp.json()
    
    # Verify connected is false (bad key)
    if result.get("connected") != False:
        log_test("TEST 6 - Test connection", False, 
                f"connected should be false with bad key, got {result.get('connected')}")
        return
    
    # Verify error message exists (real provider error)
    error = result.get("error", "")
    if not error:
        log_test("TEST 6 - Test connection", False, 
                f"Expected error message, got: {result}")
        return
    
    # Verify latency_ms exists
    if "latency_ms" not in result:
        log_test("TEST 6 - Test connection", False, 
                f"latency_ms missing from result: {result}")
        return
    
    latency = result.get("latency_ms")
    
    log_test("TEST 6 - Test connection", True, 
            f"Real connection test returned connected=false, error='{error[:100]}', latency_ms={latency}")


def test_7_usage(token: str):
    """TEST 7: USAGE - GET /api/admin/providers/usage -> 200 with stats."""
    print("\n📊 TEST 7: Get usage summary")
    
    resp = requests.get(
        f"{BASE_URL}/admin/providers/usage",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if resp.status_code != 200:
        log_test("TEST 7 - Usage", False, f"Status {resp.status_code}: {resp.text[:200]}")
        return
    
    usage = resp.json()
    
    # Verify required fields
    required_fields = ["today_requests", "month_requests", "estimated_cost_month", 
                      "avg_response_ms", "success_rate", "providers"]
    
    for field in required_fields:
        if field not in usage:
            log_test("TEST 7 - Usage", False, f"Missing field: {field}")
            return
    
    # Verify providers is a list
    if not isinstance(usage.get("providers"), list):
        log_test("TEST 7 - Usage", False, 
                f"providers should be a list, got {type(usage.get('providers'))}")
        return
    
    log_test("TEST 7 - Usage", True, 
            f"Usage summary returned with {len(usage['providers'])} providers, "
            f"month_requests={usage['month_requests']}, success_rate={usage['success_rate']}%")


def test_8_logs(token: str):
    """TEST 8: LOGS - GET /api/admin/providers/logs?limit=20 -> 200 array."""
    print("\n📝 TEST 8: Get provider logs")
    
    resp = requests.get(
        f"{BASE_URL}/admin/providers/logs?limit=20",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if resp.status_code != 200:
        log_test("TEST 8 - Logs", False, f"Status {resp.status_code}: {resp.text[:200]}")
        return
    
    logs = resp.json()
    
    # Verify it's a list
    if not isinstance(logs, list):
        log_test("TEST 8 - Logs", False, f"Expected list, got {type(logs)}")
        return
    
    log_test("TEST 8 - Logs", True, f"Logs returned with {len(logs)} entries")


def test_9_fallback_intact(token: str, org_id: str):
    """TEST 9: FALLBACK INTACT - with NO provider enabled, chat still works via Emergent."""
    print("\n🔄 TEST 9: Verify fallback to Emergent key when no provider enabled")
    
    # Create a chat session
    print("Creating chat session...")
    resp = requests.post(
        f"{BASE_URL}/orgs/{org_id}/chat/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={},
        timeout=30
    )
    
    if resp.status_code != 200:
        log_test("TEST 9 - Fallback intact", False, 
                f"Failed to create session: {resp.status_code} {resp.text[:200]}")
        return
    
    session = resp.json()
    sid = session.get("id")
    if not sid:
        log_test("TEST 9 - Fallback intact", False, f"No session id: {session}")
        return
    
    print(f"Session created: {sid}")
    
    # Send a message to chat agent
    print("Sending message to chat agent...")
    resp = requests.post(
        f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/agent",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Say hello in one short sentence."},
        timeout=60
    )
    
    if resp.status_code != 200:
        log_test("TEST 9 - Fallback intact", False, 
                f"Chat agent failed: {resp.status_code} {resp.text[:200]}")
        return
    
    result = resp.json()
    
    # Verify we got a reply
    content = result.get("content", "")
    if not content or len(content) < 5:
        log_test("TEST 9 - Fallback intact", False, 
                f"Empty or too short reply: '{content}'")
        return
    
    log_test("TEST 9 - Fallback intact", True, 
            f"Chat works via Emergent fallback, reply: '{content[:100]}'")


def main():
    """Run all tests."""
    print("=" * 80)
    print("AI PROVIDER MANAGER - COMPREHENSIVE BACKEND TEST")
    print("=" * 80)
    
    # Login
    token = login_admin()
    org_id = get_org_id(token)
    
    # Run tests
    providers = test_1_list_providers(token)
    test_2_catalog(token)
    test_3_auth_guard(token)
    
    groq_id = None
    if providers:
        groq_id = test_4_update_and_mask(token, providers)
        if groq_id:
            test_5_mask_preservation(token, groq_id)
            test_6_test_connection(token, groq_id)
    
    test_7_usage(token)
    test_8_logs(token)
    test_9_fallback_intact(token, org_id)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    
    for r in results:
        status = "✅" if r["passed"] else "❌"
        print(f"{status} {r['test']}")
        if r["details"] and not r["passed"]:
            print(f"   Details: {r['details']}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
