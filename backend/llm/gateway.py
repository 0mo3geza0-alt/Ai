import os
import base64
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAITextToSpeech
from core.logging import logger

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

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


async def generate_image(prompt: str):
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id="img", system_message="You are an AI image generator.")
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
