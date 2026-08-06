#!/usr/bin/env python3
"""
Backend test for UPGRADED web app generation feature.
Tests the webapp action that produces stunning single-file HTML sites.
"""
import requests
import time
import re
import os

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://1b35aedf-76ce-4c25-b9a8-124de34f8867.preview.emergentagent.com')
BASE_URL = f"{BACKEND_URL}/api"

# Test credentials
EMAIL = "admin@aiplatform.com"
PASSWORD = "admin12345"

def test_webapp_generation():
    """Test the upgraded webapp generation feature end-to-end."""
    print("=" * 80)
    print("TESTING UPGRADED WEB APP GENERATION FEATURE")
    print("=" * 80)
    
    # Step 1: Login
    print("\n[STEP 1] Login to get Bearer token...")
    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": EMAIL, "password": PASSWORD}
    )
    print(f"Login status: {login_resp.status_code}")
    if login_resp.status_code != 200:
        print(f"❌ FAIL: Login failed with status {login_resp.status_code}")
        print(f"Response: {login_resp.text}")
        return False
    
    login_data = login_resp.json()
    token = login_data.get("token") or login_data.get("access_token")
    if not token:
        print(f"❌ FAIL: No token in login response")
        print(f"Response: {login_data}")
        return False
    
    print(f"✅ Login successful, got token: {token[:20]}...")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Get org_id
    print("\n[STEP 2] Get org_id from /api/auth/me...")
    me_resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print(f"Auth/me status: {me_resp.status_code}")
    if me_resp.status_code != 200:
        print(f"❌ FAIL: /auth/me failed with status {me_resp.status_code}")
        print(f"Response: {me_resp.text}")
        return False
    
    me_data = me_resp.json()
    org_id = me_data.get("default_org_id")
    if not org_id:
        print(f"❌ FAIL: No default_org_id in /auth/me response")
        print(f"Response: {me_data}")
        return False
    
    print(f"✅ Got org_id: {org_id}")
    
    # Step 3: Create a chat session
    print("\n[STEP 3] Create a chat session...")
    session_resp = requests.post(
        f"{BASE_URL}/orgs/{org_id}/chat/sessions",
        headers=headers,
        json={"title": "webapp test"}
    )
    print(f"Create session status: {session_resp.status_code}")
    if session_resp.status_code != 200:
        print(f"❌ FAIL: Create session failed with status {session_resp.status_code}")
        print(f"Response: {session_resp.text}")
        return False
    
    session_data = session_resp.json()
    sid = session_data.get("id")
    if not sid:
        print(f"❌ FAIL: No id in session response")
        print(f"Response: {session_data}")
        return False
    
    print(f"✅ Created session with id: {sid}")
    
    # Step 4: Trigger webapp build
    print("\n[STEP 4] Trigger webapp build...")
    webapp_prompt = "Build me an immersive 3D landing page for a space travel startup called Nova with an animated starfield hero and smooth scroll animations."
    
    # First try the /agent endpoint (which handles webapp generation via intent routing)
    print(f"Sending message to /agent endpoint: '{webapp_prompt[:60]}...'")
    agent_resp = requests.post(
        f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/agent",
        headers=headers,
        json={"message": webapp_prompt}
    )
    print(f"Agent endpoint status: {agent_resp.status_code}")
    
    if agent_resp.status_code != 200:
        print(f"⚠️  /agent endpoint failed with status {agent_resp.status_code}")
        print(f"Response: {agent_resp.text}")
        
        # Try the /send endpoint as mentioned in review request
        print("\nTrying /send endpoint instead...")
        send_resp = requests.post(
            f"{BASE_URL}/orgs/{org_id}/chat/sessions/{sid}/send",
            headers=headers,
            json={"message": webapp_prompt}
        )
        print(f"Send endpoint status: {send_resp.status_code}")
        
        if send_resp.status_code == 422:
            print(f"Got 422 error, checking field name...")
            print(f"Response: {send_resp.text}")
            # The /send endpoint expects "message" field according to ChatSendBody
        
        if send_resp.status_code != 200:
            print(f"❌ FAIL: Both /agent and /send endpoints failed")
            return False
        
        agent_data = send_resp.json()
    else:
        agent_data = agent_resp.json()
    
    print(f"Response data: {agent_data}")
    
    # Check if we got a webapp creation
    action = agent_data.get("action")
    media = agent_data.get("media")
    
    if not media:
        print(f"❌ FAIL: No media object in response")
        print(f"Full response: {agent_data}")
        return False
    
    cid = media.get("cid")
    status = media.get("status")
    
    if not cid:
        print(f"❌ FAIL: No cid (creation id) in media object")
        print(f"Media: {media}")
        return False
    
    print(f"✅ Got creation id: {cid}")
    print(f"   Action: {action}")
    print(f"   Initial status: {status}")
    
    if status != "processing":
        print(f"⚠️  WARNING: Expected status 'processing', got '{status}'")
    
    # Step 5: Poll for completion
    print("\n[STEP 5] Polling for completion (max 90 seconds)...")
    max_polls = 30  # 30 polls * 3 seconds = 90 seconds
    poll_count = 0
    final_status = None
    
    while poll_count < max_polls:
        poll_count += 1
        time.sleep(3)
        
        status_resp = requests.get(
            f"{BASE_URL}/orgs/{org_id}/creations/{cid}/status",
            headers=headers
        )
        
        if status_resp.status_code != 200:
            print(f"⚠️  Poll {poll_count}: Status check failed with {status_resp.status_code}")
            continue
        
        status_data = status_resp.json()
        current_status = status_data.get("status")
        print(f"Poll {poll_count}: status = {current_status}")
        
        if current_status == "done":
            final_status = "done"
            print(f"✅ Generation completed after {poll_count * 3} seconds")
            break
        elif current_status == "failed":
            final_status = "failed"
            error = status_data.get("error", "Unknown error")
            print(f"❌ FAIL: Generation failed with error: {error}")
            return False
    
    if final_status != "done":
        print(f"❌ FAIL: Generation did not complete within 90 seconds (status: {final_status})")
        return False
    
    # Step 6: Retrieve and verify the generated HTML
    print("\n[STEP 6] Retrieve and verify generated HTML...")
    
    # First try to get HTML from the status response
    html_content = None
    
    # Try getting from creations list
    creations_resp = requests.get(
        f"{BASE_URL}/orgs/{org_id}/creations",
        headers=headers
    )
    
    if creations_resp.status_code == 200:
        creations = creations_resp.json()
        for creation in creations:
            if creation.get("id") == cid:
                html_content = creation.get("content")
                break
    
    if not html_content:
        # Try getting the file directly
        file_resp = requests.get(
            f"{BASE_URL}/orgs/{org_id}/creations/{cid}/file",
            headers=headers
        )
        if file_resp.status_code == 200:
            html_content = file_resp.text
    
    if not html_content:
        print(f"❌ FAIL: Could not retrieve HTML content")
        return False
    
    print(f"✅ Retrieved HTML content ({len(html_content)} characters)")
    print(f"\nFirst 300 characters:")
    print("-" * 80)
    print(html_content[:300])
    print("-" * 80)
    
    # Verify HTML structure
    print("\n[VERIFICATION] Checking HTML quality...")
    
    html_lower = html_content.lower()
    
    # Check 1: Full HTML document
    has_doctype = "<!doctype html>" in html_lower or "<html" in html_lower
    has_closing_html = "</html>" in html_lower
    
    print(f"✓ Has DOCTYPE or <html>: {has_doctype}")
    print(f"✓ Has </html>: {has_closing_html}")
    
    if not (has_doctype and has_closing_html):
        print(f"❌ FAIL: Not a complete HTML document")
        return False
    
    # Check 2: Upgraded quality markers
    print("\n[VERIFICATION] Checking for upgraded quality markers...")
    
    quality_markers = {
        "three.js": "three" in html_lower,
        "GSAP": "gsap" in html_lower,
        "Tailwind CDN": "cdn.tailwindcss.com" in html_lower,
        "Canvas": "<canvas" in html_lower,
        "requestAnimationFrame": "requestanimationframe" in html_lower,
        "Google Fonts": "fonts.googleapis.com" in html_lower,
        "Keyframe animations": "@keyframes" in html_lower or "scrolltrigger" in html_lower
    }
    
    found_markers = []
    for marker, present in quality_markers.items():
        status_icon = "✅" if present else "❌"
        print(f"{status_icon} {marker}: {present}")
        if present:
            found_markers.append(marker)
    
    if not found_markers:
        print(f"\n❌ FAIL: No upgraded quality markers found!")
        print(f"Expected at least ONE of: three.js, GSAP, Tailwind CDN, Canvas, requestAnimationFrame, Google Fonts, or keyframe animations")
        return False
    
    print(f"\n✅ PASS: Found {len(found_markers)} quality marker(s): {', '.join(found_markers)}")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Status: DONE (not failed)")
    print(f"✅ HTML length: {len(html_content)} characters")
    print(f"✅ Complete HTML document: Yes")
    print(f"✅ Quality markers found: {', '.join(found_markers)}")
    print(f"\nFirst 300 characters of HTML:")
    print(html_content[:300])
    print("\n" + "=" * 80)
    print("🎉 ALL TESTS PASSED - UPGRADED WEBAPP GENERATION WORKING!")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    try:
        success = test_webapp_generation()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
