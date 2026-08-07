#!/usr/bin/env python3
"""
Voice Chat Endpoint Test Suite for VibeVerse
Tests the NEW live voice-chat backend endpoint: POST /api/orgs/{org_id}/chat/sessions/{sid}/voice-chat

Test scenarios:
1. Create a chat session
2. Get current credits before the call
3. POST voice-chat endpoint - verify response structure (reply, audio base64, mime, credits)
4. Verify credits decreased by 1
5. Verify persistence - both user and assistant messages saved
6. Test identity - reply must mention VibeVerse, no forbidden keywords
7. Error cases - non-existent session (404), empty message (400)
"""
import requests
import base64
import sys
import time

# Backend URL from frontend/.env
BASE_URL = "https://vibe-preview-6.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

# Identity keywords that must NOT appear in AI responses (case-insensitive)
FORBIDDEN_KEYWORDS = ["openai", "chatgpt", "gpt", "anthropic", "claude", "google", "gemini", "llama"]

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
    return True

def main():
    log("=" * 80)
    log("VibeVerse Voice Chat Endpoint Test Suite")
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
    
    # ========== TEST 1: Create a chat session ==========
    log("\n" + "=" * 80)
    log("TEST 1: Create a chat session")
    log("=" * 80)
    try:
        session_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions",
            headers=headers,
            json={},
            timeout=30
        )
        if session_resp.status_code != 200:
            error(f"TEST 1 FAILED: Create session failed: {session_resp.status_code} - {session_resp.text}")
            return False
        
        sid = session_resp.json().get("id")
        if not sid:
            error("TEST 1 FAILED: No session id in response")
            return False
        
        success(f"TEST 1 PASSED: Chat session created: {sid}")
    except Exception as e:
        error(f"TEST 1 FAILED: {e}")
        return False
    
    # ========== TEST 2: Get current credits before the call ==========
    log("\n" + "=" * 80)
    log("TEST 2: Get current credits before the call")
    log("=" * 80)
    try:
        usage_resp = requests.get(f"{BASE_URL}/orgs/{org_id}/usage", headers=headers, timeout=30)
        if usage_resp.status_code != 200:
            error(f"TEST 2 FAILED: GET /usage failed: {usage_resp.status_code} - {usage_resp.text}")
            return False
        
        credits_before = usage_resp.json().get("credits")
        if credits_before is None:
            error("TEST 2 FAILED: No credits field in response")
            return False
        
        success(f"TEST 2 PASSED: Current credits: {credits_before}")
    except Exception as e:
        error(f"TEST 2 FAILED: {e}")
        return False
    
    # ========== TEST 3: POST voice-chat endpoint - verify response structure ==========
    log("\n" + "=" * 80)
    log("TEST 3: POST voice-chat endpoint - verify response structure")
    log("=" * 80)
    
    test_message = "Hello, what can you help me with today?"
    test_voice = "nova"
    
    log(f"Sending message: '{test_message}' with voice: '{test_voice}'")
    
    try:
        voice_chat_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/voice-chat",
            headers=headers,
            json={"message": test_message, "voice": test_voice},
            timeout=90
        )
        
        if voice_chat_resp.status_code != 200:
            error(f"TEST 3 FAILED: Expected 200, got {voice_chat_resp.status_code} - {voice_chat_resp.text}")
            return False
        
        voice_data = voice_chat_resp.json()
        log(f"Response keys: {list(voice_data.keys())}")
        
        # Verify required fields
        required_fields = ["reply", "audio", "mime", "credits"]
        missing_fields = [f for f in required_fields if f not in voice_data]
        if missing_fields:
            error(f"TEST 3 FAILED: Missing required fields: {missing_fields}")
            return False
        
        # Verify reply is non-empty string
        reply = voice_data.get("reply")
        if not reply or not isinstance(reply, str):
            error(f"TEST 3 FAILED: 'reply' is empty or not a string: {reply}")
            return False
        
        log(f"Reply text ({len(reply)} chars): {reply}")
        
        # Verify audio is non-empty base64 string
        audio_b64 = voice_data.get("audio")
        if not audio_b64 or not isinstance(audio_b64, str):
            error(f"TEST 3 FAILED: 'audio' is empty or not a string")
            return False
        
        log(f"Audio base64 length: {len(audio_b64)} chars")
        
        # Verify base64 decodes to non-empty bytes
        try:
            audio_bytes = base64.b64decode(audio_b64)
            if not audio_bytes:
                error(f"TEST 3 FAILED: Decoded audio is empty")
                return False
            
            log(f"Decoded audio size: {len(audio_bytes)} bytes")
            
            # Check if it starts with ID3 or MP3 frame markers
            if audio_bytes[:3] == b'ID3':
                log("Audio starts with ID3 tag (valid MP3)")
            elif audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0:
                log("Audio starts with MP3 frame sync (valid MP3)")
            else:
                log(f"Warning: Audio doesn't start with typical MP3 markers. First 10 bytes: {audio_bytes[:10].hex()}")
        except Exception as e:
            error(f"TEST 3 FAILED: Failed to decode base64 audio: {e}")
            return False
        
        # Verify mime is "audio/mpeg"
        mime = voice_data.get("mime")
        if mime != "audio/mpeg":
            error(f"TEST 3 FAILED: Expected mime='audio/mpeg', got '{mime}'")
            return False
        
        # Verify credits is an integer
        credits_after = voice_data.get("credits")
        if not isinstance(credits_after, int):
            error(f"TEST 3 FAILED: 'credits' is not an integer: {credits_after}")
            return False
        
        log(f"Credits after: {credits_after}")
        
        success(f"TEST 3 PASSED: All required fields present and valid")
        success(f"  - reply: '{reply}'")
        success(f"  - audio: {len(audio_bytes)} bytes of valid audio data")
        success(f"  - mime: {mime}")
        success(f"  - credits: {credits_after}")
        
    except Exception as e:
        error(f"TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ========== TEST 4: Verify credits decreased by 1 ==========
    log("\n" + "=" * 80)
    log("TEST 4: Verify credits decreased by 1")
    log("=" * 80)
    
    expected_credits = credits_before - 1
    if credits_after != expected_credits:
        error(f"TEST 4 FAILED: Expected credits={expected_credits}, got {credits_after}")
        error(f"  Credits before: {credits_before}")
        error(f"  Credits after: {credits_after}")
        error(f"  Difference: {credits_before - credits_after}")
        return False
    
    success(f"TEST 4 PASSED: Credits decreased by exactly 1 (from {credits_before} to {credits_after})")
    
    # ========== TEST 5: Verify persistence - both user and assistant messages saved ==========
    log("\n" + "=" * 80)
    log("TEST 5: Verify persistence - both user and assistant messages saved")
    log("=" * 80)
    
    try:
        messages_resp = requests.get(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/messages",
            headers=headers,
            timeout=30
        )
        if messages_resp.status_code != 200:
            error(f"TEST 5 FAILED: GET /messages failed: {messages_resp.status_code} - {messages_resp.text}")
            return False
        
        messages = messages_resp.json()
        log(f"Total messages in session: {len(messages)}")
        
        # Should have at least 2 messages (user + assistant)
        if len(messages) < 2:
            error(f"TEST 5 FAILED: Expected at least 2 messages, got {len(messages)}")
            return False
        
        # Find the user message with our test message
        user_msg = None
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content") == test_message:
                user_msg = msg
                break
        
        if not user_msg:
            error(f"TEST 5 FAILED: User message '{test_message}' not found in chat history")
            log(f"Messages: {messages}")
            return False
        
        # Verify user message has kind='text'
        if user_msg.get("kind") != "text":
            error(f"TEST 5 FAILED: User message kind is '{user_msg.get('kind')}', expected 'text'")
            return False
        
        success(f"User message found: role={user_msg.get('role')}, kind={user_msg.get('kind')}, content='{user_msg.get('content')}'")
        
        # Find the assistant message with the reply
        assistant_msg = None
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("content") == reply:
                assistant_msg = msg
                break
        
        if not assistant_msg:
            error(f"TEST 5 FAILED: Assistant message with reply '{reply}' not found in chat history")
            log(f"Messages: {messages}")
            return False
        
        # Verify assistant message has kind='text'
        if assistant_msg.get("kind") != "text":
            error(f"TEST 5 FAILED: Assistant message kind is '{assistant_msg.get('kind')}', expected 'text'")
            return False
        
        success(f"Assistant message found: role={assistant_msg.get('role')}, kind={assistant_msg.get('kind')}, content='{assistant_msg.get('content')}'")
        success(f"TEST 5 PASSED: Both user and assistant messages persisted with kind='text'")
        
    except Exception as e:
        error(f"TEST 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ========== TEST 6: Test identity - reply must mention VibeVerse, no forbidden keywords ==========
    log("\n" + "=" * 80)
    log("TEST 6: Test identity - reply must mention VibeVerse, no forbidden keywords")
    log("=" * 80)
    
    identity_message = "Who created you? Which AI model are you?"
    identity_voice = "onyx"
    
    log(f"Sending identity question: '{identity_message}' with voice: '{identity_voice}'")
    
    try:
        identity_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/voice-chat",
            headers=headers,
            json={"message": identity_message, "voice": identity_voice},
            timeout=90
        )
        
        if identity_resp.status_code != 200:
            error(f"TEST 6 FAILED: Expected 200, got {identity_resp.status_code} - {identity_resp.text}")
            return False
        
        identity_data = identity_resp.json()
        identity_reply = identity_data.get("reply", "")
        
        if not identity_reply:
            error(f"TEST 6 FAILED: Empty reply")
            return False
        
        log(f"Identity reply ({len(identity_reply)} chars): {identity_reply}")
        
        # Check identity
        if not check_identity_response(identity_reply, "TEST 6"):
            return False
        
        success(f"TEST 6 PASSED: Identity check passed - mentions VibeVerse, no forbidden keywords")
        success(f"  Reply: '{identity_reply}'")
        
    except Exception as e:
        error(f"TEST 6 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ========== TEST 7a: Error case - non-existent session (404) ==========
    log("\n" + "=" * 80)
    log("TEST 7a: Error case - non-existent session (404)")
    log("=" * 80)
    
    fake_sid = "507f1f77bcf86cd799439011"  # Valid ObjectId format but doesn't exist
    
    try:
        error_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions/{fake_sid}/voice-chat",
            headers=headers,
            json={"message": "test", "voice": "nova"},
            timeout=30
        )
        
        if error_resp.status_code != 404:
            error(f"TEST 7a FAILED: Expected 404, got {error_resp.status_code}")
            error(f"Response: {error_resp.text}")
            return False
        
        success(f"TEST 7a PASSED: Non-existent session returns 404")
        
    except Exception as e:
        error(f"TEST 7a FAILED: {e}")
        return False
    
    # ========== TEST 7b: Error case - empty message (400) ==========
    log("\n" + "=" * 80)
    log("TEST 7b: Error case - empty/whitespace message (400)")
    log("=" * 80)
    
    try:
        error_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/voice-chat",
            headers=headers,
            json={"message": "   ", "voice": "nova"},
            timeout=30
        )
        
        if error_resp.status_code != 400:
            error(f"TEST 7b FAILED: Expected 400, got {error_resp.status_code}")
            error(f"Response: {error_resp.text}")
            return False
        
        success(f"TEST 7b PASSED: Empty/whitespace message returns 400")
        
    except Exception as e:
        error(f"TEST 7b FAILED: {e}")
        return False
    
    # ========== ALL TESTS PASSED ==========
    log("\n" + "=" * 80)
    success("🎉 ALL 7 TESTS PASSED!")
    log("=" * 80)
    log("✅ TEST 1: Chat session created successfully")
    log("✅ TEST 2: Retrieved current credits before call")
    log("✅ TEST 3: Voice-chat endpoint returns correct structure (reply, audio base64, mime, credits)")
    log("✅ TEST 4: Credits decreased by exactly 1")
    log("✅ TEST 5: Both user and assistant messages persisted with kind='text'")
    log("✅ TEST 6: Identity check passed - mentions VibeVerse, no forbidden keywords")
    log("✅ TEST 7a: Non-existent session returns 404")
    log("✅ TEST 7b: Empty/whitespace message returns 400")
    log("=" * 80)
    
    # Print the actual reply texts for review
    log("\n" + "=" * 80)
    log("ACTUAL REPLY TEXTS FOR REVIEW:")
    log("=" * 80)
    log(f"Test 3 reply: {reply}")
    log(f"Test 6 reply (identity): {identity_reply}")
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
