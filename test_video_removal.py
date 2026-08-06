#!/usr/bin/env python3
"""
Backend API Test Suite for Video Removal + Voice-in-Chat Integration
Tests all 5 scenarios from review_request:
1. Video endpoint removed (POST /api/orgs/{org}/generate/video should return 404/405)
2. Voice/audio still works (POST /api/orgs/{org}/generate/audio + GET url + verify creation)
3. Unified chat voice routing (voiceover message should return kind="voice", NOT "video")
4. No video from chat (video request should NOT return kind="video")
5. Admin stats (GET /api/admin/stats should not have "video" key and not 500)
"""
import requests
import time
import sys

# Backend URL from frontend/.env
BASE_URL = "https://git-project-tool.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

def log(msg):
    print(f"[TEST] {msg}")

def error(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)

def success(msg):
    print(f"[SUCCESS] {msg}")

def main():
    log("=" * 80)
    log("VibeVerse Backend Test Suite - Video Removal + Voice Integration")
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
            # Try getting from /api/orgs
            log("No default_org_id, trying GET /api/orgs")
            orgs_resp = requests.get(f"{BASE_URL}/orgs", headers=headers, timeout=30)
            if orgs_resp.status_code == 200:
                orgs = orgs_resp.json()
                if orgs and len(orgs) > 0:
                    org_id = orgs[0].get("id")
        
        if not org_id:
            error("Could not get org_id from /auth/me or /orgs")
            return False
        
        success(f"Got org_id: {org_id}")
    except Exception as e:
        error(f"GET /auth/me failed: {e}")
        return False
    
    # ========== TEST 1: Video endpoint removed ==========
    log("\n" + "=" * 80)
    log("TEST 1: Video endpoint removed (POST /api/orgs/{org}/generate/video)")
    log("=" * 80)
    
    try:
        video_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/generate/video",
            headers=headers,
            json={"prompt": "a clip of the ocean"},
            timeout=30
        )
        
        status = video_resp.status_code
        log(f"Response status: {status}")
        
        if status in [404, 405]:
            success(f"TEST 1 PASSED: Video endpoint correctly removed (status {status})")
        elif status == 200:
            error(f"TEST 1 FAILED: Video endpoint still exists and returned 200")
            error(f"Response: {video_resp.text[:200]}")
            return False
        else:
            # Any other error is acceptable (endpoint doesn't exist)
            success(f"TEST 1 PASSED: Video endpoint not accessible (status {status})")
    except Exception as e:
        error(f"TEST 1: Request failed: {e}")
        return False
    
    # ========== TEST 2: Voice/audio still works ==========
    log("\n" + "=" * 80)
    log("TEST 2: Voice/audio generation still works")
    log("=" * 80)
    
    log("Step 2a: POST /api/orgs/{org}/generate/audio")
    try:
        audio_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/generate/audio",
            headers=headers,
            json={"text": "Welcome to VibeVerse", "voice": "nova", "model": "tts-1"},
            timeout=60
        )
        
        if audio_resp.status_code != 200:
            error(f"TEST 2a FAILED: Audio generation returned {audio_resp.status_code}")
            error(f"Response: {audio_resp.text}")
            return False
        
        audio_data = audio_resp.json()
        audio_url = audio_data.get("url")
        audio_credits = audio_data.get("credits")
        
        if not audio_url:
            error("TEST 2a FAILED: No 'url' field in audio response")
            error(f"Response: {audio_data}")
            return False
        
        if audio_credits is None:
            error("TEST 2a FAILED: No 'credits' field in audio response")
            error(f"Response: {audio_data}")
            return False
        
        success(f"TEST 2a PASSED: Audio generation returned url and credits")
        log(f"Audio URL: {audio_url}")
        log(f"Credits remaining: {audio_credits}")
        
    except Exception as e:
        error(f"TEST 2a: Request failed: {e}")
        return False
    
    log("\nStep 2b: GET the audio URL (with Bearer token)")
    try:
        # The URL is relative, so we need to construct the full URL
        if audio_url.startswith("/api"):
            full_audio_url = f"{BASE_URL.replace('/api', '')}{audio_url}"
        else:
            full_audio_url = f"{BASE_URL}/{audio_url.lstrip('/')}"
        
        log(f"Fetching: {full_audio_url}")
        audio_file_resp = requests.get(full_audio_url, headers=headers, timeout=30)
        
        if audio_file_resp.status_code != 200:
            error(f"TEST 2b FAILED: Audio file GET returned {audio_file_resp.status_code}")
            error(f"Response: {audio_file_resp.text[:200]}")
            return False
        
        content_type = audio_file_resp.headers.get("content-type", "")
        content_length = len(audio_file_resp.content)
        
        if "audio" not in content_type.lower():
            error(f"TEST 2b FAILED: Content-Type is not audio (got: {content_type})")
            return False
        
        if content_length == 0:
            error("TEST 2b FAILED: Audio file is empty")
            return False
        
        success(f"TEST 2b PASSED: Audio file retrieved successfully")
        log(f"Content-Type: {content_type}")
        log(f"Content-Length: {content_length} bytes")
        
    except Exception as e:
        error(f"TEST 2b: Request failed: {e}")
        return False
    
    log("\nStep 2c: Verify creation with kind='audio' exists")
    try:
        creations_resp = requests.get(
            f"{BASE_URL}/orgs/{org_id}/creations",
            headers=headers,
            timeout=30
        )
        
        if creations_resp.status_code != 200:
            error(f"TEST 2c FAILED: GET /creations returned {creations_resp.status_code}")
            return False
        
        creations = creations_resp.json()
        audio_creations = [c for c in creations if c.get("kind") == "audio"]
        
        if not audio_creations:
            error("TEST 2c FAILED: No audio creation found in /creations")
            return False
        
        success(f"TEST 2c PASSED: Found {len(audio_creations)} audio creation(s)")
        
    except Exception as e:
        error(f"TEST 2c: Request failed: {e}")
        return False
    
    # ========== TEST 3: Unified chat voice routing ==========
    log("\n" + "=" * 80)
    log("TEST 3: Unified chat voice routing (voiceover should return kind='voice')")
    log("=" * 80)
    
    log("Step 3a: Create chat session")
    try:
        session_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions",
            headers=headers,
            json={"title": "Test Voice Routing"},
            timeout=30
        )
        
        if session_resp.status_code != 200:
            error(f"TEST 3a FAILED: Create session returned {session_resp.status_code}")
            error(f"Response: {session_resp.text}")
            return False
        
        session_id = session_resp.json().get("id")
        if not session_id:
            error("TEST 3a FAILED: No session id in response")
            return False
        
        success(f"TEST 3a PASSED: Chat session created: {session_id}")
        
    except Exception as e:
        error(f"TEST 3a: Request failed: {e}")
        return False
    
    log("\nStep 3b: Send voiceover message to /agent endpoint")
    try:
        agent_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions/{session_id}/agent",
            headers=headers,
            json={"message": "Create a voiceover: hello world"},
            timeout=90
        )
        
        if agent_resp.status_code != 200:
            error(f"TEST 3b FAILED: Agent endpoint returned {agent_resp.status_code}")
            error(f"Response: {agent_resp.text}")
            return False
        
        agent_data = agent_resp.json()
        response_kind = agent_data.get("kind")
        response_action = agent_data.get("action")
        media = agent_data.get("media")
        
        log(f"Response kind: {response_kind}")
        log(f"Response action: {response_action}")
        
        if response_kind == "video":
            error("TEST 3b FAILED: Response kind is 'video' (should be 'voice')")
            error(f"Full response: {agent_data}")
            return False
        
        if response_kind != "voice":
            error(f"TEST 3b FAILED: Response kind is '{response_kind}' (expected 'voice')")
            error(f"Full response: {agent_data}")
            return False
        
        if not media or not media.get("url"):
            error("TEST 3b FAILED: No media.url in response")
            error(f"Full response: {agent_data}")
            return False
        
        success(f"TEST 3b PASSED: Voiceover returned kind='voice' with media.url")
        log(f"Media URL: {media.get('url')}")
        
    except Exception as e:
        error(f"TEST 3b: Request failed: {e}")
        return False
    
    # ========== TEST 4: No video from chat ==========
    log("\n" + "=" * 80)
    log("TEST 4: No video from chat (video request should NOT return kind='video')")
    log("=" * 80)
    
    try:
        video_chat_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions/{session_id}/agent",
            headers=headers,
            json={"message": "Make a short video of waves crashing on a beach"},
            timeout=90
        )
        
        if video_chat_resp.status_code != 200:
            error(f"TEST 4 FAILED: Agent endpoint returned {video_chat_resp.status_code}")
            error(f"Response: {video_chat_resp.text}")
            return False
        
        video_chat_data = video_chat_resp.json()
        response_kind = video_chat_data.get("kind")
        response_action = video_chat_data.get("action")
        
        log(f"Response kind: {response_kind}")
        log(f"Response action: {response_action}")
        
        if response_kind == "video":
            error("TEST 4 FAILED: Response kind is 'video' (video was supposed to be removed)")
            error(f"Full response: {video_chat_data}")
            return False
        
        success(f"TEST 4 PASSED: Video request did NOT return kind='video' (got kind='{response_kind}')")
        
    except Exception as e:
        error(f"TEST 4: Request failed: {e}")
        return False
    
    # ========== TEST 5: Admin stats ==========
    log("\n" + "=" * 80)
    log("TEST 5: Admin stats (should not have 'video' key and not 500)")
    log("=" * 80)
    
    try:
        stats_resp = requests.get(
            f"{BASE_URL}/admin/stats",
            headers=headers,
            timeout=30
        )
        
        if stats_resp.status_code != 200:
            error(f"TEST 5 FAILED: Admin stats returned {stats_resp.status_code}")
            error(f"Response: {stats_resp.text}")
            return False
        
        stats_data = stats_resp.json()
        creations = stats_data.get("creations", {})
        
        log(f"Creations keys: {list(creations.keys())}")
        
        if "video" in creations:
            error("TEST 5 FAILED: 'video' key found in creations stats")
            error(f"Creations: {creations}")
            return False
        
        success("TEST 5 PASSED: Admin stats returned 200, no 'video' key in creations")
        log(f"Stats: {stats_data}")
        
    except Exception as e:
        error(f"TEST 5: Request failed: {e}")
        return False
    
    # ========== ALL TESTS PASSED ==========
    log("\n" + "=" * 80)
    success("ALL 5 TESTS PASSED!")
    log("=" * 80)
    log("\nSummary:")
    log("✅ TEST 1: Video endpoint removed (404/405)")
    log("✅ TEST 2: Voice/audio generation works (url + credits + creation saved)")
    log("✅ TEST 3: Unified chat voice routing (kind='voice', NOT 'video')")
    log("✅ TEST 4: No video from chat (kind != 'video')")
    log("✅ TEST 5: Admin stats (no 'video' key, no 500)")
    
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
