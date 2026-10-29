"""Tkinter interface. AI runs in a worker; only the main thread touches Tk."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .agents import AgentConfig, SearchCancelled, make_agent
from .board import Board, SIZE, X, coordinate, parse_coordinate, symbol
from .records import add_move, load_record, new_record, save_record

LABELS = {"Người chơi": "human", "Random": "random",
          "MiniMax + Alpha-Beta": "alphabeta", "MiniMax (không cắt tỉa)": "minimax",
          "MCTS + UCT": "mcts"}
REVERSE_LABELS = {value: key for key, value in LABELS.items()}
BG, INK, ACCENT = "#eef2f6", "#182235", "#0f766e"


class PlayerPanel(ttk.LabelFrame):
    def __init__(self, parent, title: str, algorithm: str):
        super().__init__(parent, text=title, padding=10)
        self.columnconfigure(1, weight=1)
        self.variables = {"algorithm": tk.StringVar(value=REVERSE_LABELS[algorithm]),
                          "depth": tk.StringVar(value="2"),
                          "candidates": tk.StringVar(value="10"),
                          "iterations": tk.StringVar(value="300"),
                          "c": tk.StringVar(value="1.4"),
                          "rollout": tk.StringVar(value="random")}
        algorithm_box = ttk.Combobox(self, textvariable=self.variables["algorithm"],
                                     values=list(LABELS), state="readonly", width=28)
        algorithm_box.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        self.fields = {}
        for row, ((key1, text1), (key2, text2)) in enumerate((
            (("depth", "Độ sâu d"), ("candidates", "Ứng viên K")),
            (("iterations", "Iteration"), ("c", "Hệ số c")),
        ), start=1):
            for col, key, text in ((0, key1, text1), (2, key2, text2)):
                ttk.Label(self, text=text).grid(row=row, column=col, sticky="w", padx=(0, 5), pady=3)
                entry = ttk.Entry(self, textvariable=self.variables[key], width=7)
                entry.grid(row=row, column=col + 1, sticky="ew", padx=(0, 8), pady=3)
                self.fields[key] = entry
        ttk.Label(self, text="Rollout").grid(row=3, column=0, sticky="w", pady=3)
        self.rollout_box = ttk.Combobox(self, textvariable=self.variables["rollout"],
                                        values=("random", "tactical"), state="readonly", width=10)
        self.rollout_box.grid(row=3, column=1, columnspan=3, sticky="ew", padx=(0, 8))
        algorithm_box.bind("<<ComboboxSelected>>", lambda _: self.update_fields())
        self.update_fields()

    def update_fields(self) -> None:
        algorithm = LABELS[self.variables["algorithm"].get()]
        for key, entry in self.fields.items():
            enabled = (algorithm in ("alphabeta", "minimax") and key in ("depth", "candidates")) or (
                algorithm == "mcts" and key in ("iterations", "c"))
            entry.configure(state="normal" if enabled else "disabled")
        self.rollout_box.configure(state="readonly" if algorithm == "mcts" else "disabled")

    def config(self) -> AgentConfig:
        algorithm = LABELS[self.variables["algorithm"].get()]
        # Only relevant fields are parsed; disabled stale fields cannot block a game.
        values = {"algorithm": algorithm}
        if algorithm in ("alphabeta", "minimax"):
            values.update(depth=int(self.variables["depth"].get()),
                          candidates=int(self.variables["candidates"].get()))
        if algorithm == "mcts":
            values.update(iterations=int(self.variables["iterations"].get()),
                          c=float(self.variables["c"].get()),
                          rollout=self.variables["rollout"].get())
        return AgentConfig(**values)

    def set_config(self, config: AgentConfig) -> None:
        for key, value in asdict(config).items():
            self.variables[key].set(REVERSE_LABELS[value] if key == "algorithm" else str(value))
        self.update_fields()


class CaroApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Caro AI | MiniMax • Alpha-Beta • MCTS")
        root.geometry("1120x820")
        root.minsize(1020, 760)
        root.configure(bg=BG)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("TLabelframe", background=BG)
        style.configure("TLabelframe.Label", background=BG, foreground=INK,
                        font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7))
        style.configure("Accent.TButton", background=ACCENT, foreground="white")
        style.map("Accent.TButton", background=[("active", "#115e59")])
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 9))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        header = tk.Frame(root, bg=INK, padx=24, pady=16)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(header, text="CARO / AI LAB", bg=INK, fg="white",
                 font=("Segoe UI", 21, "bold")).pack(side="left")
        tk.Label(header, text="9 × 9  |  Năm quân liên tiếp để thắng", bg=INK, fg="#cbd5e1",
                 font=("Segoe UI", 11)).pack(side="right")

        main = ttk.Frame(root, padding=(20, 15))
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)
        self.status = tk.StringVar()
        ttk.Label(main, textvariable=self.status, font=("Segoe UI", 12, "bold"),
                  wraplength=600).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.canvas = tk.Canvas(main, bg="#e8d5b5", highlightthickness=0,
                                width=570, height=480)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=(0, 18))
        self.canvas.bind("<Configure>", lambda _: self.draw())
        self.canvas.bind("<Button-1>", self.click)
        sidebar = ttk.Frame(main, width=360)
        sidebar.grid(row=0, column=1, rowspan=2, sticky="ns")
        self.panels = {X: PlayerPanel(sidebar, "X · đi trước", "human"),
                       -X: PlayerPanel(sidebar, "O · đi sau", "alphabeta")}
        for index, player in enumerate((X, -X)):
            self.panels[player].grid(row=index, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.seed = tk.StringVar(value="2026")
        seed_row = ttk.Frame(sidebar)
        seed_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(seed_row, text="Random seed").pack(side="left")
        ttk.Entry(seed_row, textvariable=self.seed, width=12).pack(side="right")
        ttk.Label(sidebar, text="Tham số áp dụng khi bấm Ván mới.\nCó thể chọn AI cho cả X và O.",
                  foreground="#64748b").grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Button(sidebar, text="Ván mới", style="Accent.TButton", command=self.new_game).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=4)
        self.pause_button = ttk.Button(sidebar, text="Tạm dừng", command=self.toggle_pause)
        self.pause_button.grid(row=5, column=0, sticky="ew", padx=(0, 4), pady=4)
        ttk.Button(sidebar, text="AI đi 1 bước", command=self.step).grid(
            row=5, column=1, sticky="ew", pady=4)
        ttk.Button(sidebar, text="Lưu nhật ký", command=self.save).grid(
            row=6, column=0, sticky="ew", padx=(0, 4), pady=4)
        ttk.Button(sidebar, text="Mở nhật ký", command=self.load).grid(
            row=6, column=1, sticky="ew", pady=4)
        ttk.Button(sidebar, text="Nạp thế cờ (A1, E5, ...)", command=self.import_position).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=4)

        bottom = ttk.Frame(root, padding=(20, 0, 20, 14))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, text="NHẬT KÝ SUY LUẬN", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 5))
        columns = ("ply", "player", "move", "algorithm", "depth", "ms", "nodes", "iters", "cuts")
        self.table = ttk.Treeview(bottom, columns=columns, show="headings", height=5)
        widths = (48, 48, 60, 145, 60, 100, 110, 80, 70)
        headings = ("Lượt", "Bên", "Ô", "Thuật toán", "Độ sâu", "Thời gian ms", "Số nút", "Iteration", "Cắt tỉa")
        for name, width, heading in zip(columns, widths, headings):
            self.table.heading(name, text=heading)
            self.table.column(name, width=width, anchor="center")
        self.table.grid(row=1, column=0, sticky="ew")
        scroll = ttk.Scrollbar(bottom, orient="vertical", command=self.table.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scroll.set)
        ttk.Label(bottom, text="d đếm số nửa lượt. Nút MCTS = nút cây tạo ra, không gồm bước rollout. "
                  "Rollout random là bản cơ sở; tactical ưu tiên thắng/chặn ngay.",
                  foreground="#64748b", wraplength=1040).grid(row=2, column=0, sticky="w", pady=(6, 0))

        self.board = Board()
        self.record = {}
        self.configs = {}
        self.agents = {}
        self.results = queue.Queue()
        self.generation = 0
        self.cancel = threading.Event()
        self.busy = False
        self.paused = False
        self.single_step = False
        self.pending_result = None
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.new_game()
        root.after(50, self.poll)

    def invalidate_worker(self) -> None:
        self.cancel.set()
        self.generation += 1
        self.cancel = threading.Event()
        self.busy = False
        self.pending_result = None

    def new_game(self) -> None:
        try:
            configs = {player: panel.config() for player, panel in self.panels.items()}
            seed = int(self.seed.get())
        except (ValueError, OverflowError) as exc:
            messagebox.showerror("Tham số không hợp lệ", str(exc), parent=self.root)
            return
        self.invalidate_worker()
        self.configs = configs
        self.agents = {player: make_agent(config, seed + (11 if player == X else 29))
                       for player, config in configs.items() if config.algorithm != "human"}
        self.board = Board()
        self.record = new_record(configs[X], configs[-X], seed)
        self.record["agent_seeds"] = {"X": seed + 11, "O": seed + 29}
        self.paused = self.single_step = False
        self.pause_button.configure(text="Tạm dừng")
        self.table.delete(*self.table.get_children())
        self.refresh()
        self.root.after(100, self.schedule)

    def refresh(self) -> None:
        if self.board.terminal:
            self.status.set(f"{symbol(self.board.winner)} thắng!" if self.board.winner else "Hòa: bàn cờ đã đầy.")
        else:
            label = REVERSE_LABELS[self.configs[self.board.turn].algorithm]
            extra = " · tạm dừng" if self.paused else " · đang suy luận..." if self.busy else ""
            self.status.set(f"Lượt {symbol(self.board.turn)} · {label}{extra}")
        self.draw()

    def layout(self):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        cell = max(1, (min(width, height) - 54) / SIZE)
        return (width - cell * SIZE) / 2, (height - cell * SIZE) / 2, cell

    def draw(self) -> None:
        self.canvas.delete("all")
        ox, oy, cell = self.layout()
        winning = set(self.board.winning_line())
        for index in range(SIZE):
            self.canvas.create_text(ox + (index + .5) * cell, oy - 17,
                                    text=chr(65 + index), fill="#61523e", font=("Segoe UI", 10))
            self.canvas.create_text(ox - 17, oy + (index + .5) * cell,
                                    text=str(index + 1), fill="#61523e", font=("Segoe UI", 10))
        for move in range(81):
            r, c = divmod(move, SIZE)
            x1, y1 = ox + c * cell, oy + r * cell
            color = "#b8d9af" if move in winning else "#f4dfb7" if move == self.board.last_move else "#efddbe"
            self.canvas.create_rectangle(x1, y1, x1 + cell, y1 + cell, fill=color, outline="#bca680")
            player = self.board.at(move)
            margin = cell * .25
            if player == X:
                for start, end in (((x1 + margin, y1 + margin), (x1 + cell - margin, y1 + cell - margin)),
                                   ((x1 + margin, y1 + cell - margin), (x1 + cell - margin, y1 + margin))):
                    self.canvas.create_line(*start, *end, fill="#2563a6", width=3)
            elif player == -X:
                self.canvas.create_oval(x1 + margin, y1 + margin, x1 + cell - margin,
                                        y1 + cell - margin, outline="#c45443", width=3)
            if move == self.board.last_move:
                self.canvas.create_oval(x1 + cell - 8, y1 + 3, x1 + cell - 3, y1 + 8,
                                        fill=ACCENT, outline="")

    def click(self, event) -> None:
        if self.busy or self.paused or self.board.terminal:
            return
        if self.configs[self.board.turn].algorithm != "human":
            return
        ox, oy, cell = self.layout()
        c, r = int((event.x - ox) // cell), int((event.y - oy) // cell)
        if not (0 <= r < SIZE and 0 <= c < SIZE):
            return
        try:
            self.apply_move(r * SIZE + c)
        except ValueError as exc:
            self.root.bell()
            self.status.set(str(exc))

    def append_row(self, item: dict) -> None:
        row = self.table.insert("", "end", values=(
            item["ply"], item["player"], coordinate(item["move"]), item["algorithm"],
            item.get("depth", 0) or "—", f"{item['elapsed_ms']:.2f}", item["nodes"],
            item.get("iterations", 0) or "—", item.get("cutoffs", 0)))
        self.table.see(row)

    def apply_move(self, move: int, result=None) -> None:
        self.board = add_move(self.record, self.board, move, result)
        self.append_row(self.record["moves"][-1])
        self.refresh()
        if self.board.terminal:
            messagebox.showinfo("Kết thúc ván", self.status.get(), parent=self.root)
        elif not self.paused:
            self.root.after(120, self.schedule)

    def schedule(self) -> None:
        if self.busy or self.board.terminal or (self.paused and not self.single_step):
            return
        if self.configs[self.board.turn].algorithm == "human":
            return
        self.busy = True
        generation, agent, board, cancel = self.generation, self.agents[self.board.turn], self.board, self.cancel
        self.refresh()
        def work():
            try:
                self.results.put((generation, agent.choose(board, cancel), None))
            except SearchCancelled:
                pass
            except Exception as exc:
                self.results.put((generation, None, str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self) -> None:
        try:
            while True:
                generation, result, error = self.results.get_nowait()
                if generation != self.generation:
                    continue
                self.busy = False
                if error:
                    self.paused = True
                    self.single_step = False
                    self.pause_button.configure(text="Tiếp tục")
                    messagebox.showerror("Lỗi AI", error, parent=self.root)
                    self.refresh()
                elif self.paused and not self.single_step:
                    self.pending_result = result  # A pause never applies a completed move.
                    self.refresh()
                else:
                    self.single_step = False
                    self.apply_move(result.move, result)
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.pause_button.configure(text="Tiếp tục" if self.paused else "Tạm dừng")
        if not self.paused and self.pending_result is not None:
            result, self.pending_result = self.pending_result, None
            self.apply_move(result.move, result)
        self.refresh()
        if not self.paused:
            self.schedule()

    def step(self) -> None:
        if self.board.terminal or self.configs[self.board.turn].algorithm == "human":
            return
        self.paused = True
        self.pause_button.configure(text="Tiếp tục")
        if self.pending_result is not None:
            result, self.pending_result = self.pending_result, None
            self.apply_move(result.move, result)
        else:
            self.single_step = True
            self.schedule()

    def save(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                          initialfile="caro_game.json", filetypes=[("JSON", "*.json")])
        if path:
            try:
                save_record(self.record, path)
                self.status.set(f"Đã lưu {Path(path).name}")
            except OSError as exc:
                messagebox.showerror("Không lưu được", str(exc), parent=self.root)

    def install_record(self, record: dict, board: Board) -> None:
        self.invalidate_worker()
        self.board, self.record = board, record
        self.seed.set(str(record["seed"]))
        self.configs = {player: AgentConfig(**record["configs"][symbol(player)]) for player in (X, -X)}
        for player, panel in self.panels.items():
            panel.set_config(self.configs[player])
        # Board/log history is replayed exactly; RNG streams restart on load.
        # The record explicitly flags this, and README documents continuation.
        self.agents = {player: make_agent(config, record.get("agent_seeds", {}).get(
            symbol(player), int(record["seed"]) + (11 if player == X else 29)))
            for player, config in self.configs.items() if config.algorithm != "human"}
        self.record["continuation_rng_restarted"] = True
        self.paused, self.single_step = True, False
        self.pause_button.configure(text="Tiếp tục")
        self.table.delete(*self.table.get_children())
        for item in record["moves"]:
            self.append_row(item)
        self.refresh()

    def load(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("JSON", "*.json")])
        if path:
            try:
                record, board = load_record(path)
                self.install_record(record, board)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                messagebox.showerror("Nhật ký không hợp lệ", str(exc), parent=self.root)

    def import_position(self) -> None:
        text = simpledialog.askstring("Nạp thế cờ", "Nhập các nước lần lượt X, O. Ví dụ:\nE5 D5 E4 D4 F4 F5",
                                      parent=self.root)
        if text is None:
            return
        try:
            moves = text.replace(",", " ").split()
            board = Board.from_moves(moves)
            configs = {player: panel.config() for player, panel in self.panels.items()}
            seed = int(self.seed.get())
            record = new_record(configs[X], configs[-X], seed)
            replay = Board()
            for move in moves:
                replay = add_move(record, replay, parse_coordinate(move))
            self.install_record(record, board)
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Thế cờ không hợp lệ", str(exc), parent=self.root)

    def close(self) -> None:
        self.cancel.set()
        self.root.destroy()


def run_gui() -> None:
    root = tk.Tk()
    CaroApp(root)
    root.mainloop()
