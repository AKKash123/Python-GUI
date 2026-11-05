"""
=====================================================================
 ORDER MANAGEMENT SYSTEM (OMS) - Professional Dashboard Edition
=====================================================================
A desktop application built with tkinter (standard library only).
Uses the same orders.json format as the command-line version.

Dashboard
---------
 * KPI cards : orders, revenue, delivered revenue, avg order value,
               delivery rate
 * Charts    : monthly revenue (bar), order status mix (donut),
               top products (bar), top customers (bar)
 * Recent orders panel, period filter, hover tooltips on every chart

Orders
------
 * Sortable, colour-coded table  * Live search + status filter
 * Add / edit / delete with validated forms

Tools
-----
 * Timestamped backups  * CSV export  * Reload from disk

Shortcuts: Ctrl+N new order | Ctrl+1 dashboard | Ctrl+2 orders |
           Ctrl+F search | Delete remove | F5 reload

Run :  python order_management_dashboard.py
Data:  orders.json (same folder as this script)
=====================================================================
"""

import csv
import json
import math
import os
import tkinter as tk
from collections import defaultdict
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "orders.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
VALID_STATUSES = ["Pending", "Shipped", "Delivered", "Cancelled"]

# Palette
SIDEBAR = "#1789ac"
SIDEBAR_HOVER = "#243053"
ACCENT = "#3b6ef5"
ACCENT_DARK = "#2c58d1"
BG = "#f2f5fa"
CARD = "#ffffff"
BORDER = "#e1e6ef"
TEXT = "#1f2937"
MUTED = "#6b7280"
GRID = "#e8ecf3"

STATUS_COLORS = {   # (row background, chart colour)
    "Pending":   ("#fff6d6", "#f2b01e"),
    "Shipped":   ("#dbeafe", "#3b82f6"),
    "Delivered": ("#dcf5e3", "#22a05b"),
    "Cancelled": ("#fde2e4", "#e5484d"),
}
SERIES = ["#3b6ef5", "#7c5cdb", "#14a3a3", "#f08a24", "#e5484d", "#22a05b"]

FONT = "Segoe UI"

COLUMNS = [  # key, heading, width, anchor, numeric?
    ("order_id",      "Order ID",   90,  "w",      False),
    ("customer_name", "Customer",   180, "w",      False),
    ("product",       "Product",    180, "w",      False),
    ("quantity",      "Qty",        60,  "e",      True),
    ("unit_price",    "Unit Price", 110, "e",      True),
    ("total_amount",  "Total",      120, "e",      True),
    ("status",        "Status",     100, "center", False),
    ("order_date",    "Order Date", 150, "center", False),
]


# ---------------------------------------------------------------------
# File handling layer
# ---------------------------------------------------------------------
def load_orders():
    """Load orders from JSON. Returns [] if missing/corrupt."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError) as e:
        messagebox.showwarning("Data file problem",
                               f"Could not read data file:\n{e}\n\nStarting with an empty list.")
        return []


def save_orders(orders):
    """Save orders to JSON. Returns True on success."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(orders, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        messagebox.showerror("Save failed", f"Could not save data:\n{e}")
        return False


def generate_order_id(orders):
    """Next sequential ID: ORD001, ORD002, ..."""
    max_num = 0
    for o in orders:
        oid = str(o.get("order_id", ""))
        if oid.startswith("ORD"):
            try:
                max_num = max(max_num, int(oid[3:]))
            except ValueError:
                continue
    return f"ORD{max_num + 1:03d}"


# ---------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------
def money(value):
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def short(v):
    """Compact number: 1.2K, 3.4L (lakh), 2.1Cr (crore)."""
    v = float(v)
    a = abs(v)
    if a >= 1e7:
        return f"{v / 1e7:.1f}Cr"
    if a >= 1e5:
        return f"{v / 1e5:.1f}L"
    if a >= 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{v:.0f}"


def nice_max(v):
    """Round a maximum up to a pleasant axis ceiling."""
    if v <= 0:
        return 1
    exp = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


def parse_date(text):
    try:
        return datetime.strptime(str(text)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(str(text)[:10], "%Y-%m-%d")
        except ValueError:
            return None


def trunc(text, n):
    text = str(text)
    return text if len(text) <= n else text[:n - 1] + "…"


# ---------------------------------------------------------------------
# Dashboard widgets
# ---------------------------------------------------------------------
class ChartCard(tk.Frame):
    """White card with a title and a canvas that redraws on resize.
    Supports hover tooltips through self.tip(item_id, text)."""

    def __init__(self, parent, title, subtitle=""):
        super().__init__(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        head = tk.Frame(self, bg=CARD)
        head.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(head, text=title, bg=CARD, fg=TEXT,
                 font=(FONT, 11, "bold")).pack(side="left")
        if subtitle:
            tk.Label(head, text=subtitle, bg=CARD, fg=MUTED,
                     font=(FONT, 9)).pack(side="left", padx=(8, 0), pady=(2, 0))
        self.canvas = tk.Canvas(self, bg=CARD, highlightthickness=0, height=170)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.draw_fn = None
        self._job = None
        self.canvas.bind("<Configure>", lambda e: self._schedule())

    def set_draw(self, fn):
        self.draw_fn = fn

    def _schedule(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(30, self.draw)

    def draw(self):
        self._job = None
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 40 or h < 40 or not self.draw_fn:
            return
        self.draw_fn(self, c, w, h)

    def empty(self, text="No data for this period"):
        c = self.canvas
        c.create_text(c.winfo_width() / 2, c.winfo_height() / 2, text=text,
                      fill=MUTED, font=(FONT, 10))

    # ----- tooltips -----
    def tip(self, item, text):
        c = self.canvas
        c.tag_bind(item, "<Enter>", lambda e, t=text: self._show_tip(e, t))
        c.tag_bind(item, "<Motion>", lambda e, t=text: self._show_tip(e, t))
        c.tag_bind(item, "<Leave>", lambda e: c.delete("tip"))

    def _show_tip(self, e, text):
        c = self.canvas
        c.delete("tip")
        right_side = e.x > c.winfo_width() * 0.6
        x = e.x - 12 if right_side else e.x + 12
        t = c.create_text(x, e.y - 8, text=text, fill="white", font=(FONT, 9, "bold"),
                          anchor="se" if right_side else "sw", tags="tip")
        x1, y1, x2, y2 = c.bbox(t)
        r = c.create_rectangle(x1 - 6, y1 - 3, x2 + 6, y2 + 3, fill="#111827",
                               outline="", tags="tip")
        c.tag_raise(t, r)


def draw_vbars(card, c, w, h, labels, values, color):
    """Vertical bar chart with gridlines, value labels and tooltips."""
    if not values or max(values) <= 0:
        return card.empty()
    pl, pr, pt, pb = 46, 14, 22, 26
    top = nice_max(max(values))
    ph = h - pt - pb
    pw = w - pl - pr
    for i in range(5):
        v = top * i / 4
        y = pt + ph - ph * i / 4
        c.create_line(pl, y, w - pr, y, fill=GRID)
        c.create_text(pl - 6, y, text=short(v), anchor="e", fill=MUTED, font=(FONT, 8))
    slot = pw / len(values)
    bw = min(slot * 0.55, 56)
    for i, (lab, val) in enumerate(zip(labels, values)):
        cx = pl + slot * (i + 0.5)
        y = pt + ph - ph * val / top
        bar = c.create_rectangle(cx - bw / 2, y, cx + bw / 2, pt + ph,
                                 fill=color, outline="", width=0)
        c.create_text(cx, y - 8, text=short(val), fill=TEXT, font=(FONT, 8, "bold"))
        c.create_text(cx, h - pb + 13, text=lab, fill=MUTED, font=(FONT, 8))
        card.tip(bar, f"{lab}: Rs {val:,.2f}")


def draw_hbars(card, c, w, h, labels, values, color):
    """Horizontal ranked bar chart."""
    if not values or max(values) <= 0:
        return card.empty()
    left, right, top_pad = 118, 62, 6
    n = len(values)
    row_h = min(34, (h - top_pad * 2) / n)
    bar_h = row_h * 0.52
    mx = max(values)
    avail = max(w - left - right, 20)
    for i, (lab, val) in enumerate(zip(labels, values)):
        cy = top_pad + row_h * (i + 0.5)
        c.create_text(left - 8, cy, text=trunc(lab, 17), anchor="e", fill=TEXT, font=(FONT, 9))
        c.create_rectangle(left, cy - bar_h / 2, left + avail, cy + bar_h / 2,
                           fill="#eef1f7", outline="")
        length = max(avail * val / mx, 3)
        bar = c.create_rectangle(left, cy - bar_h / 2, left + length, cy + bar_h / 2,
                                 fill=SERIES[i % len(SERIES)] if color is None else color,
                                 outline="")
        c.create_text(left + avail + 8, cy, text=short(val), anchor="w", fill=TEXT,
                      font=(FONT, 9, "bold"))
        card.tip(bar, f"{lab}: Rs {val:,.2f}")


def draw_donut(card, c, w, h, items):
    """Donut chart + legend. items = [(label, value, color), ...]"""
    total = sum(v for _, v, _ in items)
    if total <= 0:
        return card.empty()
    d = min(h - 16, w * 0.42)
    x0, y0 = 14, (h - d) / 2
    thick = max(d * 0.22, 14)
    box = (x0 + thick / 2, y0 + thick / 2, x0 + d - thick / 2, y0 + d - thick / 2)
    c.create_oval(*box, outline=GRID, width=thick)
    start = 90.0
    for label, val, color in items:
        if val <= 0:
            continue
        extent = -min(360 * val / total, 359.99)
        arc = c.create_arc(*box, start=start, extent=extent, style="arc",
                           outline=color, width=thick)
        card.tip(arc, f"{label}: {int(val)} ({val / total * 100:.1f}%)")
        start += extent
    c.create_text(x0 + d / 2, y0 + d / 2 - 8, text=str(int(total)), fill=TEXT,
                  font=(FONT, 20, "bold"))
    c.create_text(x0 + d / 2, y0 + d / 2 + 14, text="orders", fill=MUTED, font=(FONT, 9))
    lx = x0 + d + 24
    row = 34
    ly = h / 2 - len(items) * row / 2
    for i, (label, val, color) in enumerate(items):
        y = ly + i * row + 12
        c.create_rectangle(lx, y - 6, lx + 12, y + 6, fill=color, outline="")
        c.create_text(lx + 20, y - 6, text=label, anchor="w", fill=TEXT, font=(FONT, 10))
        c.create_text(lx + 20, y + 8, text=f"{int(val)} orders · {val / total * 100:.0f}%",
                      anchor="w", fill=MUTED, font=(FONT, 8))


# ---------------------------------------------------------------------
# Add / Edit dialog
# ---------------------------------------------------------------------
class OrderDialog(tk.Toplevel):
    """Modal form for creating or editing an order."""

    def __init__(self, parent, title, order_id, order=None):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(parent)
        self.result = None

        order = order or {}
        self.var_customer = tk.StringVar(value=order.get("customer_name", ""))
        self.var_product = tk.StringVar(value=order.get("product", ""))
        self.var_qty = tk.StringVar(value=str(order.get("quantity", 1)))
        self.var_price = tk.StringVar(value=str(order.get("unit_price", "")))
        self.var_status = tk.StringVar(value=order.get("status", "Pending"))
        self.var_total = tk.StringVar()

        head = tk.Frame(self, bg=ACCENT)
        head.pack(fill="x")
        tk.Label(head, text=title, bg=ACCENT, fg="white",
                 font=(FONT, 13, "bold")).pack(side="left", padx=20, pady=12)
        tk.Label(head, text=order_id, bg=ACCENT, fg="#cfdcff",
                 font=(FONT, 11, "bold")).pack(side="right", padx=20)

        body = tk.Frame(self, bg=CARD, padx=22, pady=16)
        body.pack(fill="both")
        self.entries = {}
        fields = [("Customer Name *", self.var_customer),
                  ("Product Name *", self.var_product),
                  ("Quantity *", self.var_qty),
                  ("Unit Price (Rs) *", self.var_price)]
        for i, (label, var) in enumerate(fields):
            tk.Label(body, text=label, bg=CARD, fg=MUTED, font=(FONT, 9)).grid(
                row=i * 2, column=0, sticky="w", pady=(6, 0))
            e = ttk.Entry(body, textvariable=var, width=34)
            e.grid(row=i * 2 + 1, column=0, sticky="we")
            self.entries[label] = e
        tk.Label(body, text="Status", bg=CARD, fg=MUTED, font=(FONT, 9)).grid(
            row=8, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(body, textvariable=self.var_status, values=VALID_STATUSES,
                     state="readonly").grid(row=9, column=0, sticky="we")

        tot = tk.Frame(body, bg="#f0f7f2", highlightbackground="#cfe8d7", highlightthickness=1)
        tot.grid(row=10, column=0, sticky="we", pady=(16, 0))
        tk.Label(tot, text="Order Total", bg="#f0f7f2", fg=MUTED,
                 font=(FONT, 9)).pack(side="left", padx=12, pady=8)
        tk.Label(tot, textvariable=self.var_total, bg="#f0f7f2", fg="#1d8a4e",
                 font=(FONT, 13, "bold")).pack(side="right", padx=12)

        btns = tk.Frame(body, bg=CARD)
        btns.grid(row=11, column=0, sticky="e", pady=(18, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="Save Order", style="Accent.TButton",
                   command=self._save).pack(side="right")

        self.var_qty.trace_add("write", lambda *_: self._update_total())
        self.var_price.trace_add("write", lambda *_: self._update_total())
        self._update_total()

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.entries["Customer Name *"].focus_set()
        self.grab_set()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _update_total(self):
        try:
            total = int(self.var_qty.get()) * float(self.var_price.get())
            self.var_total.set(f"Rs {total:,.2f}")
        except ValueError:
            self.var_total.set("Rs 0.00")

    def _save(self):
        customer = self.var_customer.get().strip()
        product = self.var_product.get().strip()
        if not customer:
            return self._error("Customer name cannot be empty.", "Customer Name *")
        if not product:
            return self._error("Product name cannot be empty.", "Product Name *")
        try:
            qty = int(self.var_qty.get().strip())
            if qty < 1:
                raise ValueError
        except ValueError:
            return self._error("Quantity must be a whole number of at least 1.", "Quantity *")
        try:
            price = float(self.var_price.get().strip())
            if price < 0:
                raise ValueError
        except ValueError:
            return self._error("Unit price must be a number (0 or more).", "Unit Price (Rs) *")

        self.result = {
            "customer_name": customer,
            "product": product,
            "quantity": qty,
            "unit_price": price,
            "total_amount": qty * price,
            "status": self.var_status.get(),
        }
        self.destroy()

    def _error(self, msg, field):
        messagebox.showerror("Invalid input", msg, parent=self)
        self.entries[field].focus_set()


# ---------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------
class OrderApp(tk.Tk):
    PERIODS = ["All time", "This month", "Last 30 days", "This year"]

    def __init__(self):
        super().__init__()
        self.title("Order Management System")
        self.geometry("1320x780")
        self.minsize(1120, 680)
        self.configure(bg=BG)

        self.orders = load_orders()
        self.sort_key = "order_id"
        self.sort_reverse = False
        self.kpi_vars = {}
        self.nav_buttons = {}
        self.pages = {}
        self.current_page = None
        self.dash = {}

        self._setup_style()
        self._build_sidebar()
        self._build_main()
        self._bind_keys()
        self.show_page("dashboard")
        self.refresh_all()
        self._tick()

    # ----- styling -----
    def _setup_style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=BG, font=(FONT, 10))
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=TEXT)
        s.configure("TButton", padding=(12, 6), background="#e7ebf3", foreground=TEXT,
                    borderwidth=0, focusthickness=0)
        s.map("TButton", background=[("active", "#d9dfeb")])
        s.configure("Accent.TButton", background=ACCENT, foreground="white")
        s.map("Accent.TButton", background=[("active", ACCENT_DARK)])
        s.configure("Danger.TButton", background="#fde2e4", foreground="#b42330")
        s.map("Danger.TButton", background=[("active", "#f9c9ce")])
        s.configure("TEntry", padding=5, fieldbackground="white")
        s.configure("TCombobox", padding=4, fieldbackground="white")
        s.configure("Treeview", rowheight=30, font=(FONT, 10), borderwidth=0,
                    fieldbackground="white", background="white")
        s.configure("Treeview.Heading", font=(FONT, 10, "bold"), background="#e9eef7",
                    foreground=TEXT, padding=8, relief="flat")
        s.map("Treeview.Heading", background=[("active", "#dde5f3")])
        s.map("Treeview", background=[("selected", ACCENT)],
              foreground=[("selected", "white")])

    # ----- sidebar -----
    def _build_sidebar(self):
        sb = tk.Frame(self, bg=SIDEBAR, width=215)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        tk.Label(sb, text="◆  OMS", bg=SIDEBAR, fg="white",
                 font=(FONT, 18, "bold")).pack(anchor="w", padx=22, pady=(24, 0))
        tk.Label(sb, text="Order Management", bg=SIDEBAR, fg="#8d9ab8",
                 font=(FONT, 9)).pack(anchor="w", padx=24, pady=(0, 24))

        self._section(sb, "MENU")
        self._nav(sb, "dashboard", "▦   Dashboard", lambda: self.show_page("dashboard"))
        self._nav(sb, "orders", "☰   Orders", lambda: self.show_page("orders"))

        self._section(sb, "QUICK ACTIONS")
        tk.Button(sb, text="＋   New Order", command=self.add_order, bg=ACCENT, fg="white",
                  activebackground=ACCENT_DARK, activeforeground="white", relief="flat",
                  font=(FONT, 10, "bold"), cursor="hand2", anchor="w", padx=18, pady=9,
                  bd=0, highlightthickness=0).pack(fill="x", padx=14, pady=(4, 8))
        self._nav(sb, None, "⤓   Backup Data", self.backup_orders)
        self._nav(sb, None, "⇪   Export CSV", self.export_csv)
        self._nav(sb, None, "⟳   Reload", self.reload)

        tk.Label(sb, text=f"v2.0  ·  {os.path.basename(DATA_FILE)}", bg=SIDEBAR, fg="#6c7a99",
                 font=(FONT, 8)).pack(side="bottom", anchor="w", padx=22, pady=14)

    def _section(self, parent, text):
        tk.Label(parent, text=text, bg=SIDEBAR, fg="#6c7a99",
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=24, pady=(14, 4))

    def _nav(self, parent, key, text, command):
        b = tk.Button(parent, text=text, command=command, bg=SIDEBAR, fg="#d6dcec",
                      activebackground=SIDEBAR_HOVER, activeforeground="white",
                      relief="flat", anchor="w", font=(FONT, 10), padx=22, pady=9,
                      cursor="hand2", bd=0, highlightthickness=0)
        b.pack(fill="x", padx=8, pady=1)
        b.bind("<Enter>", lambda e, b=b, k=key: b.config(bg=SIDEBAR_HOVER)
               if k != self.current_page else None)
        b.bind("<Leave>", lambda e, b=b, k=key: b.config(
            bg=ACCENT if k == self.current_page and k else SIDEBAR))
        if key:
            self.nav_buttons[key] = b

    def show_page(self, key):
        self.current_page = key
        for k, b in self.nav_buttons.items():
            b.config(bg=ACCENT if k == key else SIDEBAR,
                     fg="white" if k == key else "#d6dcec")
        for k, p in self.pages.items():
            p.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        self.title_var.set("Dashboard" if key == "dashboard" else "Orders")
        self.sub_var.set("Business insights at a glance" if key == "dashboard"
                         else "Browse, search and manage all orders")
        if key == "dashboard":
            self.after(50, self.redraw_charts)

    # ----- main area -----
    def _build_main(self):
        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True)

        top = tk.Frame(main, bg=BG)
        top.pack(fill="x", padx=24, pady=(18, 6))
        left = tk.Frame(top, bg=BG)
        left.pack(side="left")
        self.title_var, self.sub_var = tk.StringVar(), tk.StringVar()
        tk.Label(left, textvariable=self.title_var, bg=BG, fg=TEXT,
                 font=(FONT, 20, "bold")).pack(anchor="w")
        tk.Label(left, textvariable=self.sub_var, bg=BG, fg=MUTED,
                 font=(FONT, 10)).pack(anchor="w")
        self.clock_var = tk.StringVar()
        tk.Label(top, textvariable=self.clock_var, bg=BG, fg=MUTED,
                 font=(FONT, 10)).pack(side="right", anchor="n", pady=6)

        self.content = tk.Frame(main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=(4, 0))
        self.pages["dashboard"] = self._build_dashboard(self.content)
        self.pages["orders"] = self._build_orders(self.content)

        self.status_text = tk.StringVar()
        tk.Label(main, textvariable=self.status_text, anchor="w", bg="#e5eaf3", fg=MUTED,
                 font=(FONT, 9), padx=16, pady=5).pack(fill="x", side="bottom", before=self.content)

    def _tick(self):
        self.clock_var.set(datetime.now().strftime("%A, %d %B %Y   %H:%M:%S"))
        self.after(1000, self._tick)

    # ----- dashboard page -----
    def _build_dashboard(self, parent):
        page = tk.Frame(parent, bg=BG)

        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        tk.Label(bar, text="Period:", bg=BG, fg=MUTED, font=(FONT, 10)).pack(side="left")
        self.period_var = tk.StringVar(value=self.PERIODS[0])
        cb = ttk.Combobox(bar, textvariable=self.period_var, values=self.PERIODS,
                          state="readonly", width=14)
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_dashboard())
        self.period_note = tk.StringVar()
        tk.Label(bar, textvariable=self.period_note, bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(side="left", padx=6)
        tk.Label(bar, text="Revenue excludes cancelled orders", bg=BG, fg=MUTED,
                 font=(FONT, 9, "italic")).pack(side="right")

        # KPI row
        kpi = tk.Frame(page, bg=BG)
        kpi.pack(fill="x")
        specs = [("orders", "TOTAL ORDERS", "#3b6ef5"),
                 ("revenue", "NET REVENUE", "#7c5cdb"),
                 ("delivered", "DELIVERED REVENUE", "#22a05b"),
                 ("avg", "AVG ORDER VALUE", "#f08a24"),
                 ("rate", "DELIVERY RATE", "#14a3a3")]
        for i, (key, label, color) in enumerate(specs):
            kpi.columnconfigure(i, weight=1, uniform="kpi")
            card = tk.Frame(kpi, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            tk.Frame(card, bg=color, height=4).pack(fill="x")
            tk.Label(card, text=label, bg=CARD, fg=MUTED,
                     font=(FONT, 8, "bold")).pack(anchor="w", padx=14, pady=(10, 0))
            val, sub = tk.StringVar(value="0"), tk.StringVar()
            tk.Label(card, textvariable=val, bg=CARD, fg=TEXT,
                     font=(FONT, 15, "bold")).pack(anchor="w", padx=14)
            tk.Label(card, textvariable=sub, bg=CARD, fg=MUTED,
                     font=(FONT, 9)).pack(anchor="w", padx=14, pady=(0, 10))
            self.kpi_vars[key] = (val, sub)

        # Charts grid (6 equal columns)
        grid = tk.Frame(page, bg=BG)
        grid.pack(fill="both", expand=True, pady=(10, 8))
        for col in range(6):
            grid.columnconfigure(col, weight=1, uniform="g")
        grid.rowconfigure(0, weight=1, uniform="r")
        grid.rowconfigure(1, weight=1, uniform="r")

        self.card_month = ChartCard(grid, "Monthly Revenue", "bar chart")
        self.card_month.grid(row=0, column=0, columnspan=4, sticky="nsew", padx=(0, 8), pady=(0, 8))
        self.card_month.set_draw(lambda cd, c, w, h: draw_vbars(
            cd, c, w, h, self.dash.get("m_labels", []), self.dash.get("m_values", []), ACCENT))

        self.card_status = ChartCard(grid, "Orders by Status", "share of orders")
        self.card_status.grid(row=0, column=4, columnspan=2, sticky="nsew", pady=(0, 8))
        self.card_status.set_draw(lambda cd, c, w, h: draw_donut(
            cd, c, w, h, self.dash.get("status_items", [])))

        self.card_prod = ChartCard(grid, "Top Products", "by revenue")
        self.card_prod.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=(0, 8))
        self.card_prod.set_draw(lambda cd, c, w, h: draw_hbars(
            cd, c, w, h, self.dash.get("p_labels", []), self.dash.get("p_values", []), None))

        self.card_cust = ChartCard(grid, "Top Customers", "by revenue")
        self.card_cust.grid(row=1, column=2, columnspan=2, sticky="nsew", padx=(0, 8))
        self.card_cust.set_draw(lambda cd, c, w, h: draw_hbars(
            cd, c, w, h, self.dash.get("c_labels", []), self.dash.get("c_values", []), "#7c5cdb"))

        recent = tk.Frame(grid, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        recent.grid(row=1, column=4, columnspan=2, sticky="nsew")
        tk.Label(recent, text="Recent Orders", bg=CARD, fg=TEXT,
                 font=(FONT, 11, "bold")).pack(anchor="w", padx=14, pady=(10, 4))
        cols = ("id", "customer", "total", "status")
        self.recent_tree = ttk.Treeview(recent, columns=cols, show="headings",
                                        selectmode="none", height=5)
        for key, text, width, anchor in [("id", "ID", 62, "w"), ("customer", "Customer", 90, "w"),
                                         ("total", "Total", 78, "e"), ("status", "Status", 72, "center")]:
            self.recent_tree.heading(key, text=text)
            self.recent_tree.column(key, width=width, anchor=anchor, stretch=True)
        for st, (bgc, _) in STATUS_COLORS.items():
            self.recent_tree.tag_configure(st, background=bgc)
        self.recent_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        return page

    # ----- orders page -----
    def _build_orders(self, parent):
        page = tk.Frame(parent, bg=BG)

        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Button(bar, text="＋ Add", style="Accent.TButton",
                   command=self.add_order).pack(side="left")
        ttk.Button(bar, text="✎ Edit", command=self.edit_order).pack(side="left", padx=6)
        ttk.Button(bar, text="🗑 Delete", style="Danger.TButton",
                   command=self.delete_order).pack(side="left")

        right = tk.Frame(bar, bg=BG)
        right.pack(side="right")
        tk.Label(right, text="Status", bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left")
        self.status_var = tk.StringVar(value="All")
        scb = ttk.Combobox(right, textvariable=self.status_var, state="readonly", width=10,
                           values=["All"] + VALID_STATUSES)
        scb.pack(side="left", padx=(6, 12))
        scb.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())

        self.field_var = tk.StringVar(value="All")
        fcb = ttk.Combobox(right, textvariable=self.field_var, state="readonly", width=9,
                           values=["All", "Order ID", "Customer", "Product"])
        fcb.pack(side="left")
        fcb.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_table())
        self.search_entry = ttk.Entry(right, textvariable=self.search_var, width=24)
        self.search_entry.pack(side="left", padx=6)
        ttk.Button(right, text="Clear", command=self.clear_filters).pack(side="left")

        wrap = tk.Frame(page, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in COLUMNS],
                                 show="headings", selectmode="browse")
        for key, heading, width, anchor, _ in COLUMNS:
            self.tree.heading(key, text=heading, command=lambda k=key: self.sort_by(k))
            self.tree.column(key, width=width, anchor=anchor, stretch=True)
        for st, (bgc, _) in STATUS_COLORS.items():
            self.tree.tag_configure(st, background=bgc)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.edit_order())
        self.tree.bind("<Return>", lambda e: self.edit_order())
        return page

    def _bind_keys(self):
        self.bind("<Control-n>", lambda e: self.add_order())
        self.bind("<Control-1>", lambda e: self.show_page("dashboard"))
        self.bind("<Control-2>", lambda e: self.show_page("orders"))
        self.bind("<Control-f>", lambda e: (self.show_page("orders"), self.search_entry.focus_set()))
        self.bind("<Delete>", lambda e: self.delete_order() if self.current_page == "orders" else None)
        self.bind("<F5>", lambda e: self.reload())

    # ----- refresh logic -----
    def refresh_all(self, select_id=None):
        self.refresh_table(select_id)
        self.refresh_dashboard()

    def _period_orders(self):
        period = self.period_var.get()
        now = datetime.now()
        if period == "All time":
            return list(self.orders)
        out = []
        for o in self.orders:
            d = parse_date(o.get("order_date", ""))
            if not d:
                continue
            if period == "This month" and (d.year, d.month) == (now.year, now.month):
                out.append(o)
            elif period == "Last 30 days" and d >= now - timedelta(days=30):
                out.append(o)
            elif period == "This year" and d.year == now.year:
                out.append(o)
        return out

    def refresh_dashboard(self):
        orders = self._period_orders()
        net = [o for o in orders if o.get("status") != "Cancelled"]
        total = len(orders)
        gross = sum(o.get("total_amount", 0) for o in orders)
        revenue = sum(o.get("total_amount", 0) for o in net)
        delivered_list = [o for o in orders if o.get("status") == "Delivered"]
        delivered = sum(o.get("total_amount", 0) for o in delivered_list)
        avg = revenue / len(net) if net else 0
        rate = len(delivered_list) / total * 100 if total else 0
        counts = {s: sum(1 for o in orders if o.get("status") == s) for s in VALID_STATUSES}

        self.kpi_vars["orders"][0].set(str(total))
        self.kpi_vars["orders"][1].set(f"{counts['Pending']} pending · {counts['Cancelled']} cancelled")
        self.kpi_vars["revenue"][0].set(f"Rs {revenue:,.0f}")
        self.kpi_vars["revenue"][1].set(f"Gross Rs {gross:,.0f}")
        self.kpi_vars["delivered"][0].set(f"Rs {delivered:,.0f}")
        self.kpi_vars["delivered"][1].set(f"{len(delivered_list)} delivered orders")
        self.kpi_vars["avg"][0].set(f"Rs {avg:,.0f}")
        self.kpi_vars["avg"][1].set("per non-cancelled order")
        self.kpi_vars["rate"][0].set(f"{rate:.1f}%")
        self.kpi_vars["rate"][1].set(f"{len(delivered_list)} of {total} orders")
        self.period_note.set(f"{total} orders in selected period")

        # monthly revenue (last 6 months with data)
        by_month = defaultdict(float)
        for o in net:
            d = parse_date(o.get("order_date", ""))
            if d:
                by_month[d.strftime("%Y-%m")] += o.get("total_amount", 0)
        months = sorted(by_month)[-6:]
        self.dash["m_labels"] = [datetime.strptime(m, "%Y-%m").strftime("%b %y") for m in months]
        self.dash["m_values"] = [by_month[m] for m in months]

        # status donut
        self.dash["status_items"] = [(s, counts[s], STATUS_COLORS[s][1]) for s in VALID_STATUSES]

        # top products / customers
        prod, cust = defaultdict(float), defaultdict(float)
        for o in net:
            prod[o.get("product", "?")] += o.get("total_amount", 0)
            cust[o.get("customer_name", "?")] += o.get("total_amount", 0)
        tp = sorted(prod.items(), key=lambda kv: kv[1], reverse=True)[:5]
        tc = sorted(cust.items(), key=lambda kv: kv[1], reverse=True)[:5]
        self.dash["p_labels"], self.dash["p_values"] = [k for k, _ in tp], [v for _, v in tp]
        self.dash["c_labels"], self.dash["c_values"] = [k for k, _ in tc], [v for _, v in tc]

        # recent orders
        self.recent_tree.delete(*self.recent_tree.get_children())
        recent = sorted(orders, key=lambda o: str(o.get("order_date", "")), reverse=True)[:6]
        for o in recent:
            self.recent_tree.insert("", "end", tags=(o.get("status", ""),), values=(
                o.get("order_id", ""), trunc(o.get("customer_name", ""), 12),
                short(o.get("total_amount", 0)), o.get("status", "")))

        self.redraw_charts()

    def redraw_charts(self):
        for card in (self.card_month, self.card_status, self.card_prod, self.card_cust):
            card.draw()

    # ----- orders table -----
    def _filtered(self):
        text = self.search_var.get().strip().lower()
        status = self.status_var.get()
        keys = {"All": ["order_id", "customer_name", "product"],
                "Order ID": ["order_id"],
                "Customer": ["customer_name"],
                "Product": ["product"]}[self.field_var.get()]
        out = []
        for o in self.orders:
            if status != "All" and o.get("status", "").title() != status:
                continue
            if text and not any(text in str(o.get(k, "")).lower() for k in keys):
                continue
            out.append(o)
        return out

    def _sort_value(self, order):
        numeric = next(c[4] for c in COLUMNS if c[0] == self.sort_key)
        val = order.get(self.sort_key, 0 if numeric else "")
        if numeric:
            try:
                return float(val)
            except (TypeError, ValueError):
                return 0.0
        return str(val).lower()

    def refresh_table(self, select_id=None):
        rows = sorted(self._filtered(), key=self._sort_value, reverse=self.sort_reverse)
        self.tree.delete(*self.tree.get_children())
        for o in rows:
            self.tree.insert("", "end", iid=o.get("order_id"), tags=(o.get("status", ""),), values=(
                o.get("order_id", ""), o.get("customer_name", ""), o.get("product", ""),
                o.get("quantity", 0), money(o.get("unit_price", 0)),
                money(o.get("total_amount", 0)), o.get("status", ""), o.get("order_date", "")))
        if select_id and self.tree.exists(select_id):
            self.tree.selection_set(select_id)
            self.tree.see(select_id)
        for key, heading, *_ in COLUMNS:
            arrow = (" ▼" if self.sort_reverse else " ▲") if key == self.sort_key else ""
            self.tree.heading(key, text=heading + arrow)
        self.status_text.set(f"Showing {len(rows)} of {len(self.orders)} orders      |      "
                             f"Data file: {DATA_FILE}")

    def sort_by(self, key):
        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key, self.sort_reverse = key, False
        self.refresh_table()

    def clear_filters(self):
        self.search_var.set("")
        self.field_var.set("All")
        self.status_var.set("All")
        self.refresh_table()

    def reload(self):
        self.orders = load_orders()
        self.refresh_all()

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return next((o for o in self.orders if o.get("order_id") == sel[0]), None)

    # ----- actions -----
    def add_order(self):
        order_id = generate_order_id(self.orders)
        dlg = OrderDialog(self, "Add New Order", order_id)
        self.wait_window(dlg)
        if not dlg.result:
            return
        order = {"order_id": order_id, **dlg.result,
                 "order_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.orders.append(order)
        if save_orders(self.orders):
            self.refresh_all(select_id=order_id)
            messagebox.showinfo("Order added",
                                f"Order {order_id} added.\nTotal: Rs {order['total_amount']:,.2f}")
        else:
            self.orders.remove(order)

    def edit_order(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Edit order", "Please select an order in the Orders page first.")
            return
        dlg = OrderDialog(self, "Edit Order", order["order_id"], order)
        self.wait_window(dlg)
        if not dlg.result:
            return
        old = dict(order)
        order.update(dlg.result)
        if save_orders(self.orders):
            self.refresh_all(select_id=order["order_id"])
        else:
            order.clear()
            order.update(old)

    def delete_order(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Delete order", "Please select an order first.")
            return
        if messagebox.askyesno(
                "Confirm delete",
                f"Delete order {order['order_id']}?\n\n"
                f"Customer: {order.get('customer_name', '')}\n"
                f"Product : {order.get('product', '')}\n"
                f"Total   : Rs {money(order.get('total_amount', 0))}\n\nThis cannot be undone.",
                icon="warning"):
            idx = self.orders.index(order)
            self.orders.pop(idx)
            if save_orders(self.orders):
                self.refresh_all()
            else:
                self.orders.insert(idx, order)

    def backup_orders(self):
        if not self.orders:
            messagebox.showinfo("Backup", "No orders to back up.")
            return
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(BACKUP_DIR, f"orders_backup_{stamp}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.orders, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Backup created",
                                f"Backed up {len(self.orders)} orders to:\n{path}")
        except IOError as e:
            messagebox.showerror("Backup failed", str(e))

    def export_csv(self):
        if not self.orders:
            messagebox.showinfo("Export", "No orders to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
            initialfile="orders_export.csv", title="Export orders to CSV")
        if not path:
            return
        keys = [c[0] for c in COLUMNS]
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                w.writeheader()
                w.writerows(self.orders)
            messagebox.showinfo("Export complete", f"Exported {len(self.orders)} orders to:\n{path}")
        except IOError as e:
            messagebox.showerror("Export failed", str(e))


if __name__ == "__main__":
    OrderApp().mainloop()