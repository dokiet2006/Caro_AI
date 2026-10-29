"""Command-line entry points; core algorithms work without Tk/display/pip."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agents import AgentConfig, make_agent
from .board import Board, X, coordinate, parse_coordinate, symbol
from .records import add_move, new_record, save_record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Caro 9x9: MiniMax / Alpha-Beta / MCTS + UCT")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="Mở giao diện đồ họa (mặc định).")
    play = sub.add_parser("play", help="Chơi trong terminal; hỗ trợ người-máy, máy-máy.")
    for player, default in (("x", "human"), ("o", "alphabeta")):
        play.add_argument(f"--{player}", choices=("human", "random", "alphabeta", "minimax", "mcts"), default=default)
        play.add_argument(f"--{player}-depth", type=int, default=2)
        play.add_argument(f"--{player}-candidates", type=int, default=10)
        play.add_argument(f"--{player}-iterations", type=int, default=300)
        play.add_argument(f"--{player}-c", type=float, default=1.4)
        play.add_argument(f"--{player}-rollout", choices=("random", "tactical"), default="random")
    play.add_argument("--seed", type=int, default=2026)
    play.add_argument("--log", type=Path, default=Path("results/last_game.json"))
    play.add_argument("--quiet", action="store_true", help="Ẩn bảng sau mỗi nước; vẫn in kết quả.")
    play.add_argument("--moves", nargs="*", default=[], metavar="E5", help="Thế cờ hợp lệ: X, O luân phiên.")

    experiment = sub.add_parser("experiment", help="Đối sánh + khảo sát c/iteration, CSV, SVG, HTML.")
    experiment.add_argument("--games", type=int, default=20, help="Số chẵn >=20 cho mỗi cấu hình.")
    experiment.add_argument("--seed", type=int, default=2026)
    experiment.add_argument("--depth", type=int, default=2)
    experiment.add_argument("--candidates", type=int, default=10)
    experiment.add_argument("--iterations", type=int, default=300, help="Giữ cố định khi khảo sát c.")
    experiment.add_argument("--c", type=float, default=1.4, help="Giữ cố định khi khảo sát iteration.")
    experiment.add_argument("--opponent", choices=("random", "alphabeta"), default="random")
    experiment.add_argument("--output", type=Path, default=Path("results/new_run"))
    experiment.add_argument("--smoke", action="store_true", help="Cho phép <20 ván, đánh dấu là thử nhanh.")
    experiment.add_argument("--include-heuristic", action="store_true", help="Thêm so sánh rollout tactical/random.")

    benchmark = sub.add_parser("benchmark", help="So MiniMax thường với Alpha-Beta trên 4 thế cờ.")
    benchmark.add_argument("--depth", type=int, default=3)
    benchmark.add_argument("--candidates", type=int, default=10)
    return parser


def run_terminal(args) -> None:
    configs = {}
    for player, prefix in ((X, "x"), (-X, "o")):
        configs[player] = AgentConfig(
            algorithm=getattr(args, prefix), depth=getattr(args, f"{prefix}_depth"),
            candidates=getattr(args, f"{prefix}_candidates"),
            iterations=getattr(args, f"{prefix}_iterations"), c=getattr(args, f"{prefix}_c"),
            rollout=getattr(args, f"{prefix}_rollout"))
    agents = {player: make_agent(cfg, args.seed + (11 if player == X else 29))
              for player, cfg in configs.items() if cfg.algorithm != "human"}
    record = new_record(configs[X], configs[-X], args.seed)
    record["agent_seeds"] = {"X": args.seed + 11, "O": args.seed + 29}
    board = Board()
    for text in args.moves:
        board = add_move(record, board, parse_coordinate(text))
    if not args.quiet:
        print(board.text())
    try:
        while not board.terminal:
            player = board.turn
            if configs[player].algorithm == "human":
                try:
                    value = input(f"{symbol(player)} đi (A1-I9; q để thoát): ").strip()
                    if value.lower() in ("q", "quit", "exit"):
                        print("Đã dừng và lưu ván đang chơi.")
                        break
                    move = parse_coordinate(value)
                    board = add_move(record, board, move)
                except ValueError as exc:
                    print(exc)
                    continue
            else:
                result = agents[player].choose(board)
                board = add_move(record, board, result.move, result)
                if not args.quiet:
                    print(f"{symbol(player)} / {result.algorithm}: {coordinate(result.move)} | "
                          f"d={result.depth} | {result.elapsed_ms:.2f} ms | "
                          f"nodes={result.nodes} | iterations={result.iterations} | cutoffs={result.cutoffs}")
            if not args.quiet:
                print(board.text())
    except (EOFError, KeyboardInterrupt):
        print("\nĐã dừng và lưu ván đang chơi.")
    finally:
        save_record(record, args.log)
    if board.terminal:
        print(board.text())
        print(f"Kết quả: {symbol(board.winner)} thắng." if board.winner else "Kết quả: Hòa.")
    print(f"Nhật ký: {args.log}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command in (None, "gui"):
            try:
                from .gui import run_gui
                run_gui()
            except ImportError as exc:
                if exc.name not in ("tkinter", "_tkinter"):
                    raise
                print("Python này thiếu Tkinter. Trên Windows dùng bản Python có Tcl/Tk; "
                      "trên Ubuntu cài python3-tk. Hoặc chạy: python main.py play", file=sys.stderr)
                return 1
            except Exception as exc:
                # Only turn display initialization errors into a useful terminal hint.
                if exc.__class__.__name__ != "TclError":
                    raise
                print(f"Không mở được cửa sổ Tkinter: {exc}\n"
                      "Có thể chơi không cần giao diện: python main.py play", file=sys.stderr)
                return 1
        elif args.command == "play":
            run_terminal(args)
        elif args.command == "experiment":
            from .experiments import run_suite
            run_suite(args.output, args.games, args.seed, args.depth, args.candidates,
                      args.iterations, args.c, args.opponent, args.smoke, args.include_heuristic)
        elif args.command == "benchmark":
            from .experiments import benchmark_pruning
            print(json.dumps(benchmark_pruning(args.depth, args.candidates), indent=2, ensure_ascii=False))
    except (ValueError, OSError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 2
    return 0
