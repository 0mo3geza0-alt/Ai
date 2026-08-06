import os, sys
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from litellm import speech

key = os.environ["EMERGENT_LLM_KEY"]
proxy = os.environ.get("INTEGRATION_PROXY_URL", "https://integrations.emergentagent.com").rstrip("/") + "/llm"

def try_call(model, voice, instructions=None):
    params = {
        "model": f"openai/{model}",
        "input": "أهلاً بيك! إزيك النهارده؟ يلا نعمل حاجة حلوة مع بعض.",
        "voice": voice,
        "api_key": key,
        "api_base": proxy,
        "custom_llm_provider": "openai",
    }
    if instructions:
        params["instructions"] = instructions
    try:
        resp = speech(**params)
        content = resp.content if hasattr(resp, "content") else resp.read()
        print(f"OK {model} voice={voice} instr={bool(instructions)} bytes={len(content)}")
        return True
    except Exception as e:
        print(f"FAIL {model} voice={voice} instr={bool(instructions)}: {repr(e)[:300]}")
        return False

try_call("gpt-4o-mini-tts", "nova", "Speak with warm excitement and a light laugh, in an Egyptian Arabic dialect.")
try_call("gpt-4o-mini-tts", "ballad", "Speak calmly.")
try_call("tts-1-hd", "nova")
