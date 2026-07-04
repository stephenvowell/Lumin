"""Capture a polished README screenshot of the Lumin launcher."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageGrab

from lumin_launcher import LuminLauncher
from lumin_theme import BG

OUTPUT = ROOT / "docs" / "screenshot.png"
MARGIN = 56


def stage_demo(app: LuminLauncher) -> None:
    app._clear()
    app._set_running(True)
    app._log("\n--- session started ---\n", "sys")
    app._log("Lumin ready — Witty co-pilot mode for Stephen.\n")
    app._log("Voice: en-US-JennyNeural (+0%, +0Hz)\n")
    app._log("Calibrating microphone (one time)...\n")
    app._log("Lumin is thinking...\n")
    app._log("Good morning, Stephen. I'm here whenever you need me.\n")
    app._log("\nListening...\n", "sys")
    app._log("You said: What's the weather like in Sierra Vista today?\n")
    app._log("Lumin is thinking...\n")
    app._log("Give me a sec, I'll look that up.\n")
    app._log("[Tool] web_search: Search results for 'weather Sierra Vista AZ'...\n", "sys")
    app._log(
        "It's sunny and about 94 degrees in Sierra Vista right now — "
        "pretty typical for early July.\n"
    )
    app._log("\nListening...\n", "sys")


def capture_window(app: LuminLauncher) -> Image.Image:
    app.geometry("760x660+80+60")
    app.update_idletasks()
    app.update()
    app.lift()
    app.attributes("-topmost", True)
    app.update_idletasks()
    app.update()

    x = app.winfo_rootx()
    y = app.winfo_rooty()
    w = app.winfo_width()
    h = app.winfo_height()
    grab = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)

    canvas = Image.new("RGB", (grab.width + MARGIN * 2, grab.height + MARGIN * 2), BG)
    canvas.paste(grab, (MARGIN, MARGIN))
    return canvas


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    app = LuminLauncher()
    stage_demo(app)
    image = capture_window(app)
    image.save(OUTPUT, format="PNG", optimize=True)
    app.destroy()
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
