"""Reproducible paired games, CSV/JSONL evidence and dependency-free SVG plots.

Timing is perf_counter around choose() only; no drawing/file IO is timed.
Games run sequentially so parallel workloads do not contaminate timings.
"""
from __future__ import annotations

import csv
import html
import json
import os
import platform
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from time import perf_counter

from .agents import AgentConfig, make_agent
from .board import Board, X, coordinate, symbol
from .records import add_move, new_record


def _cpu_model() -> str:
    path = Path("/proc/cpuinfo")
    if path.is_file():
        for line in path.read_text(errors="replace").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[-1].strip()
    return platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown")


def play_game(x_config: AgentConfig, o_config: AgentConfig,
              x_seed: int, o_seed: int) -> dict:
    agents = {X: make_agent(x_config, x_seed), -X: make_agent(o_config, o_seed)}
    board = Board()
    record = new_record(x_config, o_config, x_seed)
    record["agent_seeds"] = {"X": x_seed, "O": o_seed}
    start = perf_counter()
    while not board.terminal:
        result = agents[board.turn].choose(board)
        board = add_move(record, board, result.move, result, detailed=False)
    record["wall_seconds"] = perf_counter() - start
    return record


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def paired_match(subject: AgentConfig, opponent: AgentConfig, games: int,
                 seed: int, family: str, name: str, evidence, game_rows: list[dict]) -> dict:
    wins = draws = losses = 0
    subject_times, opponent_times = [], []
    per_game_subject_means = []
    total_wall = 0.0
    for pair in range(games // 2):
        # Repeat the same role-based seeds in the color-swapped leg.
        subject_seed, opponent_seed = seed + pair * 10000 + 11, seed + pair * 10000 + 29
        for leg in range(2):
            subject_side = X if leg == 0 else -X
            if subject_side == X:
                record = play_game(subject, opponent, subject_seed, opponent_seed)
            else:
                record = play_game(opponent, subject, opponent_seed, subject_seed)
            result = record["outcome"]
            won, drawn = result == subject_side, result == 0
            wins += int(won)
            draws += int(drawn)
            losses += int(not won and not drawn)
            own = [m["elapsed_ms"] for m in record["moves"]
                   if m["player"] == symbol(subject_side)]
            other = [m["elapsed_ms"] for m in record["moves"]
                     if m["player"] != symbol(subject_side)]
            subject_times.extend(own)
            opponent_times.extend(other)
            per_game_subject_means.append(mean(own))
            total_wall += record["wall_seconds"]
            game_id = f"{family}/{name}/pair{pair + 1:02}/leg{leg + 1}"
            record.update({"game_id": game_id, "family": family,
                           "configuration": name, "subject_symbol": symbol(subject_side)})
            evidence.write(json.dumps(record, ensure_ascii=False) + "\n")
            evidence.flush()
            game_rows.append({"game_id": game_id, "family": family, "configuration": name,
                              "pair": pair + 1, "leg": leg + 1,
                              "subject": subject.algorithm, "opponent": opponent.algorithm,
                              "subject_symbol": symbol(subject_side),
                              "subject_seed": subject_seed, "opponent_seed": opponent_seed,
                              "result": "win" if won else "draw" if drawn else "loss",
                              "winner": symbol(result) if result else "draw",
                              "plies": len(record["moves"]),
                              "subject_mean_ms": mean(own), "subject_moves": len(own),
                              "opponent_mean_ms": mean(other),
                              "wall_seconds": record["wall_seconds"]})
            print(f"  {name}: {pair * 2 + leg + 1:2}/{games} "
                  f"X={record['configs']['X']['algorithm']} "
                  f"O={record['configs']['O']['algorithm']} -> "
                  f"{symbol(result) if result else 'draw'}", flush=True)
    return {"family": family, "configuration": name,
            "subject": subject.algorithm, "opponent": opponent.algorithm,
            "depth": subject.depth, "candidates": subject.candidates,
            "c": subject.c, "iterations": subject.iterations, "rollout": subject.rollout,
            "games": games, "wins": wins, "draws": draws, "losses": losses,
            "win_rate": wins / games, "draw_rate": draws / games, "loss_rate": losses / games,
            "mean_move_ms": mean(subject_times),
            "mean_game_move_ms": mean(per_game_subject_means),
            "opponent_mean_move_ms": mean(opponent_times),
            "subject_move_count": len(subject_times), "total_wall_seconds": total_wall}


BENCHMARK_POSITIONS = {
    "empty": [],
    "opening": ["E5", "D5", "E4", "D4", "F4", "F5"],
    "middle": ["E5", "D5", "E4", "D4", "F4", "F5", "F3", "G2", "D6", "C7"],
    "threat": ["B5", "A5", "C5", "I1", "D5", "H1", "E5", "G2"],
}


def benchmark_pruning(depth: int, candidates: int) -> list[dict]:
    rows = []
    for name, moves in BENCHMARK_POSITIONS.items():
        board = Board.from_moves(moves)
        plain = make_agent(AgentConfig("minimax", depth, candidates)).choose(board)
        pruned = make_agent(AgentConfig("alphabeta", depth, candidates)).choose(board)
        if (plain.move, plain.score) != (pruned.move, pruned.score):
            raise AssertionError("Alpha-Beta phải cho cùng kết quả MiniMax trên cùng cây.")
        rows.append({"position": name, "opening_moves": " ".join(moves),
                     "depth": depth, "candidates": candidates,
                     "move": coordinate(plain.move), "score": plain.score,
                     "minimax_nodes": plain.nodes, "alphabeta_nodes": pruned.nodes,
                     "minimax_ms": plain.elapsed_ms, "alphabeta_ms": pruned.elapsed_ms,
                     "cutoffs": pruned.cutoffs,
                     "node_reduction": 1 - pruned.nodes / plain.nodes})
    return rows


def _svg_plot(path: Path, title: str, labels: list[str],
              series: list[tuple[str, list[float], str]], ylabel: str,
              maximum: float | None = None) -> None:
    """Exact SVG output; generated data, labels and colors are never rasterized."""
    width, height, left, top, plot_w, plot_h = 900, 450, 85, 85, 720, 260
    maximum = maximum if maximum is not None else max(
        (value for _, values, _ in series for value in values), default=1) * 1.15
    maximum = max(maximum, 1e-9)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img">',
           f'<title>{html.escape(title)}</title>',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           '<g font-family="Arial,sans-serif" fill="#172033">',
           f'<text x="{left}" y="32" font-size="20" font-weight="bold">{html.escape(title)}</text>',
           f'<text x="{left}" y="60" font-size="13">{html.escape(ylabel)}</text>']
    for tick in range(6):
        value = tick * maximum / 5
        y = top + plot_h * (1 - tick / 5)
        svg.append(f'<line x1="{left}" y1="{y}" x2="{left + plot_w}" y2="{y}" '
                   'stroke="#e2e8f0"/>')
        svg.append(f'<text x="{left - 12}" y="{y + 4}" text-anchor="end" '
                   f'font-size="12">{value:.1f}</text>')
    def x_at(index: int) -> float:
        return left + plot_w * ((index + 0.5) / max(1, len(labels)))
    for i, label in enumerate(labels):
        svg.append(f'<text x="{x_at(i)}" y="{top + plot_h + 27}" text-anchor="middle" '
                   f'font-size="12">{html.escape(label)}</text>')
    for si, (name, values, color) in enumerate(series):
        points = " ".join(f"{x_at(i)},{top + plot_h * (1 - v / maximum)}"
                          for i, v in enumerate(values))
        svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{points}"/>')
        for i, value in enumerate(values):
            y = top + plot_h * (1 - value / maximum)
            svg.append(f'<circle cx="{x_at(i)}" cy="{y}" r="4" fill="{color}"/>')
        legend_x = left + si * 225
        svg.append(f'<rect x="{legend_x}" y="401" width="18" height="4" fill="{color}"/>')
        svg.append(f'<text x="{legend_x + 25}" y="408" font-size="13">{html.escape(name)}</text>')
    svg.append('</g></svg>')
    path.write_text("\n".join(svg), encoding="utf-8")


def make_charts(output: Path, rows: list[dict]) -> None:
    colors = ("#0d9488", "#64748b", "#e76f51")
    for family, filename, title in (
        ("c_sweep", "01_c_rates.svg", "MCTS: ty le thang / hoa / thua theo c"),
        ("iteration_sweep", "02_iteration_rates.svg", "MCTS: ket qua theo so iteration"),
    ):
        selected = [row for row in rows if row["family"] == family]
        labels = [str(row["c"] if family == "c_sweep" else row["iterations"])
                  for row in selected]
        series = [(name, [row[key] * 100 for row in selected], color)
                  for name, key, color in zip(("Thang", "Hoa", "Thua"),
                                             ("win_rate", "draw_rate", "loss_rate"), colors)]
        _svg_plot(output / filename, title, labels, series, "Ty le (%)", 100)
    selected = [row for row in rows if row["family"] == "iteration_sweep"]
    _svg_plot(output / "03_iteration_time.svg", "MCTS: thoi gian theo so iteration",
              [str(row["iterations"]) for row in selected],
              [("Trung binh / nuoc", [row["mean_move_ms"] for row in selected], "#6366f1")],
              "Thoi gian (ms / nuoc)")


def write_dashboard(output: Path, metadata: dict, rows: list[dict], benchmark: list[dict]) -> None:
    smoke = metadata["smoke"]
    table_rows = "\n".join(
        f"<tr><td>{html.escape(row['family'])}</td><td>{html.escape(row['configuration'])}</td>"
        f"<td>{row['opponent']}</td><td>{row['wins']}-{row['draws']}-{row['losses']}</td>"
        f"<td>{100 * row['win_rate']:.1f}%</td><td>{row['mean_move_ms']:.3f}</td></tr>"
        for row in rows)
    bench_rows = "\n".join(
        f"<tr><td>{row['position']}</td><td>{row['move']}</td>"
        f"<td>{row['minimax_nodes']}</td><td>{row['alphabeta_nodes']}</td>"
        f"<td>{row['node_reduction']:.1%}</td></tr>" for row in benchmark)
    message = ("SMOKE TEST: số ván nhỏ, không đạt yêu cầu thực nghiệm của đề."
               if smoke else "Mỗi cấu hình có ít nhất 20 ván, ghép cặp đổi bên X/O.")
    document = f'''<!doctype html><html lang="vi"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Caro AI | Kết quả thực nghiệm</title>
<style>body{{font:15px/1.6 system-ui,sans-serif;color:#172033;background:#f1f5f9;margin:0}}
main{{max-width:1050px;margin:32px auto;padding:28px;background:white;border-radius:16px}}
h1{{line-height:1.2}}h2{{margin-top:32px}}table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{padding:9px;border-bottom:1px solid #dbe2ea;text-align:left}}th{{background:#edf2f7}}
img{{display:block;width:100%;margin:18px 0}}code{{background:#edf2f7;padding:2px 5px}}
.notice{{padding:14px;background:#ecfdf5;border-left:4px solid #0d9488}}a{{color:#0f766e}}
</style><main><p>CARO 9×9 / AI LAB</p><h1>Kết quả thực nghiệm</h1>
<p class="notice">{message} Đây là dữ liệu chạy thật trên máy được ghi bên dưới.</p>
<p>Seed: <b>{metadata['seed']}</b> · Python {html.escape(metadata['python'])}<br>
CPU: {html.escape(metadata['cpu_model'])}<br>Hệ điều hành: {html.escape(metadata['platform'])}</p>
<p>Không đặt thời hạn theo giây. MCTS dùng đúng số iteration; MiniMax tìm đến độ sâu đã chọn.
Thời gian là trung bình theo tất cả nước đi của tác nhân khảo sát, chỉ đo hàm chọn nước đi.</p>
<h2>Đối sánh và khảo sát tham số</h2><table><thead><tr><th>Nhóm</th><th>Cấu hình</th>
<th>Đối thủ</th><th>Thắng-Hòa-Thua</th><th>Tỷ lệ thắng</th><th>ms / nước</th></tr></thead>
<tbody>{table_rows}</tbody></table>
<img src="01_c_rates.svg" alt="Tỷ lệ thắng hòa thua theo c">
<img src="02_iteration_rates.svg" alt="Tỷ lệ thắng hòa thua theo iteration">
<img src="03_iteration_time.svg" alt="Thời gian xử lý theo iteration">
<h2>Hiệu quả cắt tỉa Alpha-Beta</h2><p>Hai thuật toán dùng cùng hàm đánh giá, độ sâu,
thứ tự và tập ứng viên; kiểm tra cùng nước đi và giá trị trước khi xuất bảng.</p>
<table><tr><th>Thế cờ</th><th>Nước chọn</th><th>Nút MiniMax</th><th>Nút Alpha-Beta</th>
<th>Giảm số nút</th></tr>{bench_rows}</table>
<h2>Cách đọc kết quả</h2><p>20 ván/cấu hình là mức tối thiểu, còn nhiều biến động thống kê.
Không kết luận MCTS luôn thắng hoặc tăng c/iteration luôn làm tăng tỷ lệ thắng.
MCTS cơ sở rollout ngẫu nhiên đến hết ván, có thể bỏ lỡ đe dọa chiến thuật với ngân sách nhỏ.
MiniMax giới hạn K ứng viên nên không bảo đảm tối ưu trên toàn bộ cây hợp lệ.</p>
<p>Không so trực tiếp “nút” của hai họ thuật toán: Alpha-Beta đếm trạng thái gọi đệ quy;
MCTS đếm nút cây được tạo, tách khỏi số bước rollout.</p>
<p><a href="summary.csv">Bảng tổng hợp CSV</a> · <a href="games.csv">Từng ván CSV</a> ·
<a href="games.jsonl">Nhật ký từng nước</a> · <a href="metadata.json">Cấu hình máy và tham số</a></p>
</main></html>'''
    (output / "index.html").write_text(document, encoding="utf-8")


def run_suite(output: Path, games: int = 20, seed: int = 2026, depth: int = 2,
              candidates: int = 10, iterations: int = 300, c: float = 1.4,
              opponent_name: str = "random", smoke: bool = False,
              include_heuristic: bool = False) -> list[dict]:
    if games < 2 or games % 2 or (games < 20 and not smoke):
        raise ValueError("Cần số ván chẵn >= 20; chỉ dùng --smoke để kiểm tra nhanh >= 2 ván.")
    if opponent_name not in ("random", "alphabeta"):
        raise ValueError("Đối thủ khảo sát phải là random hoặc alphabeta.")
    random_cfg = AgentConfig("random")
    ab = AgentConfig("alphabeta", depth=depth, candidates=candidates)
    mcts = AgentConfig("mcts", iterations=iterations, c=c)
    opponent = random_cfg if opponent_name == "random" else ab
    jobs = [("round_robin", "alphabeta_vs_random", ab, random_cfg),
            ("round_robin", "mcts_vs_random", mcts, random_cfg),
            ("round_robin", "mcts_vs_alphabeta", mcts, ab)]
    for value in (0.5, 1.0, 1.4, 2.0):
        jobs.append(("c_sweep", f"c={value}",
                     AgentConfig("mcts", iterations=iterations, c=value), opponent))
    for value in (100, 300, 500):
        jobs.append(("iteration_sweep", f"iterations={value}",
                     AgentConfig("mcts", iterations=value, c=c), opponent))
    if include_heuristic:
        # Same opponent and budgets as base MCTS; distinct family in the output.
        for policy in ("random", "tactical"):
            jobs.append(("rollout_sweep", f"rollout={policy}",
                         AgentConfig("mcts", iterations=iterations, c=c, rollout=policy), opponent))
    if (output / "metadata.json").exists():
        raise FileExistsError("Thư mục đã có kết quả. Chọn --output mới để giữ dữ liệu cũ.")
    output.mkdir(parents=True, exist_ok=True)
    metadata = {"format": "caro-ai-experiments-v1", "started_utc": datetime.now(timezone.utc).isoformat(),
                "complete": False, "smoke": smoke, "required_games_met": games >= 20,
                "games_per_config": games, "pairs_per_config": games // 2,
                "seed": seed, "python": platform.python_version(),
                "platform": platform.platform(), "cpu_model": _cpu_model(),
                "logical_cpus": os.cpu_count(), "time_limit_seconds": None,
                "timing": "perf_counter inside choose; move-weighted mean; sequential games",
                "seed_rule": "pair p (zero based): subject=seed+10000*p+11, opponent=seed+10000*p+29; reuse on swapped leg",
                "opening": "empty board; X first; no random opening",
                "win_rule": "at least five, including blocked ends and overlines",
                "reward": "win=1, draw=0.5, loss=0; per node player_just_moved",
                "mcts_moves": "all legal moves; random expansion; final maximum visits",
                "sweep_opponent": asdict(opponent),
                "jobs": [{"family": f, "name": n, "subject": asdict(a), "opponent": asdict(b)}
                         for f, n, a, b in jobs]}
    metadata_path = output / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    rows, game_rows = [], []
    start = perf_counter()
    with (output / "games.jsonl").open("w", encoding="utf-8") as evidence:
        for family, name, subject, opp in jobs:
            print(f"\n[{family}] {name} vs {opp.algorithm}", flush=True)
            rows.append(paired_match(subject, opp, games, seed, family, name, evidence, game_rows))
            _write_csv(output / "summary.csv", rows)
            _write_csv(output / "games.csv", game_rows)
    benchmark = benchmark_pruning(max(3, depth), candidates)
    _write_csv(output / "pruning.csv", benchmark)
    make_charts(output, rows)
    metadata.update({"complete": True, "finished_utc": datetime.now(timezone.utc).isoformat(),
                     "total_games": len(game_rows), "total_seconds": perf_counter() - start,
                     "pruning_benchmark_depth": max(3, depth)})
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    write_dashboard(output, metadata, rows, benchmark)
    print(f"\nHoàn tất {len(game_rows)} ván. Mở {output / 'index.html'}", flush=True)
    return rows
