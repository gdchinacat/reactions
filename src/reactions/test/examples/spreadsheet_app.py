
import asyncio
from functools import partial, wraps
import re
from statistics import mean, StatisticsError
from threading import Thread, Event
import tkinter as tk
from tkinter import font as tkfont
from typing import Iterator, Literal, Callable

from reactions import (Field, ExecutorFieldManager, Executor, FieldChange,
                       ReactionCanceler)
from pip._vendor.rich import cells

type Number = int | float 
type CellValue = Number | str

# todo
#    - use namedtuple for cell address rather than r, c args all over

# =============================================================================
#  CELL MODEL
# =============================================================================

class Cell(ExecutorFieldManager):
    '''
    A spreadsheet cell.
    Has two values, the raw value and the evaluated value. The raw values are
    the text the user entered into the cell (str). The evaluated value is the
    inferred type after evaluation (float, int, str).

    Reactions are used to:
        - evaluate the value when raw value changes
        - evaluate evaluated value when referenced cell evaluated value changes
    '''

    row: int
    col: int
    raw = Field["Cell", str]("")
    value = Field["Cell", CellValue]("")

    def __init__(self, engine: "SpreadsheetEngine", row: int, col: int):
        self.engine = engine
        super().__init__(executor=engine.executor)
        self.row, self.col = row, col
        self._cancelers: dict[Cell, ReactionCanceler] = {}

    @property
    def address(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"{_col_name(self.col)}{self.row + 1}"

    def __repr__(self) -> str:
        return f"<Cell {self.address} raw={self.raw!r} value={self.value!r}>"

    def _register_value_reaction(self, cell: Cell) -> Cell:
        '''
        Register a reaction for when cell.value changes. The canceler for the
        reaction is apppended to self._cancelers.
        The cell is returned so it can be used with map to chain generators.
        '''
        if cell not in self._cancelers:
            canceler = Cell.value[cell](self.__value_change).canceler
            self._cancelers[cell] = canceler
        return cell

    def _eval_formula(self, raw: str, register_reactions: bool) -> CellValue:
        # todo - _eval_formula each time is pretty expensive since it has
        #        to parse the formula whenever a referenced cell value. Keep
        #        the AST of the regex around an only reevaluate when raw
        #        value is updated.

        watched_cells: set[Cell] = set()  # avoid duplicate reactions
        def expand_range(m: re.Match[str]) -> str:
            '''replace aggregation functions with value'''
            fn = m.group(1).upper()
            c1, r1 = _col_index(m.group(2)), int(m.group(3)) - 1
            c2, r2 = _col_index(m.group(4)), int(m.group(5)) - 1

            # Generator expressions avoid creating potentially huge lists.
            cells: Iterator[Cell] = (self.engine.cells[r][c]
                     for r in range(min(r1,r2), max(r1,r2)+1)
                     for c in range(min(c1,c2), max(c1,c2)+1))
            cells = map(self._register_value_reaction, cells)
            nums: Iterator[int|float] = (
                cell.value for cell in cells
                if isinstance(cell.value, (int, float)))

            func = AGGREGATION_FUNCTIONS.get(fn)
            if func is None:
                raise ValueError(f"Unknown function {fn}")
            return str(func(nums))
        expr = RANGE_RE.sub(expand_range, raw)

        def replace_ref(m: re.Match[str]) -> str:
            cell = self.engine.cell_by_addr(m.group(0))
            if cell is None: raise ValueError(f"Unknown {m.group(0)}")

            if register_reactions and cell not in watched_cells:
                self._register_value_reaction(cell)
                watched_cells.add(cell)

            v = cell.value
            if isinstance(v, (int, float)): return str(v)
            raise ValueError(f"{m.group(0)} is not numeric")

        expr = CELL_RE.sub(replace_ref, expr)
        result = eval(expr, {"__builtins__": {}},   # noqa: S307
                      {"abs": abs, "round": round, "min": min, "max": max})
        if isinstance(result, (int, float)):
            return result
        else:
            return str(result)

    def __evaluate(self,
                   change: FieldChange[Cell, str]  # raw
                          |FieldChange[Cell, CellValue], # value
                   register_reactions: bool=False) -> None:
        '''
        Update the evaluated value based on the raw value.
        This handles both raw value change and referenced cell value change.
        Performs data type conversion from raw string to properly typed value.
        '''
        if self.raw.startswith("="):
            try:
                self.value = self._eval_formula(self.raw[1:],
                    register_reactions=register_reactions)
            except Exception as e:
                self.value = f"#ERR {e}"
        else:
            # todo more data type support (ie date, currency)
            try:
                value = float(self.raw) if '.' in self.raw else int(self.raw)
                self.value = value
            except ValueError:
                self.value = self.raw

    async def __value_change(self,
                             changed_cell: "Cell",
                             change: "FieldChange[Cell, CellValue]") -> None:
        '''reaction for when a referenced cell value changes'''
        self.__evaluate(change)

    async def __raw_changed(self,
                            change: "FieldChange[Cell, str]") -> None:
        '''reaction for when the raw value changes'''

        # raw value changed, clear the existing reactions to avoid leaking them
        # or creating duplicates when they are registered during evaluation.
        for (cell, canceler) in self._cancelers.items():
            canceler()
        self._cancelers.clear()

        self.__evaluate(change, register_reactions=True)

    raw(__raw_changed)


# =============================================================================
#  SPREADSHEET ENGINE
# =============================================================================

CELL_RE  = re.compile(r"\b([A-Z]+)(\d+)\b")
RANGE_RE = re.compile(r"(SUM|AVG|MIN|MAX|COUNT)\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)",
                      re.IGNORECASE)

type agg_func = Callable[[Iterator[int|float]], int|float]

def _zero_on_error(func: agg_func) -> agg_func:
    '''"Safely" call and return func(nums), returning 0 if (ValueError,
    StatisticsError) is raised.'''
    @wraps(func)
    def wrap(nums: Iterator[int|float]) -> int|float:
        try:
            return func(nums)
        except (ValueError, StatisticsError):
            return 0
    return wrap


AGGREGATION_FUNCTIONS: dict[str, agg_func] = {
            "SUM":   sum,
            "AVG":   _zero_on_error(mean),
            "MIN":   _zero_on_error(min),
            "MAX":   _zero_on_error(max),
            "COUNT": lambda nums: sum(1 for _ in nums),
            }


def _col_name(idx: int) -> str:
    name, n = "", idx + 1
    while n:
        n, r = divmod(n - 1, 26)
        name = chr(65 + r) + name
    return name


def _col_index(name: str) -> int:
    r = 0
    for ch in name.upper():
        r = r * 26 + (ord(ch) - 64)
    return r - 1


class SpreadsheetEngine:
    """
    Spreadsheet with grid of cells.
    Has an asyncio event loop thread to process reactions for cells.
    Updates from UI are scheduled in event loop to allow reactions they cause
    to be responded to.
    """

    def __init__(self, nrows: int = 20, ncols: int = 8):
        self.executor = Executor()
        self.cells: list[list[Cell]] = [
            [Cell(self, r, c) for c in range(ncols)]
            for r in range(nrows)
        ]
        # Threading - each engine has its own thread and asyncio event loop to
        # process reactions in. This allows the spreadsheet reactions to work
        # with frameworks that are not async and control the "main" thread.
        # The event loop is exposed so that external updates to the cells raw
        # values can be scheduled with the event loop in a threadsafe way.
        def reactions_thread() -> None:
            '''thread to run the asyncio event loop for the spreadsheet'''
            async def run() -> None:
                self._loop = asyncio.get_running_loop()
                await self.executor.start()
            asyncio.run(run())

        self.thread = Thread(target=reactions_thread, daemon=True)
        self.thread.start()

    # ── Public ────────────────────────────────────────────────────────────────

    @property
    def nrows(self) -> int:
        return len(self.cells)

    @property
    def ncols(self) -> int:
        return len(self.cells[0]) if self.cells else 0
   
    def set_raw(self, row: int, col: int, text: str) -> None:
        '''set the raw value of the cell'''
        cell = self.cells[row][col]
        async def _set() -> None:
            cell.raw = text.strip() if text else ''
        asyncio.run_coroutine_threadsafe(_set(), self._loop)

    def cell_by_addr(self, addr: str) -> Cell | None:
        m = re.fullmatch(r"([A-Z]+)(\d+)", addr.upper())
        if not m:
            return None
        c = _col_index(m.group(1))
        r = int(m.group(2)) - 1
        if 0 <= r < self.nrows and 0 <= c < self.ncols:
            return self.cells[r][c]
        return None

    def _parse_refs(self, expr: str) -> list[str]:
        """Return unique cell addresses referenced in expr."""
        # Strip range functions first so we don't double-count range refs
        expanded = RANGE_RE.sub("0", expr)
        # Also collect individual refs inside ranges
        range_refs = []
        for m in RANGE_RE.finditer(expr):
            c1, r1 = _col_index(m.group(2)), int(m.group(3))
            c2, r2 = _col_index(m.group(4)), int(m.group(5))
            for rr in range(min(r1,r2), max(r1,r2)+1):
                for cc in range(min(c1,c2), max(c1,c2)+1):
                    range_refs.append(f"{_col_name(cc)}{rr}")
        seen, result = set(), []
        for m in CELL_RE.finditer(expanded):
            addr = f"{m.group(1)}{m.group(2)}"
            if addr not in seen:
                seen.add(addr); result.append(addr)
        for addr in range_refs:
            if addr not in seen:
                seen.add(addr); result.append(addr)
        return result

# =============================================================================
#  COLOUR PALETTE
# =============================================================================

P = dict(
    bg       = "#1e1e2e",
    surface  = "#2a2a3e",

    even     = "#1e1e2e",  # cell background for even rows
    odd      = "#2a2a3e",  # cell background for odd rows

    header   = "#313244",
    border   = "#45475a",
    text     = "#cdd6f4",
    dim      = "#6c7086",
    accent   = "#cba6f7",
    formula  = "#89dceb",
    green    = "#a6e3a1",
    error      = "#f38ba8",
    sel      = "#45475a",
    entry_bg = "#181825",
    entry_fg = "#cdd6f4",
    cursor   = "#cba6f7",
)


# =============================================================================
#  TKINTER UI
# =============================================================================

class SpreadsheetUI:

    CELL_W = 10   # char width of each cell label
    _selected: Cell|None = None

    def __init__(self, root: tk.Tk, engine: SpreadsheetEngine):
        self.root   = root
        self.engine = engine

        self.executor = engine.executor # todo - needed to resolve executor for Cell.value reaction
        Cell.value(self._on_cell_changed)  # todo all UIs notified for all cell changes!

        self._editing = False

        bold  = tkfont.Font(family="Helvetica", size=9,  weight="bold")
        small = tkfont.Font(family="Helvetica", size=8)
        self._mono  = tkfont.Font(family="Courier",   size=10)
        self._bold  = bold
        self._small = small

        self._build(root)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self, root: tk.Tk) -> None:
        root.configure(bg=P["bg"])

        # Formula bar
        fbar = tk.Frame(root, bg=P["surface"], pady=4, padx=8)
        fbar.pack(fill="x")
        self._addr_var    = tk.StringVar(value="")
        self._formula_var = tk.StringVar(value="")
        tk.Label(fbar, textvariable=self._addr_var, width=5, anchor="center",
                 font=self._bold, fg=P["accent"], bg=P["surface"]
                 ).pack(side="left")
        tk.Label(fbar, text="fx", font=self._bold,
                 fg=P["dim"], bg=P["surface"], padx=4).pack(side="left")
        self._fentry = tk.Entry(fbar, textvariable=self._formula_var,
                                font=self._mono, fg=P["formula"],
                                bg=P["entry_bg"], insertbackground=P["cursor"],
                                relief="flat", bd=2)
        self._fentry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._fentry.bind("<Return>",   partial(self._commit, where='return'))
        self._fentry.bind("<Escape>",   self._cancel)
        self._fentry.bind("<Tab>",      partial(self._commit, where='tab'))
        self._fentry.bind("<FocusOut>", partial(self._commit, where='focusout'))

        # Scrollable grid
        outer = tk.Frame(root, bg=P["bg"])
        outer.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(outer, bg=P["bg"], highlightthickness=0)
        vbar = tk.Scrollbar(outer, orient="vertical",   command=self._canvas.yview)
        hbar = tk.Scrollbar(root,  orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        vbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        hbar.pack(fill="x")
        self._inner = tk.Frame(self._canvas, bg=P["bg"])
        cwin = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(cwin, width=e.width))
        for seq, d in (("<MouseWheel>", None),
                       ("<Button-4>", -1),
                       ("<Button-5>", 1)):
            cb = lambda e, d=d: self._canvas.yview_scroll(
                d or -1*(e.delta//120), "units")
            self._canvas.bind(seq, cb)

        self._build_grid()

        # Status bar
        sb = tk.Frame(root, bg=P["header"], pady=3)
        sb.pack(fill="x", side="bottom")
        self._status_var = tk.StringVar(
            value="Click a cell to select  •  Type or double-click to edit  "
                  "•  Formulas start with =  •  SUM/AVG/MIN/MAX/COUNT(A1:B3) supported")
        tk.Label(sb, textvariable=self._status_var, font=self._small,
                 fg=P["dim"], bg=P["header"], anchor="w", padx=8).pack(side="left")
        tk.Label(sb, text="github.com/gdchinacat/reactions",
                 font=self._small, fg=P["dim"], bg=P["header"],
                 anchor="e", padx=8).pack(side="right")

    def _build_grid(self) -> None:
        W = self.CELL_W
        tk.Label(self._inner, text="", bg=P["header"], width=4,
                 relief="flat").grid(row=0, column=0, sticky="nsew", ipadx=2, ipady=3)
        for c in range(self.engine.ncols):
            tk.Label(self._inner, text=_col_name(c), font=self._bold,
                     fg=P["dim"], bg=P["header"], width=W, anchor="center",
                     relief="flat").grid(row=0, column=c+1, sticky="nsew",
                                         ipadx=2, ipady=3)
        self._labels: list[list[tk.Label]] = []
        for r in range(self.engine.nrows):
            row_bg = P["even"] if r % 2 == 0 else P["odd"]
            tk.Label(self._inner, text=str(r+1), font=self._small,
                     fg=P["dim"], bg=P["header"], width=4, anchor="e",
                     relief="flat").grid(row=r+1, column=0, sticky="nsew", ipadx=4)
            row_labels = []
            for c in range(self.engine.ncols):
                lbl = tk.Label(self._inner, text="", font=self._mono,
                               fg=P["text"], bg=row_bg, anchor="w",
                               relief="flat", width=W, padx=4, pady=2,
                               takefocus=True)
                lbl.grid(row=r+1, column=c+1, sticky="nsew", padx=1, pady=1)
                lbl.bind("<Button-1>",        partial(self._select, r, c))
                lbl.bind("<Double-Button-1>", partial(self._begin_edit, r, c))
                lbl.bind("<Key>",             partial(self._key, r, c))
                row_labels.append(lbl)
            self._labels.append(row_labels)

    # ── Selection / editing ───────────────────────────────────────────────────

    def _row_bg(self, r: int) -> str:
        return P["even"] if r % 2 == 0 else P["odd"]

    def _select(self, row: int, col: int,
                event: tk.Event|None=None,
                commit:bool=True) -> None:
        '''select the cell at row:col'''
        # turn off bg for currently selected cell
        if self._selected:
            if commit: self._commit(where='_select')  # save whatever is in the function line to current cell
            self._selected_label.configure(bg=self._row_bg(self._selected.row))

        self._selected = self.engine.cells[row][col]  # todo - rest should be
                                                      # reaction to update?
        label = self._labels[row][col]
        label.configure(bg=P["sel"])
        label.focus_set()

        cell = self.engine.cells[row][col]
        self._addr_var.set(cell.address)
        self._formula_var.set(cell.raw or "")  # todo - wrong thread? maybe the
                                               # best way is to use reaction on
                                               # self._selected to get the
                                               # values and on_cell_changed
                                               # like callback to update UI
        # todo - display was removed since it was apt to access cell value from
        #        wrong thread. Get the value from the cell widget text
        lbl = self._labels[row][col]
        self._status_var.set(f"{cell.address}  =  {lbl.cget('text')}")

    def _begin_edit(self, row: int, col: int, event: tk.Event|None=None) -> None:
        self._select(row, col, commit=False)
        self._fentry.focus_set()
        self._fentry.icursor("end")
        self._editing = True

    def _key(self, row: int, col: int, event: tk.Event) -> None:
        k = event.keysym
        if k in ("Return", "F2"):    self._begin_edit(row, col)
        elif k == "Delete":
            self.engine.set_raw(row, col, "")
            self._refresh_cell(self.engine.cells[row][col], "", "")
            self._select(row, col, commit=False)
        elif k == "Tab":
            nc = (col + 1) % self.engine.ncols
            nr = row + (1 if col + 1 >= self.engine.ncols else 0)
            if nr < self.engine.nrows: self._select(nr, nc)
        elif k == "Up"    and row > 0:                      self._select(row-1, col)
        elif k == "Down"  and row < self.engine.nrows - 1:  self._select(row+1, col)
        elif k == "Left"  and col > 0:                      self._select(row, col-1)
        elif k == "Right" and col < self.engine.ncols - 1:  self._select(row, col+1)
        elif len(event.char) == 1 and event.char.isprintable():
            self._formula_var.set(event.char)
            self._fentry.focus_set()
            self._fentry.icursor("end")
            self._editing = True

    @property
    def _selected_label(self) -> tk.Label:
        assert self._selected
        return self._labels[self._selected.row][self._selected.col]

    def _commit(self, event:tk.Event|None=None, where:str='?') -> None:
        if self._selected is None: return
        self._selected_label.focus_set()
        if not self._editing: return
        raw = self._formula_var.get()
        self.engine.set_raw(self._selected.row, self._selected.col, raw)
        self._editing = False

    def _cancel(self, event:tk.Event|None=None) -> None:
        if not self._selected: return
        r, c = self._selected.row, self._selected.col
        self._formula_var.set(str(self.engine.cells[r][c].raw or ""))
        self._editing = False
        self._selected_label.focus_set()

    # ── UI refresh ────────────────────────────────────────────────────────────

    def _refresh_cell(self, cell: Cell, raw: str, value: str) -> None:
        '''
        refresh the contents of cell.
        executes in tkinter thread, do not access cell values
        '''
        r, c = cell.row, cell.col
        raw = raw or ""
        fg = (P["error"]     if isinstance(value, str) and value.startswith("#ERR")
              else P["formula"] if raw.startswith("=")
              else P["text"])
        lbl = self._labels[r][c]
        lbl.configure(text=value, fg=fg)
        if cell is self._selected:
            self._status_var.set(f"{cell.address}  =  {value}")

    async def _on_cell_changed(self, cell: Cell,
                               change: FieldChange[Cell, CellValue]) -> None:
        '''
        reaction when cell value changes - refresh cell
        Executes in Spreadsheet event loop. Do not access widgets.
        '''
        value = change.new
        if isinstance(value, float) and value == int(value):
            value = int(value)
        value = str(value)

        self.root.after(0, self._refresh_cell, cell, cell.raw, value)


def main() -> None:
    root = tk.Tk()
    root.title("Reactions Demo Spreadsheet")
    root.geometry("960x580")
    root.minsize(640, 400)

    engine = SpreadsheetEngine(nrows=20, ncols=8)

    SpreadsheetUI(root, engine)
    root.mainloop()


if __name__ == "__main__":
    main()
