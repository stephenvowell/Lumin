import os
from dotenv import load_dotenv

load_dotenv()


def _int(name, default):
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def _float(name, default):
    value = os.environ.get(name)
    return float(value) if value not in (None, "") else default


class LuminConfig:
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

    LLM_MODEL = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
    STT_MODEL = os.environ.get("STT_MODEL", "whisper-large-v3-turbo")
    TTS_VOICE = os.environ.get("TTS_VOICE", "")
    TTS_RATE = os.environ.get("TTS_RATE", "")
    TTS_PITCH = os.environ.get("TTS_PITCH", "")

    PERSONALITY = os.environ.get("LUMIN_PERSONALITY", "witty_co_pilot")
    USER_NAME = os.environ.get("LUMIN_USER_NAME", "Stephen")
    MEMORY_ENABLED = os.environ.get("MEMORY_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    MEMORY_FILE = os.environ.get("MEMORY_FILE", "data/user_profile.json")

    TEMPERATURE = _float("TEMPERATURE", 0.0)
    MAX_TOKENS = _int("MAX_TOKENS", 1000)
    MAX_HISTORY_MESSAGES = _int("MAX_HISTORY_MESSAGES", 20)
    API_MAX_RETRIES = _int("API_MAX_RETRIES", 3)

    MIC_INDEX = os.environ.get("MIC_INDEX")
    MIC_INDEX = int(MIC_INDEX) if MIC_INDEX not in (None, "") else None
    LISTEN_TIMEOUT = _int("LISTEN_TIMEOUT", 10)
    PHRASE_TIME_LIMIT = _int("PHRASE_TIME_LIMIT", 15)
    AMBIENT_NOISE_DURATION = _float("AMBIENT_NOISE_DURATION", 0.5)
    LISTEN_CHIME = os.environ.get("LISTEN_CHIME", "true").lower() in ("1", "true", "yes")

    TIMEZONE = os.environ.get("TIMEZONE", "America/Chicago")
    LOG_DIR = os.environ.get("LOG_DIR", "logs")

    WEB_SEARCH_ENABLED = os.environ.get("WEB_SEARCH_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    WEB_SEARCH_MAX_RESULTS = _int("WEB_SEARCH_MAX_RESULTS", 5)
    WEB_FETCH_MAX_CHARS = _int("WEB_FETCH_MAX_CHARS", 4000)
    WEB_FETCH_TIMEOUT = _float("WEB_FETCH_TIMEOUT", 12.0)
    WEB_USER_AGENT = os.environ.get(
        "WEB_USER_AGENT",
        "Mozilla/5.0 (compatible; LuminVoiceAssistant/1.0)",
    )

    CUSTOM_SYSTEM_PROMPT = os.environ.get("LUMIN_SYSTEM_PROMPT", "")
