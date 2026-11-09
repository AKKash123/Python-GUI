"""To-Do List app (Tkinter) with save and load using JSON.

Features
- Add tasks (button or Enter key)
- Mark tasks done / not done (double-click or button)
- Delete selected task, clear completed tasks
- Auto-load on start and auto-save on close (tasks.json)
- File menu: Open..., Save, Save As...
"""

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

DEFAULT_FILE = Path(__file__).with_name("tasks.json")


class TodoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("To-Do List")
        self.geometry("420x500")
        self.minsize(360, 400)

        self.tasks = []                 # [{"text": str, "done": bool}, ...]
        self.current_file = DEFAULT_FILE

        self._build_menu()
        self._build_ui()
        self.load_tasks(self.current_file, silent=True)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------ UI
    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open...", accelerator="Ctrl+O",
                              command=self.open_file)
        file_menu.add_command(label="Save", accelerator="Ctrl+S",
                              command=self.save_tasks)
        file_menu.add_command(label="Save As...", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

        self.bind("<Control-o>", lambda e: self.open_file())
        self.bind("<Control-s>", lambda e: self.save_tasks())

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        # Row 0: input + Add button
        self.entry = ttk.Entry(main)
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.entry.bind("<Return>", lambda e: self.add_task())
        self.entry.focus()
        ttk.Button(main, text="Add", command=self.add_task).grid(row=0, column=1)

        # Row 1: list + scrollbar
        list_frame = ttk.Frame(main)
        list_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=10)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(list_frame, activestyle="none",
                                  selectmode=tk.SINGLE, font=("Segoe UI", 11))
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self.listbox.bind("<Double-Button-1>", lambda e: self.toggle_done())
        self.listbox.bind("<Delete>", lambda e: self.delete_task())

        scroll = ttk.Scrollbar(list_frame, orient="vertical",
                               command=self.listbox.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.listbox.config(yscrollcommand=scroll.set)

        # Row 2: action buttons
        buttons = ttk.Frame(main)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew")
        for i in range(3):
            buttons.columnconfigure(i, weight=1)
        ttk.Button(buttons, text="Done / Undo",
                   command=self.toggle_done).grid(row=0, column=0, padx=2, sticky="ew")
        ttk.Button(buttons, text="Delete",
                   command=self.delete_task).grid(row=0, column=1, padx=2, sticky="ew")
        ttk.Button(buttons, text="Clear completed",
                   command=self.clear_completed).grid(row=0, column=2, padx=2, sticky="ew")

        # Row 3: status bar
        self.status = tk.StringVar(value="Ready")
        ttk.Label(main, textvariable=self.status, anchor="w").grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    # ------------------------------------------------------------ display
    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for i, task in enumerate(self.tasks):
            prefix = "\u2713 " if task["done"] else "\u2610 "
            self.listbox.insert(tk.END, prefix + task["text"])
            if task["done"]:
                self.listbox.itemconfig(i, fg="gray")
        done = sum(t["done"] for t in self.tasks)
        self.status.set(f"{len(self.tasks)} tasks, {done} completed")

    def selected_index(self):
        selection = self.listbox.curselection()
        return selection[0] if selection else None

    # ------------------------------------------------------------ actions
    def add_task(self):
        text = self.entry.get().strip()
        if not text:
            messagebox.showwarning("Empty task", "Please type a task first.")
            return
        self.tasks.append({"text": text, "done": False})
        self.entry.delete(0, tk.END)
        self.refresh_list()
        self.listbox.see(tk.END)

    def toggle_done(self):
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("No selection", "Select a task first.")
            return
        self.tasks[index]["done"] = not self.tasks[index]["done"]
        self.refresh_list()
        self.listbox.selection_set(index)

    def delete_task(self):
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("No selection", "Select a task first.")
            return
        del self.tasks[index]
        self.refresh_list()

    def clear_completed(self):
        if not any(t["done"] for t in self.tasks):
            return
        if messagebox.askyesno("Confirm", "Remove all completed tasks?"):
            self.tasks = [t for t in self.tasks if not t["done"]]
            self.refresh_list()

    # -------------------------------------------------------- save / load
    def save_tasks(self, path=None):
        path = Path(path or self.current_file)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, indent=2, ensure_ascii=False)
        except OSError as err:
            messagebox.showerror("Save failed", str(err))
            return False
        self.current_file = path
        self.status.set(f"Saved to {path.name}")
        return True

    def save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=self.current_file.name)
        if path:
            self.save_tasks(path)

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            self.load_tasks(path)

    def load_tasks(self, path, silent=False):
        path = Path(path)
        if not path.exists():
            if not silent:
                messagebox.showerror("Not found", f"{path} does not exist.")
            self.refresh_list()
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # Validate structure before accepting it
            self.tasks = [
                {"text": str(item["text"]), "done": bool(item.get("done", False))}
                for item in data
            ]
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            messagebox.showerror("Load failed",
                                 "The file is not a valid to-do list.")
            return
        self.current_file = path
        self.refresh_list()
        self.status.set(f"Loaded {len(self.tasks)} tasks from {path.name}")

    def on_close(self):
        self.save_tasks()
        self.destroy()


if __name__ == "__main__":
    TodoApp().mainloop()