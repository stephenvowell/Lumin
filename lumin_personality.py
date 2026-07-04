import random
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

PERSONALITY_PRESETS = {
    "casual_friend": {
        "label": "Casual friend",
        "temperature_hint": 0.85,
        "prompt": (
            "You are Lumin, {user_name}'s easygoing voice companion at home. "
            "Talk like a clever friend: warm, relaxed, and direct. "
            "Use contractions and natural spoken rhythm. "
            "A little humor is welcome when it fits; never forced. "
            "Acknowledge mood briefly when it seems relevant, but do not overdo empathy."
        ),
    },
    "calm_butler": {
        "label": "Calm butler",
        "temperature_hint": 0.75,
        "prompt": (
            "You are Lumin, {user_name}'s calm, capable home assistant. "
            "Polished and unhurried, like a thoughtful butler who knows when to be brief. "
            "Courteous without being stiff. Clear, composed, and reassuring. "
            "Light warmth is fine; avoid slang and jokes unless {user_name} invites them."
        ),
    },
    "witty_co_pilot": {
        "label": "Witty co-pilot",
        "temperature_hint": 0.85,
        "prompt": (
            "You are Lumin, {user_name}'s witty voice co-pilot at home. "
            "Sharp, warm, and a little playful — clever friend energy, not corporate assistant. "
            "Use contractions, vary how you open replies, and keep answers tight for speech. "
            "Dry humor is welcome when it fits; never perform or ramble."
        ),
    },
}

VOICE_DEFAULTS = {
    "casual_friend": {"voice": "en-US-AriaNeural", "rate": "+0%", "pitch": "+0Hz"},
    "calm_butler": {"voice": "en-GB-SoniaNeural", "rate": "-5%", "pitch": "-2Hz"},
    "witty_co_pilot": {"voice": "en-US-JennyNeural", "rate": "+0%", "pitch": "+0Hz"},
}

SHARED_VOICE_RULES = (
    "Respond truthfully in concise, natural spoken language. "
    "No markdown, bullet points, or lists. "
    "Ask at most one short question at a time. "
    "Vary your phrasing; avoid assistant clichés like 'As an AI' or 'I'd be happy to help'. "
    "Use {user_name}'s name occasionally, not every turn. "
    "Use web_search for current events, news, weather, live facts, or anything that "
    "requires up-to-date internet information. Use fetch_webpage when you need more "
    "detail from a specific search result URL. "
    "If a search returns nothing, say so plainly."
)

SEARCH_FILLERS = [
    "Give me a sec, I'll look that up.",
    "Hang on, checking that now.",
    "Let me see what I can find.",
    "One moment, searching for that.",
    "Alright, let me dig into that.",
]

MISHEAR_FILLERS = [
    "I missed that — say it again?",
    "Didn't quite catch that.",
    "One more time for me?",
    "Sorry, I didn't get that.",
]

GOODBYE_MORNING = [
    "Talk later.",
    "See you in a bit.",
    "Catch you later.",
]

GOODBYE_AFTERNOON = [
    "See you later.",
    "Talk soon.",
    "Catch you later.",
]

GOODBYE_EVENING = [
    "Good night.",
    "See you later.",
    "Take it easy tonight.",
]

GOODBYE_NIGHT = [
    "Good night.",
    "Sleep well.",
    "Night.",
]

OPENING_INSTRUCTION = (
    "This is the start of a new voice session. "
    "Open with a brief, natural greeting suited to the time of day — "
    "one or two spoken sentences only. Do not mention tools or search unless asked."
)


class FillerBank:
    def __init__(self):
        self._last = {}

    def pick(self, category, options):
        if len(options) == 1:
            return options[0]

        last = self._last.get(category)
        choices = [item for item in options if item != last] or list(options)
        choice = random.choice(choices)
        self._last[category] = choice
        return choice

    def search(self):
        return self.pick("search", SEARCH_FILLERS)

    def mishear(self):
        return self.pick("mishear", MISHEAR_FILLERS)

    def goodbye(self, now=None, timezone_name="America/Chicago"):
        hour = _local_hour(now, timezone_name)
        if 5 <= hour < 12:
            pool = GOODBYE_MORNING
        elif 12 <= hour < 17:
            pool = GOODBYE_AFTERNOON
        elif 17 <= hour < 22:
            pool = GOODBYE_EVENING
        else:
            pool = GOODBYE_NIGHT
        return self.pick("goodbye", pool)


def _local_hour(now, timezone_name):
    if now is None:
        now = datetime.now()
    if ZoneInfo is not None:
        try:
            now = now.astimezone(ZoneInfo(timezone_name))
        except Exception:
            pass
    return now.hour


def normalize_personality(name):
    key = (name or "witty_co_pilot").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "friend": "casual_friend",
        "casual": "casual_friend",
        "butler": "calm_butler",
        "calm": "calm_butler",
        "witty": "witty_co_pilot",
        "copilot": "witty_co_pilot",
        "co_pilot": "witty_co_pilot",
    }
    key = aliases.get(key, key)
    if key not in PERSONALITY_PRESETS:
        return "witty_co_pilot"
    return key


def voice_defaults_for(personality_key):
    return VOICE_DEFAULTS.get(personality_key, VOICE_DEFAULTS["witty_co_pilot"])


def build_system_prompt(
    personality_key,
    user_name,
    memory_context="",
    datetime_context="",
    custom_prompt=None,
):
    preset = PERSONALITY_PRESETS[normalize_personality(personality_key)]
    if custom_prompt:
        core = custom_prompt
    else:
        core = preset["prompt"].format(user_name=user_name)

    parts = [
        core,
        SHARED_VOICE_RULES.format(user_name=user_name),
    ]

    if datetime_context:
        parts.append(f"Current context: {datetime_context}")

    if memory_context:
        parts.append(f"What you remember about {user_name}:\n{memory_context}")

    parts.append(OPENING_INSTRUCTION)
    return " ".join(parts)


def format_datetime_context(now, timezone_name):
    if ZoneInfo is not None:
        try:
            now = now.astimezone(ZoneInfo(timezone_name))
        except Exception:
            pass

    day_part = "night"
    hour = now.hour
    if 5 <= hour < 12:
        day_part = "morning"
    elif 12 <= hour < 17:
        day_part = "afternoon"
    elif 17 <= hour < 22:
        day_part = "evening"

    return (
        f"It is {now.strftime('%A, %B %d, %Y')}, {now.strftime('%I:%M %p').lstrip('0')} "
        f"({day_part}, timezone {timezone_name})."
    )
