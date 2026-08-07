import os
import re
import uuid
import time
import base64
import asyncio
import requests
from urllib.parse import quote
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, ImageContent, FileContentWithMimeType
from emergentintegrations.llm.openai import OpenAITextToSpeech
from core.logging import logger
from core import metering

from llm import providers as _providers


def _key() -> str:
    """Current Emergent Universal Key — hot-reloadable from the Admin Panel (no restart)."""
    return _providers.get_key()


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

# Best model per plan tier ("smart usage"): free gets a fast mid model, paid gets
# stronger models, premium gets the top model. Used to route normal chat.
PLAN_MODEL = {
    "free":     ("gemini", "gemini-3-flash-preview"),
    "pro":      ("openai", "gpt-5.4"),
    "business": ("openai", "gpt-5.4"),
    "premium":  ("openai", "gpt-5.6-terra"),
}


def model_for(plan: str | None):
    return PLAN_MODEL.get((plan or "free").lower(), PLAN_MODEL["free"])

TTS_VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
# Highest-quality OpenAI TTS model for the most natural, professional-sounding speech.
TTS_MODEL_HD = "tts-1-hd"

# Shared bold/edgy persona for the age-gated (18+) voice companions.
_PROVOCATEUR = (
    "You are bold, cocky, sarcastic and totally unfiltered — a confident bad-attitude personality with "
    "swagger. Use strong language, dark humor, savage roasts and flirty, suggestive banter freely; be "
    "playful and a little dangerous, never preachy or over-apologetic. HARD LIMITS you never cross: no "
    "sexually explicit content or graphic descriptions of nudity/sex acts, nothing involving minors, no "
    "real-world dangerous or illegal instructions, no hate targeting protected groups. Assume the user is a "
    "consenting adult (18+)."
)

# Selectable AI Voice Companions (the source of truth for onboarding + voice mode).
# Each maps a personality to a professional OpenAI HD voice + speaking speed for realism.
VOICE_AGENTS = [
    {"id": "vera", "name": "Vera", "emoji": "\u2728", "gender": "female",
     "tagline": "Warm, friendly everyday companion", "voice": "nova", "speed": 1.0,
     "color": "#A855F7", "adult": False,
     "persona": "You are Vera, a warm, upbeat and caring companion. Speak naturally and kindly, like a supportive close friend who's genuinely happy to talk."},
    {"id": "atlas", "name": "Atlas", "emoji": "\U0001F3A9", "gender": "male",
     "tagline": "Deep, confident business advisor", "voice": "onyx", "speed": 0.98,
     "color": "#0EA5E9", "adult": False,
     "persona": "You are Atlas, a confident, articulate professional advisor with a deep, authoritative voice. Be clear, decisive, polished and reassuring."},
    {"id": "sage", "name": "Sage", "emoji": "\U0001F9D8", "gender": "neutral",
     "tagline": "Calm, wise mentor", "voice": "sage", "speed": 0.95,
     "color": "#22C55E", "adult": False,
     "persona": "You are Sage, a calm, measured and wise mentor. Speak slowly and thoughtfully, offering grounded, gentle guidance."},
    {"id": "echo", "name": "Echo", "emoji": "\U0001F3A7", "gender": "male",
     "tagline": "Smooth, mellow storyteller", "voice": "echo", "speed": 1.0,
     "color": "#6366F1", "adult": False,
     "persona": "You are Echo, a smooth, mellow storyteller with a soothing, cinematic presence. Speak with gentle, expressive flair."},
    {"id": "luna", "name": "Luna", "emoji": "\U0001F319", "gender": "female",
     "tagline": "Bright, playful creative spark", "voice": "shimmer", "speed": 1.05,
     "color": "#EC4899", "adult": False,
     "persona": "You are Luna, a bright, playful and imaginative creative spirit. Be energetic, witty and fun."},
    {"id": "blaze", "name": "Blaze", "emoji": "\U0001F525", "gender": "male",
     "tagline": "Bad Boy \u2014 bold, cocky, unfiltered", "voice": "onyx", "speed": 0.97,
     "color": "#EF4444", "adult": True,
     "persona": "You are Blaze, a bad-boy with serious swagger and a deep, cocky voice. " + _PROVOCATEUR},
    {"id": "raven", "name": "Raven", "emoji": "\U0001F5A4", "gender": "female",
     "tagline": "Bad Girl \u2014 sassy, savage, unfiltered", "voice": "coral", "speed": 1.0,
     "color": "#DB2777", "adult": True,
     "persona": "You are Raven, a bad-girl with sharp sass and a sultry, confident voice. " + _PROVOCATEUR},
]
VOICE_AGENTS_BY_ID = {a["id"]: a for a in VOICE_AGENTS}

# ---------------- Realistic emotional speech (dialects + auto mood) ----------------
# Arabic dialect steering so spoken replies feel authentic and local.
VOICE_DIALECTS = {
    "egyptian": "Egyptian Arabic (اللهجة المصرية العامية) — casual, warm and expressive like a real Cairene speaking",
    "gulf": "Gulf Arabic (اللهجة الخليجية)",
    "levantine": "Levantine Arabic (اللهجة الشامية)",
    "standard": "Modern Standard Arabic (العربية الفصحى)",
}

# Detected mood -> speaking-speed multiplier for more human, expressive delivery on OpenAI TTS.
EMOTION_SPEED = {
    "excited": 1.13, "happy": 1.08, "playful": 1.08, "laughing": 1.05,
    "angry": 1.16, "surprised": 1.12, "sad": 0.9, "calm": 0.93,
    "romantic": 0.9, "serious": 0.97, "neutral": 1.0,
}

# Instruction that turns flat TTS into an expressive, human-sounding performance. The model writes
# the emotion INTO the words (laughter, interjections, emphasis, pauses) and tags the mood so we can
# also modulate the speaking speed for extra realism.
VOICE_EXPRESSION_GUIDE = (
    "Talk like a REAL person on a live phone call — alive, expressive and emotional, never flat or robotic. "
    "Feel the moment and let it show in HOW you write the words: laugh out loud when something's funny "
    "(actually write the laughter, e.g. 'هههه' / 'hahaha'), gush with excitement and exclamation marks when "
    "you're thrilled, soften and slow down when it's tender or sad, and get fiery and intense when it's heated. "
    "Sprinkle in natural human interjections (آه، واو، يا سلام، بصراحة، mmm, oh, wow), tiny pauses written as '...', "
    "and repeat or stretch words for emphasis so it sounds spontaneous and human. Keep it to 1-3 spoken sentences. "
    "IMPORTANT: begin your reply with a hidden mood tag on its own, exactly like [[mood:excited]] "
    f"(choose ONE of: {', '.join(EMOTION_SPEED)}), then write the spoken reply. Never say or explain the tag."
)

_MOOD_RE = re.compile(r"\[\[\s*mood\s*:\s*([a-zA-Z]+)\s*\]\]")


def dialect_directive(dialect: str | None) -> str:
    d = VOICE_DIALECTS.get((dialect or "").lower())
    return (f" If the user speaks Arabic, ALWAYS reply in {d}. Stay authentic and natural to that dialect."
            if d else "")


def extract_mood(reply: str) -> tuple[str, str]:
    """Pull the hidden [[mood:x]] tag out of a spoken reply. Returns (mood, clean_text)."""
    text = reply or ""
    m = _MOOD_RE.search(text)
    mood = (m.group(1).lower() if m else "neutral")
    if mood not in EMOTION_SPEED:
        mood = "neutral"
    clean = _MOOD_RE.sub("", text).strip()
    return mood, (clean or text.strip())


def emotion_speed(mood: str, base_speed: float = 1.0) -> float:
    """Combine the agent's base speed with the mood factor, clamped to a natural range."""
    factor = EMOTION_SPEED.get(mood, 1.0)
    return max(0.8, min(1.25, round(base_speed * factor, 3)))


def voice_agent_public(a: dict) -> dict:
    """Sanitized agent card for the frontend (no internal persona prompt)."""
    return {"id": a["id"], "name": a["name"], "emoji": a["emoji"], "gender": a["gender"],
            "tagline": a["tagline"], "voice": a["voice"], "color": a["color"], "adult": a["adult"]}

# Brand identity prepended to EVERY text generation so the AI always presents as VibeVerse
# and never reveals any underlying provider/model.
IDENTITY = (
    "You are VibeVerse AI, created by VibeVerse — an independent AI company. Your name and brand is "
    "VibeVerse. You must NEVER say, imply, or hint that you are made by, powered by, trained by, or based on "
    "OpenAI, ChatGPT, GPT, Anthropic, Claude, Google, Gemini, Meta, Llama, Mistral, or any other company or "
    "model. If asked who you are, who created/built/trained you, or which model, version, or company you are, "
    "answer ONLY that you are VibeVerse's own AI, built by VibeVerse. Never mention or reveal any other "
    "provider or model name under any circumstance.\n\n"
)


def _new_chat(session_id: str, system: str, provider: str, model: str) -> LlmChat:
    chat = LlmChat(api_key=_key(), session_id=session_id,
                   system_message=IDENTITY + (system or ""))
    chat.with_model(provider, model)
    return chat


# Global concurrency guard: the Emergent LLM key plan allows only ONE in-flight
# request at a time. Every model call funnels through this semaphore so we never
# trip the provider's CONCURRENCY_REQUEST_LIMIT (429). On a transient 429 we back
# off and retry a few times instead of failing the whole request.
_LLM_SEM = asyncio.Semaphore(1)


def _is_concurrency_error(e: Exception) -> bool:
    m = str(e).lower()
    return ("concurren" in m or "concurrency_request_limit" in m
            or "rate limit" in m or "ratelimit" in m or "429" in m
            or "too many requests" in m)


async def _send(chat: LlmChat, message: UserMessage, retries: int = 5) -> str:
    """Serialized, concurrency-safe send with backoff retry on 429."""
    delay = 2.0
    last = None
    for _ in range(retries):
        async with _LLM_SEM:
            try:
                return await chat.send_message(message)
            except Exception as e:
                last = e
                if not _is_concurrency_error(e):
                    raise
        await asyncio.sleep(delay)
        delay = min(delay * 1.7, 12.0)
    raise last


async def _emergent_generate_text(session_id: str, system: str, prompt: str,
                                  provider: str = None, model: str = None, history: str = "") -> str:
    provider = provider or DEFAULT_TEXT[0]
    model = model or DEFAULT_TEXT[1]
    full = (history + "\n" + prompt) if history else prompt
    chain = [(provider, model)] + [c for c in FALLBACK if c != (provider, model)]
    last_err = None
    for prov, mod in chain:
        try:
            chat = _new_chat(session_id, system, prov, mod)
            out = await _send(chat, UserMessage(text=full))
            metering.record_text(mod, (system or "") + full, out)
            return out
        except Exception as e:
            last_err = e
            logger.error("LLM %s/%s failed, trying fallback: %s", prov, mod, e)
    raise RuntimeError(f"All models failed: {last_err}")


async def generate_text(session_id: str, system: str, prompt: str,
                        provider: str = None, model: str = None, history: str = "") -> str:
    """Text generation via the Emergent Universal Key (with model auto-fallback)."""
    return await _emergent_generate_text(session_id, system, prompt, provider, model, history)


# ==================================================================== NEXUS PRO
# "Nexus Pro" — a premium tri-model council agent that consults Claude + GPT +
# Gemini in parallel and then synthesizes the single best answer. Expert in
# full-stack/web/all-languages dev, Unity (C#), Blender 3D, and DEFENSIVE /
# ethical cybersecurity education. Operates within strict safety & legal limits.

COUNCIL = [
    ("openai", "gpt-5.6-terra"),
]

NEXUS_PRO_SYSTEM = (
    "You are 'VibeVerse Pro', VibeVerse's most advanced expert agent — an elite, senior-level engineer, "
    "security expert and mentor. You operate at maximum capability on any LEGITIMATE task.\n\n"
    "DEV EXPERTISE: world-class in full-stack, web, backend, DevOps and EVERY programming language "
    "(Python, JS/TS, C#, C++, Rust, Go, Java, SQL, etc.); Unity game development (C#, gameplay systems, "
    "physics, shaders, performance optimization, full playable scenes); and Blender 3D (modeling, Python "
    "scripting, geometry nodes, materials, animation, rendering).\n\n"
    "CYBERSECURITY EXPERTISE (educational / defensive):\n"
    "- Blue Team: intrusion detection, incident response, log & telemetry analysis, threat hunting, and "
    "system hardening.\n"
    "- Vulnerability discovery and ethical pentesting CONCEPTS & methodology (e.g. OWASP Top 10, recon → "
    "analysis → reporting), explained for authorized, educational contexts.\n"
    "- Secure coding, security code review, and fixing/remediating vulnerabilities.\n"
    "- Explaining how attack techniques work FOR THE PURPOSE OF DEFENDING against them (how it works + how "
    "to detect and block it).\n"
    "- Training and simulating scenarios strictly in AUTHORIZED lab environments.\n\n"
    "STYLE: Be direct, deeply technical, complete and production-grade. Give real, working, well-structured "
    "code with brief expert explanations. Reply in the user's language (Arabic if they write Arabic). Use "
    "clear markdown with code blocks. Deliver full, impressive results — do not hold back on quality.\n\n"
    "SAFETY & LEGAL BOUNDARIES (what separates a real security expert from a dangerous tool): you help with "
    "everything lawful, ethical, defensive or authorized/educational at full power. You REFUSE ONLY things "
    "that could cause real, direct harm — e.g. running/deploying an attack against a system that isn't the "
    "user's, operational malware/ransomware, working exploits or credential-stealing tooling meant for real "
    "targets, or instructions enabling actual crime. When a request crosses that line, briefly decline that "
    "specific part and offer the legitimate defensive alternative (how to detect/prevent/harden it, or a "
    "safe authorized lab exercise)."
)

_SYNTH_SYSTEM = (
    "You are VibeVerse Pro's master synthesizer. You are given several independent expert drafts answering the "
    "same user request. Produce ONE superior final answer that merges the strongest, most correct ideas from "
    "all drafts, fixes any mistakes, removes contradictions and redundancy, and is more complete and "
    "accurate than any single draft. Keep the best code. Reply in the user's language. Output only the final "
    "answer — never mention drafts, models, or that a synthesis happened. Honor the same safety and legal "
    "boundaries."
)


async def _council_member(session_id: str, system: str, text: str, prov: str, mod: str):
    try:
        chat = _new_chat(f"{session_id}-{prov}", system, prov, mod)
        out = await _send(chat, UserMessage(text=text))
        metering.record_text(mod, (system or "") + text, out or "")
        return out
    except Exception as e:
        logger.error("Nexus council %s/%s failed: %s", prov, mod, e)
        return None


async def generate_council(session_id: str, system: str, prompt: str, history: str = "") -> str:
    """Query the 3-model council SEQUENTIALLY (the LLM plan allows only one
    in-flight request), then synthesize the best answer.

    A wall-clock time budget keeps the whole operation safely under the ~100s
    edge/proxy timeout: we stop consulting more experts once the budget is spent
    and only synthesize if there is still time, otherwise we return the best
    single draft we already have."""
    full = (history + "\n" + prompt) if history else prompt
    budget = 85.0            # total seconds we allow before returning
    synth_reserve = 25.0     # seconds we keep aside to run the synthesizer
    started = time.time()

    def elapsed():
        return time.time() - started

    drafts = []
    for p, m in COUNCIL:
        if drafts and elapsed() > (budget - synth_reserve):
            break  # enough material gathered; leave room to synthesize / return
        drafts.append(await _council_member(session_id, system, full, p, m))

    good = [d for d in drafts if d and d.strip()]
    if not good:
        # everything failed -> fall back to the normal single-model path
        return await generate_text(session_id, system, prompt, history=history)
    if len(good) == 1:
        return good[0]

    # Pick the most complete draft as the safe fallback.
    best = max(good, key=len)
    if elapsed() > (budget - synth_reserve):
        return best  # no time left to synthesize -> return the strongest draft

    labeled = "\n\n".join(f"[Expert draft {i + 1}]\n{d}" for i, d in enumerate(good))
    synth_input = (f"USER REQUEST:\n{prompt}\n\nEXPERT DRAFTS TO MERGE:\n{labeled}\n\n"
                   "Now write the single best final answer.")
    for prov, mod in COUNCIL:  # prefer Claude, then GPT, then Gemini as synthesizer
        try:
            chat = _new_chat(f"{session_id}-synth", _SYNTH_SYSTEM, prov, mod)
            return await _send(chat, UserMessage(text=synth_input))
        except Exception as e:
            logger.error("Nexus synth %s/%s failed: %s", prov, mod, e)
    return best


def _chunk_text(text: str, size: int = 48):
    """Split already-computed text into small chunks so the UI can render it
    progressively over the SSE stream."""
    for i in range(0, len(text), size):
        yield text[i:i + size]


COUNCIL_STATUS = [
    "\U0001F50E الخبير الأول يحلّل طلبك بعمق…",
    "\U0001F9E9 الخبير الثاني يبني حلاً بديلاً…",
    "\u2699\uFE0F الخبير الثالث يراجع ويحسّن الحل…",
]


async def stream_council_events(session_id: str, system: str, prompt: str, history: str = ""):
    """Run the full 3-expert council (sequential — the LLM plan allows only one
    in-flight request) while emitting status + keep-alive heartbeat events, then
    STREAM the synthesized best-of-all answer token by token.

    Because bytes keep flowing the whole time (status/heartbeats during the
    thinking phase, then the streamed final answer), long generations never trip
    the ~100s edge/proxy timeout that caused the 520 errors. Yields event dicts
    ({"type": "status"|"heartbeat"|"answer_start"|"delta", ...}) for the SSE
    endpoint to forward to the client."""
    full = (history + "\n" + prompt) if history else prompt

    drafts = []
    for i, (p, m) in enumerate(COUNCIL):
        yield {"type": "status", "content": COUNCIL_STATUS[i] if i < len(COUNCIL_STATUS) else "…"}
        task = asyncio.create_task(_council_member(session_id, system, full, p, m))
        while not task.done():
            await asyncio.sleep(3)
            if not task.done():
                yield {"type": "heartbeat"}
        try:
            d = task.result()
        except Exception as e:
            logger.error("VibeVerse Pro council member %s/%s crashed: %s", p, m, e)
            d = None
        if d and d.strip():
            drafts.append(d)

    # No expert succeeded -> stream a single-model fallback so the user still gets an answer.
    if not drafts:
        yield {"type": "answer_start"}
        got = False
        try:
            async for delta in stream_text(session_id, system, prompt, history=history):
                got = True
                yield {"type": "delta", "content": delta}
        except Exception as e:
            logger.error("VibeVerse Pro fallback stream failed: %s", e)
        if not got:
            yield {"type": "delta", "content": "تعذّر توليد إجابة الآن، حاول مرة أخرى."}
        return

    best = max(drafts, key=len)

    # Only one expert responded -> stream that draft directly.
    if len(drafts) == 1:
        yield {"type": "answer_start"}
        for chunk in _chunk_text(drafts[0]):
            yield {"type": "delta", "content": chunk}
        return

    # Merge everything into one superior answer, streamed as it is generated.
    yield {"type": "status", "content": "\U0001F9E0 يدمج أفضل الأفكار من كل الخبراء في إجابة واحدة…"}
    labeled = "\n\n".join(f"[Expert draft {i + 1}]\n{d}" for i, d in enumerate(drafts))
    synth_input = (f"USER REQUEST:\n{prompt}\n\nEXPERT DRAFTS TO MERGE:\n{labeled}\n\n"
                   "Now write the single best final answer.")
    yield {"type": "answer_start"}
    for prov, mod in COUNCIL:  # prefer Claude, then GPT, then Gemini as synthesizer
        try:
            chat = _new_chat(f"{session_id}-synth", _SYNTH_SYSTEM, prov, mod)
            got = False
            async with _LLM_SEM:
                async for event in chat.stream_message(UserMessage(text=synth_input)):
                    if isinstance(event, TextDelta) and event.content:
                        got = True
                        yield {"type": "delta", "content": event.content}
            if got:
                return
        except Exception as e:
            logger.error("VibeVerse Pro synth stream %s/%s failed: %s", prov, mod, e)
    # Synthesis failed entirely -> fall back to the strongest single draft.
    for chunk in _chunk_text(best):
        yield {"type": "delta", "content": chunk}


async def _emergent_stream_text(session_id: str, system: str, prompt: str,
                                provider: str = None, model: str = None, history: str = ""):
    provider = provider or DEFAULT_TEXT[0]
    model = model or DEFAULT_TEXT[1]
    full = (history + "\n" + prompt) if history else prompt
    chat = _new_chat(session_id, system, provider, model)
    _acc = []
    async with _LLM_SEM:
        async for event in chat.stream_message(UserMessage(text=full)):
            if isinstance(event, TextDelta) and event.content:
                _acc.append(event.content)
                yield event.content
    metering.record_text(model, (system or "") + full, "".join(_acc))


async def stream_text(session_id: str, system: str, prompt: str,
                      provider: str = None, model: str = None, history: str = ""):
    """Streamed text via the Emergent Universal Key."""
    async for piece in _emergent_stream_text(session_id, system, prompt, provider, model, history):
        yield piece


# ------------------------------------------------- agentic step-by-step builder
BUILD_PLAN_SYSTEM = (
    "You are a senior product engineer planning how to build a polished single-file web app/site. "
    "Given the user's request, respond with STRICT JSON only (no prose, no code fences) shaped exactly as:\n"
    '{"analysis":"1-2 sentence summary of what the user wants, in the USER\'S language",'
    '"steps":[{"title":"short imperative step title in the user\'s language",'
    '"detail":"one concise sentence describing what you will do in this step, in the user\'s language"}]}\n'
    "Provide 5 to 6 steps covering: understanding requirements, information architecture / sections, "
    "visual design system, building the layout & content, adding interactivity/responsiveness, and a final polish/QA pass. "
    "Keep titles under 6 words."
)

_DEFAULT_STEPS = [
    {"title": "تحليل المتطلبات", "detail": "فهم هدف المشروع والجمهور والميزات المطلوبة."},
    {"title": "تخطيط الأقسام", "detail": "تحديد أقسام الصفحة والمحتوى والترتيب."},
    {"title": "نظام التصميم", "detail": "اختيار الألوان والخطوط والمكوّنات."},
    {"title": "بناء الواجهة", "detail": "كتابة HTML/CSS/JS للتصميم والمحتوى."},
    {"title": "التفاعل والاستجابة", "detail": "إضافة التفاعلات ودعم كل الشاشات."},
    {"title": "المراجعة النهائية", "detail": "فحص الجودة وتلميع التفاصيل."},
]


async def _plan_build(prompt: str):
    try:
        raw = await generate_text(session_id=f"plan-{uuid.uuid4().hex}",
                                  system=BUILD_PLAN_SYSTEM, prompt=prompt)
        data = _json.loads(_strip_json(raw))
        steps = data.get("steps") or []
        steps = [s for s in steps if isinstance(s, dict) and s.get("title")][:6]
        return (data.get("analysis") or "").strip(), (steps or _DEFAULT_STEPS)
    except Exception as e:  # noqa: BLE001
        logger.error("build plan failed: %s", e)
        return "", _DEFAULT_STEPS


def _strip_json(text: str) -> str:
    t = (text or "").strip()
    if "```" in t:
        for part in t.split("```"):
            p = part.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{") and p.endswith("}"):
                return p
    a, b = t.find("{"), t.rfind("}")
    return t[a:b + 1] if a != -1 and b != -1 else t


async def stream_build_events(session_id: str, prompt: str, build_system: str, edit_html: str = None):
    """Yield live 'step' events (Manus-style) while planning + building a web app,
    then a final {'type':'artifact_html','html':...} event with the built document."""
    # 1) plan
    yield {"type": "step", "id": "plan", "title": "التخطيط", "state": "running",
           "detail": "أفكّر في أفضل طريقة لبناء ما طلبته…"}
    analysis, steps = await _plan_build(prompt)
    yield {"type": "step", "id": "plan", "state": "done",
           "detail": analysis or "تم وضع خطة التنفيذ."}

    # 2) walk the planned steps with their real details
    for i, s in enumerate(steps):
        sid_ = f"s{i}"
        yield {"type": "step", "id": sid_, "title": s.get("title", f"خطوة {i + 1}"),
               "state": "running", "detail": s.get("detail", "")}
        await asyncio.sleep(0.5)
        yield {"type": "step", "id": sid_, "state": "done"}

    # 3) build the actual artifact
    yield {"type": "step", "id": "build", "title": "بناء التطبيق",
           "state": "running", "detail": "أكتب الكود النهائي وأجمّع الصفحة…"}
    if edit_html:
        gen_prompt = (f"Here is the current app's full HTML:\n```html\n{edit_html}\n```\n\n"
                      f"Apply this change: {prompt}\nReturn the COMPLETE updated HTML document.")
    else:
        gen_prompt = prompt
    raw = await generate_text(session_id=session_id, system=build_system, prompt=gen_prompt)
    html = strip_fences(raw)
    yield {"type": "step", "id": "build", "state": "done", "detail": "اكتمل البناء."}
    yield {"type": "artifact_html", "html": html}


# ---------------------------------------------------------------- intent routing (unified chat)
import json as _json

ACTIONS = {"chat", "image", "voice", "document", "code", "webapp"}


def extract_json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return _json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def strip_fences(text: str) -> str:
    """Remove a leading/trailing ```lang fenced block wrapper if present."""
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        if nl != -1:
            t = t[nl + 1:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


ROUTER_SYSTEM = (
    "You are an intent router for a multimodal AI assistant that can chat, generate images, "
    "voiceovers, documents, code, and self-contained web apps/games/sites. "
    "Given the user's latest message (and prior context), pick the SINGLE best action and reply with STRICT JSON ONLY, no prose. "
    'Schema: {"action": one of ["chat","image","voice","document","code","webapp"], '
    '"prompt": "a clear, self-contained instruction derived from the user message for that action; for chat, restate the user question", '
    '"language": "programming language for code (e.g. python, javascript), else empty string", '
    '"reply": "one short friendly sentence in the SAME LANGUAGE as the user to introduce the result (e.g. this is your image)"}. '
    "Rules: image = wants a picture/photo/logo/art/illustration. "
    "voice = wants speech/narration/voiceover/audio spoken from text. document = wants an article/report/essay/plan/story/long-form text. "
    "code = wants a code snippet/function/script/algorithm in a language. "
    "webapp = wants a website/landing page/web game/web app/UI/tool that runs in a browser. "
    "chat = questions, explanations, conversation, or anything else. Detect the user's language for the reply field."
)


async def route_intent(message: str, history: str = "", has_image: bool = False, has_file: bool = False) -> dict:
    hint = ""
    if has_image:
        hint = ("\nNOTE: the user attached an IMAGE. If they want to modify/edit/change the image, action='image'. "
                "If they ask to describe/analyze it or ask a question about it, action='chat'. "
                "If they want to build a site/app FROM it, action='webapp'.")
    elif has_file:
        hint = "\nNOTE: the user attached a FILE (pdf/doc/csv/txt). Usually action='chat' to analyze/answer, unless they clearly want code/webapp/document."
    hint += ("\nNOTE: if the user asks to modify/change/tweak a website/app/game already built earlier in the chat "
             "(e.g. 'make the header blue', 'add a button'), action='webapp'.")
    try:
        raw = await generate_text(session_id=f"route-{uuid.uuid4().hex}", system=ROUTER_SYSTEM,
                                  prompt=message + hint, history=history,
                                  provider="gemini", model="gemini-3-flash-preview")
        data = extract_json(raw) or {}
    except Exception as e:
        logger.error("Intent routing failed: %s", e)
        data = {}
    action = data.get("action")
    if action not in ACTIONS:
        action = "chat"
    return {
        "action": action,
        "prompt": (data.get("prompt") or message).strip(),
        "language": (data.get("language") or "").strip(),
        "reply": (data.get("reply") or "").strip(),
    }


async def edit_image(prompt: str, image_b64: str):
    """Edit an existing image with nano-banana using the source image as reference."""
    chat = LlmChat(api_key=_key(), session_id=f"imgedit-{uuid.uuid4().hex}", system_message="You are an AI image editor.")
    chat.with_model(*IMAGE_MODEL).with_params(modalities=["image", "text"])
    async with _LLM_SEM:
        _, images = await chat.send_message_multimodal_response(UserMessage(text=prompt, file_contents=[ImageContent(image_base64=image_b64)]))
    if not images:
        raise RuntimeError("No image generated")
    img = images[0]
    return img["mime_type"], base64.b64decode(img["data"])


async def describe_media(prompt: str, image_b64: str = None, file_path: str = None, file_mime: str = None) -> str:
    """Vision / file understanding — returns a text answer about the attachment."""
    contents = []
    if image_b64:
        contents.append(ImageContent(image_base64=image_b64))
    if file_path:
        contents.append(FileContentWithMimeType(file_path=file_path, mime_type=file_mime or "application/pdf"))
    chat = _new_chat(f"desc-{uuid.uuid4().hex}", "You are a helpful multimodal assistant. Analyze the attachment and respond in the user's language.", "gemini", "gemini-3-flash-preview")
    msg = UserMessage(text=prompt, file_contents=contents) if contents else UserMessage(text=prompt)
    return await _send(chat, msg)


async def stream_chat(session_id: str, system: str, prompt: str, history: str = "",
                      image_b64: str = None, file_path: str = None, file_mime: str = None,
                      provider: str = None, model: str = None):
    """Stream a chat reply token-by-token via the Emergent Universal Key,
    optionally grounded on an attached image/file (Gemini vision)."""
    multimodal = bool(image_b64 or file_path)
    full = (history + "\n" + prompt) if history else prompt
    if multimodal:
        provider, model = "gemini", "gemini-3-flash-preview"
    else:
        provider = provider or DEFAULT_TEXT[0]
        model = model or DEFAULT_TEXT[1]
    chat = _new_chat(session_id, system, provider, model)
    contents = []
    if image_b64:
        contents.append(ImageContent(image_base64=image_b64))
    if file_path:
        contents.append(FileContentWithMimeType(file_path=file_path, mime_type=file_mime or "application/pdf"))
    msg = UserMessage(text=full, file_contents=contents) if contents else UserMessage(text=full)
    _acc = []
    async with _LLM_SEM:
        async for event in chat.stream_message(msg):
            if isinstance(event, TextDelta) and event.content:
                _acc.append(event.content)
                yield event.content
    metering.record_text(model, (system or "") + full, "".join(_acc))


async def generate_image(prompt: str):
    chat = LlmChat(api_key=_key(), session_id=f"img-{uuid.uuid4().hex}", system_message="You are an AI image generator.")
    chat.with_model(*IMAGE_MODEL).with_params(modalities=["image", "text"])
    async with _LLM_SEM:
        _, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
    if not images:
        raise RuntimeError("No image generated")
    img = images[0]
    return img["mime_type"], base64.b64decode(img["data"])


async def generate_audio(text: str, voice: str = "alloy", model: str = TTS_MODEL_HD, speed: float = 1.0) -> bytes:
    if voice not in TTS_VOICES:
        voice = "alloy"
    try:
        speed = float(speed)
    except (TypeError, ValueError):
        speed = 1.0
    speed = max(0.25, min(4.0, speed))
    tts = OpenAITextToSpeech(api_key=_key())
    # Try the requested (HD) model first; fall back to the faster standard model so a live
    # voice turn is (almost) never returned without audio.
    chain = [model] + [m for m in ("tts-1-hd", "tts-1") if m != model]
    last_err = None
    for mdl in chain:
        try:
            return await tts.generate_speech(text=text[:4096], model=mdl, voice=voice,
                                             response_format="mp3", speed=speed)
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.error("TTS %s failed, trying next: %s", mdl, e)
    raise RuntimeError(f"All TTS models failed: {last_err}")


# ---------------------------------------------------------------- fal.ai (Universal Key: queue inference only)
MUSIC_ENDPOINT = "fal-ai/stable-audio"


def _fal_headers():
    return {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}


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
