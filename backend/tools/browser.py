"""Browser Automation — Phase 8 / Module.

Lightweight server-side browsing: fetch a URL and extract its readable text.
No extra dependencies (regex-based HTML → text). Good enough for agent grounding.
"""
import re
import requests

from core.logging import logger

URL_RE = re.compile(r"https?://[^\s)>\]\"']+", re.I)
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def find_url(text: str) -> str | None:
    m = URL_RE.search(text or "")
    if not m:
        return None
    return m.group(0).rstrip(".,);]”’")


def _clean_html(html: str) -> tuple[str, str]:
    tm = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = re.sub(r"\s+", " ", tm.group(1)).strip() if tm else ""
    # drop non-content blocks
    html = re.sub(r"<(script|style|noscript|svg|head|nav|footer|form)[^>]*>.*?</\1>",
                  " ", html, flags=re.I | re.S)
    # turn block-level closers into line breaks
    html = re.sub(r"(?i)<\s*(br|/p|/div|/li|/h[1-6]|/tr|/section|/article)\s*/?>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    replacements = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
                    "&quot;": '"', "&#39;": "'", "&rsquo;": "'", "&mdash;": "—"}
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return title, text.strip()


def fetch_url(url: str, max_chars: int = 4000, timeout: int = 20) -> dict:
    """Fetch a URL and return {url, ok, title, text, truncated}."""
    if not re.match(r"^https?://", url or "", re.I):
        url = "https://" + (url or "").strip()
    try:
        r = requests.get(url, headers={"User-Agent": _UA,
                                       "Accept": "text/html,application/xhtml+xml,*/*"},
                         timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        logger.error("browse fetch failed %s: %s", url, e)
        return {"url": url, "ok": False, "error": str(e), "title": "", "text": ""}
    ctype = r.headers.get("content-type", "").lower()
    body = r.text or ""
    if "html" in ctype or "<html" in body[:2000].lower():
        title, text = _clean_html(body)
    else:
        title, text = "", body
    full_len = len(text)
    return {"url": r.url, "ok": True, "title": title,
            "text": text[:max_chars], "truncated": full_len > max_chars,
            "chars": min(full_len, max_chars)}


def browse(query_or_url: str, max_chars: int = 4000) -> dict:
    url = find_url(query_or_url) or (query_or_url or "").strip()
    return fetch_url(url, max_chars=max_chars)
