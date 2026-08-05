import os
import uuid
import time
import base64
import requests
from urllib.parse import quote
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta
from emergentintegrations.llm.openai import OpenAITextToSpeech
from core.logging import logger

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
INTEGRATION_PROXY_BASE = os.environ.get("INTEGRATION_PROXY_URL", "https://integrations.emergentagent.com").rstrip("/")
FAL_BASE = f"{INTEGRATION_PROXY_BASE}/api/v1/fal"

# Available models exposed to the frontend (Model Gateway)
MODELS = {
    "openai": ["gpt-5.6-terra", "gpt-5.4", "gpt-5.4-mini"],
    "anthropic": ["claude-sonnet-5", "claude-sonnet-4-6"],
    "gemini": ["gemini-3.1-pro-preview", "gemini-3-flash-preview"],
}
DEFAULT_TEXT = ("openai", "gpt-5.6-terra")
IMAGE_MODEL = ("gemini", "gemini-3.1-flash-image-preview")
# fallback chain if the primary provider errors
FALLBACK = [("anthropic", "claude-sonnet-5"), ("gemini", "gemini-3-flash-preview")]

TTS_VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]


def _new_chat(session_id: str, system: str, provider: str, model: str) -> LlmChat:
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=system)
    chat.with_model(provider, model)
    return chat


async def generate_text(session_id: str, system: str, prompt: str,
                        provider: str = None, model: str = None, history: str = "") -> str:
    provider = provider or DEFAULT_TEXT[0]
    model = model or DEFAULT_TEXT[1]
    full = (history + "\n" + prompt) if history else prompt
    chain = [(provider, model)] + [c for c in FALLBACK if c != (provider, model)]
    last_err = None
    for prov, mod in chain:
        try:
            chat = _new_chat(session_id, system, prov, mod)
            return await chat.send_message(UserMessage(text=full))
        except Exception as e:
            last_err = e
            logger.error("LLM %s/%s failed, trying fallback: %s", prov, mod, e)
    raise RuntimeError(f"All models failed: {last_err}")


async def stream_text(session_id: str, system: str, prompt: str,
                      provider: str = None, model: str = None, history: str = ""):
    """Async generator yielding text token deltas as they arrive from the model."""
    provider = provider or DEFAULT_TEXT[0]
    model = model or DEFAULT_TEXT[1]
    full = (history + "\n" + prompt) if history else prompt
    chat = _new_chat(session_id, system, provider, model)
    async for event in chat.stream_message(UserMessage(text=full)):
        if isinstance(event, TextDelta) and event.content:
            yield event.content


async def generate_image(prompt: str):
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"img-{uuid.uuid4().hex}", system_message="You are an AI image generator.")
    chat.with_model(*IMAGE_MODEL).with_params(modalities=["image", "text"])
    _, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
    if not images:
        raise RuntimeError("No image generated")
    img = images[0]
    return img["mime_type"], base64.b64decode(img["data"])


async def generate_audio(text: str, voice: str = "alloy", model: str = "tts-1") -> bytes:
    if voice not in TTS_VOICES:
        voice = "alloy"
    tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
    return await tts.generate_speech(text=text[:4096], model=model, voice=voice, response_format="mp3")


# ---------------------------------------------------------------- fal.ai (Universal Key: queue inference only)
VIDEO_ENDPOINT = "fal-ai/ltx-video"
MUSIC_ENDPOINT = "fal-ai/stable-audio"


def _fal_headers():
    return {"Authorization": f"Bearer {EMERGENT_LLM_KEY}", "Content-Type": "application/json"}


def _fal_run(endpoint_id: str, payload: dict, timeout: int = 240) -> dict:
    """Blocking submit -> poll -> result via the Emergent integration proxy. Run in a thread."""
    submit = requests.post(f"{FAL_BASE}/proxy", headers={**_fal_headers(), "X-Fal-Target-Url": f"https://queue.fal.run/{endpoint_id}"},
                           json=payload, timeout=60)
    if submit.status_code == 402:
        raise PermissionError("insufficient_universal_credits")
    submit.raise_for_status()
    data = submit.json()
    status_url, response_url = data["status_url"], data["response_url"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = requests.get(status_url, headers=_fal_headers(), timeout=30)
        st.raise_for_status()
        status = (st.json().get("status") or "").upper()
        if status in {"COMPLETED", "OK"}:
            res = requests.get(response_url, headers=_fal_headers(), timeout=60)
            res.raise_for_status()
            return res.json()
        if status in {"FAILED", "CANCELLED", "CANCELED", "ERROR"}:
            raise RuntimeError(f"fal generation {status}")
        time.sleep(2)
    raise TimeoutError("fal generation timed out")


def _download(url: str) -> bytes:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.content


def generate_video(prompt: str) -> tuple[bytes, str]:
    result = _fal_run(VIDEO_ENDPOINT, {"prompt": prompt})
    video = result.get("video") or {}
    url = video.get("url")
    if not url:
        raise RuntimeError("No video returned")
    return _download(url), video.get("content_type", "video/mp4")


def generate_music(prompt: str, seconds: int = 30) -> tuple[bytes, str]:
    result = _fal_run(MUSIC_ENDPOINT, {"prompt": prompt, "seconds_total": max(5, min(seconds, 60))})
    audio = result.get("audio_file") or {}
    url = audio.get("url")
    if not url:
        raise RuntimeError("No audio returned")
    return _download(url), audio.get("content_type", "audio/mpeg")


# ---------------------------------------------------------------- web research (DuckDuckGo, no key)
def web_search(query: str, max_results: int = 6) -> list[dict]:
    try:
        r = requests.get("https://api.duckduckgo.com/", params={"q": query, "format": "json", "no_html": 1, "t": "nexus"}, timeout=20)
        data = r.json()
    except Exception as e:
        logger.error("DDG search failed: %s", e)
        return []
    out = []
    def walk(topics):
        for t in topics:
            if "Topics" in t:
                walk(t["Topics"])
            elif t.get("FirstURL") and t.get("Text"):
                out.append({"title": t["Text"][:120], "url": t["FirstURL"], "snippet": t["Text"]})
    walk(data.get("RelatedTopics", []))
    if data.get("AbstractText"):
        out.insert(0, {"title": data.get("Heading", query), "url": data.get("AbstractURL", ""), "snippet": data["AbstractText"]})
    return out[:max_results]
