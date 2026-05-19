import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID", "")
BASE_URL = os.getenv("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
TTS_MODEL = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")
STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LLM_PROVIDER    = os.getenv("LLM_PROVIDER", "")  # openai | bedrock

#OpenAI
LLM_API_KEY     = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL    = os.getenv("LLM_BASE_URL", "")
LLM_MODEL       = os.getenv("LLM_MODEL", "gpt-5.1-mini")
LLM_API_VERSION = os.getenv("LLM_API_VERSION", "")  # requerido para Azure OpenAI

# Bedrock
AWS_BEARER_TOKEN_BEDROCK = os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")
AWS_REGION               = os.getenv("AWS_REGION", "eu-west-3")
BEDROCK_MODEL_ID         = os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-pro-v1:0")

if not API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY is required")