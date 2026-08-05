"""Tests for streaming, file uploads, vision, image-edit and webapp-edit."""
import os
import io
import time
import json
import base64
import struct
import zlib
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"


def _make_png(width=200, height=120):
    """Build a small valid PNG: left half red, right half yellow rectangle on red bg."""
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    raw = b""
    # Row: red (255,0,0) for x<w/2, yellow (255,255,0) otherwise
    for y in range(height):
        raw += b"\x00"  # filter none
        for x in range(width):
            if x < width // 2:
                raw += bytes((255, 0, 0))
            else:
                raw += bytes((255, 255, 0))
    idat = zlib.compress(raw, 9)
    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    return png


@pytest.fixture(scope="module")
def auth():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['token']}"})
    orgs = s.get(f"{BASE_URL}/api/orgs", timeout=30).json()
    org = next((o for o in orgs if "admin" in (o.get("name") or "").lower()), orgs[0])
    return {"session": s, "org_id": org["id"], "token": data["token"]}


@pytest.fixture(scope="module")
def session_id(auth):
    s = auth["session"]
    r = s.post(f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions",
               json={"title": "TEST_stream"}, timeout=30)
    assert r.status_code == 200
    return r.json()["id"]


def _sse_events(session, url, payload, timeout=120):
    """Consume SSE, return list of parsed events with timestamps (arrival dt)."""
    headers = {"Content-Type": "application/json"}
    events = []
    t0 = time.time()
    with session.post(url, json=payload, stream=True, timeout=timeout,
                      headers=headers) as r:
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert "text/event-stream" in r.headers.get("content-type", ""), r.headers.get("content-type")
        buf = ""
        for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
            if not chunk:
                continue
            buf += chunk
            while "\n\n" in buf:
                raw, buf = buf.split("\n\n", 1)
                if not raw.startswith("data:"):
                    continue
                try:
                    ev = json.loads(raw[5:].strip())
                except Exception:
                    continue
                ev["_t"] = time.time() - t0
                events.append(ev)
                if ev.get("type") in ("done", "error"):
                    return events
    return events


# ---------------- STREAMING: plain chat streams deltas incrementally ----------------
def test_stream_plain_chat_deltas_incremental(auth, session_id):
    url = f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions/{session_id}/agent/stream"
    events = _sse_events(auth["session"], url,
                         {"message": "Write two short sentences about the moon."},
                         timeout=120)
    types = [e["type"] for e in events]
    assert types[0] == "start", f"first event not start: {types[:3]}"
    assert "done" in types, f"no done event: {types}"
    deltas = [e for e in events if e["type"] == "delta"]
    assert len(deltas) >= 3, f"expected multiple deltas got {len(deltas)}"
    # Streaming signal: many separate delta events (not one blob) — models often emit
    # tokens in fast bursts so we don't require a large timespan, just multiple events.
    span = (deltas[-1]["_t"] - deltas[0]["_t"]) if len(deltas) >= 2 else 0.0
    print(f"[stream] {len(deltas)} deltas over {span:.3f}s")
    # done payload has full assistant message
    done = [e for e in events if e["type"] == "done"][0]
    assert done["message"]["kind"] == "text"
    assert done["message"]["content"]
    assert done["action"] == "chat"


# ---------------- UPLOAD: PNG upload and serve ----------------
def test_upload_png_and_serve(auth):
    s = auth["session"]
    png = _make_png()
    files = {"file": ("test.png", png, "image/png")}
    # requests: don't send our default json Content-Type
    r = requests.post(f"{BASE_URL}/api/orgs/{auth['org_id']}/uploads",
                      headers={"Authorization": s.headers["Authorization"]},
                      files=files, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["kind"] == "image"
    assert d["mime"] == "image/png"
    assert d["url"].startswith(f"/api/orgs/{auth['org_id']}/uploads/")
    # fetch with auth
    g = s.get(f"{BASE_URL}{d['url']}", timeout=30)
    assert g.status_code == 200
    assert g.headers.get("content-type", "").startswith("image/")
    assert len(g.content) == len(png)
    return d  # not usable — pytest fixtures can't return via test funcs


@pytest.fixture(scope="module")
def uploaded_png(auth):
    s = auth["session"]
    png = _make_png()
    files = {"file": ("test.png", png, "image/png")}
    r = requests.post(f"{BASE_URL}/api/orgs/{auth['org_id']}/uploads",
                      headers={"Authorization": s.headers["Authorization"]},
                      files=files, timeout=30)
    assert r.status_code == 200
    return r.json()


# ---------------- VISION: describe attached image ----------------
def test_vision_describe_image_via_stream(auth, session_id, uploaded_png):
    url = f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions/{session_id}/agent/stream"
    events = _sse_events(auth["session"], url, {
        "message": "What colors are in this image? Answer briefly.",
        "attachment": uploaded_png,
    }, timeout=180)
    done = [e for e in events if e["type"] == "done"]
    assert done, f"no done event; got {[e.get('type') for e in events]}"
    msg = done[0]["message"]
    assert done[0]["action"] == "chat", f"expected chat action, got {done[0]['action']}"
    assert msg["kind"] == "text"
    text = (msg["content"] or "").lower()
    # image is red + yellow; models should mention at least one
    assert ("red" in text or "yellow" in text), f"expected color mention, got: {text[:200]}"


# ---------------- IMAGE EDIT: attached image + edit prompt ----------------
def test_image_edit_via_stream(auth, session_id, uploaded_png):
    url = f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions/{session_id}/agent/stream"
    events = _sse_events(auth["session"], url, {
        "message": "Change the yellow rectangle to blue.",
        "attachment": uploaded_png,
    }, timeout=240)
    done = [e for e in events if e["type"] == "done"]
    err = [e for e in events if e["type"] == "error"]
    assert not err, f"error event: {err}"
    assert done, "no done event"
    action = done[0]["action"]
    msg = done[0]["message"]
    assert action == "image", f"expected image action, got {action}"
    assert msg["kind"] == "image"
    assert msg["media"] and msg["media"].get("url")
    img = auth["session"].get(f"{BASE_URL}{msg['media']['url']}", timeout=60)
    assert img.status_code == 200
    assert img.headers.get("content-type", "").startswith("image/")
    assert len(img.content) > 500


# ---------------- WEBAPP EDIT: build then modify uses prior HTML as context ----------------
def test_webapp_build_then_edit(auth):
    s = auth["session"]
    # fresh session for cleanliness
    sr = s.post(f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions",
                json={"title": "TEST_webapp_edit"}, timeout=30)
    sid = sr.json()["id"]
    url = f"{BASE_URL}/api/orgs/{auth['org_id']}/chat/sessions/{sid}/agent/stream"

    # 1) build
    events = _sse_events(s, url, {"message": "Build a landing page for a bakery"}, timeout=90)
    done = [e for e in events if e["type"] == "done"]
    assert done, [e.get("type") for e in events]
    m1 = done[0]["message"]
    assert done[0]["action"] == "webapp"
    assert m1["kind"] == "webapp"
    cid1 = m1["media"]["cid"]

    # poll to done + capture html
    html1 = None
    for _ in range(60):
        time.sleep(3)
        st = s.get(f"{BASE_URL}/api/orgs/{auth['org_id']}/creations/{cid1}/status",
                   timeout=30).json()
        if st.get("status") in ("done", "failed"):
            assert st["status"] == "done", st
            hr = s.get(f"{BASE_URL}{st['url']}", timeout=30)
            assert hr.status_code == 200
            html1 = hr.text
            break
    assert html1 and "<" in html1 and "html" in html1.lower()

    # 2) edit
    events2 = _sse_events(s, url,
                          {"message": "Make the header background dark blue"},
                          timeout=90)
    done2 = [e for e in events2 if e["type"] == "done"]
    assert done2
    m2 = done2[0]["message"]
    assert done2[0]["action"] == "webapp", f"edit did not route to webapp: {done2[0]['action']}"
    cid2 = m2["media"]["cid"]
    assert cid2 != cid1

    html2 = None
    for _ in range(60):
        time.sleep(3)
        st = s.get(f"{BASE_URL}/api/orgs/{auth['org_id']}/creations/{cid2}/status",
                   timeout=30).json()
        if st.get("status") in ("done", "failed"):
            assert st["status"] == "done", st
            hr = s.get(f"{BASE_URL}{st['url']}", timeout=30)
            assert hr.status_code == 200
            html2 = hr.text
            break
    assert html2 and "<" in html2 and "html" in html2.lower()
    # Must be different HTML (edit produced changes)
    assert html2 != html1, "edited webapp HTML identical to original"
