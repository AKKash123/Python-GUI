"""Typing Speed Tester PRO (Tkinter) - a more interactive version.

What's new compared with the basic version
- Type directly on the passage (no separate input box) with a moving caret
- On-screen keyboard: the next key glows, pressed keys flash green / red
- Live WPM graph drawn on a Canvas, updated every second
- Progress bar, stat cards (time, WPM, accuracy, best score)
- Modes (15s / 30s / 60s / 25 words) and levels (Easy / Medium / Hard)
- Dark / light theme switch, hover effects on every clickable item
- Results dialog with a WPM-over-time graph and personal-best detection
- Settings and score history saved to typing_data.json

Shortcuts: Tab or Esc = new test, Backspace = fix a mistake.
"""

import json
import math
import random
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont

DATA_FILE = Path(__file__).with_name("typing_data.json")
UI = "Segoe UI"

THEMES = {
    "dark": dict(bg="#1b1c23", card="#262833", hover="#33364a", text="#e8e9ef",
                 muted="#7b8096", accent="#f5c542", on_accent="#1b1c23",
                 correct="#5ad18f", wrong="#ff6b7a", wrong_bg="#4a2630",
                 key="#30333f", key_text="#c9ccd8", grid="#363a4a"),
    "light": dict(bg="#f3f4f9", card="#ffffff", hover="#e1e5f2", text="#262838",
                  muted="#8a90a8", accent="#3b6bff", on_accent="#ffffff",
                  correct="#16a34a", wrong="#dc2f45", wrong_bg="#fde1e5",
                  key="#e4e7f1", key_text="#3b3f55", grid="#e6e9f2"),
}

MODES = {"15s": ("time", 15), "30s": ("time", 30), "60s": ("time", 60),
         "25 words": ("words", 25)}
LEVELS = ["Easy", "Medium", "Hard"]

EASY = ("the be to of and a in that have it for not on with he as you do at this "
        "but his by from they we say her she or an will my one all would there "
        "their what so up out if about who get which go me when make can like "
        "time no just him know take people into year your good some could them "
        "see other than then now look only come its over think also back after "
        "use two how our work first well way even new want because any these "
        "give day most us").split()

HARD = ("algorithm architecture beautiful challenge development environment "
        "framework generation hypothesis implementation javascript knowledge "
        "laboratory mechanism navigation optimization performance quantum rhythm "
        "sophisticated technology unpredictable vocabulary workshop xylophone "
        "yesterday zealous asynchronous bandwidth compiler database encryption "
        "function interface keyboard language network protocol recursion syntax "
        "variable").split()

SHIFT_MAP = {"<": ",", ">": ".", "?": "/", ":": ";", '"': "'", "_": "-",
             "+": "=", "{": "[", "}": "]"}


def make_text(count, level):
    """Build a random passage of `count` words for the chosen level."""
    words = []
    for _ in range(count):
        if level == "Easy":
            word = random.choice(EASY)
        elif level == "Medium":
            word = random.choice(HARD if random.random() < 0.3 else EASY)
        else:
            word = random.choice(HARD)
            if random.random() < 0.15:
                word = word.capitalize()
            if random.random() < 0.2:
                word += random.choice(",.;")
        words.append(word)
    return " ".join(words)


class Segment(tk.Frame):
    """A row of clickable 'pills' (like radio buttons) with hover effects."""

    def __init__(self, master, options, command, initial, app):
        super().__init__(master)
        self.app, self.command, self.value = app, command, initial
        self.labels = {}
        for opt in options:
            lbl = tk.Label(self, text=opt, padx=12, pady=5, cursor="hand2",
                           font=(UI, 10, "bold"))
            lbl.pack(side="left", padx=(0, 2))
            lbl.bind("<Button-1>", lambda e, o=opt: self.select(o))
            lbl.bind("<Enter>", lambda e, o=opt: self._hover(o, True))
            lbl.bind("<Leave>", lambda e, o=opt: self._hover(o, False))
            self.labels[opt] = lbl

    def select(self, opt):
        if opt == self.value:
            return
        self.value = opt
        self.restyle()
        self.command(opt)

    def _hover(self, opt, inside):
        if opt != self.value:
            t = self.app.theme
            self.labels[opt].config(bg=t["hover"] if inside else t["card"])

    def restyle(self):
        t = self.app.theme
        self.config(bg=t["bg"])
        for opt, lbl in self.labels.items():
            on = opt == self.value
            lbl.config(bg=t["accent"] if on else t["card"],
                       fg=t["on_accent"] if on else t["muted"])


class TypingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Typing Speed Tester Pro")
        self.geometry("880x790")
        self.minsize(780, 720)

        self.mono = tkfont.nametofont("TkFixedFont").actual("family")
        self.data = self.load_data()
        self.theme_name = self.data["theme"]
        self.theme = THEMES[self.theme_name]
        self.mode_name = self.data["mode"]
        self.level = self.data["level"]

        self._themed = []            # (widget, bg key, fg key) for theme switching
        self.kb_keys = {}            # character -> (rect id, text id)
        self.job = None              # timer job id
        self.flash_job = None
        self.samples = []            # [(seconds, wpm), ...] for the graph
        self.progress_frac = 0.0
        self.target = self.typed = ""
        self.finished = False
        self.start_time = None
        self.limit = None
        self.word_mode = False
        self.keys_total = self.keys_correct = self.last_sample = 0

        self._build_ui()
        self.apply_theme()
        self.bind("<Key>", self.on_key)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.new_test()

    # --------------------------------------------------------------- helpers
    def reg(self, widget, bg, fg=None):
        """Register a widget so apply_theme() can recolour it."""
        self._themed.append((widget, bg, fg))
        return widget

    # -------------------------------------------------------------------- UI
    def _build_ui(self):
        # Header
        header = self.reg(tk.Frame(self), "bg")
        header.pack(fill="x", padx=24, pady=(18, 6))
        self.reg(tk.Label(header, text="Typing Speed Tester",
                          font=(UI, 20, "bold")), "bg", "text").pack(side="left")
        self.theme_btn = self.reg(
            tk.Label(header, padx=12, pady=5, cursor="hand2", font=(UI, 10, "bold")),
            "card", "text")
        self.theme_btn.pack(side="right")
        self.theme_btn.bind("<Button-1>", lambda e: self.toggle_theme())

        # Options row
        opts = self.reg(tk.Frame(self), "bg")
        opts.pack(fill="x", padx=24, pady=6)
        self.reg(tk.Label(opts, text="MODE", font=(UI, 8, "bold")),
                 "bg", "muted").pack(side="left")
        self.mode_seg = Segment(opts, list(MODES), self.on_mode, self.mode_name, self)
        self.mode_seg.pack(side="left", padx=(8, 28))
        self.reg(tk.Label(opts, text="LEVEL", font=(UI, 8, "bold")),
                 "bg", "muted").pack(side="left")
        self.level_seg = Segment(opts, LEVELS, self.on_level, self.level, self)
        self.level_seg.pack(side="left", padx=8)

        # Stat cards
        cards = self.reg(tk.Frame(self), "bg")
        cards.pack(fill="x", padx=24, pady=10)
        self.stat_vars = {}
        for i, (key, caption) in enumerate([("time", "TIME"), ("wpm", "WPM"),
                                            ("acc", "ACCURACY"),
                                            ("best", "BEST (THIS MODE)")]):
            cards.columnconfigure(i, weight=1, uniform="cards")
            card = self.reg(tk.Frame(cards, padx=14, pady=10), "card")
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            var = tk.StringVar(value="-")
            self.stat_vars[key] = var
            self.reg(tk.Label(card, textvariable=var, font=(UI, 26, "bold"),
                              anchor="w"),
                     "card", "accent" if key == "wpm" else "text").pack(fill="x")
            self.reg(tk.Label(card, text=caption, font=(UI, 8, "bold"), anchor="w"),
                     "card", "muted").pack(fill="x")

        # Progress bar
        self.progress = self.reg(tk.Canvas(self, height=6, highlightthickness=0), "bg")
        self.progress.pack(fill="x", padx=24, pady=(0, 10))
        self.progress.bind("<Configure>", lambda e: self.draw_progress())

        # Passage (read-only; keys are captured by the window)
        self.display = tk.Text(self, height=5, wrap="word", font=(self.mono, 20),
                               padx=18, pady=14, relief="flat", bd=0,
                               highlightthickness=0, cursor="arrow", takefocus=0,
                               spacing1=4, spacing3=4, state="disabled")
        self.reg(self.display, "card", "muted")
        self.display.pack(fill="x", padx=24)
        for ev in ("<Button-1>", "<B1-Motion>", "<Double-Button-1>",
                   "<Triple-Button-1>", "<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.display.bind(ev, lambda e: "break")

        # Hint
        self.hint = tk.StringVar()
        self.reg(tk.Label(self, textvariable=self.hint, font=(UI, 10)),
                 "bg", "muted").pack(pady=8)

        # Live graph
        self.graph = self.reg(tk.Canvas(self, height=120, highlightthickness=0), "card")
        self.graph.pack(fill="x", padx=24)
        self.graph.bind("<Configure>",
                        lambda e: self.draw_graph(self.graph, self.samples,
                                                  self.graph_xmax()))

        # On-screen keyboard
        self._build_keyboard()

    def _build_keyboard(self):
        unit, size = 36, 32
        self.kb = self.reg(tk.Canvas(self, width=int(13 * unit) + 8,
                                     height=5 * unit + 6, highlightthickness=0), "bg")
        self.kb.pack(pady=12)
        rows = [("1234567890-=", 0), ("qwertyuiop[]", 0.5),
                ("asdfghjkl;'", 0.8), ("zxcvbnm,./", 1.3)]
        for r, (keys, offset) in enumerate(rows):
            for i, ch in enumerate(keys):
                x, y = 4 + (offset + i) * unit, 3 + r * unit
                rect = self.kb.create_rectangle(x, y, x + size, y + size, width=0)
                txt = self.kb.create_text(x + size / 2, y + size / 2,
                                          text=ch.upper() if ch.isalpha() else ch,
                                          font=(UI, 10, "bold"))
                self.kb_keys[ch] = (rect, txt)
        x, y, width = 4 + 3.3 * unit, 3 + 4 * unit, 6 * unit - 4
        rect = self.kb.create_rectangle(x, y, x + width, y + size, width=0)
        txt = self.kb.create_text(x + width / 2, y + size / 2, text="space",
                                  font=(UI, 9, "bold"))
        self.kb_keys[" "] = (rect, txt)

    # ----------------------------------------------------------------- theme
    def apply_theme(self):
        t = self.theme
        self.configure(bg=t["bg"])
        for widget, bg, fg in self._themed:
            options = {"bg": t[bg]}
            if fg:
                options["fg"] = t[fg]
            widget.config(**options)
        self.mode_seg.restyle()
        self.level_seg.restyle()
        self.theme_btn.config(
            text="Light mode" if self.theme_name == "dark" else "Dark mode")

        d = self.display
        d.tag_configure("correct", foreground=t["correct"])
        d.tag_configure("wrong", foreground=t["wrong"], background=t["wrong_bg"])
        d.tag_configure("cursor", foreground=t["on_accent"], background=t["accent"])

        self.draw_progress()
        self.draw_graph(self.graph, self.samples, self.graph_xmax())
        self.refresh_keyboard()

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.theme = THEMES[self.theme_name]
        self.apply_theme()
        self.save_data()

    # ------------------------------------------------------------ test flow
    def on_mode(self, name):
        self.mode_name = name
        self.save_data()
        self.new_test()

    def on_level(self, name):
        self.level = name
        self.save_data()
        self.new_test()

    def new_test(self):
        if self.job:
            self.after_cancel(self.job)
            self.job = None
        kind, value = MODES[self.mode_name]
        self.word_mode = kind == "words"
        self.limit = value if kind == "time" else None
        self.target = make_text(value if self.word_mode else 40, self.level)
        self.typed = ""
        self.start_time = None
        self.finished = False
        self.keys_total = self.keys_correct = self.last_sample = 0
        self.samples = []

        d = self.display
        d.config(state="normal")
        d.delete("1.0", "end")
        d.insert("1.0", self.target)
        d.config(state="disabled")
        d.yview_moveto(0)

        self.stat_vars["time"].set(f"{self.limit}s" if self.limit else "0.0s")
        self.stat_vars["wpm"].set("0")
        self.stat_vars["acc"].set("100%")
        self.update_best_card()
        self.progress_frac = 0.0
        self.draw_progress()
        self.hint.set("Start typing to begin   |   Tab or Esc = restart")
        self.render()
        self.refresh_keyboard()
        self.draw_graph(self.graph, self.samples, self.graph_xmax())
        self.focus_set()

    def extend_target(self):
        """Time modes: append more words so the passage never runs out."""
        extra = " " + make_text(20, self.level)
        self.target += extra
        d = self.display
        d.config(state="normal")
        d.insert("end-1c", extra)
        d.config(state="disabled")

    def start(self):
        self.start_time = time.perf_counter()
        self.hint.set("Go!   Backspace fixes mistakes")
        self.tick()

    def elapsed(self):
        return 0.0 if self.start_time is None else time.perf_counter() - self.start_time

    # ---------------------------------------------------------------- keys
    def on_key(self, event):
        if event.keysym in ("Escape", "Tab"):
            self.new_test()
            return "break"
        if self.finished:
            return
        if event.keysym == "BackSpace":
            if self.typed:
                self.typed = self.typed[:-1]
                self.render()
                self.refresh_keyboard()
            return
        if not event.char or not event.char.isprintable() or event.state & 0x4:
            return                                    # ignore Shift, Ctrl+..., etc.

        if self.start_time is None:
            self.start()
        expected = self.target[len(self.typed)]
        ok = event.char == expected
        self.keys_total += 1
        self.keys_correct += ok
        self.typed += event.char
        self.render()
        self.flash_key(event.char, ok)

        if self.word_mode and len(self.typed) >= len(self.target):
            self.finish()
        elif not self.word_mode and len(self.target) - len(self.typed) < 120:
            self.extend_target()

    def render(self):
        """Colour typed characters and move the caret highlight."""
        d = self.display
        for tag in ("correct", "wrong", "cursor"):
            d.tag_remove(tag, "1.0", "end")
        for i, ch in enumerate(self.typed):
            tag = "correct" if ch == self.target[i] else "wrong"
            d.tag_add(tag, f"1.0+{i}c", f"1.0+{i + 1}c")
        n = len(self.typed)
        if n < len(self.target):
            d.tag_add("cursor", f"1.0+{n}c", f"1.0+{n + 1}c")
            d.see(f"1.0+{n}c")
        if self.word_mode:
            self.progress_frac = n / len(self.target)
            self.draw_progress()

    # ------------------------------------------------------------ keyboard
    def key_for(self, ch):
        low = ch.lower()
        return low if low in self.kb_keys else SHIFT_MAP.get(ch)

    def refresh_keyboard(self):
        t = self.theme
        nxt = None
        if not self.finished and len(self.typed) < len(self.target):
            nxt = self.key_for(self.target[len(self.typed)])
        for ch, (rect, txt) in self.kb_keys.items():
            hot = ch == nxt
            self.kb.itemconfig(rect, fill=t["accent"] if hot else t["key"])
            self.kb.itemconfig(txt, fill=t["on_accent"] if hot else t["key_text"])

    def flash_key(self, ch, ok):
        self.refresh_keyboard()
        key = self.key_for(ch)
        if key:
            rect, txt = self.kb_keys[key]
            self.kb.itemconfig(rect, fill=self.theme["correct" if ok else "wrong"])
            self.kb.itemconfig(txt, fill=self.theme["on_accent"])
        if self.flash_job:
            self.after_cancel(self.flash_job)
        self.flash_job = self.after(160, self.refresh_keyboard)

    # --------------------------------------------------------------- stats
    def correct_chars(self):
        return sum(1 for i, ch in enumerate(self.typed) if ch == self.target[i])

    def live_stats(self):
        minutes = max(self.elapsed(), 1.0) / 60
        wpm = self.correct_chars() / 5 / minutes       # 1 word = 5 characters
        acc = 100 * self.keys_correct / self.keys_total if self.keys_total else 100
        return wpm, acc

    def tick(self):
        if self.finished or self.start_time is None:
            return
        el = self.elapsed()
        if self.limit and el >= self.limit:
            self.finish()
            return
        wpm, acc = self.live_stats()
        shown = f"{math.ceil(self.limit - el)}s" if self.limit else f"{el:.1f}s"
        self.stat_vars["time"].set(shown)
        self.stat_vars["wpm"].set(f"{wpm:.0f}")
        self.stat_vars["acc"].set(f"{acc:.0f}%")
        if self.limit:
            self.progress_frac = el / self.limit
            self.draw_progress()
        if int(el) > self.last_sample:                 # one graph point per second
            self.last_sample = int(el)
            self.samples.append((int(el), wpm))
            self.draw_graph(self.graph, self.samples, self.graph_xmax())
        self.job = self.after(100, self.tick)

    def finish(self):
        if self.finished:
            return
        self.finished = True
        if self.job:
            self.after_cancel(self.job)
            self.job = None
        el = self.elapsed()
        if self.limit:
            el = min(el, self.limit)
        el = max(el, 0.5)

        correct = self.correct_chars()
        wpm = correct / 5 / (el / 60)
        raw = len(self.typed) / 5 / (el / 60)
        acc = 100 * self.keys_correct / self.keys_total if self.keys_total else 100
        self.samples.append((el, wpm))

        previous = self.best_for()
        new_best = previous is None or wpm > previous
        self.data["history"].append({
            "wpm": round(wpm, 1), "accuracy": round(acc, 1),
            "mode": self.mode_name, "level": self.level,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")})
        self.data["history"] = self.data["history"][-100:]
        self.save_data()

        self.stat_vars["time"].set(f"{el:.1f}s")
        self.stat_vars["wpm"].set(f"{wpm:.0f}")
        self.stat_vars["acc"].set(f"{acc:.0f}%")
        self.update_best_card()
        self.progress_frac = 1.0
        self.draw_progress()
        self.hint.set("Finished!   Press Tab or Esc for a new test")
        self.refresh_keyboard()
        self.draw_graph(self.graph, self.samples, self.graph_xmax())
        self.show_results(wpm, raw, acc, el, correct, new_best)

    # ------------------------------------------------------------- drawing
    def draw_progress(self):
        c, t = self.progress, self.theme
        c.delete("all")
        w = c.winfo_width()
        c.create_rectangle(0, 0, w, 6, fill=t["card"], width=0)
        c.create_rectangle(0, 0, w * self.progress_frac, 6, fill=t["accent"], width=0)

    def graph_xmax(self):
        if self.limit:
            return self.limit
        return max([s[0] for s in self.samples] + [5])

    def draw_graph(self, cv, samples, xmax):
        t = self.theme
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 20:                                     # not laid out yet
            w, h = int(cv.cget("width")), int(cv.cget("height"))
        if len(samples) < 2:
            cv.create_text(w / 2, h / 2, text="Your live WPM graph appears here",
                           fill=t["muted"], font=(UI, 10))
            return
        left, right, top, bottom = 36, 12, 10, 20
        pw, ph = w - left - right, h - top - bottom
        ymax = max(30, max(s[1] for s in samples) * 1.25)
        xmax = max(xmax, 1)

        for frac in (0, 0.5, 1):
            y = top + ph * (1 - frac)
            cv.create_line(left, y, w - right, y, fill=t["grid"])
            cv.create_text(left - 6, y, text=f"{ymax * frac:.0f}", anchor="e",
                           fill=t["muted"], font=(UI, 8))
        points = []
        for sec, value in samples:
            points += [left + pw * min(sec / xmax, 1), top + ph * (1 - value / ymax)]
        cv.create_line(*points, fill=t["accent"], width=2, smooth=True)
        x, y = points[-2:]
        cv.create_oval(x - 4, y - 4, x + 4, y + 4, fill=t["accent"], outline="")
        cv.create_text(left, h - 8, text="0s", anchor="w", fill=t["muted"], font=(UI, 8))
        cv.create_text(w - right, h - 8, text=f"{xmax:.0f}s", anchor="e",
                       fill=t["muted"], font=(UI, 8))

    # ------------------------------------------------------------- results
    def show_results(self, wpm, raw, acc, el, correct, new_best):
        t = self.theme
        win = tk.Toplevel(self)
        win.title("Results")
        win.configure(bg=t["bg"], padx=30, pady=20)
        win.transient(self)
        win.resizable(False, False)

        def close(again=False):
            win.grab_release()
            win.destroy()
            if again:
                self.new_test()
            self.focus_set()

        tk.Label(win, text=f"{wpm:.0f}", font=(UI, 60, "bold"),
                 fg=t["accent"], bg=t["bg"]).pack()
        tk.Label(win, text="WORDS PER MINUTE", font=(UI, 9, "bold"),
                 fg=t["muted"], bg=t["bg"]).pack()
        if new_best:
            tk.Label(win, text="New personal best!", font=(UI, 11, "bold"),
                     fg=t["correct"], bg=t["bg"]).pack(pady=(8, 0))

        stats = tk.Frame(win, bg=t["bg"])
        stats.pack(pady=14)
        for i, (caption, value) in enumerate([
                ("ACCURACY", f"{acc:.0f}%"), ("RAW WPM", f"{raw:.0f}"),
                ("CORRECT CHARS", f"{correct}/{len(self.typed)}"),
                ("TIME", f"{el:.1f}s")]):
            box = tk.Frame(stats, bg=t["card"], padx=14, pady=8)
            box.grid(row=0, column=i, padx=4)
            tk.Label(box, text=value, font=(UI, 16, "bold"), fg=t["text"],
                     bg=t["card"]).pack()
            tk.Label(box, text=caption, font=(UI, 7, "bold"), fg=t["muted"],
                     bg=t["card"]).pack()

        cv = tk.Canvas(win, width=480, height=140, bg=t["card"], highlightthickness=0)
        cv.pack()
        self.draw_graph(cv, self.samples, self.graph_xmax())

        buttons = tk.Frame(win, bg=t["bg"])
        buttons.pack(pady=(16, 0))
        for text, again, primary in (("Try again (Enter)", True, True),
                                     ("Close (Esc)", False, False)):
            btn = tk.Label(buttons, text=text, padx=18, pady=8, cursor="hand2",
                           font=(UI, 11, "bold"),
                           bg=t["accent"] if primary else t["card"],
                           fg=t["on_accent"] if primary else t["text"])
            btn.pack(side="left", padx=6)
            btn.bind("<Button-1>", lambda e, a=again: close(a))
            if not primary:
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=t["hover"]))
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg=t["card"]))
        win.bind("<Return>", lambda e: close(True))
        win.bind("<Escape>", lambda e: close(False))
        win.protocol("WM_DELETE_WINDOW", lambda: close(False))

        win.update_idletasks()                         # centre over the main window
        x = self.winfo_rootx() + (self.winfo_width() - win.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - win.winfo_reqheight()) // 2
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        try:
            win.wait_visibility()
            win.grab_set()
        except tk.TclError:
            pass
        win.focus_set()

    # --------------------------------------------------------------- data
    def load_data(self):
        data = {"theme": "dark", "mode": "30s", "level": "Medium", "history": []}
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                saved = json.load(f)
            for key in data:
                if key in saved:
                    data[key] = saved[key]
        except (OSError, ValueError, TypeError):
            pass
        if data["theme"] not in THEMES:
            data["theme"] = "dark"
        if data["mode"] not in MODES:
            data["mode"] = "30s"
        if data["level"] not in LEVELS:
            data["level"] = "Medium"
        if not isinstance(data["history"], list):
            data["history"] = []
        return data

    def save_data(self):
        self.data.update(theme=self.theme_name, mode=self.mode_name, level=self.level)
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except OSError:
            pass

    def best_for(self):
        values = [h["wpm"] for h in self.data["history"]
                  if isinstance(h, dict) and h.get("mode") == self.mode_name
                  and h.get("level") == self.level
                  and isinstance(h.get("wpm"), (int, float))]
        return max(values) if values else None

    def update_best_card(self):
        best = self.best_for()
        self.stat_vars["best"].set(f"{best:.0f}" if best else "-")

    def on_close(self):
        self.save_data()
        self.destroy()


if __name__ == "__main__":
    TypingApp().mainloop()
