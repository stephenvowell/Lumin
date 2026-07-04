import argparse
import asyncio
import json
import os
import random
import re
import sys
import tempfile
import time
import winsound
from datetime import datetime

import edge_tts
import pygame
import speech_recognition as sr
from groq import Groq

from lumin_config import LuminConfig
from lumin_tools import LuminToolRouter
from lumin_web import WEB_TOOL_NAMES

if not LuminConfig.GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is not set")

client = Groq(api_key=LuminConfig.GROQ_API_KEY)

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

QUIT_WORDS = {"exit", "quit", "bye", "stop", "end", "shutdown"}
# Whisper often transcribes "quit" as "quite"
QUIT_MISHEARINGS = {"quite"}


def normalize_command(text):
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def wants_to_quit(text):
    normalized = normalize_command(text)
    if not normalized:
        return False

    if normalized in QUIT_WORDS | QUIT_MISHEARINGS | {"goodbye", "good bye", "shut down", "turn off", "stop listening"}:
        return True

    words = normalized.split()
    if not words:
        return False

    if len(words) <= 4 and (words[0] in QUIT_WORDS or words[-1] in QUIT_WORDS | QUIT_MISHEARINGS):
        return True

    if len(words) <= 3 and any(word in QUIT_WORDS for word in words):
        return True

    return False


def list_microphones():
    print("Available microphones:")
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        marker = " <-- default" if index == (LuminConfig.MIC_INDEX or 0) else ""
        print(f"  [{index}] {name}{marker}")
    print("\nSet MIC_INDEX in .env to choose a device.")


def clean_text_for_speech(text):
    if not text:
        return ""
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sentences(text):
    text = clean_text_for_speech(text)
    if not text:
        return []
    parts = SENTENCE_END.split(text)
    return [part.strip() for part in parts if part.strip()]


def init_audio_player():
    if not pygame.mixer.get_init():
        pygame.mixer.init()


async def _synthesize_to_file(text, path):
    communicate = edge_tts.Communicate(
        text,
        LuminConfig.TTS_VOICE,
        rate=LuminConfig.TTS_RATE,
    )
    await communicate.save(path)


async def _play_mp3(path):
    init_audio_player()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.02)


def chunk_for_speech(text, max_chars=2500):
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""
    for sentence in split_sentences(text):
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks or [text]


def speak(text, pause_after=True):
    text = clean_text_for_speech(text)
    if not text:
        return

    print(text)

    for chunk in chunk_for_speech(text):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            asyncio.run(_synthesize_to_file(chunk, tmp_path))
            asyncio.run(_play_mp3(tmp_path))
        except Exception as exc:
            print(f"(Speech failed: {exc})")
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    if pause_after:
        time.sleep(0.02)


class SpeechSession:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.mic_kwargs = {}
        if LuminConfig.MIC_INDEX is not None:
            self.mic_kwargs["device_index"] = LuminConfig.MIC_INDEX
        self._calibrated = False

    def calibrate(self):
        if self._calibrated:
            return
        with sr.Microphone(**self.mic_kwargs) as source:
            print("Calibrating microphone (one time)...")
            self.recognizer.adjust_for_ambient_noise(
                source, duration=LuminConfig.AMBIENT_NOISE_DURATION
            )
        self._calibrated = True

    def listen_chime(self):
        if not LuminConfig.LISTEN_CHIME:
            return
        try:
            winsound.Beep(880, 100)
        except Exception:
            pass

    def capture(self):
        self.listen_chime()
        print("Listening...")
        with sr.Microphone(**self.mic_kwargs) as source:
            try:
                audio = self.recognizer.listen(
                    source,
                    timeout=LuminConfig.LISTEN_TIMEOUT,
                    phrase_time_limit=LuminConfig.PHRASE_TIME_LIMIT,
                )
            except sr.WaitTimeoutError:
                print("No speech detected.")
                return ""

            print("Audio captured, transcribing...")
            try:
                text = transcribe_audio(audio)
                print(f"You said: {text}")
                return text
            except Exception as exc:
                print(f"Transcription failed: {exc}")
        return ""


def trim_history(history):
    if len(history) <= LuminConfig.MAX_HISTORY_MESSAGES + 1:
        return history

    system = history[0]
    recent = history[-LuminConfig.MAX_HISTORY_MESSAGES :]
    return [system] + recent


def groq_chat_create(**kwargs):
    last_error = None
    for attempt in range(LuminConfig.API_MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            last_error = exc
            if "tool_use_failed" in str(exc):
                break
            if attempt >= LuminConfig.API_MAX_RETRIES:
                break
            wait = min(8.0, 0.5 * (2**attempt)) + random.uniform(0, 0.25)
            print(f"API retry in {wait:.1f}s ({exc})")
            time.sleep(wait)
    raise last_error


def transcribe_audio(audio_data):
    wav_bytes = audio_data.get_wav_data()
    for attempt in range(LuminConfig.API_MAX_RETRIES + 1):
        try:
            transcription = client.audio.transcriptions.create(
                model=LuminConfig.STT_MODEL,
                file=("speech.wav", wav_bytes, "audio/wav"),
                language="en",
            )
            return transcription.text.strip()
        except Exception as exc:
            if attempt >= LuminConfig.API_MAX_RETRIES:
                raise
            wait = min(8.0, 0.5 * (2**attempt))
            print(f"STT retry in {wait:.1f}s ({exc})")
            time.sleep(wait)
    return ""


def message_to_dict(message):
    data = {"role": message.role, "content": message.content or ""}
    if message.tool_calls:
        data["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]
    return data


def speak_streamed_text(buffer, spoken_index):
    new_text = buffer[spoken_index:]
    if not new_text.strip():
        return spoken_index

    parts = SENTENCE_END.split(new_text)
    if len(parts) <= 1:
        return spoken_index

    batch = " ".join(part.strip() for part in parts[:-1] if part.strip())
    if not batch:
        return spoken_index

    speak(batch, pause_after=False)
    return spoken_index + (len(new_text) - len(parts[-1]))


def run_tool_rounds(history, tool_router):
    tools = tool_router.get_tools() if tool_router else None
    if not tools:
        return None

    last_user_message = next(
        (msg["content"] for msg in reversed(history) if msg.get("role") == "user"),
        "",
    )

    for _ in range(5):
        try:
            response = groq_chat_create(
                model=LuminConfig.LLM_MODEL,
                messages=history,
                max_tokens=LuminConfig.MAX_TOKENS,
                temperature=LuminConfig.TEMPERATURE,
                tools=tools,
                tool_choice="auto",
                stream=False,
            )
        except Exception as exc:
            if "tool_use_failed" in str(exc) and tool_router.web and last_user_message:
                print("Tool call failed, running direct web search fallback...")
                speak("Let me search the internet.")
                result = tool_router.web.web_search(last_user_message)
                history.append(
                    {
                        "role": "user",
                        "content": (
                            f"Use these internet search results to answer my previous question.\n"
                            f"{result}\n\nMy question was: {last_user_message}"
                        ),
                    }
                )
                return None
            raise

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content

        assistant_message = {"role": "assistant", "content": message.content}
        assistant_message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]
        history.append(assistant_message)

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            if tool_name in WEB_TOOL_NAMES:
                speak("Let me search the internet.")

            result = tool_router.run_tool(tool_call)
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )
            preview = result[:240] + ("..." if len(result) > 240 else "")
            print(f"[Tool] {tool_name}: {preview}")

    return None


def stream_spoken_response(history):
    stream = groq_chat_create(
        model=LuminConfig.LLM_MODEL,
        messages=history,
        max_tokens=LuminConfig.MAX_TOKENS,
        temperature=LuminConfig.TEMPERATURE,
        stream=True,
    )

    content_parts = []
    spoken_index = 0

    for chunk in stream:
        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta
        if delta.content:
            content_parts.append(delta.content)
            buffer = "".join(content_parts)
            spoken_index = speak_streamed_text(buffer, spoken_index)

    full_text = "".join(content_parts)
    remainder = full_text[spoken_index:].strip()
    if remainder:
        speak(remainder)

    return full_text


def respond(history, tool_router):
    history = trim_history(history)
    tool_answer = run_tool_rounds(history, tool_router)

    if tool_answer is not None:
        if tool_answer:
            speak(tool_answer)
        return tool_answer

    return stream_spoken_response(history)


def create_session_log_path():
    os.makedirs(LuminConfig.LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    return os.path.join(LuminConfig.LOG_DIR, f"conversation_{timestamp}.txt")


def write_to_file(log_path, user_input, assistant_response):
    with open(log_path, "a", encoding="utf-8") as file:
        current_datetime = datetime.now().strftime("%d-%m-%Y %I:%M %p")
        file.write(f"TIME: {current_datetime}\n")
        file.write(f"USER: {user_input}\n")
        file.write(f"ASSISTANT: {assistant_response}\n\n")


def capture_speech(session):
    return session.capture()


def main():
    parser = argparse.ArgumentParser(description="Lumin voice assistant")
    parser.add_argument("--list-mics", action="store_true", help="List microphone devices and exit")
    args = parser.parse_args()

    if args.list_mics:
        list_microphones()
        return

    tool_router = LuminToolRouter()
    speech_session = SpeechSession()
    speech_session.calibrate()
    log_path = create_session_log_path()
    current_datetime = datetime.now().strftime("%d-%m-%Y %I:%M %p")

    chat_history = [
        {"role": "system", "content": LuminConfig.SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Hello, the current date and time is {current_datetime}.",
        },
    ]

    try:
        print("Lumin is thinking...")
        response = respond(chat_history, tool_router)
        chat_history.append({"role": "assistant", "content": response})
        write_to_file(log_path, "(session start)", response)
        print(f"Session log: {log_path}")

        while True:
            user_input = capture_speech(speech_session)
            if not user_input:
                speak("Sorry, I didn't catch that. Please try again.")
                continue
            if wants_to_quit(user_input):
                speak("Goodbye.")
                break

            chat_history.append({"role": "user", "content": user_input})

            print("Lumin is thinking...")
            response = respond(chat_history, tool_router)
            chat_history.append({"role": "assistant", "content": response})
            write_to_file(log_path, user_input, response)

    except KeyboardInterrupt:
        print("\nInterrupted.")
        speak("Goodbye.")
    finally:
        tool_router.close()


if __name__ == "__main__":
    main()
