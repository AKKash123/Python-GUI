"""Typing Speed Tester (Tkinter).

Concepts practiced
- Key events:   <KeyPress> starts the timer, <KeyRelease> checks the text
- Timing:       time.perf_counter() and root.after() for a live timer
- WPM maths:    WPM = (correct characters / 5) / minutes
- Text tags:    colour each character green (correct) or red (wrong)
- JSON:         the best score is saved between sessions
"""

import json
import random
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

BEST_FILE = Path(__file__).with_name("best_score.json")

PASSAGES = [
    "The quick brown fox jumps over the lazy dog while the sun sets slowly "
    "behind the distant hills.",
    "Programming is the art of telling a computer exactly what to do, one "
    "small and careful step at a time.",
    "A journey of a thousand miles begins with a single step, and every "
    "expert was once a beginner.",
    "Practice makes progress. Type slowly and accurately first, and the "
    "speed will come naturally with time.",
    "Good software is built by curious people who read the documentation, "
    "test their ideas and learn from mistakes.",
    "Rain tapped softly on the window as she opened her laptop, ready to "
    "write the first line of her new project.",
]

TIME_LIMITS = {"Until finished": None, "30 seconds": 30, "60 seconds": 60}


class TypingTester(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Typing Speed Tester")
        self.geometry("720x520")
        self.minsize(600, 460)

        self.target = ""
        self.start_time = None      # set on the first key press
        self.finished = False
        self.timer_job = None
        self.best = self.load_best()

        self._build_ui()
        self.reset()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main = ttk.Frame(self, padding=15)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        # Top bar: time-limit selector + stats
        top = ttk.Frame(main)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        self.limit_var = tk.StringVar(value="Until finished")
        limit_box = ttk.Combobox(top, textvariable=self.limit_var, width=15,
                                 values=list(TIME_LIMITS), state="readonly")
        limit_box.grid(row=0, column=0, sticky="w")
        limit_box.bind("<<ComboboxSelected>>", lambda e: self.reset())

        self.stats_var = tk.StringVar()
        ttk.Label(top, textvariable=self.stats_var,
                  font=("Segoe UI", 11, "bold")).grid(row=0, column=1, sticky="e")

        # Passage to copy (read-only)
        self.display = tk.Text(main, height=6, wrap="word", font=("Consolas", 16),
                               padx=10, pady=10, relief="flat", bg="#f4f4f4",
                               cursor="arrow")
        self.display.grid(row=1, column=0, sticky="ew", pady=15)
        self.display.tag_configure("correct", foreground="#1a8f3c")
        self.display.tag_configure("wrong", foreground="white", background="#d33")
        self.display.tag_configure("cursor", background="#cfe3ff")

        # Typing area
        self.input = tk.Text(main, height=5, wrap="word", font=("Consolas", 16),
                             padx=10, pady=10)
        self.input.grid(row=2, column=0, sticky="ew")
        self.input.bind("<KeyPress>", self.on_key_press)
        self.input.bind("<KeyRelease>", self.on_key_release)
        self.input.bind("<Return>", lambda e: "break")       # no new lines
        self.input.bind("<<Paste>>", lambda e: "break")      # no cheating

        # Buttons + result line
        bottom = ttk.Frame(main)
        bottom.grid(row=3, column=0, sticky="ew", pady=15)
        bottom.columnconfigure(0, weight=1)
        self.result_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.result_var,
                  font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Restart (Esc)",
                   command=self.reset).grid(row=0, column=1)
        self.bind("<Escape>", lambda e: self.reset())

        self.best_var = tk.StringVar()
        ttk.Label(main, textvariable=self.best_var).grid(row=4, column=0, sticky="w")

    # ---------------------------------------------------------------- logic
    def reset(self):
        """Prepare a fresh test with a new random passage."""
        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        self.target = random.choice(PASSAGES)
        self.start_time = None
        self.finished = False

        self.display.config(state="normal")
        self.display.delete("1.0", tk.END)
        self.display.insert("1.0", self.target)
        self.display.tag_remove("correct", "1.0", tk.END)
        self.display.tag_remove("wrong", "1.0", tk.END)
        self.display.config(state="disabled")

        self.input.config(state="normal")
        self.input.delete("1.0", tk.END)
        self.input.focus_set()

        self.result_var.set("Start typing to begin the timer.")
        self.stats_var.set("Time: 0.0s   WPM: 0   Accuracy: 100%")
        self.show_best()
        self.highlight("")

    def on_key_press(self, event):
        # Start the clock on the first real (printable) key
        if self.start_time is None and not self.finished:
            if event.char and event.char.isprintable():
                self.start_time = time.perf_counter()
                self.tick()

    def on_key_release(self, event):
        if self.finished:
            return
        typed = self.input.get("1.0", "end-1c")
        self.highlight(typed)
        if len(typed) >= len(self.target):
            self.finish()

    def highlight(self, typed):
        """Colour each typed character green or red; mark the next one."""
        self.display.tag_remove("correct", "1.0", tk.END)
        self.display.tag_remove("wrong", "1.0", tk.END)
        self.display.tag_remove("cursor", "1.0", tk.END)
        for i, ch in enumerate(typed[:len(self.target)]):
            tag = "correct" if ch == self.target[i] else "wrong"
            self.display.tag_add(tag, f"1.0+{i}c", f"1.0+{i + 1}c")
        if len(typed) < len(self.target):
            self.display.tag_add("cursor", f"1.0+{len(typed)}c",
                                 f"1.0+{len(typed) + 1}c")

    # ---------------------------------------------------------- statistics
    def elapsed(self):
        return 0.0 if self.start_time is None else time.perf_counter() - self.start_time

    def compute_stats(self):
        """Return (wpm, accuracy_percent) for the text typed so far."""
        typed = self.input.get("1.0", "end-1c")[:len(self.target)]
        correct = sum(1 for i, ch in enumerate(typed) if ch == self.target[i])
        minutes = max(self.elapsed(), 0.001) / 60
        wpm = (correct / 5) / minutes          # 1 "word" = 5 characters
        accuracy = (correct / len(typed) * 100) if typed else 100.0
        return wpm, accuracy

    def tick(self):
        """Refresh the live stats every 100 ms while the test is running."""
        if self.finished or self.start_time is None:
            return
        limit = TIME_LIMITS[self.limit_var.get()]
        elapsed = self.elapsed()
        if limit and elapsed >= limit:
            self.finish()
            return
        wpm, accuracy = self.compute_stats()
        shown = f"{max(limit - elapsed, 0):.1f}s left" if limit else f"{elapsed:.1f}s"
        self.stats_var.set(f"Time: {shown}   WPM: {wpm:.0f}   Accuracy: {accuracy:.0f}%")
        self.timer_job = self.after(100, self.tick)

    def finish(self):
        self.finished = True
        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        self.input.config(state="disabled")

        wpm, accuracy = self.compute_stats()
        self.stats_var.set(f"Time: {self.elapsed():.1f}s   WPM: {wpm:.0f}   "
                           f"Accuracy: {accuracy:.0f}%")
        message = f"Finished! {wpm:.1f} WPM at {accuracy:.0f}% accuracy."
        if wpm > self.best.get("wpm", 0):
            message += "  New personal best!"
            self.best = {"wpm": round(wpm, 1), "accuracy": round(accuracy, 1)}
            self.save_best()
            self.show_best()
        self.result_var.set(message)

    # ------------------------------------------------------- best score file
    def load_best(self):
        try:
            with open(BEST_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return {"wpm": float(data["wpm"]), "accuracy": float(data["accuracy"])}
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    def save_best(self):
        try:
            with open(BEST_FILE, "w", encoding="utf-8") as f:
                json.dump(self.best, f)
        except OSError:
            pass

    def show_best(self):
        if self.best:
            self.best_var.set(f"Best: {self.best['wpm']:.1f} WPM "
                              f"({self.best['accuracy']:.0f}% accuracy)")
        else:
            self.best_var.set("Best: no score yet")


if __name__ == "__main__":
    TypingTester().mainloop()