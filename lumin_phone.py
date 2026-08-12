"""Phone browser UI so Lumin can use a Samsung (or any) microphone.

Run:  python lumin_phone.py
Open the printed HTTPS URL on the phone, allow the mic, then tap to talk.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import secrets
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import lumin
from lumin_config import LuminConfig
from lumin_memory import UserMemory
from lumin_personality import PERSONALITY_PRESETS
from lumin_tools import LuminToolRouter

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "web" / "phone.html"
ACCESS_KEY = os.environ.get("LUMIN_PHONE_KEY") or secrets.token_urlsafe(8)


def synthesize_mp3(text: str) -> bytes:
    text = lumin.clean_text_for_speech(text)
    if not text:
        return b""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        path = tmp.name
    try:
        asyncio.run(lumin._synthesize_to_file(text, path))
        return Path(path).read_bytes()
    except Exception as exc:
        print(f"(Phone TTS failed: {exc})")
        return b""
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


class PhoneSession:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.memory = (
            UserMemory(LuminConfig.MEMORY_FILE, default_name=LuminConfig.USER_NAME)
            if LuminConfig.MEMORY_ENABLED
            else None
        )
        self.tool_router = LuminToolRouter()
        system_prompt, _user_name = lumin.build_chat_context(self.memory)
        self.log_path = lumin.create_session_log_path()
        self.history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "[Session start — greet me naturally.]"},
        ]
        self.started = False

    def start(self) -> dict:
        with self.lock:
            if not self.started:
                print("Lumin is thinking...")
                reply = lumin.respond(self.history, self.tool_router) or ""
                self.history.append({"role": "assistant", "content": reply})
                lumin.write_to_file(self.log_path, "(session start)", reply)
                self.started = True
            else:
                reply = self.history[-1]["content"] if self.history else ""
        return {"reply": reply, "audio": _b64_audio(reply)}

    def turn(self, user_input: str) -> dict:
        user_input = (user_input or "").strip()
        if not user_input:
            reply = "I missed that — say it again?"
            return {"user": "", "reply": reply, "audio": _b64_audio(reply), "quit": False}
        if lumin.wants_to_quit(user_input):
            reply = lumin.FILLERS.goodbye(timezone_name=LuminConfig.TIMEZONE)
            return {"user": user_input, "reply": reply, "audio": _b64_audio(reply), "quit": True}

        with self.lock:
            self.history.append({"role": "user", "content": user_input})
            print("Lumin is thinking...")
            reply = lumin.respond(self.history, self.tool_router) or ""
            self.history.append({"role": "assistant", "content": reply})
            lumin.write_to_file(self.log_path, user_input, reply)
            if self.memory:
                self.memory.observe_exchange(user_input, reply)
        return {"user": user_input, "reply": reply, "audio": _b64_audio(reply), "quit": False}


SESSION: PhoneSession | None = None


def _b64_audio(text: str) -> str:
    audio = synthesize_mp3(text)
    return base64.b64encode(audio).decode("ascii") if audio else ""


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    parsed = urlparse(handler.path)
    key = parse_qs(parsed.query).get("k", [""])[0]
    header = handler.headers.get("X-Lumin-Key", "")
    return secrets.compare_digest(key or header, ACCESS_KEY)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html", "/phone"}:
            if not authorized(self):
                self._send(401, b"Missing or invalid access key.", "text/plain; charset=utf-8")
                return
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            return
        if parsed.path == "/health":
            self._json(200, {"ok": True})
            return
        self._send(404, b"Not found", "text/plain")

    def do_POST(self) -> None:
        if not authorized(self):
            self._json(401, {"error": "Missing or invalid access key."})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "Invalid JSON"})
            return

        assert SESSION is not None
        path = urlparse(self.path).path
        try:
            if path == "/api/start":
                self._json(200, SESSION.start())
                return
            if path == "/api/turn":
                user_text = (payload.get("text") or "").strip()
                if not user_text and payload.get("audio"):
                    audio = base64.b64decode(payload["audio"])
                    mime = payload.get("mime") or "audio/webm"
                    print(f"Transcribing {len(audio)} bytes ({mime})")
                    user_text = lumin.transcribe_bytes(audio, mime=mime)
                    print(f"You said: {user_text}")
                self._json(200, SESSION.turn(user_text))
                return
        except Exception as exc:
            print(f"Phone API error: {exc}")
            self._json(500, {"error": str(exc)})
            return
        self._json(404, {"error": "Not found"})


def main() -> None:
    global SESSION

    parser = argparse.ArgumentParser(description="Lumin phone microphone UI")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("LUMIN_PHONE_PORT", "8787")))
    args = parser.parse_args()

    if not PAGE.is_file():
        raise SystemExit(f"Missing {PAGE}")

    lumin.SPEAK_ALOUD = False
    lumin.VOICE_SETTINGS = lumin.resolve_voice_settings()
    SESSION = PhoneSession()

    personality = PERSONALITY_PRESETS[lumin.PERSONALITY_KEY]["label"]
    user_name = lumin.resolve_user_name(SESSION.memory)
    print(f"Lumin phone UI — {personality} for {user_name}")
    print(f"Local:  http://127.0.0.1:{args.port}/?k={ACCESS_KEY}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping phone UI.")
    finally:
        server.server_close()
        if SESSION and SESSION.memory:
            SESSION.memory.finalize_session(SESSION.history)
        if SESSION:
            SESSION.tool_router.close()


if __name__ == "__main__":
    main()
