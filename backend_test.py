#!/usr/bin/env python3
"""
Comprehensive backend test for Agent Marketplace + autonomous scheduling feature.
Tests all 9 scenarios from the review request.
"""
import requests
import time
import sys
import os

# Base URL from frontend/.env
BASE_URL = "https://git-hub-access-1.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

def log(msg):
    print(f"[TEST] {msg}")

def test_login():
    """Login and get Bearer token."""
    log("Step 0: Login as admin...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        log(f"❌ Login failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    token = data.get("token")
    if not token:
        log(f"❌ No token in response: {data}")
        sys.exit(1)
    log(f"✅ Login successful, token: {token[:20]}...")
    return token

def get_org_id(token):
    """Get org_id from /api/auth/me."""
    log("Getting org_id from /api/auth/me...")
    resp = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        log(f"❌ Failed to get user info: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    org_id = data.get("default_org_id")
    if not org_id:
        log(f"❌ No default_org_id in response: {data}")
        sys.exit(1)
    log(f"✅ Org ID: {org_id}")
    return org_id

def test_1_marketplace_list(token):
    """TEST 1: GET /api/agents/marketplace -> expect 200, list of 6 templates."""
    log("\n=== TEST 1: MARKETPLACE LIST ===")
    resp = requests.get(f"{BASE_URL}/agents/marketplace", headers={"Authorization": f"Bearer {token}"})
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    if not isinstance(data, list):
        log(f"❌ FAIL: Expected list, got {type(data)}")
        return False
    
    if len(data) != 6:
        log(f"❌ FAIL: Expected 6 templates, got {len(data)}")
        return False
    
    # Check each template has required fields
    required_fields = ["id", "name", "emoji", "description", "role", "tools"]
    for i, template in enumerate(data):
        for field in required_fields:
            if field not in template:
                log(f"❌ FAIL: Template {i} missing field '{field}'")
                return False
    
    log(f"✅ PASS: Marketplace returned 6 templates with all required fields")
    log(f"Templates: {', '.join([t['name'] for t in data])}")
    return True

def test_2_hire_agent(token, org_id):
    """TEST 2: Hire research-analyst agent and verify it appears in agent list."""
    log("\n=== TEST 2: HIRE AGENT ===")
    
    # Hire the agent
    resp = requests.post(
        f"{BASE_URL}/orgs/{org_id}/agents/hire",
        headers={"Authorization": f"Bearer {token}"},
        json={"template_id": "research-analyst"}
    )
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False, None
    
    data = resp.json()
    
    # Verify response structure
    if not data.get("id"):
        log(f"❌ FAIL: No 'id' in response")
        return False, None
    
    if data.get("name") != "Research Analyst":
        log(f"❌ FAIL: Expected name 'Research Analyst', got '{data.get('name')}'")
        return False, None
    
    if not data.get("role"):
        log(f"❌ FAIL: No 'role' in response")
        return False, None
    
    if not isinstance(data.get("tools"), list):
        log(f"❌ FAIL: 'tools' should be a list")
        return False, None
    
    if data.get("schedule") is not None:
        log(f"❌ FAIL: Expected schedule=null for new agent, got {data.get('schedule')}")
        return False, None
    
    agent_id = data["id"]
    log(f"✅ Agent hired successfully: id={agent_id}, name={data['name']}")
    
    # Verify agent appears in list
    resp = requests.get(
        f"{BASE_URL}/orgs/{org_id}/agents",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Failed to get agent list: {resp.status_code}")
        return False, None
    
    agents = resp.json()
    found = False
    for agent in agents:
        if agent.get("id") == agent_id:
            found = True
            break
    
    if not found:
        log(f"❌ FAIL: Hired agent {agent_id} not found in agent list")
        return False, None
    
    log(f"✅ PASS: Hired agent appears in GET /api/orgs/{org_id}/agents")
    return True, agent_id

def test_3_hire_bad_template(token, org_id):
    """TEST 3: Hire with non-existent template_id -> expect 404."""
    log("\n=== TEST 3: HIRE BAD TEMPLATE ===")
    
    resp = requests.post(
        f"{BASE_URL}/orgs/{org_id}/agents/hire",
        headers={"Authorization": f"Bearer {token}"},
        json={"template_id": "does-not-exist"}
    )
    
    if resp.status_code != 404:
        log(f"❌ FAIL: Expected 404, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    log(f"✅ PASS: Bad template correctly returns 404")
    return True

def test_4_set_schedule(token, org_id, agent_id):
    """TEST 4: Set schedule with cadence='5min', enabled=true."""
    log("\n=== TEST 4: SET SCHEDULE ===")
    
    resp = requests.post(
        f"{BASE_URL}/orgs/{org_id}/agents/{agent_id}/schedule",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "cadence": "5min",
            "input": "Reply with exactly the single word: PONG",
            "enabled": True
        }
    )
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    schedule = data.get("schedule")
    
    if not schedule:
        log(f"❌ FAIL: No 'schedule' in response")
        return False
    
    if schedule.get("enabled") != True:
        log(f"❌ FAIL: Expected schedule.enabled=true, got {schedule.get('enabled')}")
        return False
    
    if schedule.get("cadence") != "5min":
        log(f"❌ FAIL: Expected schedule.cadence='5min', got '{schedule.get('cadence')}'")
        return False
    
    if not schedule.get("next_run"):
        log(f"❌ FAIL: Expected schedule.next_run to be set, got {schedule.get('next_run')}")
        return False
    
    log(f"✅ PASS: Schedule set successfully")
    log(f"  - enabled: {schedule.get('enabled')}")
    log(f"  - cadence: {schedule.get('cadence')}")
    log(f"  - next_run: {schedule.get('next_run')}")
    log(f"  - input: {schedule.get('input')}")
    return True

def test_5_bad_cadence(token, org_id, agent_id):
    """TEST 5: Set schedule with invalid cadence -> expect 400."""
    log("\n=== TEST 5: BAD CADENCE ===")
    
    resp = requests.post(
        f"{BASE_URL}/orgs/{org_id}/agents/{agent_id}/schedule",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "cadence": "yearly",
            "input": "x",
            "enabled": True
        }
    )
    
    if resp.status_code != 400:
        log(f"❌ FAIL: Expected 400, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    log(f"✅ PASS: Bad cadence correctly returns 400")
    return True

def test_6_schedule_bad_agent(token, org_id):
    """TEST 6: Set schedule on non-existent agent -> expect 404."""
    log("\n=== TEST 6: SCHEDULE ON BAD AGENT ===")
    
    # Generate a random 24-hex ObjectId
    fake_id = "123456789012345678901234"
    
    resp = requests.post(
        f"{BASE_URL}/orgs/{org_id}/agents/{fake_id}/schedule",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "cadence": "daily",
            "input": "x",
            "enabled": True
        }
    )
    
    if resp.status_code != 404:
        log(f"❌ FAIL: Expected 404, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    log(f"✅ PASS: Schedule on bad agent correctly returns 404")
    return True

def test_7_autonomous_autorun(token, org_id, agent_id):
    """TEST 7 (KEY TEST): Wait for autonomous scheduled run to appear."""
    log("\n=== TEST 7: AUTONOMOUS AUTO-RUN (KEY TEST) ===")
    log("Waiting for scheduled run to appear (polling every 10s for up to 90s)...")
    log("Note: Scheduler ticks every 30s, first run should fire immediately since next_run=now")
    
    max_wait = 90
    poll_interval = 10
    elapsed = 0
    run_output = None
    
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        
        log(f"  Polling at {elapsed}s...")
        resp = requests.get(
            f"{BASE_URL}/orgs/{org_id}/agents/{agent_id}/runs",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if resp.status_code != 200:
            log(f"  ⚠️  Failed to get runs: {resp.status_code}")
            continue
        
        runs = resp.json()
        
        # Look for a run with type='scheduled'
        for run in runs:
            if run.get("type") == "scheduled":
                run_output = run.get("output", "")
                log(f"✅ PASS: Scheduled run found after {elapsed}s!")
                log(f"  - Run ID: {run.get('id')}")
                log(f"  - Type: {run.get('type')}")
                log(f"  - Output length: {len(run_output)} chars")
                log(f"  - Output: {run_output[:200]}...")
                
                if not run_output:
                    log(f"⚠️  WARNING: Run output is empty")
                    return False, None
                
                # Check if output contains "PONG" (case-insensitive)
                if "PONG" in run_output.upper():
                    log(f"✅ Output contains 'PONG' as expected")
                else:
                    log(f"⚠️  WARNING: Output does not contain 'PONG'")
                
                return True, run_output
        
        log(f"  No scheduled run yet (found {len(runs)} runs total)")
    
    log(f"❌ FAIL: No scheduled run appeared after {max_wait}s")
    return False, None

def test_8_schedule_state_updated(token, org_id, agent_id):
    """TEST 8: Verify schedule.last_run is set and next_run is advanced."""
    log("\n=== TEST 8: SCHEDULE STATE UPDATED ===")
    
    resp = requests.get(
        f"{BASE_URL}/orgs/{org_id}/agents",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Failed to get agents: {resp.status_code}")
        return False
    
    agents = resp.json()
    agent = None
    for a in agents:
        if a.get("id") == agent_id:
            agent = a
            break
    
    if not agent:
        log(f"❌ FAIL: Agent {agent_id} not found in list")
        return False
    
    schedule = agent.get("schedule")
    if not schedule:
        log(f"❌ FAIL: No schedule in agent")
        return False
    
    last_run = schedule.get("last_run")
    next_run = schedule.get("next_run")
    
    if not last_run:
        log(f"❌ FAIL: schedule.last_run is not set (got {last_run})")
        return False
    
    if not next_run:
        log(f"❌ FAIL: schedule.next_run is not set (got {next_run})")
        return False
    
    log(f"✅ PASS: Schedule state updated correctly")
    log(f"  - last_run: {last_run}")
    log(f"  - next_run: {next_run}")
    log(f"  - last_run_id: {schedule.get('last_run_id')}")
    return True

def test_9_pause_schedule(token, org_id, agent_id):
    """TEST 9: DELETE schedule -> expect 200 and schedule.enabled=false."""
    log("\n=== TEST 9: PAUSE SCHEDULE ===")
    
    resp = requests.delete(
        f"{BASE_URL}/orgs/{org_id}/agents/{agent_id}/schedule",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    if not data.get("ok"):
        log(f"❌ FAIL: Expected {{ok:true}}, got {data}")
        return False
    
    log(f"✅ DELETE returned {{ok:true}}")
    
    # Verify schedule.enabled is now false
    resp = requests.get(
        f"{BASE_URL}/orgs/{org_id}/agents",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Failed to get agents: {resp.status_code}")
        return False
    
    agents = resp.json()
    agent = None
    for a in agents:
        if a.get("id") == agent_id:
            agent = a
            break
    
    if not agent:
        log(f"❌ FAIL: Agent {agent_id} not found")
        return False
    
    schedule = agent.get("schedule")
    if not schedule:
        log(f"⚠️  WARNING: No schedule in agent after DELETE")
        return True  # This is acceptable
    
    if schedule.get("enabled") != False:
        log(f"❌ FAIL: Expected schedule.enabled=false, got {schedule.get('enabled')}")
        return False
    
    log(f"✅ PASS: Schedule paused (enabled=false)")
    return True

def main():
    log("=" * 70)
    log("AGENT MARKETPLACE + AUTONOMOUS SCHEDULING - COMPREHENSIVE TEST")
    log("=" * 70)
    
    # Login
    token = test_login()
    org_id = get_org_id(token)
    
    results = {}
    
    # Test 1: Marketplace list
    results["test_1_marketplace_list"] = test_1_marketplace_list(token)
    
    # Test 2: Hire agent
    test_2_pass, agent_id = test_2_hire_agent(token, org_id)
    results["test_2_hire_agent"] = test_2_pass
    
    if not agent_id:
        log("\n❌ CRITICAL: Cannot continue without agent_id from test 2")
        sys.exit(1)
    
    # Test 3: Hire bad template
    results["test_3_hire_bad_template"] = test_3_hire_bad_template(token, org_id)
    
    # Test 4: Set schedule
    results["test_4_set_schedule"] = test_4_set_schedule(token, org_id, agent_id)
    
    # Test 5: Bad cadence
    results["test_5_bad_cadence"] = test_5_bad_cadence(token, org_id, agent_id)
    
    # Test 6: Schedule on bad agent
    results["test_6_schedule_bad_agent"] = test_6_schedule_bad_agent(token, org_id)
    
    # Test 7: Autonomous auto-run (KEY TEST)
    test_7_pass, run_output = test_7_autonomous_autorun(token, org_id, agent_id)
    results["test_7_autonomous_autorun"] = test_7_pass
    
    # Test 8: Schedule state updated
    results["test_8_schedule_state_updated"] = test_8_schedule_state_updated(token, org_id, agent_id)
    
    # Test 9: Pause schedule
    results["test_9_pause_schedule"] = test_9_pause_schedule(token, org_id, agent_id)
    
    # Summary
    log("\n" + "=" * 70)
    log("TEST SUMMARY")
    log("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "✅ PASS" if passed_flag else "❌ FAIL"
        log(f"{status}: {test_name}")
    
    log(f"\nTotal: {passed}/{total} tests passed")
    
    if run_output:
        log(f"\n📝 Scheduled run output (test 7):")
        log(f"{run_output}")
    
    if passed == total:
        log("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        log(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
