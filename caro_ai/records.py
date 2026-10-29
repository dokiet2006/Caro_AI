"""Portable JSON game logs; loading replays every move through the same rules."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .agents import AgentConfig, SearchResult
from .board import Board, coordinate, symbol

FORMAT = "caro-ai-game-v1"


def new_record(x_config: AgentConfig, o_config: AgentConfig, seed: int) -> dict:
    return {"format": FORMAT, "created_utc": datetime.now(timezone.utc).isoformat(),
            "seed": seed, "board_size": 9, "win_length": 5,
            "configs": {"X": asdict(x_config), "O": asdict(o_config)},
            "moves": [], "outcome": None}


def add_move(record: dict, before: Board, move: int,
             result: SearchResult | None = None, detailed: bool = True) -> Board:
    after = before.play(move)
    metrics = result.to_dict() if result else {
        "move": move, "coordinate": coordinate(move), "algorithm": "human",
        "elapsed_ms": 0.0, "nodes": 0, "depth": 0, "iterations": 0, "cutoffs": 0}
    if not detailed:
        metrics.pop("root_children", None)
    record["moves"].append({"ply": after.ply, "player": symbol(before.turn), **metrics})
    record["outcome"] = after.outcome
    return after


def save_record(record: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_record(path: str | Path) -> tuple[dict, Board]:
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("format") != FORMAT:
        raise ValueError("Định dạng nhật ký không được hỗ trợ.")
    if record.get("board_size") != 9 or record.get("win_length") != 5:
        raise ValueError("Nhật ký không phải Caro 9x9, thắng từ 5 quân.")
    for player in ("X", "O"):
        AgentConfig(**record["configs"][player])
    state = Board()
    for index, item in enumerate(record["moves"], start=1):
        if item.get("ply") != index or item.get("player") != symbol(state.turn):
            raise ValueError("Sai số lượt hoặc sai thứ tự X/O trong nhật ký.")
        state = state.play(item["move"])
    if record.get("outcome") != state.outcome:
        raise ValueError("Kết quả ghi trong nhật ký không khớp bàn cờ.")
    return record, state
