# Lumin

A personable voice assistant for Windows. Speak naturally, get spoken answers, and look things up on the web when needed.

Lumin uses **Groq** for speech-to-text and chat, **Edge TTS** for voice output, and **DuckDuckGo** for live web search — no extra search API key required.

## Features

- **Voice loop** — listen, transcribe, think, speak (streaming responses)
- **Web search** — `web_search` and `fetch_webpage` tools for current events, weather, news, and facts
- **Personality presets** — witty co-pilot (default), casual friend, or calm butler
- **Session memory** — remembers your name, preferences, and recent topics across runs
- **Desktop app** — dark Tkinter launcher and one-click Windows `.exe` build

## Quick start

### 1. Install dependencies

Requires **Python 3.10+** on Windows.

```powershell
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your [Groq API key](https://console.groq.com/):

```env
GROQ_API_KEY=your_key_here
```

### 2. Run from source

**Desktop launcher (recommended):**

```powershell
python lumin_launcher.py
```

**CLI only:**

```powershell
python lumin.py
```

List microphones:

```powershell
python lumin.py --list-mics
```

### 3. Build a standalone `.exe`

```powershell
.\build_exe.ps1
```

Output: `dist\Lumin.exe` plus a desktop shortcut. Edit `dist\.env` with your API key before first run.

## Configuration

All settings live in `.env`. See `.env.example` for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `LUMIN_PERSONALITY` | `witty_co_pilot` | `casual_friend`, `calm_butler`, or `witty_co_pilot` |
| `LUMIN_USER_NAME` | `Stephen` | Name Lumin uses in conversation |
| `MEMORY_ENABLED` | `true` | Persist profile to `data/user_profile.json` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Groq chat model |
| `STT_MODEL` | `whisper-large-v3-turbo` | Groq transcription model |
| `TTS_VOICE` | *(personality default)* | Edge TTS voice name |
| `TIMEZONE` | `America/Chicago` | Used for greetings and context |

Say things like **"call me Steph"** or **"remember that I like short answers"** — Lumin picks those up over time.

## Project layout

```
lumin.py              Voice assistant core
lumin_launcher.py     Desktop GUI (Tkinter)
lumin_config.py       Environment config
lumin_personality.py  Personality presets and fillers
lumin_memory.py       Cross-session user profile
lumin_web.py          DuckDuckGo search tools
lumin_tools.py        Tool router
lumin_theme.py        UI color palette
build_exe.ps1         PyInstaller build + desktop shortcut
```

## Requirements

- Windows (uses `winsound` for the listen chime)
- Microphone
- Groq API key
- Internet for STT, LLM, TTS, and web search

## License

MIT
