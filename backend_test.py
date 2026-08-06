#!/usr/bin/env python3
"""
Test script for Chat with Files (session-pinned document Q&A) feature.
Tests the ability to pin a document to a chat session and ask multiple questions grounded in that document.
"""
import requests
import time
import os
import tempfile

# Configuration
BACKEND_URL = "https://git-hub-access-1.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

# Test document content with unique facts
TEST_DOC_CONTENT = """VibeVerse internal memo. Project codename: BLUE-PELICAN-7. The secret launch date is March 14, 2031. The lead engineer is Dr. Zara Kovac. The office is on floor 42 of the Nimbus Tower."""

def print_test(num, desc):
    print(f"\n{'='*80}")
    print(f"TEST {num}: {desc}")
    print('='*80)

def print_pass(msg):
    print(f"✅ PASS: {msg}")

def print_fail(msg):
    print(f"❌ FAIL: {msg}")

def main():
    print("="*80)
    print("CHAT WITH FILES (SESSION-PINNED DOCUMENT) TEST SUITE")
    print("="*80)
    
    # Step 0: Login
    print_test(0, "Admin Login")
    login_resp = requests.post(f"{BACKEND_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if login_resp.status_code != 200:
        print_fail(f"Login failed: {login_resp.status_code} {login_resp.text}")
        return
    
    token = login_resp.json().get("token")
    if not token:
        print_fail("No token in login response")
        return
    
    print_pass(f"Login successful, got token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get org_id
    me_resp = requests.get(f"{BACKEND_URL}/auth/me", headers=headers)
    if me_resp.status_code != 200:
        print_fail(f"Failed to get user info: {me_resp.status_code}")
        return
    
    org_id = me_resp.json().get("default_org_id")
    if not org_id:
        print_fail("No default_org_id in /auth/me response")
        return
    
    print_pass(f"Got org_id: {org_id}")
    
    # TEST 1: UPLOAD document
    print_test(1, "UPLOAD - Upload test document as .txt file")
    
    # Create temporary file with test content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(TEST_DOC_CONTENT)
        temp_file_path = f.name
    
    try:
        with open(temp_file_path, 'rb') as f:
            files = {'file': ('vibeverse_memo.txt', f, 'text/plain')}
            upload_resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/uploads", 
                                       headers=headers, files=files)
        
        if upload_resp.status_code != 200:
            print_fail(f"Upload failed: {upload_resp.status_code} {upload_resp.text}")
            return
        
        upload_data = upload_resp.json()
        required_fields = ['path', 'mime', 'kind', 'name', 'url']
        missing = [f for f in required_fields if f not in upload_data]
        if missing:
            print_fail(f"Upload response missing fields: {missing}")
            return
        
        if upload_data['kind'] != 'file':
            print_fail(f"Expected kind='file', got '{upload_data['kind']}'")
            return
        
        print_pass(f"Upload successful: {upload_data['name']}, path={upload_data['path']}, url={upload_data['url']}")
        
        # Store upload info for pinning
        doc_attachment = {
            'path': upload_data['path'],
            'mime': upload_data['mime'],
            'kind': upload_data['kind'],
            'name': upload_data['name'],
            'url': upload_data['url']
        }
        
    finally:
        os.unlink(temp_file_path)
    
    # TEST 2: CREATE SESSION
    print_test(2, "CREATE SESSION - Create new chat session")
    
    session_resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions",
                                headers=headers, json={})
    
    if session_resp.status_code != 200:
        print_fail(f"Session creation failed: {session_resp.status_code} {session_resp.text}")
        return
    
    session_data = session_resp.json()
    sid = session_data.get('id')
    if not sid:
        print_fail("No session id in response")
        return
    
    print_pass(f"Session created: {sid}")
    
    # TEST 3: PIN DOC
    print_test(3, "PIN DOC - Pin document to session")
    
    pin_resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{sid}/document",
                            headers=headers, json=doc_attachment)
    
    if pin_resp.status_code != 200:
        print_fail(f"Pin document failed: {pin_resp.status_code} {pin_resp.text}")
        return
    
    pin_data = pin_resp.json()
    if not pin_data.get('ok'):
        print_fail(f"Pin response ok=False: {pin_data}")
        return
    
    if 'pinned_doc' not in pin_data:
        print_fail("No pinned_doc in response")
        return
    
    pinned = pin_data['pinned_doc']
    if pinned.get('name') != doc_attachment['name']:
        print_fail(f"Pinned doc name mismatch: expected {doc_attachment['name']}, got {pinned.get('name')}")
        return
    
    print_pass(f"Document pinned successfully: {pinned}")
    
    # TEST 4: SESSION LIST REFLECTS PIN
    print_test(4, "SESSION LIST - Verify session list shows pinned_doc")
    
    sessions_resp = requests.get(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions", headers=headers)
    
    if sessions_resp.status_code != 200:
        print_fail(f"Get sessions failed: {sessions_resp.status_code} {sessions_resp.text}")
        return
    
    sessions = sessions_resp.json()
    target_session = None
    for s in sessions:
        if s.get('id') == sid:
            target_session = s
            break
    
    if not target_session:
        print_fail(f"Session {sid} not found in sessions list")
        return
    
    if 'pinned_doc' not in target_session:
        print_fail("Session in list does not have pinned_doc field")
        return
    
    if target_session['pinned_doc'].get('name') != doc_attachment['name']:
        print_fail(f"Session pinned_doc name mismatch: {target_session['pinned_doc']}")
        return
    
    print_pass(f"Session list correctly shows pinned_doc: {target_session['pinned_doc']['name']}")
    
    # TEST 5: GROUNDED ANSWER (KEY TEST)
    print_test(5, "GROUNDED ANSWER - Ask question answerable only from pinned doc (NO attachment field)")
    
    question1 = "What is the project codename and who is the lead engineer?"
    
    agent_resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{sid}/agent",
                              headers=headers, json={"message": question1})
    
    if agent_resp.status_code != 200:
        print_fail(f"Agent call failed: {agent_resp.status_code} {agent_resp.text}")
        return
    
    agent_data = agent_resp.json()
    content = agent_data.get('content', '')
    
    print(f"\n📝 Question: {question1}")
    print(f"🤖 Assistant response: {content}")
    
    # Check for required facts (case-insensitive)
    content_lower = content.lower()
    has_codename = 'blue-pelican-7' in content_lower or 'blue pelican 7' in content_lower
    has_engineer = 'zara kovac' in content_lower or 'dr. zara kovac' in content_lower or 'dr zara kovac' in content_lower
    
    if not has_codename:
        print_fail(f"Response does not contain 'BLUE-PELICAN-7' (case-insensitive)")
        print(f"Content: {content}")
        return
    
    if not has_engineer:
        print_fail(f"Response does not contain 'Zara Kovac' (case-insensitive)")
        print(f"Content: {content}")
        return
    
    print_pass(f"Response correctly includes BLUE-PELICAN-7 and Zara Kovac - pinned document is being used as context!")
    
    # TEST 6: FOLLOW-UP without re-attaching
    print_test(6, "FOLLOW-UP - Ask follow-up question without re-attaching document")
    
    question2 = "What floor is the office on?"
    
    agent_resp2 = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{sid}/agent",
                               headers=headers, json={"message": question2})
    
    if agent_resp2.status_code != 200:
        print_fail(f"Agent call failed: {agent_resp2.status_code} {agent_resp2.text}")
        return
    
    agent_data2 = agent_resp2.json()
    content2 = agent_data2.get('content', '')
    
    print(f"\n📝 Question: {question2}")
    print(f"🤖 Assistant response: {content2}")
    
    # Check for floor 42
    has_floor = '42' in content2 or 'forty-two' in content2.lower() or 'forty two' in content2.lower()
    
    if not has_floor:
        print_fail(f"Response does not mention floor 42")
        print(f"Content: {content2}")
        return
    
    print_pass(f"Response correctly mentions floor 42 - pinned document context persists across turns!")
    
    # TEST 7: UNPIN
    print_test(7, "UNPIN - Remove pinned document from session")
    
    unpin_resp = requests.delete(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{sid}/document",
                                headers=headers)
    
    if unpin_resp.status_code != 200:
        print_fail(f"Unpin failed: {unpin_resp.status_code} {unpin_resp.text}")
        return
    
    unpin_data = unpin_resp.json()
    if not unpin_data.get('ok'):
        print_fail(f"Unpin response ok=False: {unpin_data}")
        return
    
    print_pass("Document unpinned successfully")
    
    # Verify session list no longer shows pinned_doc
    sessions_resp2 = requests.get(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions", headers=headers)
    if sessions_resp2.status_code == 200:
        sessions2 = sessions_resp2.json()
        target_session2 = None
        for s in sessions2:
            if s.get('id') == sid:
                target_session2 = s
                break
        
        if target_session2:
            pinned_doc_value = target_session2.get('pinned_doc')
            if pinned_doc_value is None or pinned_doc_value == {}:
                print_pass("Session list confirms pinned_doc is null/absent after unpin")
            else:
                print_fail(f"Session still shows pinned_doc after unpin: {pinned_doc_value}")
                return
    
    # TEST 8: ERROR - Invalid session ID
    print_test(8, "ERROR - Pin document to non-existent session (expect 404)")
    
    fake_sid = "123456789012345678901234"  # Valid 24-hex ObjectId format but doesn't exist
    
    error_resp = requests.post(f"{BACKEND_URL}/orgs/{org_id}/chat/sessions/{fake_sid}/document",
                              headers=headers, json=doc_attachment)
    
    if error_resp.status_code == 404:
        print_pass(f"Correctly returned 404 for non-existent session")
    else:
        print_fail(f"Expected 404, got {error_resp.status_code}: {error_resp.text}")
        return
    
    # SUMMARY
    print("\n" + "="*80)
    print("🎉 ALL 8 TESTS PASSED!")
    print("="*80)
    print("\nSUMMARY:")
    print("✅ TEST 1: Document upload working (returns path, mime, kind='file', name, url)")
    print("✅ TEST 2: Session creation working")
    print("✅ TEST 3: Document pinning working (returns ok=true, pinned_doc)")
    print("✅ TEST 4: Session list reflects pinned document")
    print("✅ TEST 5: GROUNDED ANSWER - Assistant correctly answered using pinned doc context")
    print(f"           Response included: BLUE-PELICAN-7 and Zara Kovac")
    print("✅ TEST 6: FOLLOW-UP - Assistant answered follow-up question using pinned doc")
    print(f"           Response mentioned: floor 42")
    print("✅ TEST 7: Document unpinning working (pinned_doc becomes null)")
    print("✅ TEST 8: Error handling working (404 for invalid session)")
    print("\n" + "="*80)
    print("ACTUAL ASSISTANT RESPONSES:")
    print("="*80)
    print(f"\nQ1: {question1}")
    print(f"A1: {content}")
    print(f"\nQ2: {question2}")
    print(f"A2: {content2}")
    print("="*80)

if __name__ == "__main__":
    main()
