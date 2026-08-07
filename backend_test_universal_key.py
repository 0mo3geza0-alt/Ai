#!/usr/bin/env python3
"""
Comprehensive backend test for the NEW Emergent Universal Key admin feature.
Tests the refactored single-key manager that replaced the old multi-provider system.
"""
import os
import sys
import requests
import json
from dotenv import load_dotenv
from pathlib import Path

# Load frontend .env to get REACT_APP_BACKEND_URL
frontend_env = Path("/app/frontend/.env")
if frontend_env.exists():
    load_dotenv(frontend_env)

BASE_URL = os.getenv("REACT_APP_BACKEND_URL", "").rstrip("/") + "/api"
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

print(f"🔧 Base URL: {BASE_URL}")
print(f"🔑 Admin: {ADMIN_EMAIL}")
print()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def login():
    """Login as admin and return Bearer token + org_id."""
    print("🔐 Logging in as admin...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    }, timeout=30)
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    token = data.get("token")
    if not token:
        print(f"❌ No token in login response: {data}")
        sys.exit(1)
    
    # Get org_id from /api/auth/me
    me_resp = requests.get(f"{BASE_URL}/auth/me", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=30)
    if me_resp.status_code != 200:
        print(f"❌ Failed to get user info: {me_resp.status_code}")
        sys.exit(1)
    me_data = me_resp.json()
    org_id = me_data.get("default_org_id")
    if not org_id:
        print(f"❌ No default_org_id in user data: {me_data}")
        sys.exit(1)
    
    print(f"✅ Login successful. Token: {token[:20]}... Org: {org_id}")
    return token, org_id


def test_get_universal_key(token):
    """TEST 1: GET /api/admin/providers/universal-key"""
    print("\n" + "="*80)
    print("TEST 1: GET /api/admin/providers/universal-key")
    print("="*80)
    
    resp = requests.get(f"{BASE_URL}/admin/providers/universal-key", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=30)
    
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    # Verify required fields
    required_fields = ["key_masked", "has_key", "source", "is_custom", "has_default"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"❌ FAIL: Missing fields: {missing}")
        return False
    
    # Verify field values
    if not isinstance(data["key_masked"], str) or not data["key_masked"]:
        print(f"❌ FAIL: key_masked should be non-empty string, got: {data['key_masked']}")
        return False
    
    if data["has_key"] != True:
        print(f"❌ FAIL: has_key should be true, got: {data['has_key']}")
        return False
    
    if data["source"] not in ["default", "custom"]:
        print(f"❌ FAIL: source should be 'default' or 'custom', got: {data['source']}")
        return False
    
    if not isinstance(data["is_custom"], bool):
        print(f"❌ FAIL: is_custom should be boolean, got: {data['is_custom']}")
        return False
    
    if data["has_default"] != True:
        print(f"❌ FAIL: has_default should be true, got: {data['has_default']}")
        return False
    
    print(f"✅ PASS: All required fields present and valid")
    print(f"   - key_masked: {data['key_masked']}")
    print(f"   - has_key: {data['has_key']}")
    print(f"   - source: {data['source']}")
    print(f"   - is_custom: {data['is_custom']}")
    print(f"   - has_default: {data['has_default']}")
    return True


def test_set_universal_key(token):
    """TEST 2: PUT /api/admin/providers/universal-key with valid key"""
    print("\n" + "="*80)
    print("TEST 2: PUT /api/admin/providers/universal-key (set custom key)")
    print("="*80)
    
    test_key = "sk-emergent-TESTKEY123456"
    resp = requests.put(f"{BASE_URL}/admin/providers/universal-key", 
                        headers={"Authorization": f"Bearer {token}"},
                        json={"api_key": test_key},
                        timeout=30)
    
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    # Verify source is now 'custom'
    if data.get("source") != "custom":
        print(f"❌ FAIL: source should be 'custom', got: {data.get('source')}")
        return False
    
    if data.get("is_custom") != True:
        print(f"❌ FAIL: is_custom should be true, got: {data.get('is_custom')}")
        return False
    
    # Verify key_masked reflects the new key but is NOT the full plaintext
    key_masked = data.get("key_masked", "")
    if not key_masked:
        print(f"❌ FAIL: key_masked is empty")
        return False
    
    if key_masked == test_key:
        print(f"❌ FAIL: key_masked should NOT be the full plaintext key")
        print(f"   Got: {key_masked}")
        return False
    
    # Should contain some part of the key (prefix or suffix) and some masking
    if "*" not in key_masked:
        print(f"❌ FAIL: key_masked should contain masking characters (*)")
        print(f"   Got: {key_masked}")
        return False
    
    print(f"✅ PASS: Custom key set successfully")
    print(f"   - source: {data['source']}")
    print(f"   - is_custom: {data['is_custom']}")
    print(f"   - key_masked: {key_masked} (correctly masked)")
    return True


def test_set_masked_key_rejected(token):
    """TEST 3: PUT with masked value (contains '*') should return 400"""
    print("\n" + "="*80)
    print("TEST 3: PUT /api/admin/providers/universal-key (masked value rejected)")
    print("="*80)
    
    masked_key = "sk-emergent-****1234"
    resp = requests.put(f"{BASE_URL}/admin/providers/universal-key",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"api_key": masked_key},
                        timeout=30)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    if resp.status_code != 400:
        print(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    
    print(f"✅ PASS: Masked value correctly rejected with 400")
    return True


def test_set_empty_key_rejected(token):
    """TEST 4: PUT with empty string should return 400 or 422"""
    print("\n" + "="*80)
    print("TEST 4: PUT /api/admin/providers/universal-key (empty key rejected)")
    print("="*80)
    
    resp = requests.put(f"{BASE_URL}/admin/providers/universal-key",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"api_key": ""},
                        timeout=30)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    if resp.status_code not in [400, 422]:
        print(f"❌ FAIL: Expected 400 or 422, got {resp.status_code}")
        return False
    
    print(f"✅ PASS: Empty key correctly rejected with {resp.status_code}")
    return True


def test_reset_universal_key(token):
    """TEST 5: POST /api/admin/providers/universal-key/reset"""
    print("\n" + "="*80)
    print("TEST 5: POST /api/admin/providers/universal-key/reset")
    print("="*80)
    
    resp = requests.post(f"{BASE_URL}/admin/providers/universal-key/reset",
                         headers={"Authorization": f"Bearer {token}"},
                         timeout=30)
    
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    # Verify source is back to 'default'
    if data.get("source") != "default":
        print(f"❌ FAIL: source should be 'default' after reset, got: {data.get('source')}")
        return False
    
    if data.get("is_custom") != False:
        print(f"❌ FAIL: is_custom should be false after reset, got: {data.get('is_custom')}")
        return False
    
    print(f"✅ PASS: Key reset to default successfully")
    print(f"   - source: {data['source']}")
    print(f"   - is_custom: {data['is_custom']}")
    return True


def test_auth_guard(token):
    """TEST 6: All endpoints should return 401 without Authorization header"""
    print("\n" + "="*80)
    print("TEST 6: AUTH GUARD - No token should return 401")
    print("="*80)
    
    endpoints = [
        ("GET", f"{BASE_URL}/admin/providers/universal-key"),
        ("PUT", f"{BASE_URL}/admin/providers/universal-key"),
        ("POST", f"{BASE_URL}/admin/providers/universal-key/reset"),
    ]
    
    all_passed = True
    for method, url in endpoints:
        print(f"\nTesting {method} {url.replace(BASE_URL, '')} without token...")
        
        if method == "GET":
            resp = requests.get(url, timeout=30)
        elif method == "PUT":
            resp = requests.put(url, json={"api_key": "test"}, timeout=30)
        elif method == "POST":
            resp = requests.post(url, timeout=30)
        
        print(f"Status: {resp.status_code}")
        
        if resp.status_code != 401:
            print(f"❌ FAIL: Expected 401, got {resp.status_code}")
            all_passed = False
        else:
            print(f"✅ PASS: Correctly returned 401")
    
    return all_passed


def test_chat_regression(token, org_id):
    """TEST 7: CRITICAL REGRESSION - Chat should still work with Emergent key"""
    print("\n" + "="*80)
    print("TEST 7: CRITICAL REGRESSION - Chat still works")
    print("="*80)
    
    # Create a chat session
    print("Creating chat session...")
    session_resp = requests.post(f"{BASE_URL}/orgs/{org_id}/chat/sessions",
                                 headers={"Authorization": f"Bearer {token}"},
                                 json={},
                                 timeout=30)
    
    if session_resp.status_code != 200:
        print(f"❌ FAIL: Failed to create session: {session_resp.status_code}")
        print(f"Response: {session_resp.text}")
        return False
    
    session_data = session_resp.json()
    sid = session_data.get("id")
    if not sid:
        print(f"❌ FAIL: No session id in response: {session_data}")
        return False
    
    print(f"✅ Session created: {sid}")
    
    # Send a message
    print("Sending message to chat agent...")
    message = "Say hi in one short sentence"
    agent_resp = requests.post(f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/agent",
                               headers={"Authorization": f"Bearer {token}"},
                               json={"message": message},
                               timeout=60)
    
    print(f"Status: {agent_resp.status_code}")
    
    if agent_resp.status_code != 200:
        print(f"❌ FAIL: Chat agent failed: {agent_resp.status_code}")
        print(f"Response: {agent_resp.text}")
        return False
    
    agent_data = agent_resp.json()
    reply = agent_data.get("content", "")
    
    if not reply:
        print(f"❌ FAIL: Empty reply from chat agent")
        print(f"Response: {json.dumps(agent_data, indent=2)}")
        return False
    
    print(f"✅ PASS: Chat working correctly")
    print(f"   Message: {message}")
    print(f"   Reply: {reply}")
    return True


def test_old_endpoints_removed():
    """Verify old multi-provider endpoints are GONE (should return 404)"""
    print("\n" + "="*80)
    print("BONUS TEST: Verify old multi-provider endpoints are removed")
    print("="*80)
    
    # These endpoints should NOT exist anymore
    old_endpoints = [
        f"{BASE_URL}/admin/providers",  # list providers
        f"{BASE_URL}/admin/providers/catalog",
        f"{BASE_URL}/admin/providers/usage",
        f"{BASE_URL}/admin/providers/logs",
        f"{BASE_URL}/admin/providers/emergent",
    ]
    
    all_removed = True
    for url in old_endpoints:
        print(f"\nChecking {url.replace(BASE_URL, '')}...")
        try:
            resp = requests.get(url, timeout=10)
            print(f"Status: {resp.status_code}")
            
            # We expect 401 (no auth) or 404 (not found)
            # If we get 200, that means the endpoint still exists
            if resp.status_code == 200:
                print(f"⚠️  WARNING: Old endpoint still exists and returns 200")
                all_removed = False
            else:
                print(f"✅ Endpoint removed or requires auth (status {resp.status_code})")
        except Exception as e:
            print(f"✅ Endpoint not accessible: {e}")
    
    return all_removed


# ============================================================================
# MAIN TEST EXECUTION
# ============================================================================

def main():
    print("="*80)
    print("🧪 EMERGENT UNIVERSAL KEY ADMIN FEATURE - COMPREHENSIVE TEST")
    print("="*80)
    print()
    
    # Login
    token, org_id = login()
    
    # Run all tests
    results = {}
    
    results["TEST 1: GET universal-key"] = test_get_universal_key(token)
    results["TEST 2: PUT universal-key (set custom)"] = test_set_universal_key(token)
    results["TEST 3: PUT universal-key (masked rejected)"] = test_set_masked_key_rejected(token)
    results["TEST 4: PUT universal-key (empty rejected)"] = test_set_empty_key_rejected(token)
    results["TEST 5: POST reset"] = test_reset_universal_key(token)
    results["TEST 6: Auth guard"] = test_auth_guard(token)
    results["TEST 7: Chat regression"] = test_chat_regression(token, org_id)
    
    # Bonus test
    print("\n")
    test_old_endpoints_removed()
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
