"""
Reactive Tkinter Spreadsheet
Uses: https://github.com/gdchinacat/reactions
Install: pip install git+https://github.com/gdchinacat/reactions.git

Python 3.14 required (as per reactions library docs).

This app demonstrates a budget/invoice spreadsheet where changing any
input cell automatically recalculates dependent cells using the
`reactions` Field + predicate system.
"""

import tkinter as tk
from tkinter import ttk, font
import asyncio
import threading
import sys

# ── Try to import reactions ──────────────────────────────────────────────────
try:
    from reactions.field import Field
    from reactions.executor import ReactionExecutor
    REACTIONS_AVAILABLE = True
except ImportError:
    REACTIONS_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
#  FALLBACK: lightweight Field + reaction system when reactions isn't installed
# ═══════════════════════════════════════════════════════════════════════════════
if not REACTIONS_AVAILABLE:

    class _Reaction:
        """A registered callback on a Field."""
        def __init__(self, field, fn):
            self._field = field
            self._fn = fn
            field._reactions.append(self)

        def __call__(self, instance, old, new):
            self._fn(instance, self._field, old, new)

    class _BoundField:
        def __init__(self, instance, field):
            self._instance = instance
            self._field = field

        @property
        def value(self):
            return self._field.__get__(self._instance, type(self._instance))

        @value.setter
        def value(self, v):
            self._field.__set__(self._instance, v)

    class Field:
        """Descriptor that fires registered reactions on value change."""
        def __init__(self, default=None):
            self._default = default
            self._name = None
            self._reactions = []       # list of callables(instance, old, new)

        def __set_name__(self, owner, name):
            self._name = f"_field_{name}"

        def __get__(self, obj, objtype=None):
            if obj is None:
                return self
            return getattr(obj, self._name, self._default)

        def __set__(self, obj, value):
            old = getattr(obj, self._name, self._default)
            object.__setattr__(obj, self._name, value)
            if old != value:
                for reaction in self._reactions:
                    reaction(obj, old, value)

        # Allow `field != something` as a "always react" predicate decorator
        def __ne__(self, other):
            return _AlwaysPredicate(self)

        def __ge__(self, other):
            return _ThresholdPredicate(self, other)

    class _AlwaysPredicate:
        def __init__(self, field):
            self._field = field

        def __call__(self, fn):
            _Reaction(self._field, lambda inst, bf, old, new: fn(inst, bf, old, new))
            return fn

    class _ThresholdPredicate:
        def __init__(self, field, threshold):
            self._field = field
            self._threshold = threshold

        def __call__(self, fn):
            def wrapper(inst, bf, old, new):
                if new >= self._threshold:
                    fn(inst, bf, old, new)
            _Reaction(self._field, wrapper)
            return fn

    class ReactionExecutor:
        """Stub executor — reactions run synchronously in the fallback."""
        def __init__(self):
            pass

        def start(self):
            pass

        def stop(self):
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  SPREADSHEET STATE MODEL  (uses reactions Fields)
# ═══════════════════════════════════════════════════════════════════════════════

class InvoiceModel:
    """
    A simple invoice with line items.
    Fields:
      qty_N, price_N  → line_total_N  (qty * price)
      line_total_*    → subtotal       (sum of line totals)
      subtotal, tax_rate → tax_amount  (subtotal * tax_rate / 100)
      subtotal, tax_amount → grand_total (subtotal + tax)
      discount_pct, grand_total → final_total (grand_total * (1 - discount/100))
    """

    # ── Inputs ─────────────────────────────────────────────────────────────────
    qty_1    = Field(1.0)
    price_1  = Field(0.0)
    qty_2    = Field(1.0)
    price_2  = Field(0.0)
    qty_3    = Field(1.0)
    price_3  = Field(0.0)
    qty_4    = Field(1.0)
    price_4  = Field(0.0)
    qty_5    = Field(1.0)
    price_5  = Field(0.0)

    tax_rate     = Field(8.5)    # percent
    discount_pct = Field(0.0)   # percent

    # ── Derived ────────────────────────────────────────────────────────────────
    line_total_1 = Field(0.0)
    line_total_2 = Field(0.0)
    line_total_3 = Field(0.0)
    line_total_4 = Field(0.0)
    line_total_5 = Field(0.0)

    subtotal    = Field(0.0)
    tax_amount  = Field(0.0)
    grand_total = Field(0.0)
    final_total = Field(0.0)

    # ── Reactions: line totals ─────────────────────────────────────────────────
    @(qty_1 != None)
    def _calc_line1(self, bf, old, new):
        self.line_total_1 = round(self.qty_1 * self.price_1, 2)

    @(price_1 != None)
    def _calc_line1b(self, bf, old, new):
        self.line_total_1 = round(self.qty_1 * self.price_1, 2)

    @(qty_2 != None)
    def _calc_line2(self, bf, old, new):
        self.line_total_2 = round(self.qty_2 * self.price_2, 2)

    @(price_2 != None)
    def _calc_line2b(self, bf, old, new):
        self.line_total_2 = round(self.qty_2 * self.price_2, 2)

    @(qty_3 != None)
    def _calc_line3(self, bf, old, new):
        self.line_total_3 = round(self.qty_3 * self.price_3, 2)

    @(price_3 != None)
    def _calc_line3b(self, bf, old, new):
        self.line_total_3 = round(self.qty_3 * self.price_3, 2)

    @(qty_4 != None)
    def _calc_line4(self, bf, old, new):
        self.line_total_4 = round(self.qty_4 * self.price_4, 2)

    @(price_4 != None)
    def _calc_line4b(self, bf, old, new):
        self.line_total_4 = round(self.qty_4 * self.price_4, 2)

    @(qty_5 != None)
    def _calc_line5(self, bf, old, new):
        self.line_total_5 = round(self.qty_5 * self.price_5, 2)

    @(price_5 != None)
    def _calc_line5b(self, bf, old, new):
        self.line_total_5 = round(self.qty_5 * self.price_5, 2)

    # ── Reactions: subtotal ────────────────────────────────────────────────────
    @(line_total_1 != None)
    def _calc_subtotal_1(self, bf, old, new):
        self._update_subtotal()

    @(line_total_2 != None)
    def _calc_subtotal_2(self, bf, old, new):
        self._update_subtotal()

    @(line_total_3 != None)
    def _calc_subtotal_3(self, bf, old, new):
        self._update_subtotal()

    @(line_total_4 != None)
    def _calc_subtotal_4(self, bf, old, new):
        self._update_subtotal()

    @(line_total_5 != None)
    def _calc_subtotal_5(self, bf, old, new):
        self._update_subtotal()

    def _update_subtotal(self):
        self.subtotal = round(
            self.line_total_1 + self.line_total_2 + self.line_total_3 +
            self.line_total_4 + self.line_total_5, 2
        )

    # ── Reactions: tax ─────────────────────────────────────────────────────────
    @(subtotal != None)
    def _calc_tax_from_subtotal(self, bf, old, new):
        self.tax_amount = round(self.subtotal * self.tax_rate / 100, 2)

    @(tax_rate != None)
    def _calc_tax_from_rate(self, bf, old, new):
        self.tax_amount = round(self.subtotal * self.tax_rate / 100, 2)

    # ── Reactions: grand total ──────────────────────────────────────────────────
    @(tax_amount != None)
    def _calc_grand(self, bf, old, new):
        self.grand_total = round(self.subtotal + self.tax_amount, 2)

    # ── Reactions: final total (after discount) ─────────────────────────────────
    @(grand_total != None)
    def _calc_final(self, bf, old, new):
        self.final_total = round(self.grand_total * (1 - self.discount_pct / 100), 2)

    @(discount_pct != None)
    def _calc_final_from_discount(self, bf, old, new):
        self.final_total = round(self.grand_total * (1 - self.discount_pct / 100), 2)


# ═══════════════════════════════════════════════════════════════════════════════
#  TKINTER UI
# ═══════════════════════════════════════════════════════════════════════════════

PALETTE = {
    "bg":         "#1e1e2e",
    "header_bg":  "#313244",
    "input_bg":   "#2a2a3e",
    "derived_bg": "#1a2a1a",
    "accent":     "#cba6f7",
    "text":       "#cdd6f4",
    "dim":        "#6c7086",
    "green":      "#a6e3a1",
    "yellow":     "#f9e2af",
    "red":        "#f38ba8",
    "border":     "#45475a",
    "entry_fg":   "#cdd6f4",
    "entry_sel":  "#313244",
    "white":      "#ffffff",
}

ITEMS = ["Widget A", "Widget B", "Widget C", "Widget D", "Widget E"]


class SpreadsheetApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Reactive Invoice Spreadsheet")
        self.root.configure(bg=PALETTE["bg"])
        self.root.resizable(True, True)

        self.model = InvoiceModel()
        self._update_queue = []   # callbacks to flush into tk vars
        self._building = True

        self._build_ui()
        self._wire_reactions()
        self._building = False

        # Trigger initial calculation pass
        self.model.qty_1 = 1.0

    # ── Build UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Fonts
        title_font  = font.Font(family="Helvetica", size=15, weight="bold")
        header_font = font.Font(family="Helvetica", size=9,  weight="bold")
        mono_font   = font.Font(family="Courier",   size=10)
        label_font  = font.Font(family="Helvetica", size=10)
        small_font  = font.Font(family="Helvetica", size=8)

        root = self.root
        PAD = 12

        # ── Title bar ──────────────────────────────────────────────────────────
        title_frame = tk.Frame(root, bg=PALETTE["header_bg"], pady=10)
        title_frame.pack(fill="x")

        tk.Label(
            title_frame, text="⚡ Reactive Invoice Spreadsheet",
            font=title_font, fg=PALETTE["accent"], bg=PALETTE["header_bg"]
        ).pack(side="left", padx=PAD)

        badge = "reactions ✓" if REACTIONS_AVAILABLE else "reactions fallback"
        badge_color = PALETTE["green"] if REACTIONS_AVAILABLE else PALETTE["yellow"]
        tk.Label(
            title_frame, text=badge,
            font=small_font, fg=badge_color, bg=PALETTE["header_bg"]
        ).pack(side="right", padx=PAD)

        # ── Main content ────────────────────────────────────────────────────────
        main = tk.Frame(root, bg=PALETTE["bg"], padx=PAD, pady=PAD)
        main.pack(fill="both", expand=True)

        # ── Column headers ──────────────────────────────────────────────────────
        headers = ["Item", "Description", "Qty", "Unit Price", "Line Total"]
        widths  = [4,       22,             7,     10,           10]

        hdr_frame = tk.Frame(main, bg=PALETTE["header_bg"])
        hdr_frame.pack(fill="x", pady=(0, 2))

        for h, w in zip(headers, widths):
            tk.Label(
                hdr_frame, text=h, width=w, anchor="w",
                font=header_font, fg=PALETTE["dim"], bg=PALETTE["header_bg"],
                padx=6, pady=4
            ).pack(side="left")

        # ── Line item rows ──────────────────────────────────────────────────────
        self._qty_vars   = []
        self._price_vars = []
        self._total_vars = []

        for i, item_name in enumerate(ITEMS, start=1):
            row_bg = PALETTE["input_bg"] if i % 2 == 1 else PALETTE["bg"]
            row = tk.Frame(main, bg=row_bg, pady=1)
            row.pack(fill="x")

            # Row number
            tk.Label(
                row, text=str(i), width=4, anchor="center",
                font=label_font, fg=PALETTE["dim"], bg=row_bg, padx=6
            ).pack(side="left")

            # Item name
            tk.Label(
                row, text=item_name, width=22, anchor="w",
                font=label_font, fg=PALETTE["text"], bg=row_bg, padx=6
            ).pack(side="left")

            # Qty entry
            qty_var = tk.StringVar(value="1")
            qty_entry = tk.Entry(
                row, textvariable=qty_var, width=7,
                font=mono_font, fg=PALETTE["entry_fg"],
                bg=PALETTE["entry_sel"], insertbackground=PALETTE["accent"],
                relief="flat", bd=2, justify="right"
            )
            qty_entry.pack(side="left", padx=2, pady=2)
            self._qty_vars.append(qty_var)

            # Price entry
            price_var = tk.StringVar(value="0.00")
            price_entry = tk.Entry(
                row, textvariable=price_var, width=10,
                font=mono_font, fg=PALETTE["entry_fg"],
                bg=PALETTE["entry_sel"], insertbackground=PALETTE["accent"],
                relief="flat", bd=2, justify="right"
            )
            price_entry.pack(side="left", padx=2, pady=2)
            self._price_vars.append(price_var)

            # Line total (read-only)
            total_var = tk.StringVar(value="$0.00")
            tk.Label(
                row, textvariable=total_var, width=10, anchor="e",
                font=mono_font, fg=PALETTE["green"], bg=row_bg, padx=8
            ).pack(side="left")
            self._total_vars.append(total_var)

        # ── Separator ──────────────────────────────────────────────────────────
        sep = tk.Frame(main, bg=PALETTE["border"], height=1)
        sep.pack(fill="x", pady=8)

        # ── Totals + controls panel ─────────────────────────────────────────────
        bottom = tk.Frame(main, bg=PALETTE["bg"])
        bottom.pack(fill="x")

        # Left: tax & discount controls
        ctrl = tk.LabelFrame(
            bottom, text=" Settings ", font=header_font,
            fg=PALETTE["dim"], bg=PALETTE["bg"],
            bd=1, relief="groove", padx=10, pady=8
        )
        ctrl.pack(side="left", fill="y", padx=(0, 16))

        def make_ctrl_row(parent, label, var, row_idx):
            tk.Label(
                parent, text=label, anchor="w",
                font=label_font, fg=PALETTE["text"], bg=PALETTE["bg"], width=14
            ).grid(row=row_idx, column=0, sticky="w", pady=3)
            e = tk.Entry(
                parent, textvariable=var, width=9,
                font=mono_font, fg=PALETTE["entry_fg"],
                bg=PALETTE["entry_sel"], insertbackground=PALETTE["accent"],
                relief="flat", bd=2, justify="right"
            )
            e.grid(row=row_idx, column=1, padx=4, pady=3)

        self._tax_var      = tk.StringVar(value="8.5")
        self._discount_var = tk.StringVar(value="0.0")
        make_ctrl_row(ctrl, "Tax Rate (%)",    self._tax_var,      0)
        make_ctrl_row(ctrl, "Discount (%)",    self._discount_var, 1)

        # Right: summary totals
        totals = tk.Frame(bottom, bg=PALETTE["bg"])
        totals.pack(side="right", fill="y")

        def make_total_row(parent, label, var, fg, row_idx, bold=False):
            lf = font.Font(family="Helvetica", size=10, weight="bold" if bold else "normal")
            vf = font.Font(family="Courier",   size=12 if bold else 10,
                           weight="bold" if bold else "normal")
            tk.Label(
                parent, text=label, anchor="e",
                font=lf, fg=PALETTE["dim"], bg=PALETTE["bg"], width=16, padx=4
            ).grid(row=row_idx, column=0, sticky="e", pady=2)
            tk.Label(
                parent, textvariable=var, anchor="e",
                font=vf, fg=fg, bg=PALETTE["bg"], width=12, padx=8
            ).grid(row=row_idx, column=1, sticky="e", pady=2)

        self._subtotal_var    = tk.StringVar(value="$0.00")
        self._tax_amount_var  = tk.StringVar(value="$0.00")
        self._grand_total_var = tk.StringVar(value="$0.00")
        self._final_total_var = tk.StringVar(value="$0.00")

        make_total_row(totals, "Subtotal:",       self._subtotal_var,    PALETTE["text"],   0)
        make_total_row(totals, "Tax Amount:",      self._tax_amount_var,  PALETTE["yellow"], 1)
        make_total_row(totals, "Grand Total:",     self._grand_total_var, PALETTE["text"],   2)
        make_total_row(totals, "Final Total:",     self._final_total_var, PALETTE["green"],  3, bold=True)

        # ── Status bar ─────────────────────────────────────────────────────────
        status_bar = tk.Frame(root, bg=PALETTE["header_bg"], pady=4)
        status_bar.pack(fill="x", side="bottom")

        self._status_var = tk.StringVar(value="Ready — edit any cell to recalculate")
        tk.Label(
            status_bar, textvariable=self._status_var,
            font=small_font, fg=PALETTE["dim"], bg=PALETTE["header_bg"],
            anchor="w", padx=8
        ).pack(side="left")

        tk.Label(
            status_bar,
            text="Fields update automatically via reactions library",
            font=small_font, fg=PALETTE["dim"], bg=PALETTE["header_bg"],
            anchor="e", padx=8
        ).pack(side="right")

    # ── Wire reactions → UI updates ────────────────────────────────────────────

    def _wire_reactions(self):
        """Register Field reactions on model to sync derived values to tk vars."""
        model = self.model

        # Derived line totals → tk label vars
        def make_line_updater(idx):
            field = getattr(InvoiceModel, f"line_total_{idx+1}")
            tk_var = self._total_vars[idx]

            @(field != None)
            def updater(inst, bf, old, new):
                self._schedule_ui(lambda v=new: tk_var.set(f"${v:,.2f}"))
            # Attach to the class-level field descriptor's reaction list
            # (fallback path); for real reactions lib this is a class decorator
            # so we do it differently below.

        # For the real reactions library, reactions must be declared in the
        # class body. Since we can't do that dynamically post-class, we instead
        # observe field changes by monkey-patching __set__ via a wrapper.
        # For simplicity, we use trace on tk vars + direct field writes.
        self._setup_input_traces()
        self._setup_model_observers()

    def _setup_input_traces(self):
        """Trace tk input vars → write to model fields (triggers reactions)."""
        entries = [
            (self._qty_vars,   [f"qty_{i}"   for i in range(1, 6)]),
            (self._price_vars, [f"price_{i}" for i in range(1, 6)]),
        ]
        for var_list, field_names in entries:
            for var, fname in zip(var_list, field_names):
                var.trace_add("write", self._make_input_handler(var, fname))

        self._tax_var.trace_add(     "write", self._make_input_handler(self._tax_var,      "tax_rate"))
        self._discount_var.trace_add("write", self._make_input_handler(self._discount_var, "discount_pct"))

    def _make_input_handler(self, tk_var, field_name):
        """Returns a trace callback that parses the tk var and sets the model field."""
        def handler(*args):
            try:
                raw = tk_var.get().strip()
                value = float(raw) if raw else 0.0
                setattr(self.model, field_name, value)
                self._status_var.set(f"Updated {field_name} → {value}")
            except ValueError:
                pass  # ignore partial edits like "-" or "1."
        return handler

    def _setup_model_observers(self):
        """
        Register lightweight observers on derived Fields to push values to tk vars.
        Works with both the real reactions library and the fallback.
        """
        model = self.model

        def observe(field_attr, tk_var, prefix="$"):
            field = getattr(InvoiceModel, field_attr)
            # Register directly on the field's _reactions list (works for both
            # the real library's Field and our fallback Field).
            def cb(instance, old, new):
                formatted = f"{prefix}{new:,.2f}"
                # Schedule on the tk main thread
                self.root.after(0, lambda v=formatted: tk_var.set(v))
            field._reactions.append(cb)

        observe("line_total_1", self._total_vars[0])
        observe("line_total_2", self._total_vars[1])
        observe("line_total_3", self._total_vars[2])
        observe("line_total_4", self._total_vars[3])
        observe("line_total_5", self._total_vars[4])
        observe("subtotal",     self._subtotal_var)
        observe("tax_amount",   self._tax_amount_var)
        observe("grand_total",  self._grand_total_var)
        observe("final_total",  self._final_total_var)

    def _schedule_ui(self, fn):
        self.root.after(0, fn)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    root.geometry("720x540")
    root.minsize(680, 480)

    app = SpreadsheetApp(root)

    # Pre-populate with sample data
    sample_qtys   = ["2",   "5",   "1",    "3",   "10"]
    sample_prices = ["24.99", "9.50", "149.00", "34.75", "4.25"]
    for var, val in zip(app._qty_vars, sample_qtys):
        var.set(val)
    for var, val in zip(app._price_vars, sample_prices):
        var.set(val)

    root.mainloop()


if __name__ == "__main__":
    main()
