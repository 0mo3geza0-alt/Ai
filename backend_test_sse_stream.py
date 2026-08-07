#!/usr/bin/env python3
"""
Test the NEW agentic step-by-step website builder SSE stream for VibeVerse.
Tests the live SSE stream with step events (plan, s0-sN, build) and verifies
HTML generation, storage, and dynamic credit deduction.
"""
import os
import sys
import json
import time
import base64
import requests
from typing import List, Dict, Any

# Backend URL from frontend/.env
BACKEND_URL = "https://inspiring-wozniak-12.preview.emergentagent.com/api"

# Admin credentials from test_credentials.md
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

def login() -> tuple[str, str]:
    """Login as admin and return (token, org_id)."""
    print("🔐 Logging in as admin...")
    resp = requests.post(f"{BACKEND_URL}/auth/login", json={
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
    
    # Get org id from /api/auth/me
    me_resp = requests.get(f"{BACKEND_URL}/auth/me", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=30)
    if me_resp.status_code != 200:
        print(f"❌ GET /auth/me failed: {me_resp.status_code} {me_resp.text}")
        sys.exit(1)
    me_data = me_resp.json()
    org_id = me_data.get("default_org_id")
    if not org_id:
        print(f"❌ No default_org_id in /auth/me response: {me_data}")
        sys.exit(1)
    
    print(f"✅ Logged in successfully. Token: {token[:20]}..., Org ID: {org_id}")
    return token, org_id

def create_session(token: str, org_id: str) -> str:
    """Create a chat session and return session id."""
    print(f"\n📝 Creating chat session...")
    resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions", json={
        "title": "SSE Stream Test"
    }, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if resp.status_code != 200:
        print(f"❌ Create session failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    sid = data.get("id")
    if not sid:
        print(f"❌ No session id in response: {data}")
        sys.exit(1)
    print(f"✅ Session created: {sid}")
    return sid

def get_credits(token: str, org_id: str) -> float:
    """Get current org credits."""
    resp = requests.get(f"{BACKEND_URL}/orgs/{org_id}/usage", headers={
        "Authorization": f"Bearer {token}"
    }, timeout=30)
    if resp.status_code != 200:
        print(f"❌ GET /usage failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    credits = float(data.get("credits", 0))
    return credits

def test_sse_stream(token: str, org_id: str, sid: str) -> Dict[str, Any]:
    """
    Open SSE stream and collect all events.
    Returns dict with:
    - events: list of all events
    - event_types: ordered list of event types
    - step_events: list of (id, state) tuples for step events
    - final_done_event: the final 'done' event
    """
    print(f"\n🌊 Opening SSE stream...")
    url = f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{sid}/agent/stream"
    message = "Build a landing page for a coffee shop with a hero section and a menu section"
    
    # Open SSE stream with streaming=True
    resp = requests.post(url, json={"message": message}, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream"
    }, stream=True, timeout=180)
    
    if resp.status_code != 200:
        print(f"❌ SSE stream failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    
    print(f"✅ SSE stream opened (status 200)")
    print(f"📨 Collecting events...")
    
    events = []
    event_types = []
    step_events = []
    final_done_event = None
    
    # Read SSE stream line by line
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.strip():
            continue
        
        # SSE format: "data: {json}"
        if line.startswith("data: "):
            json_str = line[6:]  # Remove "data: " prefix
            try:
                event = json.loads(json_str)
                events.append(event)
                event_type = event.get("type")
                event_types.append(event_type)
                
                # Collect step events
                if event_type == "step":
                    step_id = event.get("id")
                    state = event.get("state")
                    step_events.append((step_id, state))
                    title = event.get("title", "")
                    detail = event.get("detail", "")
                    print(f"  📍 STEP: id={step_id}, state={state}, title={title[:30]}, detail={detail[:50]}")
                
                # Track final done event
                if event_type == "done":
                    final_done_event = event
                    print(f"  ✅ DONE event received")
                
                # Print other event types
                if event_type == "start":
                    action = event.get("action")
                    print(f"  🚀 START: action={action}")
                elif event_type == "delta":
                    pass  # Too verbose
                elif event_type == "error":
                    print(f"  ❌ ERROR: {event.get('detail')}")
                elif event_type == "artifact_html":
                    html_len = len(event.get("html", ""))
                    print(f"  📄 ARTIFACT_HTML: {html_len} chars")
            except json.JSONDecodeError as e:
                print(f"⚠️  Failed to parse event JSON: {json_str[:100]}")
                continue
    
    print(f"\n✅ Stream closed. Collected {len(events)} events.")
    return {
        "events": events,
        "event_types": event_types,
        "step_events": step_events,
        "final_done_event": final_done_event
    }

def verify_results(stream_data: Dict[str, Any], token: str, org_id: str, 
                   credits_before: float) -> Dict[str, Any]:
    """
    Verify all requirements (a-e) from the review request.
    Returns dict with pass/fail results for each requirement.
    """
    results = {}
    events = stream_data["events"]
    event_types = stream_data["event_types"]
    step_events = stream_data["step_events"]
    final_done = stream_data["final_done_event"]
    
    print(f"\n🔍 VERIFICATION RESULTS:")
    print(f"=" * 80)
    
    # (a) Early event with type=="start" and action=="webapp"
    print(f"\n(a) Checking for early 'start' event with action='webapp'...")
    start_events = [e for e in events if e.get("type") == "start"]
    if start_events:
        start_event = start_events[0]
        action = start_event.get("action")
        if action == "webapp":
            print(f"  ✅ PASS: Found 'start' event with action='webapp'")
            results["a_start_webapp"] = "PASS"
        else:
            print(f"  ❌ FAIL: 'start' event has action='{action}' (expected 'webapp')")
            results["a_start_webapp"] = f"FAIL (action={action})"
    else:
        print(f"  ❌ FAIL: No 'start' event found")
        results["a_start_webapp"] = "FAIL (no start event)"
    
    # (b) Multiple type=="step" events with specific ids and state transitions
    print(f"\n(b) Checking step events...")
    step_ids = [sid for sid, _ in step_events]
    step_states = {sid: [] for sid in set(step_ids)}
    for sid, state in step_events:
        step_states[sid].append(state)
    
    print(f"  Step IDs seen: {step_ids}")
    print(f"  Unique step IDs: {list(step_states.keys())}")
    
    # Check for "plan" step
    has_plan = "plan" in step_ids
    print(f"  - Has 'plan' step: {has_plan}")
    
    # Check for s0, s1, ... steps
    s_steps = [sid for sid in step_ids if sid.startswith("s") and sid[1:].isdigit()]
    print(f"  - Has s0..sN steps: {s_steps}")
    
    # Check for "build" step
    has_build = "build" in step_ids
    print(f"  - Has 'build' step: {has_build}")
    
    # Check state transitions (running -> done)
    all_transitions_ok = True
    for sid, states in step_states.items():
        if "running" in states and "done" in states:
            print(f"  - Step '{sid}': running -> done ✅")
        else:
            print(f"  - Step '{sid}': states={states} ⚠️")
            all_transitions_ok = False
    
    if has_plan and s_steps and has_build and all_transitions_ok:
        print(f"  ✅ PASS: Step events structure correct")
        results["b_step_events"] = "PASS"
        results["b_step_details"] = {
            "step_ids": step_ids,
            "step_states": step_states,
            "ordered_steps": [(sid, state) for sid, state in step_events]
        }
    else:
        print(f"  ❌ FAIL: Step events structure incomplete")
        results["b_step_events"] = "FAIL"
        results["b_step_details"] = {
            "has_plan": has_plan,
            "s_steps": s_steps,
            "has_build": has_build,
            "all_transitions_ok": all_transitions_ok
        }
    
    # (c) Final event with type=="done", message.kind=="webapp", message.media.url set
    print(f"\n(c) Checking final 'done' event...")
    if final_done:
        message = final_done.get("message", {})
        kind = message.get("kind")
        media = message.get("media", {})
        media_url = media.get("url")
        
        print(f"  - message.kind: {kind}")
        print(f"  - message.media.url: {media_url}")
        
        if kind == "webapp" and media_url:
            print(f"  ✅ PASS: Final 'done' event has kind='webapp' and media.url set")
            results["c_done_event"] = "PASS"
            results["c_media_url"] = media_url
        else:
            print(f"  ❌ FAIL: Final 'done' event missing kind='webapp' or media.url")
            results["c_done_event"] = f"FAIL (kind={kind}, url={media_url})"
            results["c_media_url"] = None
    else:
        print(f"  ❌ FAIL: No final 'done' event found")
        results["c_done_event"] = "FAIL (no done event)"
        results["c_media_url"] = None
    
    # (d) GET media.url returns HTML (200, contains "<html" or "<!doctype")
    print(f"\n(d) Checking media.url returns HTML...")
    media_url = results.get("c_media_url")
    if media_url:
        # media_url is relative like /api/orgs/{org}/creations/{cid}/file
        full_url = f"{BACKEND_URL.replace('/api', '')}{media_url}"
        print(f"  - Fetching: {full_url}")
        
        try:
            html_resp = requests.get(full_url, headers={
                "Authorization": f"Bearer {token}"
            }, timeout=30)
            
            if html_resp.status_code == 200:
                html_content = html_resp.text
                has_html_tag = "<html" in html_content.lower() or "<!doctype" in html_content.lower()
                
                print(f"  - Status: {html_resp.status_code}")
                print(f"  - Content length: {len(html_content)} chars")
                print(f"  - Contains HTML tags: {has_html_tag}")
                print(f"  - First 200 chars: {html_content[:200]}")
                
                if has_html_tag:
                    print(f"  ✅ PASS: media.url returns valid HTML")
                    results["d_html_content"] = "PASS"
                else:
                    print(f"  ❌ FAIL: media.url content doesn't contain HTML tags")
                    results["d_html_content"] = "FAIL (no HTML tags)"
            else:
                print(f"  ❌ FAIL: media.url returned {html_resp.status_code}")
                results["d_html_content"] = f"FAIL (status {html_resp.status_code})"
        except Exception as e:
            print(f"  ❌ FAIL: Error fetching media.url: {e}")
            results["d_html_content"] = f"FAIL (error: {e})"
    else:
        print(f"  ⚠️  SKIP: No media.url to test")
        results["d_html_content"] = "SKIP (no media.url)"
    
    # (e) Credits decreased
    print(f"\n(e) Checking credits decreased...")
    credits_after = get_credits(token, org_id)
    print(f"  - Credits before: {credits_before}")
    print(f"  - Credits after: {credits_after}")
    print(f"  - Delta: {credits_before - credits_after}")
    
    if credits_after < credits_before:
        print(f"  ✅ PASS: Credits decreased (dynamic deduction working)")
        results["e_credits_decreased"] = "PASS"
        results["e_credits_before"] = credits_before
        results["e_credits_after"] = credits_after
        results["e_credits_delta"] = credits_before - credits_after
    else:
        print(f"  ❌ FAIL: Credits did not decrease")
        results["e_credits_decreased"] = "FAIL"
        results["e_credits_before"] = credits_before
        results["e_credits_after"] = credits_after
    
    # Summary of event types
    print(f"\n📊 Event types received (ordered):")
    print(f"  {event_types}")
    results["event_types_ordered"] = event_types
    
    return results

def main():
    print("=" * 80)
    print("🧪 TESTING: Agentic Step-by-Step Website Builder SSE Stream")
    print("=" * 80)
    
    # Step 1: Login
    token, org_id = login()
    
    # Step 2: Create session
    sid = create_session(token, org_id)
    
    # Step 3: Note credits before
    print(f"\n💰 Checking credits before...")
    credits_before = get_credits(token, org_id)
    print(f"✅ Credits before: {credits_before}")
    
    # Step 4: Open SSE stream and collect events
    stream_data = test_sse_stream(token, org_id, sid)
    
    # Step 5: Verify all requirements
    results = verify_results(stream_data, token, org_id, credits_before)
    
    # Final summary
    print(f"\n" + "=" * 80)
    print(f"📋 FINAL SUMMARY")
    print(f"=" * 80)
    
    all_pass = all([
        results.get("a_start_webapp") == "PASS",
        results.get("b_step_events") == "PASS",
        results.get("c_done_event") == "PASS",
        results.get("d_html_content") == "PASS",
        results.get("e_credits_decreased") == "PASS"
    ])
    
    print(f"\n(a) Start event with action='webapp': {results.get('a_start_webapp')}")
    print(f"(b) Step events (plan, s0-sN, build): {results.get('b_step_events')}")
    print(f"(c) Final done event with webapp media: {results.get('c_done_event')}")
    print(f"(d) HTML content generated and stored: {results.get('d_html_content')}")
    print(f"(e) Credits decreased: {results.get('e_credits_decreased')}")
    
    if all_pass:
        print(f"\n✅ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
