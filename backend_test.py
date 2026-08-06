#!/usr/bin/env python3
"""
Comprehensive backend test for NEW voice-companion features in VibeVerse.
Tests A-G as specified in the review_request.
"""
import os
import sys
import requests
import base64
import json

# Backend URL from frontend/.env
BACKEND_URL = "https://git-project-tool.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

def login():
    """Login and return Bearer token + org_id."""
    print("🔐 Logging in as admin...")
    resp = requests.post(f"{BACKEND_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    token = data["token"]
    print(f"✅ Login successful, token: {token[:20]}...")
    
    # Get org_id
    resp = requests.get(f"{BACKEND_URL}/auth/me", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ Failed to get user info: {resp.status_code} {resp.text}")
        sys.exit(1)
    user = resp.json()
    org_id = user.get("default_org_id")
    print(f"✅ Org ID: {org_id}")
    return token, org_id


def test_a_voice_agents_list(token):
    """TEST A: GET /api/voice-agents -> 200 with agents and voices."""
    print("\n" + "="*80)
    print("TEST A: GET /api/voice-agents")
    print("="*80)
    
    resp = requests.get(f"{BACKEND_URL}/voice-agents", headers={"Authorization": f"Bearer {token}"})
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    print(f"Response keys: {list(data.keys())}")
    
    # Check structure
    if "agents" not in data or "voices" not in data:
        print(f"❌ FAIL: Missing 'agents' or 'voices' in response")
        return False
    
    agents = data["agents"]
    voices = data["voices"]
    
    print(f"✅ Response has 'agents' and 'voices' fields")
    print(f"Agents count: {len(agents)}")
    print(f"Voices count: {len(voices)}")
    
    # Check voices: must be 9 strings
    if not isinstance(voices, list) or len(voices) != 9:
        print(f"❌ FAIL: Expected 9 voices, got {len(voices)}")
        return False
    print(f"✅ Voices: {voices}")
    
    # Check agents: must be 7
    if len(agents) != 7:
        print(f"❌ FAIL: Expected 7 agents, got {len(agents)}")
        return False
    print(f"✅ Agents count: 7")
    
    # Check agent IDs
    expected_ids = {"vera", "atlas", "sage", "echo", "luna", "blaze", "raven"}
    actual_ids = {a["id"] for a in agents}
    if actual_ids != expected_ids:
        print(f"❌ FAIL: Expected agent IDs {expected_ids}, got {actual_ids}")
        return False
    print(f"✅ Agent IDs: {actual_ids}")
    
    # Check adult flags
    adult_agents = {a["id"] for a in agents if a.get("adult") == True}
    non_adult_agents = {a["id"] for a in agents if a.get("adult") == False}
    
    if adult_agents != {"blaze", "raven"}:
        print(f"❌ FAIL: Expected blaze and raven to have adult=true, got {adult_agents}")
        return False
    print(f"✅ Adult agents (adult=true): {adult_agents}")
    
    if non_adult_agents != {"vera", "atlas", "sage", "echo", "luna"}:
        print(f"❌ FAIL: Expected vera, atlas, sage, echo, luna to have adult=false, got {non_adult_agents}")
        return False
    print(f"✅ Non-adult agents (adult=false): {non_adult_agents}")
    
    # Check agent fields
    required_fields = {"id", "name", "emoji", "gender", "tagline", "voice", "color", "adult"}
    for agent in agents:
        if not required_fields.issubset(agent.keys()):
            print(f"❌ FAIL: Agent {agent.get('id')} missing required fields")
            print(f"   Expected: {required_fields}")
            print(f"   Got: {set(agent.keys())}")
            return False
    print(f"✅ All agents have required fields: {required_fields}")
    
    print("\n✅ TEST A: PASS")
    return True


def test_b_voice_sample(token, org_id):
    """TEST B: POST /api/orgs/{org}/voice-sample -> 200 with audio base64 MP3, not charged."""
    print("\n" + "="*80)
    print("TEST B: POST /api/orgs/{org}/voice-sample")
    print("="*80)
    
    # Get credits before
    resp = requests.get(f"{BACKEND_URL}/orgs/{org_id}/usage", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not get usage: {resp.status_code}")
        return False
    credits_before = resp.json()["credits"]
    print(f"Credits before: {credits_before}")
    
    # Request voice sample
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/voice-sample", 
                        headers={"Authorization": f"Bearer {token}"},
                        json={"agent": "vera"})
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    print(f"Response keys: {list(data.keys())}")
    
    # Check structure
    if "audio" not in data or "mime" not in data:
        print(f"❌ FAIL: Missing 'audio' or 'mime' in response")
        return False
    
    audio_b64 = data["audio"]
    mime = data["mime"]
    
    if mime != "audio/mpeg":
        print(f"❌ FAIL: Expected mime='audio/mpeg', got '{mime}'")
        return False
    print(f"✅ MIME type: {mime}")
    
    # Decode base64
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception as e:
        print(f"❌ FAIL: Could not decode base64 audio: {e}")
        return False
    
    if len(audio_bytes) == 0:
        print(f"❌ FAIL: Audio bytes are empty")
        return False
    
    print(f"✅ Audio decoded: {len(audio_bytes)} bytes")
    
    # Check MP3 signature (ID3 or MP3 frame sync)
    is_mp3 = audio_bytes[:3] == b'ID3' or (audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0)
    if not is_mp3:
        print(f"⚠️  Warning: Audio does not start with ID3 or MP3 frame sync (first 4 bytes: {audio_bytes[:4].hex()})")
    else:
        print(f"✅ Audio is valid MP3 (starts with ID3 or frame sync)")
    
    # Get credits after
    resp = requests.get(f"{BACKEND_URL}/orgs/{org_id}/usage", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not get usage after: {resp.status_code}")
        return False
    credits_after = resp.json()["credits"]
    print(f"Credits after: {credits_after}")
    
    if credits_before != credits_after:
        print(f"❌ FAIL: Credits changed! Before: {credits_before}, After: {credits_after}")
        print(f"   Voice sample should NOT be charged")
        return False
    print(f"✅ Credits unchanged (sample not charged)")
    
    print("\n✅ TEST B: PASS")
    return True


def test_c_preferences(token):
    """TEST C: PUT /api/auth/me/preferences -> 200, GET /api/auth/me shows preferences."""
    print("\n" + "="*80)
    print("TEST C: PUT /api/auth/me/preferences")
    print("="*80)
    
    # Set preferences
    resp = requests.put(f"{BACKEND_URL}/auth/me/preferences",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"voice_agent": "atlas", "voice": "onyx"})
    print(f"PUT Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    print(f"✅ PUT preferences successful")
    
    # Get user info
    resp = requests.get(f"{BACKEND_URL}/auth/me", headers={"Authorization": f"Bearer {token}"})
    print(f"GET Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    user = resp.json()
    prefs = user.get("preferences", {})
    print(f"Preferences: {prefs}")
    
    if prefs.get("voice_agent") != "atlas":
        print(f"❌ FAIL: Expected voice_agent='atlas', got '{prefs.get('voice_agent')}'")
        return False
    print(f"✅ voice_agent: atlas")
    
    if prefs.get("voice") != "onyx":
        print(f"❌ FAIL: Expected voice='onyx', got '{prefs.get('voice')}'")
        return False
    print(f"✅ voice: onyx")
    
    if prefs.get("onboarded") != True:
        print(f"❌ FAIL: Expected onboarded=true, got '{prefs.get('onboarded')}'")
        return False
    print(f"✅ onboarded: true")
    
    print("\n✅ TEST C: PASS")
    return True


def test_d_voice_chat_normal(token, org_id):
    """TEST D: Voice chat with normal agent (atlas), check credits decrease by 1."""
    print("\n" + "="*80)
    print("TEST D: POST /api/orgs/{org}/chat/sessions/{sid}/voice-chat (normal agent)")
    print("="*80)
    
    # Create session
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions",
                        headers={"Authorization": f"Bearer {token}"},
                        json={})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not create session: {resp.status_code}")
        return False, None
    sid = resp.json()["id"]
    print(f"✅ Session created: {sid}")
    
    # Get credits before
    resp = requests.get(f"{BACKEND_URL}/orgs/{org_id}/usage", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not get usage: {resp.status_code}")
        return False, sid
    credits_before = resp.json()["credits"]
    print(f"Credits before: {credits_before}")
    
    # Voice chat
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{sid}/voice-chat",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "message": "Hello, what can you help me with?",
                            "agent": "atlas",
                            "voice": "onyx"
                        })
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False, sid
    
    data = resp.json()
    print(f"Response keys: {list(data.keys())}")
    
    # Check structure
    required_fields = {"reply", "audio", "mime", "credits"}
    if not required_fields.issubset(data.keys()):
        print(f"❌ FAIL: Missing required fields")
        print(f"   Expected: {required_fields}")
        print(f"   Got: {set(data.keys())}")
        return False, sid
    
    reply = data["reply"]
    audio_b64 = data["audio"]
    mime = data["mime"]
    credits_returned = data["credits"]
    
    print(f"✅ All required fields present")
    print(f"Reply: {reply}")
    print(f"Reply length: {len(reply)} chars")
    
    if not reply or len(reply) == 0:
        print(f"❌ FAIL: Reply is empty")
        return False, sid
    print(f"✅ Reply is non-empty")
    
    if mime != "audio/mpeg":
        print(f"❌ FAIL: Expected mime='audio/mpeg', got '{mime}'")
        return False, sid
    print(f"✅ MIME: {mime}")
    
    # Decode audio
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception as e:
        print(f"❌ FAIL: Could not decode base64 audio: {e}")
        return False, sid
    
    if len(audio_bytes) == 0:
        print(f"❌ FAIL: Audio bytes are empty")
        return False, sid
    
    print(f"✅ Audio decoded: {len(audio_bytes)} bytes")
    
    # Check MP3 signature
    is_mp3 = audio_bytes[:3] == b'ID3' or (audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0)
    if not is_mp3:
        print(f"⚠️  Warning: Audio does not start with ID3 or MP3 frame sync")
    else:
        print(f"✅ Audio is valid MP3")
    
    # Check credits
    if not isinstance(credits_returned, int):
        print(f"❌ FAIL: Credits is not an integer: {type(credits_returned)}")
        return False, sid
    print(f"✅ Credits is integer: {credits_returned}")
    
    expected_credits = credits_before - 1
    if credits_returned != expected_credits:
        print(f"❌ FAIL: Expected credits={expected_credits}, got {credits_returned}")
        print(f"   Credits should decrease by exactly 1")
        return False, sid
    print(f"✅ Credits decreased by exactly 1 (from {credits_before} to {credits_returned})")
    
    print(f"\n📝 ACTUAL REPLY TEXT (TEST D):")
    print(f"   {reply}")
    
    print("\n✅ TEST D: PASS")
    return True, sid


def test_e_adult_gate(token, org_id):
    """TEST E: Adult gate - 403 without confirmation, 200 after confirmation."""
    print("\n" + "="*80)
    print("TEST E: Adult gate for blaze agent")
    print("="*80)
    
    # Create session
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions",
                        headers={"Authorization": f"Bearer {token}"},
                        json={})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not create session: {resp.status_code}")
        return False
    sid = resp.json()["id"]
    print(f"✅ Session created: {sid}")
    
    # Try voice chat with blaze WITHOUT adult_ok (should fail 403)
    print("\n--- Attempt 1: blaze with adult_ok=false (should fail 403) ---")
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{sid}/voice-chat",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "message": "hey",
                            "agent": "blaze",
                            "adult_ok": False
                        })
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 403:
        print(f"❌ FAIL: Expected 403, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    print(f"✅ Got 403 as expected (adult confirmation required)")
    
    # Set adult_confirmed in preferences
    print("\n--- Setting adult_confirmed=true in preferences ---")
    resp = requests.put(f"{BACKEND_URL}/auth/me/preferences",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"voice_agent": "blaze", "adult_confirmed": True})
    print(f"PUT Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not set preferences: {resp.status_code}")
        return False
    print(f"✅ Preferences updated with adult_confirmed=true")
    
    # Retry voice chat with blaze WITH adult_ok=true (should succeed)
    print("\n--- Attempt 2: blaze with adult_ok=true (should succeed 200) ---")
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{sid}/voice-chat",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "message": "hey there",
                            "agent": "blaze",
                            "adult_ok": True
                        })
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    data = resp.json()
    reply = data.get("reply", "")
    audio_b64 = data.get("audio", "")
    
    print(f"✅ Got 200 with reply and audio")
    print(f"Reply: {reply}")
    print(f"Audio length: {len(audio_b64)} chars (base64)")
    
    if not reply:
        print(f"❌ FAIL: Reply is empty")
        return False
    
    if not audio_b64:
        print(f"❌ FAIL: Audio is empty")
        return False
    
    print(f"\n📝 ACTUAL REPLY TEXT (TEST E - retried):")
    print(f"   {reply}")
    
    print("\n✅ TEST E: PASS")
    return True


def test_f_identity(token, org_id, sid):
    """TEST F: Identity check - reply must not contain forbidden keywords."""
    print("\n" + "="*80)
    print("TEST F: Identity check in voice-chat replies")
    print("="*80)
    
    # We already have replies from test D, but let's do another explicit check
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{sid}/voice-chat",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "message": "Who are you? What company made you?",
                            "agent": "atlas",
                            "voice": "onyx"
                        })
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    data = resp.json()
    reply = data.get("reply", "")
    print(f"Reply: {reply}")
    
    # Check for forbidden keywords (case-insensitive)
    forbidden = ["openai", "chatgpt", "gpt", "anthropic", "claude", "google", "gemini", "llama"]
    reply_lower = reply.lower()
    
    found_forbidden = []
    for keyword in forbidden:
        if keyword in reply_lower:
            found_forbidden.append(keyword)
    
    if found_forbidden:
        print(f"❌ FAIL: Reply contains forbidden keywords: {found_forbidden}")
        print(f"   Reply: {reply}")
        return False
    
    print(f"✅ Reply does NOT contain any forbidden keywords")
    print(f"   Checked: {forbidden}")
    
    print("\n✅ TEST F: PASS")
    return True


def test_g_errors(token, org_id):
    """TEST G: Error handling - 404 for non-existent session, 400 for empty message."""
    print("\n" + "="*80)
    print("TEST G: Error handling")
    print("="*80)
    
    # Test 1: Non-existent session (random 24-hex ObjectId)
    print("\n--- Test G1: Non-existent session (should return 404) ---")
    fake_sid = "123456789012345678901234"
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{fake_sid}/voice-chat",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "message": "hello",
                            "agent": "vera",
                            "voice": "nova"
                        })
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 404:
        print(f"❌ FAIL: Expected 404, got {resp.status_code}")
        return False
    print(f"✅ Got 404 for non-existent session")
    
    # Test 2: Empty/whitespace message (should return 400)
    print("\n--- Test G2: Empty message (should return 400) ---")
    # Create a valid session first
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions",
                        headers={"Authorization": f"Bearer {token}"},
                        json={})
    if resp.status_code != 200:
        print(f"❌ FAIL: Could not create session: {resp.status_code}")
        return False
    sid = resp.json()["id"]
    
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{sid}/voice-chat",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "message": "   ",
                            "agent": "vera",
                            "voice": "nova"
                        })
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 400:
        print(f"❌ FAIL: Expected 400, got {resp.status_code}")
        return False
    print(f"✅ Got 400 for empty/whitespace message")
    
    print("\n✅ TEST G: PASS")
    return True


def main():
    print("="*80)
    print("VIBEVERSE VOICE-COMPANION BACKEND TEST SUITE")
    print("="*80)
    
    # Login
    token, org_id = login()
    
    # Run all tests
    results = {}
    
    results["A"] = test_a_voice_agents_list(token)
    results["B"] = test_b_voice_sample(token, org_id)
    results["C"] = test_c_preferences(token)
    results["D"], sid = test_d_voice_chat_normal(token, org_id)
    results["E"] = test_e_adult_gate(token, org_id)
    
    # Test F uses the session from test D
    if sid:
        results["F"] = test_f_identity(token, org_id, sid)
    else:
        print("\n⚠️  Skipping TEST F (no session from TEST D)")
        results["F"] = False
    
    results["G"] = test_g_errors(token, org_id)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"TEST {test}: {status}")
    
    all_passed = all(results.values())
    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
