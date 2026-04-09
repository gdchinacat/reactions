import ast
import asyncio
from functools import partial, wraps, cached_property
import re
from statistics import mean, StatisticsError
from threading import Thread, Event
from tkinter import font as tkfont
from types import CodeType
from typing import Iterator, Literal, Callable

from reactions import (Field, ExecutorFieldManager, Executor, FieldChange,
                       ReactionCanceler)
import tkinter as tk


type Number = int | float | complex
type CellValue = Number | str

# todo
#    - use namedtuple for cell address rather than r, c args all over

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
    import ast
    code: CodeType|None = None

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

    async def _value_changed(self,
                              changed_cell: Cell,
                              change: FieldChange[Cell, CellValue]
                                     |FieldChange[Cell, str]) -> None:

        '''
        Reacts to referenced cell value changes.
        Update the evaluated value based on the raw value.
        This handles both raw value change and referenced cell value change.
        Performs data type conversion from raw string to properly typed value.
        '''
        self.__value_changed(changed_cell, change)

    def __value_changed(self,
                              changed_cell: Cell,
                              change: FieldChange[Cell, CellValue]
                                     |FieldChange[Cell, str]) -> None:
        if self.code is None:
            # If a value change is scheduled when raw changes self.code willj
            # be None when the value changed executes, ignore it.
            return

        try:
            result = eval(self.code, self.engine.globals, self.engine.locals)
        except Exception as e:
            import traceback
            traceback.print_exc()
            result = f'#ERR: {e}'

        if isinstance(result, (int, float, complex)):
            self.value = result
        else:
            self.value = str(result)

    def _set_expression(self, expression: str) -> None:
        '''
        Set the expression for the cell by compiling it to code and registering
        reactions for when dependent cells change.
        '''
        # clear the code and remove registered reactions
        self.code = None
        for canceler in self._cancelers.values():
            canceler()
        self._cancelers.clear()

        try:
            code = compile(expression, str(self), 'eval', dont_inherit=True)
        except Exception as e:
            self.value = f'#ERR: {e}'

        # register reactions for referenced cells
        for name in code.co_names:
            cell = self.engine.cell_by_addr(name)
            if cell and cell not in self._cancelers:
                canceler = Cell.value[cell](self._value_changed).canceler
                self._cancelers[cell] = canceler

        self.code = code # only set once it's been processed fully

    def _convert_raw(self, raw: str) -> CellValue:
        '''
        Convert the raw string value into the most appropriate data type.
        '''
        # todo more data type support (ie date, currency)
        try:
            return float(raw) if '.' in raw else int(raw)
        except ValueError:
            pass

        try:
            return complex(raw)
        except ValueError:
            pass

        return raw

    @ raw
    async def _raw_changed(self,
                            change: FieldChange[Cell, str]) -> None:
        if change.new and change.new[0] == '=':
            self._set_expression(change.new[1:])
            self.__value_changed(self, change)
        else:
            self.code = None
            self.value = self._convert_raw(change.new)


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


class LocalsDict(dict[str, object]):
    '''
    The exec() dict for locals.
    This is essentially a cache of cell values that uses reactions to update
    values when they change.
    todo? - functionally there is no need to purge values when no cell raw
    functions refer to them, or no code blocks for these reference them, but
    it is strictly speaking wasted resources to have cell values cached
    needlessly. In practice, I doubt it will matter, functions are unlikely to
    change necessitating them (the code doesn't have access to the cells or
    raw values so cells can't do meta-programming - yet). Basically, there is
    no use case for purging the cache. Complex mechanisms to ref count code
    references to them could be implemented to GC them...might be able to use
    weak refs, etc. FORMALIZE THIS COMMENT
    '''
    def __init__(self, engine: SpreadsheetEngine) -> None:
        self.engine = engine
        self.executor = engine.executor
        Cell.value(self._value_changed)

    def __getitem__(self, key:str) -> object:
        try:
            return super().__getitem__(key)
        except KeyError:
            # If key looks like a cell cache value for future lookups and
            # register reaction to update cached value on change.
            if cell := self.engine.cell_by_addr(key):
                #Cell.value[cell](self._value_changed)
                value = cell.value
                self[key] = value
                return value
            raise

    async def _value_changed(self,
                             cell: Cell,
                             change: FieldChange[Cell, CellValue]
                       ) -> None:
        self[cell.address] = cell.value


class SpreadsheetEngine:
    """
    Spreadsheet with grid of cells.
    Has an asyncio event loop thread to process reactions for cells.
    Updates from UI are scheduled in event loop to allow reactions they cause
    to be responded to.
    """

    def __init__(self, nrows: int = 20, ncols: int = 8,
                 filename: str='/tmp/spreadsheet.raw'):
        self.executor = Executor()
        self.cells: list[list[Cell]] = [
            [Cell(self, r, c) for c in range(ncols)]
            for r in range(nrows)
        ]

        self.globals = dict[str, object]()  # for executing cell functions
        self.locals = LocalsDict(self)      # for executing cell functions
 

        # Initialize with useful things.
        exec('''
from time import time
from math import *
        ''', self.globals, self.locals)

        # Threading - each engine has its own thread and asyncio event loop to
        # process reactions in. This allows the spreadsheet reactions to work
        # with frameworks that are not async and control the "main" thread.
        # The event loop is exposed so that external updates to the cells raw
        # values can be scheduled with the event loop in a threadsafe way.
        executor_started = Event()
        def reactions_thread() -> None:
            '''thread to run the asyncio event loop for the spreadsheet'''
            async def run() -> None:
                self._loop = asyncio.get_running_loop()
                _await = self.executor.start()
                executor_started.set()
                await _await
            asyncio.run(run())

        self.thread = Thread(target=reactions_thread, daemon=True)
        self.thread.start()
        executor_started.wait()

        self.filename = filename
        self._load()

    async def _raw_changed(self, cell: Cell,
                           change: FieldChange[Cell, str]) -> None:
        with open(self.filename, 'a') as file:
            file.write(f'{cell.address}:{change.new}\n')

    def _load(self) -> None:
        '''Load the raw values and set them on cells.'''
        async def load()->None:
            with open(self.filename, 'r') as file:
                for l in file.readlines():
                    addr, raw = l.strip().split(':', maxsplit=1)
                    cell = self.cell_by_addr(addr)
                    assert cell is not None
                    cell.raw = raw
            Cell.raw(self._raw_changed)
        asyncio.run_coroutine_threadsafe(load(), self._loop)

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
