#!/usr/bin/env python3
"""
Regression + Reliability Test for VibeVerse Voice-Chat
Tests TTS fallback (tts-1-hd -> tts-1) after recent gateway.generate_audio change
"""
import os
import sys
import requests
import base64
import time

# Load backend URL from frontend/.env
BACKEND_URL = None
try:
    with open("/app/frontend/.env", "r") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BACKEND_URL = line.split("=", 1)[1].strip()
                break
except Exception as e:
    print(f"❌ Failed to read frontend/.env: {e}")
    sys.exit(1)

if not BACKEND_URL:
    print("❌ REACT_APP_BACKEND_URL not found in frontend/.env")
    sys.exit(1)

BASE_URL = f"{BACKEND_URL}/api"
print(f"🔗 Backend URL: {BASE_URL}")

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

# Global state
TOKEN = None
ORG_ID = None

def login():
    """Login and get Bearer token + org_id"""
    global TOKEN, ORG_ID
    print("\n🔐 Logging in as admin...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    TOKEN = data.get("token")
    if not TOKEN:
        print(f"❌ No token in login response: {data}")
        sys.exit(1)
    print(f"✅ Login successful, token: {TOKEN[:20]}...")
    
    # Get org_id from /api/auth/me
    me_resp = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30)
    if me_resp.status_code != 200:
        print(f"❌ Failed to get user info: {me_resp.status_code} {me_resp.text}")
        sys.exit(1)
    me_data = me_resp.json()
    ORG_ID = me_data.get("default_org_id")
    if not ORG_ID:
        print(f"❌ No default_org_id in /auth/me response: {me_data}")
        sys.exit(1)
    print(f"✅ Org ID: {ORG_ID}")

def headers():
    """Return auth headers"""
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def test_1_create_session():
    """TEST 1: Create a chat session"""
    print("\n" + "="*80)
    print("TEST 1: Create a chat session")
    print("="*80)
    resp = requests.post(f"{BASE_URL}/orgs/{ORG_ID}/chat/sessions", json={}, headers=headers(), timeout=30)
    if resp.status_code != 200:
        print(f"❌ FAIL: Session creation failed: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    sid = data.get("id")
    if not sid:
        print(f"❌ FAIL: No session id in response: {data}")
        return None
    print(f"✅ PASS: Session created: {sid}")
    return sid

def test_2_reliability(sid):
    """TEST 2: RELIABILITY - Call voice-chat 5 times with different messages"""
    print("\n" + "="*80)
    print("TEST 2: RELIABILITY - 5 consecutive voice-chat calls")
    print("="*80)
    
    messages = [
        "Hello",
        "Tell me a fun fact",
        "What's the weather like on Mars?",
        "Give me a quick tip",
        "Say goodbye"
    ]
    
    success_count = 0
    total_calls = len(messages)
    
    for i, msg in enumerate(messages, 1):
        print(f"\n📞 Call {i}/{total_calls}: '{msg}'")
        body = {"message": msg, "agent": "vera", "voice": "nova"}
        
        try:
            resp = requests.post(f"{BASE_URL}/orgs/{ORG_ID}/chat/sessions/{sid}/voice-chat", 
                               json=body, headers=headers(), timeout=60)
            
            if resp.status_code != 200:
                print(f"  ❌ FAIL: HTTP {resp.status_code} - {resp.text[:200]}")
                continue
            
            data = resp.json()
            
            # Check required fields
            reply = data.get("reply")
            audio_b64 = data.get("audio")
            mime = data.get("mime")
            credits = data.get("credits")
            
            if not reply:
                print(f"  ❌ FAIL: Empty reply")
                continue
            
            if not audio_b64:
                print(f"  ❌ FAIL: Empty audio base64")
                continue
            
            if mime != "audio/mpeg":
                print(f"  ❌ FAIL: Wrong mime type: {mime}")
                continue
            
            if not isinstance(credits, int):
                print(f"  ❌ FAIL: Credits not an integer: {credits}")
                continue
            
            # Decode and validate audio
            try:
                audio_bytes = base64.b64decode(audio_b64)
            except Exception as e:
                print(f"  ❌ FAIL: Base64 decode error: {e}")
                continue
            
            audio_size = len(audio_bytes)
            if audio_size <= 1000:
                print(f"  ❌ FAIL: Audio too small: {audio_size} bytes (expected >1000)")
                continue
            
            # Check if it's valid MP3 (starts with ID3 or MP3 frame sync)
            is_valid_mp3 = (audio_bytes[:3] == b'ID3' or 
                          audio_bytes[:2] == b'\xff\xfb' or 
                          audio_bytes[:2] == b'\xff\xf3' or
                          audio_bytes[:2] == b'\xff\xf2')
            
            if not is_valid_mp3:
                print(f"  ❌ FAIL: Audio doesn't start with valid MP3 header: {audio_bytes[:10].hex()}")
                continue
            
            print(f"  ✅ PASS: reply={len(reply)} chars, audio={audio_size} bytes (valid MP3), credits={credits}")
            success_count += 1
            
        except Exception as e:
            print(f"  ❌ FAIL: Exception: {e}")
            continue
    
    print(f"\n{'='*80}")
    print(f"RELIABILITY RESULT: {success_count}/{total_calls} calls returned valid audio")
    print(f"{'='*80}")
    
    if success_count == total_calls:
        print("✅ PASS: All 5 calls successful")
        return True
    else:
        print(f"❌ FAIL: Only {success_count}/{total_calls} calls successful (expected 5/5)")
        return False

def test_3_adult_agent(sid):
    """TEST 3: Adult agent (blaze) with adult_confirmed preference"""
    print("\n" + "="*80)
    print("TEST 3: Adult agent (blaze) with adult_confirmed")
    print("="*80)
    
    # First set adult_confirmed preference
    print("📝 Setting adult_confirmed preference...")
    pref_resp = requests.put(f"{BASE_URL}/auth/me/preferences", 
                            json={"adult_confirmed": True}, 
                            headers=headers(), timeout=30)
    if pref_resp.status_code != 200:
        print(f"❌ FAIL: Failed to set preference: {pref_resp.status_code} {pref_resp.text}")
        return False
    print("✅ Preference set")
    
    # Now call voice-chat with blaze agent
    print("📞 Calling voice-chat with blaze agent...")
    body = {"message": "hey", "agent": "blaze", "adult_ok": True}
    resp = requests.post(f"{BASE_URL}/orgs/{ORG_ID}/chat/sessions/{sid}/voice-chat", 
                        json=body, headers=headers(), timeout=60)
    
    if resp.status_code != 200:
        print(f"❌ FAIL: HTTP {resp.status_code} - {resp.text[:200]}")
        return False
    
    data = resp.json()
    reply = data.get("reply")
    audio_b64 = data.get("audio")
    
    if not reply:
        print(f"❌ FAIL: Empty reply")
        return False
    
    if not audio_b64:
        print(f"❌ FAIL: Empty audio")
        return False
    
    # Decode audio
    try:
        audio_bytes = base64.b64decode(audio_b64)
        audio_size = len(audio_bytes)
    except Exception as e:
        print(f"❌ FAIL: Base64 decode error: {e}")
        return False
    
    if audio_size <= 1000:
        print(f"❌ FAIL: Audio too small: {audio_size} bytes")
        return False
    
    print(f"✅ PASS: Blaze agent working - reply={len(reply)} chars, audio={audio_size} bytes")
    print(f"   Reply: '{reply[:100]}...'")
    return True

def test_4_identity(sid):
    """TEST 4: IDENTITY - Check replies don't contain AI provider names"""
    print("\n" + "="*80)
    print("TEST 4: IDENTITY - No AI provider names in replies")
    print("="*80)
    
    forbidden_keywords = ["openai", "chatgpt", "gpt", "anthropic", "claude", "google", "gemini", "llama"]
    
    test_messages = [
        "Who are you?",
        "What AI model are you?",
        "Which company created you?"
    ]
    
    all_passed = True
    
    for msg in test_messages:
        print(f"\n📞 Testing: '{msg}'")
        body = {"message": msg, "agent": "vera", "voice": "nova"}
        
        try:
            resp = requests.post(f"{BASE_URL}/orgs/{ORG_ID}/chat/sessions/{sid}/voice-chat", 
                               json=body, headers=headers(), timeout=60)
            
            if resp.status_code != 200:
                print(f"  ❌ FAIL: HTTP {resp.status_code}")
                all_passed = False
                continue
            
            data = resp.json()
            reply = data.get("reply", "")
            reply_lower = reply.lower()
            
            # Check for forbidden keywords
            found_keywords = [kw for kw in forbidden_keywords if kw in reply_lower]
            
            if found_keywords:
                print(f"  ❌ FAIL: Reply contains forbidden keywords: {found_keywords}")
                print(f"     Reply: '{reply}'")
                all_passed = False
            else:
                print(f"  ✅ PASS: No forbidden keywords")
                print(f"     Reply: '{reply}'")
        
        except Exception as e:
            print(f"  ❌ FAIL: Exception: {e}")
            all_passed = False
    
    if all_passed:
        print(f"\n✅ PASS: All identity checks passed")
    else:
        print(f"\n❌ FAIL: Some identity checks failed")
    
    return all_passed

def test_5_errors():
    """TEST 5: ERROR cases - 404 for invalid session, 400 for whitespace"""
    print("\n" + "="*80)
    print("TEST 5: ERROR cases")
    print("="*80)
    
    all_passed = True
    
    # Test 5a: Invalid session (random 24-hex)
    print("\n📞 Test 5a: Invalid session ID (expect 404)")
    fake_sid = "123456789012345678901234"
    body = {"message": "test", "agent": "vera", "voice": "nova"}
    resp = requests.post(f"{BASE_URL}/orgs/{ORG_ID}/chat/sessions/{fake_sid}/voice-chat", 
                        json=body, headers=headers(), timeout=30)
    
    if resp.status_code == 404:
        print(f"  ✅ PASS: Got 404 as expected")
    else:
        print(f"  ❌ FAIL: Expected 404, got {resp.status_code}")
        all_passed = False
    
    # Test 5b: Whitespace message (expect 400)
    print("\n📞 Test 5b: Whitespace message (expect 400)")
    # First create a valid session
    sess_resp = requests.post(f"{BASE_URL}/orgs/{ORG_ID}/chat/sessions", json={}, headers=headers(), timeout=30)
    if sess_resp.status_code != 200:
        print(f"  ❌ FAIL: Could not create session for test")
        return False
    test_sid = sess_resp.json().get("id")
    
    body = {"message": "   ", "agent": "vera", "voice": "nova"}
    resp = requests.post(f"{BASE_URL}/orgs/{ORG_ID}/chat/sessions/{test_sid}/voice-chat", 
                        json=body, headers=headers(), timeout=30)
    
    if resp.status_code == 400:
        print(f"  ✅ PASS: Got 400 as expected")
    else:
        print(f"  ❌ FAIL: Expected 400, got {resp.status_code}")
        all_passed = False
    
    if all_passed:
        print(f"\n✅ PASS: All error cases handled correctly")
    else:
        print(f"\n❌ FAIL: Some error cases failed")
    
    return all_passed

def main():
    print("="*80)
    print("VIBEVERSE VOICE-CHAT REGRESSION + RELIABILITY TEST")
    print("Testing TTS fallback (tts-1-hd -> tts-1)")
    print("="*80)
    
    # Login
    login()
    
    # Test 1: Create session
    sid = test_1_create_session()
    if not sid:
        print("\n❌ CRITICAL: Cannot proceed without session")
        sys.exit(1)
    
    # Test 2: Reliability (5 calls)
    test_2_result = test_2_reliability(sid)
    
    # Test 3: Adult agent
    test_3_result = test_3_adult_agent(sid)
    
    # Test 4: Identity
    test_4_result = test_4_identity(sid)
    
    # Test 5: Errors
    test_5_result = test_5_errors()
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"TEST 1 (Create session): ✅ PASS")
    print(f"TEST 2 (Reliability 5x): {'✅ PASS' if test_2_result else '❌ FAIL'}")
    print(f"TEST 3 (Adult agent): {'✅ PASS' if test_3_result else '❌ FAIL'}")
    print(f"TEST 4 (Identity): {'✅ PASS' if test_4_result else '❌ FAIL'}")
    print(f"TEST 5 (Errors): {'✅ PASS' if test_5_result else '❌ FAIL'}")
    print("="*80)
    
    all_passed = test_2_result and test_3_result and test_4_result and test_5_result
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
