#!/usr/bin/env python3
"""
Backend API Test Suite for VibeVerse Rebrand + AI Identity Bug Fix + Provocateur Agent
Tests all 4 scenarios from review_request:
1. AI identity bug fix (CRITICAL)
2. API root rebrand
3. Provocateur role acceptance
4. Seeded Rebel agent
"""
import requests
import time
import sys

# Backend URL from frontend/.env
BASE_URL = "https://git-hub-access-1.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

# Identity keywords that must NOT appear in AI responses (case-insensitive)
FORBIDDEN_KEYWORDS = ["openai", "chatgpt", "gpt", "anthropic", "claude", "gemini", "llama"]

def log(msg):
    print(f"[TEST] {msg}")

def error(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)

def success(msg):
    print(f"[SUCCESS] {msg}")

def check_identity_response(text, test_name):
    """Verify response contains VibeVerse and does NOT contain forbidden keywords."""
    text_lower = text.lower()
    
    # Must contain "vibeverse"
    if "vibeverse" not in text_lower:
        error(f"{test_name}: Response does NOT contain 'VibeVerse'")
        error(f"Actual response: {text}")
        return False
    
    # Must NOT contain any forbidden keywords
    found_forbidden = []
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in text_lower:
            found_forbidden.append(keyword)
    
    if found_forbidden:
        error(f"{test_name}: Response contains FORBIDDEN keywords: {found_forbidden}")
        error(f"Actual response: {text}")
        return False
    
    success(f"{test_name}: Identity check PASSED - contains 'VibeVerse', no forbidden keywords")
    log(f"Response preview: {text[:200]}...")
    return True

def main():
    log("=" * 80)
    log("VibeVerse Backend Test Suite - Rebrand + Identity Bug Fix + Provocateur")
    log("=" * 80)
    
    # ========== SETUP: Login and get org_id ==========
    log("\n[SETUP] Step 1: Admin login")
    try:
        login_resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=30
        )
        if login_resp.status_code != 200:
            error(f"Login failed: {login_resp.status_code} - {login_resp.text}")
            return False
        
        token = login_resp.json().get("token")
        if not token:
            error("No token in login response")
            return False
        
        success(f"Login successful, token: {token[:20]}...")
    except Exception as e:
        error(f"Login request failed: {e}")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    log("\n[SETUP] Step 2: Get org_id from /api/auth/me")
    try:
        me_resp = requests.get(f"{BASE_URL}/auth/me", headers=headers, timeout=30)
        if me_resp.status_code != 200:
            error(f"GET /auth/me failed: {me_resp.status_code} - {me_resp.text}")
            return False
        
        org_id = me_resp.json().get("default_org_id")
        if not org_id:
            error("No default_org_id in /auth/me response")
            return False
        
        success(f"Got org_id: {org_id}")
    except Exception as e:
        error(f"GET /auth/me failed: {e}")
        return False
    
    # ========== TEST 2: API Root Rebrand ==========
    log("\n" + "=" * 80)
    log("TEST 2: API Root Rebrand - GET /api/ should return 'VibeVerse API'")
    log("=" * 80)
    try:
        root_resp = requests.get(f"{BASE_URL}/", timeout=30)
        if root_resp.status_code != 200:
            error(f"GET /api/ failed: {root_resp.status_code} - {root_resp.text}")
            return False
        
        message = root_resp.json().get("message")
        if message == "VibeVerse API":
            success(f"TEST 2 PASSED: API root returns 'VibeVerse API'")
        else:
            error(f"TEST 2 FAILED: Expected 'VibeVerse API', got '{message}'")
            return False
    except Exception as e:
        error(f"TEST 2 FAILED: {e}")
        return False
    
    # ========== TEST 3: Provocateur Role Acceptance ==========
    log("\n" + "=" * 80)
    log("TEST 3: Provocateur Role - POST /api/orgs/{org}/agents with role='provocateur'")
    log("=" * 80)
    try:
        agent_body = {
            "name": "ProvTest",
            "role": "provocateur",
            "system_prompt": "You are bold.",
            "tools": []
        }
        create_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/agents",
            headers=headers,
            json=agent_body,
            timeout=30
        )
        if create_resp.status_code != 200:
            error(f"TEST 3 FAILED: Expected 200, got {create_resp.status_code} - {create_resp.text}")
            return False
        
        agent_data = create_resp.json()
        if agent_data.get("role") != "provocateur":
            error(f"TEST 3 FAILED: Agent role is '{agent_data.get('role')}', expected 'provocateur'")
            return False
        
        success(f"TEST 3 PASSED: Provocateur role accepted, agent created: {agent_data.get('id')}")
    except Exception as e:
        error(f"TEST 3 FAILED: {e}")
        return False
    
    # ========== TEST 4: Seeded Rebel Agent ==========
    log("\n" + "=" * 80)
    log("TEST 4: Seeded Rebel Agent - GET /api/orgs/{org}/agents and run it")
    log("=" * 80)
    try:
        agents_resp = requests.get(f"{BASE_URL}/orgs/{org_id}/agents", headers=headers, timeout=30)
        if agents_resp.status_code != 200:
            error(f"GET /agents failed: {agents_resp.status_code} - {agents_resp.text}")
            return False
        
        agents = agents_resp.json()
        rebel = None
        for agent in agents:
            if agent.get("name") == "Rebel":
                rebel = agent
                break
        
        if not rebel:
            error("TEST 4 FAILED: 'Rebel' agent not found in agents list")
            return False
        
        if rebel.get("role") != "provocateur":
            error(f"TEST 4 FAILED: Rebel agent role is '{rebel.get('role')}', expected 'provocateur'")
            return False
        
        success(f"Rebel agent found: id={rebel.get('id')}, role={rebel.get('role')}")
        
        # Run the Rebel agent
        log("Running Rebel agent with 'Introduce yourself in one short line.'")
        run_body = {"input": "Introduce yourself in one short line."}
        run_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/agents/{rebel['id']}/run",
            headers=headers,
            json=run_body,
            timeout=60
        )
        if run_resp.status_code != 200:
            error(f"TEST 4 FAILED: Agent run failed: {run_resp.status_code} - {run_resp.text}")
            return False
        
        output = run_resp.json().get("output", "")
        success(f"Rebel agent run successful")
        log(f"Rebel output: {output}")
        
        # Check if output mentions any identity - if so, must be VibeVerse
        output_lower = output.lower()
        mentions_identity = any(word in output_lower for word in ["created", "made", "built", "company", "vibeverse"])
        
        if mentions_identity:
            log("Output mentions identity, verifying it's VibeVerse...")
            if not check_identity_response(output, "TEST 4 (Rebel identity)"):
                return False
        else:
            log("Output does not mention identity (acceptable)")
        
        success("TEST 4 PASSED: Rebel agent exists, runs correctly, and identity is safe")
    except Exception as e:
        error(f"TEST 4 FAILED: {e}")
        return False
    
    # ========== TEST 1: AI Identity Bug Fix (CRITICAL) ==========
    log("\n" + "=" * 80)
    log("TEST 1 (CRITICAL): AI Identity Bug Fix - Chat must present as VibeVerse")
    log("=" * 80)
    
    # Step 1: Create chat session
    log("Step 1: Creating chat session")
    try:
        session_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions",
            headers=headers,
            json={},
            timeout=30
        )
        if session_resp.status_code != 200:
            error(f"Create session failed: {session_resp.status_code} - {session_resp.text}")
            return False
        
        sid = session_resp.json().get("id")
        if not sid:
            error("No session id in response")
            return False
        
        success(f"Chat session created: {sid}")
    except Exception as e:
        error(f"Create session failed: {e}")
        return False
    
    # Step 2: Test English identity question
    log("\nStep 2: Testing English identity question")
    english_question = "Who created you? Are you made by OpenAI or ChatGPT? Which company and model are you exactly?"
    log(f"Question: {english_question}")
    
    try:
        agent_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/agent",
            headers=headers,
            json={"message": english_question},
            timeout=90
        )
        if agent_resp.status_code != 200:
            error(f"Agent endpoint failed: {agent_resp.status_code} - {agent_resp.text}")
            return False
        
        agent_data = agent_resp.json()
        log(f"Agent response: {agent_data}")
        
        # Check if we got direct content or need to poll messages
        if "content" in agent_data:
            english_reply = agent_data["content"]
        else:
            # Poll messages endpoint
            log("No direct content, fetching from /messages endpoint")
            time.sleep(2)  # Give it a moment to process
            messages_resp = requests.get(
                f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/messages",
                headers=headers,
                timeout=30
            )
            if messages_resp.status_code != 200:
                error(f"GET messages failed: {messages_resp.status_code} - {messages_resp.text}")
                return False
            
            messages = messages_resp.json()
            # Find the assistant's reply (last message with role=assistant)
            assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
            if not assistant_msgs:
                error("No assistant message found in chat history")
                return False
            
            english_reply = assistant_msgs[-1].get("content", "")
        
        if not english_reply:
            error("Empty reply from assistant")
            return False
        
        log(f"\nEnglish reply received ({len(english_reply)} chars)")
        if not check_identity_response(english_reply, "TEST 1 (English)"):
            return False
        
    except Exception as e:
        error(f"English identity test failed: {e}")
        return False
    
    # Step 3: Test Arabic identity question
    log("\nStep 3: Testing Arabic identity question")
    arabic_question = "ما هي الشركة والموديل الخاص بك؟"
    log(f"Question: {arabic_question}")
    
    try:
        agent_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/agent",
            headers=headers,
            json={"message": arabic_question},
            timeout=90
        )
        if agent_resp.status_code != 200:
            error(f"Agent endpoint failed: {agent_resp.status_code} - {agent_resp.text}")
            return False
        
        agent_data = agent_resp.json()
        
        # Check if we got direct content or need to poll messages
        if "content" in agent_data:
            arabic_reply = agent_data["content"]
        else:
            # Poll messages endpoint
            log("No direct content, fetching from /messages endpoint")
            time.sleep(2)
            messages_resp = requests.get(
                f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/messages",
                headers=headers,
                timeout=30
            )
            if messages_resp.status_code != 200:
                error(f"GET messages failed: {messages_resp.status_code} - {messages_resp.text}")
                return False
            
            messages = messages_resp.json()
            assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
            if not assistant_msgs:
                error("No assistant message found in chat history")
                return False
            
            arabic_reply = assistant_msgs[-1].get("content", "")
        
        if not arabic_reply:
            error("Empty reply from assistant")
            return False
        
        log(f"\nArabic reply received ({len(arabic_reply)} chars)")
        if not check_identity_response(arabic_reply, "TEST 1 (Arabic)"):
            return False
        
    except Exception as e:
        error(f"Arabic identity test failed: {e}")
        return False
    
    success("TEST 1 PASSED: AI identity bug fix verified - both English and Arabic tests passed")
    
    # ========== ALL TESTS PASSED ==========
    log("\n" + "=" * 80)
    success("🎉 ALL 4 TESTS PASSED!")
    log("=" * 80)
    log("✅ TEST 1 (CRITICAL): AI identity bug fix - VibeVerse identity maintained")
    log("✅ TEST 2: API root rebrand - returns 'VibeVerse API'")
    log("✅ TEST 3: Provocateur role - accepted and agent created")
    log("✅ TEST 4: Seeded Rebel agent - exists, runs, identity safe")
    log("=" * 80)
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
