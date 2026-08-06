#!/usr/bin/env python3
"""Backend API test for Agent Conversational (Episodic) Memory feature."""
import requests
import json
import sys

# Base URL from frontend/.env
BASE_URL = "https://1b35aedf-76ce-4c25-b9a8-124de34f8867.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

def log(msg, level="INFO"):
    """Print formatted log message."""
    print(f"[{level}] {msg}")

def test_episodic_memory():
    """Test the Agent Conversational (Episodic) Memory feature."""
    
    # Step 1: Login
    log("Step 1: Login with admin credentials")
    login_url = f"{API_BASE}/auth/login"
    login_data = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    
    try:
        resp = requests.post(login_url, json=login_data, timeout=30)
        log(f"Login response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL - Login failed with status {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        data = resp.json()
        token = data.get("token")
        if not token:
            log("❌ FAIL - No token in login response", "ERROR")
            return False
        
        log(f"✅ PASS - Login successful, token received")
        
    except Exception as e:
        log(f"❌ FAIL - Login request failed: {e}", "ERROR")
        return False
    
    # Headers for authenticated requests
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Get organization ID
    log("\nStep 2: Get organization ID from /api/auth/me")
    try:
        resp = requests.get(f"{API_BASE}/auth/me", headers=headers, timeout=30)
        log(f"GET /auth/me status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL - GET /auth/me failed with status {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        user_data = resp.json()
        org_id = user_data.get("default_org_id")
        
        if not org_id:
            log("❌ FAIL - No default_org_id in user data", "ERROR")
            log(f"User data: {json.dumps(user_data, indent=2)}", "ERROR")
            return False
        
        log(f"✅ PASS - Organization ID retrieved: {org_id}")
        
    except Exception as e:
        log(f"❌ FAIL - GET /auth/me request failed: {e}", "ERROR")
        return False
    
    # Step 3: Create an agent with memory tool
    log("\nStep 3: Create an agent with 'memory' tool")
    agent_data = {
        "name": "Memo",
        "role": "assistant",
        "system_prompt": "You are a helpful assistant. Use provided context/knowledge to answer.",
        "tools": ["memory"]
    }
    
    try:
        resp = requests.post(f"{API_BASE}/orgs/{org_id}/agents", 
                           json=agent_data, headers=headers, timeout=30)
        log(f"POST /orgs/{org_id}/agents status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL - Create agent failed with status {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        agent = resp.json()
        agent_id = agent.get("id")
        
        if not agent_id:
            log("❌ FAIL - No agent id in response", "ERROR")
            return False
        
        log(f"✅ PASS - Agent created with ID: {agent_id}")
        log(f"Agent details: name={agent.get('name')}, tools={agent.get('tools')}")
        
    except Exception as e:
        log(f"❌ FAIL - Create agent request failed: {e}", "ERROR")
        return False
    
    # Step 4: First run - store context
    log("\nStep 4: First run - store context (name=Ahmed, color=blue)")
    run1_data = {
        "input": "Please remember this: my name is Ahmed and my favorite color is blue.",
        "session_id": "s1"
    }
    
    try:
        resp = requests.post(f"{API_BASE}/orgs/{org_id}/agents/{agent_id}/run",
                           json=run1_data, headers=headers, timeout=60)
        log(f"POST /orgs/{org_id}/agents/{agent_id}/run (run 1) status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL - First run failed with status {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        run1_result = resp.json()
        output1 = run1_result.get("output", "")
        tools_used1 = run1_result.get("tools_used", [])
        
        log(f"✅ PASS - First run completed")
        log(f"Output: {output1[:200]}..." if len(output1) > 200 else f"Output: {output1}")
        log(f"Tools used: {tools_used1}")
        
    except Exception as e:
        log(f"❌ FAIL - First run request failed: {e}", "ERROR")
        return False
    
    # Step 5: Second run - recall context (CRITICAL TEST)
    log("\nStep 5: Second run - recall context (verify Ahmed and blue are remembered)")
    run2_data = {
        "input": "What is my name and what is my favorite color?",
        "session_id": "s2"
    }
    
    try:
        resp = requests.post(f"{API_BASE}/orgs/{org_id}/agents/{agent_id}/run",
                           json=run2_data, headers=headers, timeout=60)
        log(f"POST /orgs/{org_id}/agents/{agent_id}/run (run 2) status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL - Second run failed with status {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        run2_result = resp.json()
        output2 = run2_result.get("output", "")
        tools_used2 = run2_result.get("tools_used", [])
        
        log(f"✅ PASS - Second run completed")
        log(f"Output: {output2}")
        log(f"Tools used: {tools_used2}")
        
        # CRITICAL: Verify the agent remembered the context
        output_lower = output2.lower()
        has_ahmed = "ahmed" in output_lower
        has_blue = "blue" in output_lower
        has_memory_tool = "memory" in tools_used2
        
        log("\n=== CRITICAL VERIFICATION ===")
        log(f"Output mentions 'Ahmed': {has_ahmed}")
        log(f"Output mentions 'blue': {has_blue}")
        log(f"'memory' tool was used: {has_memory_tool}")
        
        if not has_ahmed:
            log("❌ FAIL - Agent output does NOT mention 'Ahmed' - episodic memory not working!", "ERROR")
            return False
        
        if not has_blue:
            log("❌ FAIL - Agent output does NOT mention 'blue' - episodic memory not working!", "ERROR")
            return False
        
        if not has_memory_tool:
            log("⚠️  WARNING - 'memory' tool not in tools_used, but context was recalled", "WARN")
        
        log("✅ PASS - Agent successfully recalled context from previous conversation!")
        
    except Exception as e:
        log(f"❌ FAIL - Second run request failed: {e}", "ERROR")
        return False
    
    # Step 6: Verify conversation memories exist
    log("\nStep 6: Verify conversation memories in database")
    try:
        resp = requests.get(f"{API_BASE}/orgs/{org_id}/memories", 
                          headers=headers, timeout=30)
        log(f"GET /orgs/{org_id}/memories status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL - GET memories failed with status {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        memories = resp.json()
        log(f"Total memories found: {len(memories)}")
        
        # Filter conversation memories
        conversation_memories = [m for m in memories if m.get("source") == "conversation"]
        log(f"Conversation memories: {len(conversation_memories)}")
        
        if len(conversation_memories) == 0:
            log("❌ FAIL - No conversation memories found with source='conversation'", "ERROR")
            return False
        
        log(f"✅ PASS - Found {len(conversation_memories)} conversation memory entries")
        
        # Log details of conversation memories
        for i, mem in enumerate(conversation_memories[:3], 1):
            log(f"  Memory {i}: source={mem.get('source')}, agent_id={mem.get('agent_id')}")
            log(f"    Text preview: {mem.get('text', '')[:100]}...")
        
    except Exception as e:
        log(f"❌ FAIL - GET memories request failed: {e}", "ERROR")
        return False
    
    # Step 7: Regression test - update agent knowledge should NOT delete conversation memories
    log("\nStep 7: Regression test - update agent knowledge")
    update_data = {
        "name": "Memo",
        "role": "assistant",
        "system_prompt": "You are a helpful assistant. Use provided context/knowledge to answer.",
        "tools": ["memory"],
        "knowledge": ["Ahmed works at ACME Corp."]
    }
    
    try:
        resp = requests.patch(f"{API_BASE}/orgs/{org_id}/agents/{agent_id}",
                            json=update_data, headers=headers, timeout=30)
        log(f"PATCH /orgs/{org_id}/agents/{agent_id} status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL - Update agent failed with status {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        log("✅ PASS - Agent updated with knowledge")
        
        # Verify conversation memories still exist
        resp = requests.get(f"{API_BASE}/orgs/{org_id}/memories", 
                          headers=headers, timeout=30)
        
        if resp.status_code != 200:
            log(f"❌ FAIL - GET memories after update failed", "ERROR")
            return False
        
        memories_after = resp.json()
        conversation_after = [m for m in memories_after if m.get("source") == "conversation"]
        knowledge_after = [m for m in memories_after if m.get("source") == "agent-knowledge"]
        
        log(f"After update - Total memories: {len(memories_after)}")
        log(f"After update - Conversation memories: {len(conversation_after)}")
        log(f"After update - Agent-knowledge memories: {len(knowledge_after)}")
        
        if len(conversation_after) == 0:
            log("❌ FAIL - Conversation memories were deleted when updating agent knowledge!", "ERROR")
            return False
        
        if len(knowledge_after) == 0:
            log("❌ FAIL - No agent-knowledge memories found after update", "ERROR")
            return False
        
        log("✅ PASS - Conversation memories preserved after knowledge update")
        log("✅ PASS - Agent-knowledge memories created successfully")
        
    except Exception as e:
        log(f"❌ FAIL - Regression test failed: {e}", "ERROR")
        return False
    
    log("\n" + "="*60)
    log("🎉 ALL TESTS PASSED - Agent Conversational (Episodic) Memory is working!", "SUCCESS")
    log("="*60)
    return True

if __name__ == "__main__":
    success = test_episodic_memory()
    sys.exit(0 if success else 1)
