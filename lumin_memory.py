import json
import os
import re
from datetime import datetime, timezone

DEFAULT_PROFILE = {
    "name": "",
    "preferences": [],
    "notes": [],
    "last_session_summary": "",
    "last_seen": "",
}


class UserMemory:
    def __init__(self, path, default_name=""):
        self.path = path
        self.data = self._load()
        if default_name and not self.data.get("name"):
            self.data["name"] = default_name

    def _load(self):
        if not os.path.isfile(self.path):
            return dict(DEFAULT_PROFILE)

        try:
            with open(self.path, encoding="utf-8") as file:
                loaded = json.load(file)
        except (OSError, json.JSONDecodeError):
            return dict(DEFAULT_PROFILE)

        profile = dict(DEFAULT_PROFILE)
        profile.update(loaded)
        return profile

    def save(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(self.data, file, indent=2, ensure_ascii=False)
            file.write("\n")

    @property
    def display_name(self):
        return (self.data.get("name") or "").strip()

    def context_block(self):
        lines = []
        if self.display_name:
            lines.append(f"Name: {self.display_name}")

        preferences = self._clean_list(self.data.get("preferences"))
        if preferences:
            lines.append("Preferences: " + "; ".join(preferences))

        notes = self._clean_list(self.data.get("notes"))
        if notes:
            lines.append("Notes: " + "; ".join(notes[-5:]))

        summary = (self.data.get("last_session_summary") or "").strip()
        if summary:
            lines.append(f"Last session: {summary}")

        last_seen = (self.data.get("last_seen") or "").strip()
        if last_seen:
            lines.append(f"Last seen: {last_seen}")

        return "\n".join(lines)

    def observe_exchange(self, user_text, assistant_text):
        user_text = (user_text or "").strip()
        if not user_text:
            return

        self._extract_name(user_text)
        self._extract_remember_note(user_text)
        self._extract_preferences(user_text)

    def finalize_session(self, chat_history):
        self.data["last_seen"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        summary = self._summarize_session(chat_history)
        if summary:
            self.data["last_session_summary"] = summary
        self.save()

    def _clean_list(self, values):
        if not isinstance(values, list):
            return []
        cleaned = []
        for value in values:
            text = str(value).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def _append_unique(self, field, value, limit=12):
        value = value.strip()
        if not value:
            return

        items = self._clean_list(self.data.get(field))
        if value in items:
            items.remove(value)
        items.append(value)
        self.data[field] = items[-limit:]

    def _extract_name(self, text):
        patterns = [
            r"\b(?:call me|my name is|i am|i'm)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\b",
            r"\bname(?:'s| is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                self.data["name"] = match.group(1).strip().title()
                return

    def _extract_remember_note(self, text):
        match = re.search(
            r"\bremember(?:\s+that)?\s+(.+?)(?:[.!?]|$)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            self._append_unique("notes", match.group(1).strip())

    def _extract_preferences(self, text):
        lowered = text.lower()
        preference_phrases = {
            "keep answers short": "Prefers short answers",
            "be brief": "Prefers short answers",
            "keep it brief": "Prefers short answers",
            "don't use my name": "Prefers not to use their name often",
            "do not use my name": "Prefers not to use their name often",
            "less humor": "Prefers less humor",
            "more humor": "Enjoys more humor",
        }
        for phrase, preference in preference_phrases.items():
            if phrase in lowered:
                self._append_unique("preferences", preference)

    def _summarize_session(self, chat_history):
        user_lines = [
            msg["content"].strip()
            for msg in chat_history
            if msg.get("role") == "user" and msg.get("content", "").strip()
        ]
        user_lines = [
            line
            for line in user_lines
            if not line.startswith("[Session start")
        ]
        if not user_lines:
            return ""

        recent = user_lines[-3:]
        if len(recent) == 1:
            return f"We talked about: {recent[0][:160]}"
        return "Recent topics: " + "; ".join(line[:80] for line in recent)
