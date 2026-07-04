"""Lumin desktop launcher — Tkinter control panel for the voice assistant.

Run:  python lumin_launcher.py
Build: ./build_exe.ps1
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


os.chdir(app_dir())

from lumin_config import LuminConfig
from lumin_personality import PERSONALITY_PRESETS, normalize_personality
from lumin_theme import (
    ACCENT,
    ACCENT_H,
    ACCENT_L,
    BG,
    CONSOLE_BG,
    DANGER,
    DANGER_H,
    FONT,
    MONO,
    MUTED,
    OK,
    PANEL,
    PANEL2,
    TEXT,
)

_DONE = object()
WORKER_FLAG = "--worker"


def worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, WORKER_FLAG]
    return [sys.executable, str(Path(__file__).resolve()), WORKER_FLAG]


def has_groq_key() -> bool:
    if (os.environ.get("GROQ_API_KEY") or "").strip():
        return True
    env_path = app_dir() / ".env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GROQ_API_KEY="):
                return bool(line.split("=", 1)[1].strip())
    except OSError:
        pass
    return False


class LuminLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Lumin")
        self.configure(bg=BG)
        self.geometry("720x640")
        self.minsize(560, 520)

        self.proc: subprocess.Popen | None = None
        self.out_q: queue.Queue = queue.Queue()
        self.start_btn: tk.Button | None = None
        self.stop_btn: tk.Button | None = None

        personality_key = normalize_personality(LuminConfig.PERSONALITY)
        self.personality_label = PERSONALITY_PRESETS[personality_key]["label"]

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._drain_queue)

    def _btn(
        self,
        parent,
        text,
        command,
        *,
        base=ACCENT,
        hover=ACCENT_H,
        fg="#ffffff",
        font=(FONT, 10, "bold"),
        padx=12,
        pady=8,
        width=0,
    ):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=base,
            fg=fg,
            activebackground=hover,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=font,
            padx=padx,
            pady=pady,
            width=width,
        )
        button.bind(
            "<Enter>",
            lambda _e: button.configure(bg=hover) if str(button["state"]) != "disabled" else None,
        )
        button.bind(
            "<Leave>",
            lambda _e: button.configure(bg=base) if str(button["state"]) != "disabled" else None,
        )
        button._base = base  # type: ignore[attr-defined]
        return button

    def _chip(self, parent, label: str, ok: bool) -> None:
        color = OK if ok else MUTED
        tk.Label(
            parent,
            text=f"{'●' if ok else '○'} {label}",
            bg=BG,
            fg=color,
            font=(FONT, 9),
        ).pack(side="left", padx=(0, 14))

    def _build(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=22, pady=(18, 4))
        tk.Label(header, text="Lumin", bg=BG, fg=TEXT, font=(FONT, 22, "bold")).pack(side="left")
        self.status_lbl = tk.Label(header, text="idle", bg=BG, fg=MUTED, font=(FONT, 10, "italic"))
        self.status_lbl.pack(side="right")

        status = tk.Frame(self, bg=BG)
        status.pack(fill="x", padx=22, pady=(0, 8))
        self._chip(status, "Groq API key", has_groq_key())
        self._chip(status, self.personality_label, True)
        self._chip(status, "memory on" if LuminConfig.MEMORY_ENABLED else "memory off", True)

        controls = tk.Frame(self, bg=BG)
        controls.pack(fill="x", padx=22, pady=(0, 8))

        self.start_btn = self._btn(
            controls,
            "Start listening",
            self._start,
            base=ACCENT,
            hover=ACCENT_H,
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = self._btn(
            controls,
            "Stop",
            self._stop,
            base=DANGER,
            hover=DANGER_H,
            width=8,
        )
        self.stop_btn.pack(side="left", padx=(0, 8))
        self.stop_btn.configure(state="disabled")

        self._btn(
            controls,
            "Clear",
            self._clear,
            base=PANEL,
            hover=PANEL2,
            fg=MUTED,
            width=6,
        ).pack(side="right")

        hint = tk.Label(
            self,
            text="Speak after the chime. Say exit, quit, or goodbye to stop.",
            bg=BG,
            fg=MUTED,
            font=(FONT, 9),
            anchor="w",
        )
        hint.pack(fill="x", padx=22, pady=(0, 6))

        console_wrap = tk.Frame(self, bg=ACCENT)
        console_wrap.pack(fill="both", expand=True, padx=22, pady=(0, 16))
        self.console = tk.Text(
            console_wrap,
            bg=CONSOLE_BG,
            fg=TEXT,
            insertbackground=ACCENT_L,
            font=(MONO, 10),
            relief="flat",
            bd=0,
            wrap="word",
            padx=12,
            pady=10,
            state="disabled",
            height=16,
        )
        self.console.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        scrollbar = tk.Scrollbar(console_wrap, command=self.console.yview)
        scrollbar.pack(side="right", fill="y")
        self.console.configure(yscrollcommand=scrollbar.set)
        self.console.tag_configure("sys", foreground=MUTED, font=(MONO, 9, "italic"))
        self.console.tag_configure("err", foreground=DANGER)

        self._log("Ready. Click Start listening to wake Lumin.\n", "sys")
        if not has_groq_key():
            self._log("Add GROQ_API_KEY to .env in the app folder before starting.\n", "err")

    def _log(self, text: str, tag: str | None = None) -> None:
        self.console.configure(state="normal")
        if tag:
            self.console.insert("end", text, tag)
        else:
            self.console.insert("end", text)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _clear(self) -> None:
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        self.status_lbl.configure(text="listening" if running else "idle", fg=ACCENT_L if running else MUTED)
        if self.start_btn:
            self.start_btn.configure(state="disabled" if running else "normal")
        if self.stop_btn:
            self.stop_btn.configure(state="normal" if running else "disabled")

    def _start(self) -> None:
        if self.proc is not None:
            return
        if not has_groq_key():
            self._log("Cannot start — GROQ_API_KEY is missing in .env\n", "err")
            return

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
        cwd = str(app_dir())

        try:
            self.proc = subprocess.Popen(
                worker_command(),
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            self._log(f"Failed to start: {exc}\n", "err")
            self.proc = None
            return

        self._set_running(True)
        self._log("\n--- session started ---\n", "sys")
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self) -> None:
        assert self.proc is not None
        proc = self.proc
        try:
            if proc.stdout:
                for line in proc.stdout:
                    self.out_q.put(line)
        finally:
            proc.wait()
            self.out_q.put(_DONE)

    def _stop(self) -> None:
        if self.proc is None:
            return
        self._log("\n--- stopping ---\n", "sys")
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None
        self._set_running(False)

    def _drain_queue(self) -> None:
        try:
            while True:
                item = self.out_q.get_nowait()
                if item is _DONE:
                    self.proc = None
                    self._set_running(False)
                    self._log("--- session ended ---\n", "sys")
                else:
                    self._log(str(item))
        except queue.Empty:
            pass
        self.after(50, self._drain_queue)

    def _on_close(self) -> None:
        if self.proc is not None:
            self._stop()
        self.destroy()


def run_worker() -> None:
    os.chdir(app_dir())
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    sys.argv = [arg for arg in sys.argv if arg != WORKER_FLAG]
    from lumin import main

    main()


if __name__ == "__main__":
    if WORKER_FLAG in sys.argv:
        run_worker()
    else:
        LuminLauncher().mainloop()
