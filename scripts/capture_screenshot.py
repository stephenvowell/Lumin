"""Capture a README screenshot of the Lumin launcher window."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

from lumin_launcher import LuminLauncher

OUTPUT = ROOT / "docs" / "screenshot.png"


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    app = LuminLauncher()
    app.update_idletasks()
    app.update()

    x = app.winfo_rootx()
    y = app.winfo_rooty()
    w = app.winfo_width()
    h = app.winfo_height()
    padding = 8
    bbox = (
        max(0, x - padding),
        max(0, y - padding),
        x + w + padding,
        y + h + padding,
    )

    ImageGrab.grab(bbox=bbox, all_screens=True).save(OUTPUT)
    app.destroy()
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
