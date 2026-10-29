"""Inspectable, independent implementations of MiniMax/Alpha-Beta and MCTS."""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field
from threading import Event
from time import perf_counter

from .board import (BITS, Board, X, candidate_moves, coordinate, evaluate,
                    has_five)

ALGORITHMS = ("human", "random", "alphabeta", "minimax", "mcts")


class SearchCancelled(Exception):
    """A GUI reset/close may cancel a search between iterations or nodes."""


@dataclass(frozen=True, slots=True)
class AgentConfig:
    algorithm: str = "alphabeta"
    depth: int = 2
    candidates: int = 10
    iterations: int = 300
    c: float = 1.4
    rollout: str = "random"

    def __post_init__(self) -> None:
        if self.algorithm not in ALGORITHMS:
            raise ValueError(f"Thuật toán phải thuộc {ALGORITHMS}.")
        if not isinstance(self.depth, int) or not 1 <= self.depth <= 8:
            raise ValueError("Độ sâu phải là số nguyên từ 1 đến 8.")
        if not isinstance(self.candidates, int) or not 1 <= self.candidates <= 81:
            raise ValueError("Số ứng viên phải là số nguyên từ 1 đến 81.")
        if not isinstance(self.iterations, int) or self.iterations < 1:
            raise ValueError("Iteration phải là số nguyên >= 1.")
        if not math.isfinite(self.c) or self.c <= 0:
            raise ValueError("Hệ số c phải là số hữu hạn > 0.")
        if self.rollout not in ("random", "tactical"):
            raise ValueError("Rollout phải là random hoặc tactical.")


@dataclass(slots=True)
class SearchResult:
    move: int
    algorithm: str
    elapsed_ms: float
    nodes: int
    depth: int = 0
    cutoffs: int = 0
    iterations: int = 0
    score: float = 0.0
    max_tree_depth: int = 0
    rollout_moves: int = 0
    root_children: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = asdict(self)
        result["coordinate"] = coordinate(self.move)
        return result


def _check_cancel(cancel: Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise SearchCancelled()


class MinimaxAgent:
    def __init__(self, config: AgentConfig, pruning: bool = True):
        self.config = config
        self.pruning = pruning

    def choose(self, board: Board, cancel: Event | None = None) -> SearchResult:
        if board.terminal:
            raise ValueError("Không thể tìm nước đi sau khi kết thúc ván.")
        start = perf_counter()
        root_player = board.turn
        nodes, cutoffs = 1, 0  # Root is also a visited node.

        def visit(state: Board, remaining: int, alpha: float, beta: float) -> float:
            nonlocal nodes, cutoffs
            _check_cancel(cancel)
            nodes += 1
            if remaining == 0 or state.terminal:
                return evaluate(state, root_player)
            maximizing = state.turn == root_player
            value = -math.inf if maximizing else math.inf
            for move in candidate_moves(state, self.config.candidates):
                child_value = visit(state.play(move), remaining - 1, alpha, beta)
                if maximizing:
                    value = max(value, child_value)
                    alpha = max(alpha, value)
                else:
                    value = min(value, child_value)
                    beta = min(beta, value)
                if self.pruning and alpha >= beta:
                    cutoffs += 1
                    break
            return value

        best_move, best_value = -1, -math.inf
        alpha = -math.inf
        for move in candidate_moves(board, self.config.candidates):
            value = visit(board.play(move), self.config.depth - 1, alpha, math.inf)
            if value > best_value:
                best_move, best_value = move, value
            if self.pruning:
                alpha = max(alpha, best_value)
        return SearchResult(best_move, "alphabeta" if self.pruning else "minimax",
                            (perf_counter() - start) * 1000, nodes,
                            depth=self.config.depth, cutoffs=cutoffs,
                            score=best_value)


@dataclass(slots=True)
class MCTSNode:
    board: Board
    parent: MCTSNode | None = None
    move: int | None = None
    visits: int = 0
    wins: float = 0.0
    children: list[MCTSNode] = field(default_factory=list)
    untried: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.untried = self.board.legal_moves()

    @property
    def player_just_moved(self) -> int:
        return -self.board.turn


def uct_value(child: MCTSNode, parent_visits: int, c: float) -> float:
    if child.visits == 0:
        return math.inf  # Explicit priority, never divide by zero.
    return child.wins / child.visits + c * math.sqrt(
        math.log(max(1, parent_visits)) / child.visits)


def backpropagate(node: MCTSNode, winner: int) -> None:
    """Each node stores rewards for its player_just_moved, not the root side.

    Thus a parent's UCT choice maximizes that parent's player-to-move reward.
    Opponents optimize their own outcomes. Draw=0.5; win=1; loss=0.
    """
    while node is not None:
        node.visits += 1
        node.wins += (0.5 if winner == 0 else
                      1.0 if winner == node.player_just_moved else 0.0)
        node = node.parent


def rollout(board: Board, rng: random.Random, policy: str = "random") -> tuple[int, int]:
    if board.terminal:
        return board.winner, 0
    xb, ob, turn = board.x_bits, board.o_bits, board.turn
    moves = board.legal_moves()
    steps = 0
    while moves:
        index = rng.randrange(len(moves))
        if policy == "tactical":
            own, enemy = (xb, ob) if turn == X else (ob, xb)
            winning = [i for i, m in enumerate(moves) if has_five(own | BITS[m])]
            blocking = ([] if winning else
                        [i for i, m in enumerate(moves) if has_five(enemy | BITS[m])])
            if winning or blocking:
                index = rng.choice(winning or blocking)
        move = moves[index]
        moves[index] = moves[-1]
        moves.pop()
        steps += 1
        if turn == X:
            xb |= BITS[move]
            won = has_five(xb)
        else:
            ob |= BITS[move]
            won = has_five(ob)
        if won:
            return turn, steps
        turn = -turn
    return 0, steps


class MCTSAgent:
    def __init__(self, config: AgentConfig, seed: int = 2026):
        self.config = config
        self.rng = random.Random(seed)

    def choose(self, board: Board, cancel: Event | None = None) -> SearchResult:
        if board.terminal:
            raise ValueError("Không thể tìm nước đi sau khi kết thúc ván.")
        start = perf_counter()
        root = MCTSNode(board)
        nodes, max_depth, rollout_steps = 1, 0, 0
        for _ in range(self.config.iterations):
            _check_cancel(cancel)
            node, depth = root, 0
            # 1. Selection: all children belong to the player moving at node.
            while not node.board.terminal and not node.untried:
                node = max(node.children, key=lambda child: uct_value(
                    child, node.visits, self.config.c))
                depth += 1
            # 2. Expansion: uniform untried LEGAL move; no candidate restriction.
            if not node.board.terminal and node.untried:
                index = self.rng.randrange(len(node.untried))
                move = node.untried[index]
                node.untried[index] = node.untried[-1]
                node.untried.pop()
                child = MCTSNode(node.board.play(move), node, move)
                node.children.append(child)
                node = child
                nodes += 1
                depth += 1
            max_depth = max(max_depth, depth)
            # 3. Simulation: play until an actual win/draw; no depth truncation.
            winner, steps = rollout(node.board, self.rng, self.config.rollout)
            rollout_steps += steps
            # 4. Backpropagation with alternating player perspectives.
            backpropagate(node, winner)
        # Robust child: most visits first; mean reward breaks visit ties only.
        best = max(root.children, key=lambda child: (
            child.visits, child.wins / child.visits))
        children = [{"move": child.move, "coordinate": coordinate(child.move),
                     "visits": child.visits, "reward_sum": child.wins,
                     "mean_reward": child.wins / child.visits}
                    for child in sorted(root.children,
                                        key=lambda ch: (-ch.visits, ch.move))]
        return SearchResult(best.move, "mcts", (perf_counter() - start) * 1000,
                            nodes, iterations=self.config.iterations,
                            score=best.wins / best.visits,
                            max_tree_depth=max_depth, rollout_moves=rollout_steps,
                            root_children=children)


class RandomAgent:
    def __init__(self, seed: int = 2026):
        self.rng = random.Random(seed)

    def choose(self, board: Board, cancel: Event | None = None) -> SearchResult:
        _check_cancel(cancel)
        if board.terminal:
            raise ValueError("Không thể tìm nước đi sau khi kết thúc ván.")
        start = perf_counter()
        move = self.rng.choice(board.legal_moves())
        return SearchResult(move, "random", (perf_counter() - start) * 1000, 1)


def make_agent(config: AgentConfig, seed: int = 2026):
    if config.algorithm in ("alphabeta", "minimax"):
        return MinimaxAgent(config, pruning=config.algorithm == "alphabeta")
    if config.algorithm == "mcts":
        return MCTSAgent(config, seed)
    if config.algorithm == "random":
        return RandomAgent(seed)
    raise ValueError("Người chơi tự nhập/click nước đi, không gọi AI.")
