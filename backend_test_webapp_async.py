#!/usr/bin/env python3
"""
Bug fix verification: webapp build now runs async (background job + polling)
instead of synchronous SSE streaming that times out.

Tests from review_request:
1) Create chat session
2) STREAMING WEBAPP BUILD - should complete QUICKLY (few seconds, not 60s)
   - Verify "start" event with action=="webapp"
   - NO long series of "step" events
   - Final "done" event with kind=="webapp", status=="processing", cid
3) POLL /creations/{cid}/status until status=="done"
4) GET /creations/{cid}/file returns HTML
5) REGRESSION - plain chat streaming still works
"""

import os
import sys
import time
import json
import requests
import sseclient

# Get backend URL from frontend .env
BACKEND_URL = None
try:
    with open("/app/frontend/.env", "r") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BACKEND_URL = line.split("=", 1)[1].strip()
                break
except Exception as e:
    print(f"❌ Failed to read REACT_APP_BACKEND_URL: {e}")
    sys.exit(1)

if not BACKEND_URL:
    print("❌ REACT_APP_BACKEND_URL not found in /app/frontend/.env")
    sys.exit(1)

API_BASE = f"{BACKEND_URL}/api"
print(f"🔗 Using API base: {API_BASE}")

# Test credentials
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

def login():
    """Login and return (token, org_id)"""
    print(f"\n🔐 Logging in as {ADMIN_EMAIL}...")
    resp = requests.post(f"{API_BASE}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    }, timeout=30)
    
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    
    data = resp.json()
    token = data.get("token")
    
    # Get org_id from /auth/me
    me_resp = requests.get(f"{API_BASE}/auth/me", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=30)
    
    if me_resp.status_code != 200:
        print(f"❌ Failed to get user info: {me_resp.status_code}")
        sys.exit(1)
    
    me_data = me_resp.json()
    org_id = me_data.get("default_org_id")
    
    if not org_id:
        print(f"❌ No default_org_id in /auth/me response")
        sys.exit(1)
    
    print(f"✅ Logged in successfully. Org ID: {org_id}")
    return token, org_id


def test_1_create_session(token, org_id):
    """TEST 1: Create a chat session"""
    print("\n" + "="*80)
    print("TEST 1: Create chat session")
    print("="*80)
    
    resp = requests.post(f"{API_BASE}/orgs/{org_id}/chat/sessions", 
                        json={}, 
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=30)
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Failed to create session: {resp.status_code} {resp.text}")
        return None
    
    data = resp.json()
    sid = data.get("id")
    
    if not sid:
        print(f"❌ FAIL: No session id in response")
        return None
    
    print(f"✅ PASS: Session created: {sid}")
    return sid


def test_2_streaming_webapp_build(token, org_id, sid):
    """TEST 2: STREAMING WEBAPP BUILD - should complete QUICKLY with NO step events"""
    print("\n" + "="*80)
    print("TEST 2: STREAMING WEBAPP BUILD (async background job)")
    print("="*80)
    
    message = "Build a simple landing page for a coffee shop"
    print(f"📤 Sending message: '{message}'")
    
    url = f"{API_BASE}/orgs/{org_id}/chat/sessions/{sid}/agent/stream"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json"
    }
    body = json.dumps({"message": message})
    
    start_time = time.time()
    events = []
    event_types = []
    
    print("📡 Streaming events...")
    
    try:
        resp = requests.post(url, headers=headers, data=body, stream=True, timeout=120)
        
        if resp.status_code != 200:
            print(f"❌ FAIL: Stream request failed: {resp.status_code} {resp.text}")
            return None, None
        
        client = sseclient.SSEClient(resp)
        
        for event in client.events():
            if event.data:
                try:
                    data = json.loads(event.data)
                    events.append(data)
                    event_type = data.get("type")
                    event_types.append(event_type)
                    
                    # Print event summary
                    if event_type == "start":
                        action = data.get("action")
                        print(f"  📍 START event: action={action}")
                    elif event_type == "step":
                        step_id = data.get("id")
                        state = data.get("state")
                        print(f"  ⚠️  STEP event: id={step_id}, state={state} (SHOULD NOT HAPPEN)")
                    elif event_type == "done":
                        msg = data.get("message", {})
                        kind = msg.get("kind")
                        media = msg.get("media", {})
                        status = media.get("status")
                        cid = media.get("cid")
                        print(f"  ✅ DONE event: kind={kind}, status={status}, cid={cid}")
                    elif event_type == "error":
                        detail = data.get("detail")
                        print(f"  ❌ ERROR event: {detail}")
                    elif event_type == "delta":
                        # Don't print deltas, just count them
                        pass
                    else:
                        print(f"  ℹ️  {event_type} event")
                    
                    # Stop after done or error
                    if event_type in ["done", "error"]:
                        break
                        
                except json.JSONDecodeError:
                    print(f"  ⚠️  Invalid JSON: {event.data}")
                    
    except Exception as e:
        print(f"❌ FAIL: Stream error: {e}")
        return None, None
    
    elapsed = time.time() - start_time
    print(f"\n⏱️  Stream completed in {elapsed:.2f} seconds")
    print(f"📊 Total events received: {len(events)}")
    print(f"📋 Event types (ordered): {event_types}")
    
    # VERIFICATION (a): Stream completes QUICKLY (within a few seconds, well under 60s)
    print(f"\n🔍 VERIFICATION (a): Stream duration")
    if elapsed > 60:
        print(f"❌ FAIL: Stream took {elapsed:.2f}s (should be < 60s)")
        return None, None
    elif elapsed > 10:
        print(f"⚠️  WARNING: Stream took {elapsed:.2f}s (expected < 10s for async)")
    else:
        print(f"✅ PASS: Stream completed quickly in {elapsed:.2f}s")
    
    # VERIFICATION (b): There is a "start" event with action=="webapp"
    print(f"\n🔍 VERIFICATION (b): Start event with action=webapp")
    start_events = [e for e in events if e.get("type") == "start"]
    if not start_events:
        print(f"❌ FAIL: No 'start' event found")
        return None, None
    
    start_event = start_events[0]
    if start_event.get("action") != "webapp":
        print(f"❌ FAIL: Start event action is '{start_event.get('action')}', expected 'webapp'")
        return None, None
    
    print(f"✅ PASS: Found 'start' event with action='webapp'")
    
    # VERIFICATION (c): NO long series of "step" events and NO "error" event
    print(f"\n🔍 VERIFICATION (c): No step events, no error event")
    step_events = [e for e in events if e.get("type") == "step"]
    error_events = [e for e in events if e.get("type") == "error"]
    
    if step_events:
        print(f"❌ FAIL: Found {len(step_events)} 'step' events (should be 0 for async build)")
        print(f"   Step events: {[e.get('id') for e in step_events]}")
        return None, None
    
    if error_events:
        print(f"❌ FAIL: Found 'error' event: {error_events[0].get('detail')}")
        return None, None
    
    print(f"✅ PASS: No 'step' events, no 'error' event")
    
    # VERIFICATION (d): Final "done" event with kind=="webapp", status=="processing", cid
    print(f"\n🔍 VERIFICATION (d): Done event with kind=webapp, status=processing, cid")
    done_events = [e for e in events if e.get("type") == "done"]
    if not done_events:
        print(f"❌ FAIL: No 'done' event found")
        return None, None
    
    done_event = done_events[0]
    message = done_event.get("message", {})
    kind = message.get("kind")
    media = message.get("media", {})
    status = media.get("status")
    cid = media.get("cid")
    
    if kind != "webapp":
        print(f"❌ FAIL: Done event kind is '{kind}', expected 'webapp'")
        return None, None
    
    if status != "processing":
        print(f"❌ FAIL: Done event status is '{status}', expected 'processing'")
        return None, None
    
    if not cid:
        print(f"❌ FAIL: Done event has no cid")
        return None, None
    
    print(f"✅ PASS: Done event has kind='webapp', status='processing', cid='{cid}'")
    
    print(f"\n✅ TEST 2 PASSED: Streaming webapp build works correctly (async)")
    return cid, event_types


def test_3_poll_creation_status(token, org_id, cid):
    """TEST 3: POLL /creations/{cid}/status until status=="done" """
    print("\n" + "="*80)
    print(f"TEST 3: POLL creation status (cid={cid})")
    print("="*80)
    
    url = f"{API_BASE}/orgs/{org_id}/creations/{cid}/status"
    headers = {"Authorization": f"Bearer {token}"}
    
    max_polls = 30  # 30 polls * 3s = 90s max
    poll_interval = 3
    
    print(f"📡 Polling every {poll_interval}s (max {max_polls} polls = {max_polls * poll_interval}s)...")
    
    for i in range(max_polls):
        time.sleep(poll_interval)
        
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            
            if resp.status_code != 200:
                print(f"❌ FAIL: Poll failed: {resp.status_code} {resp.text}")
                return None
            
            data = resp.json()
            status = data.get("status")
            
            print(f"  Poll {i+1}/{max_polls}: status={status}")
            
            if status == "done":
                print(f"✅ PASS: Creation reached 'done' status after {(i+1) * poll_interval}s")
                return status
            elif status == "failed":
                error = data.get("error", "unknown")
                print(f"❌ FAIL: Creation failed: {error}")
                return None
            elif status != "processing":
                print(f"⚠️  WARNING: Unexpected status: {status}")
                
        except Exception as e:
            print(f"❌ FAIL: Poll error: {e}")
            return None
    
    print(f"❌ FAIL: Creation did not reach 'done' status within {max_polls * poll_interval}s")
    return None


def test_4_get_creation_file(token, org_id, cid):
    """TEST 4: GET /creations/{cid}/file returns HTML"""
    print("\n" + "="*80)
    print(f"TEST 4: GET creation file (cid={cid})")
    print("="*80)
    
    url = f"{API_BASE}/orgs/{org_id}/creations/{cid}/file"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            print(f"❌ FAIL: GET file failed: {resp.status_code} {resp.text[:200]}")
            return False
        
        content = resp.text
        content_lower = content.lower()
        
        print(f"📄 Response length: {len(content)} bytes")
        print(f"📄 Content-Type: {resp.headers.get('Content-Type')}")
        print(f"📄 First 200 chars: {content[:200]}")
        
        # Check if it contains HTML
        if "<html" in content_lower or "<!doctype" in content_lower:
            print(f"✅ PASS: Response contains HTML")
            return True
        else:
            print(f"❌ FAIL: Response does not contain HTML")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: GET file error: {e}")
        return False


def test_5_regression_plain_chat(token, org_id):
    """TEST 5: REGRESSION - plain chat streaming still works"""
    print("\n" + "="*80)
    print("TEST 5: REGRESSION - Plain chat streaming")
    print("="*80)
    
    # Create new session
    resp = requests.post(f"{API_BASE}/orgs/{org_id}/chat/sessions", 
                        json={}, 
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=30)
    
    if resp.status_code != 200:
        print(f"❌ FAIL: Failed to create session: {resp.status_code}")
        return False
    
    sid = resp.json().get("id")
    print(f"📝 Created session: {sid}")
    
    # Send plain chat message
    message = "Say hi in one short sentence"
    print(f"📤 Sending message: '{message}'")
    
    url = f"{API_BASE}/orgs/{org_id}/chat/sessions/{sid}/agent/stream"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json"
    }
    body = json.dumps({"message": message})
    
    events = []
    reply_text = ""
    
    try:
        resp = requests.post(url, headers=headers, data=body, stream=True, timeout=60)
        
        if resp.status_code != 200:
            print(f"❌ FAIL: Stream request failed: {resp.status_code}")
            return False
        
        client = sseclient.SSEClient(resp)
        
        for event in client.events():
            if event.data:
                try:
                    data = json.loads(event.data)
                    events.append(data)
                    event_type = data.get("type")
                    
                    if event_type == "delta":
                        reply_text += data.get("content", "")
                    elif event_type == "done":
                        msg = data.get("message", {})
                        kind = msg.get("kind")
                        content = msg.get("content", "")
                        print(f"  ✅ DONE event: kind={kind}, content length={len(content)}")
                        break
                    elif event_type == "error":
                        print(f"  ❌ ERROR event: {data.get('detail')}")
                        return False
                        
                except json.JSONDecodeError:
                    pass
                    
    except Exception as e:
        print(f"❌ FAIL: Stream error: {e}")
        return False
    
    # Verify we got delta events and a done event
    delta_events = [e for e in events if e.get("type") == "delta"]
    done_events = [e for e in events if e.get("type") == "done"]
    
    print(f"📊 Received {len(delta_events)} delta events, {len(done_events)} done event")
    print(f"💬 Reply text: '{reply_text}'")
    
    if not done_events:
        print(f"❌ FAIL: No 'done' event received")
        return False
    
    done_event = done_events[0]
    message = done_event.get("message", {})
    kind = message.get("kind")
    content = message.get("content", "")
    
    if kind != "text":
        print(f"❌ FAIL: Done event kind is '{kind}', expected 'text'")
        return False
    
    if not content or len(content) < 2:
        print(f"❌ FAIL: Done event has empty reply")
        return False
    
    print(f"✅ PASS: Plain chat streaming works correctly")
    return True


def main():
    print("="*80)
    print("BUG FIX VERIFICATION: Webapp Build Async (Background Job + Polling)")
    print("="*80)
    
    # Login
    token, org_id = login()
    
    # TEST 1: Create session
    sid = test_1_create_session(token, org_id)
    if not sid:
        print("\n❌ TEST 1 FAILED - Cannot continue")
        sys.exit(1)
    
    # TEST 2: Streaming webapp build (async)
    cid, event_types = test_2_streaming_webapp_build(token, org_id, sid)
    if not cid:
        print("\n❌ TEST 2 FAILED - Cannot continue")
        sys.exit(1)
    
    # TEST 3: Poll creation status
    final_status = test_3_poll_creation_status(token, org_id, cid)
    if final_status != "done":
        print("\n❌ TEST 3 FAILED - Cannot continue")
        sys.exit(1)
    
    # TEST 4: Get creation file (HTML)
    html_ok = test_4_get_creation_file(token, org_id, cid)
    if not html_ok:
        print("\n❌ TEST 4 FAILED")
        sys.exit(1)
    
    # TEST 5: Regression - plain chat streaming
    chat_ok = test_5_regression_plain_chat(token, org_id)
    if not chat_ok:
        print("\n❌ TEST 5 FAILED")
        sys.exit(1)
    
    # SUMMARY
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✅ TEST 1 PASS: Create chat session")
    print(f"✅ TEST 2 PASS: Streaming webapp build (async, no step events)")
    print(f"   - Event types: {event_types}")
    print(f"   - CID: {cid}")
    print(f"✅ TEST 3 PASS: Poll creation status until done")
    print(f"✅ TEST 4 PASS: GET creation file returns HTML")
    print(f"✅ TEST 5 PASS: Plain chat streaming (regression)")
    print("\n🎉 ALL TESTS PASSED - Bug fix verified successfully!")


if __name__ == "__main__":
    main()
