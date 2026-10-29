"""Correctness checks for rules, adversarial perspectives, pruning and logs."""
import math
import random
import tempfile
import threading
import unittest
from pathlib import Path

from caro_ai.agents import (AgentConfig, MCTSNode, SearchCancelled,
                            backpropagate, make_agent, rollout, uct_value)
from caro_ai.board import (BITS, Board, DIRECTIONS, X, candidate_moves,
                           coordinate, evaluate, has_five, parse_coordinate)
from caro_ai.experiments import BENCHMARK_POSITIONS, run_suite
from caro_ai.records import add_move, load_record, new_record, save_record


def reference_winner(cells):
    for r in range(9):
        for c in range(9):
            player = cells[r * 9 + c]
            if not player:
                continue
            for dr, dc in DIRECTIONS:
                rr, cc = r + 4 * dr, c + 4 * dc
                if 0 <= rr < 9 and 0 <= cc < 9:
                    if all(cells[(r + k * dr) * 9 + c + k * dc] == player for k in range(5)):
                        return player
    return 0


class RulesTests(unittest.TestCase):
    def test_empty_and_coordinates(self):
        self.assertEqual(Board().legal_moves(), list(range(81)))
        self.assertEqual(Board().turn, X)
        self.assertIsNone(Board().outcome)
        for m in range(81):
            self.assertEqual(parse_coordinate(coordinate(m)), m)
        for text in ("A0", "A10", "J1", "1A", "", "E5junk"):
            with self.assertRaises(ValueError):
                parse_coordinate(text)

    def test_invalid_moves_and_immutability(self):
        board = Board()
        after = board.play(40)
        self.assertEqual(board.ply, 0)
        self.assertEqual(after.turn, -X)
        for bad in (40, -1, 81, "E5"):
            with self.assertRaises(ValueError):
                after.play(bad)

    def test_all_win_directions(self):
        for moves in (
            ["A1", "I9", "B1", "I8", "C1", "I7", "D1", "H9", "E1"],
            ["A1", "I9", "A2", "I8", "A3", "I7", "A4", "H9", "A5"],
            ["A1", "I9", "B2", "I8", "C3", "I7", "D4", "H9", "E5"],
            ["E1", "I9", "D2", "I8", "C3", "I7", "B4", "H9", "A5"],
        ):
            board = Board.from_moves(moves)
            self.assertEqual(board.winner, X)
            self.assertEqual(len(board.winning_line()), 5)
            self.assertTrue(board.terminal)
            self.assertEqual(board.legal_moves(), [])
            with self.assertRaises(ValueError):
                board.play(70)

    def test_o_can_win(self):
        board = Board.from_moves("I9 A1 I8 B1 H9 C1 H8 D1 G9 E1".split())
        self.assertEqual(board.outcome, -X)

    def test_blocked_ends_and_six_are_wins(self):
        # Leave a gap until the final move: there was no earlier terminal state.
        board = Board.from_moves("B5 A5 C5 H5 E5 I1 F5 I2 G5 I3 D5".split())
        self.assertEqual(board.winner, X)
        self.assertEqual(len(board.winning_line()), 6)

    def test_no_row_or_diagonal_wraparound(self):
        for moves in ([7, 8, 9, 10, 11], [0, 8, 16, 24, 32]):
            self.assertFalse(has_five(sum(BITS[m] for m in moves)))

    def test_full_board_draw(self):
        xs, os = [], []
        for r in range(9):
            for c in range(9):
                (xs if (r + 2 * c) % 4 < 2 else os).append(r * 9 + c)
        moves = [m for pair in zip(xs, os) for m in pair] + [xs[-1]]
        board = Board.from_moves(moves)
        self.assertEqual(board.ply, 81)
        self.assertEqual(board.outcome, 0)
        self.assertEqual(evaluate(board, X), 0)

    def test_bitboards_against_independent_reference(self):
        rng = random.Random(2026)
        for _ in range(100):
            board = Board()
            cells = [0] * 81
            while not board.terminal:
                move = rng.choice(board.legal_moves())
                cells[move] = board.turn
                board = board.play(move)
                self.assertEqual(board.winner, reference_winner(cells))
                self.assertEqual(board.ply, sum(c != 0 for c in cells))


class MinimaxTests(unittest.TestCase):
    def test_pruning_equivalence_on_positions_and_random_boards(self):
        rng = random.Random(77)
        boards = [Board.from_moves(moves) for moves in BENCHMARK_POSITIONS.values()]
        for _ in range(8):
            board = Board()
            for _ in range(10):
                board = board.play(rng.choice(board.legal_moves()))
            boards.append(board)
        for depth in (2, 3):
            for board in boards:
                plain = make_agent(AgentConfig("minimax", depth, 6)).choose(board)
                ab = make_agent(AgentConfig("alphabeta", depth, 6)).choose(board)
                self.assertEqual((plain.move, plain.score), (ab.move, ab.score))
                self.assertLessEqual(ab.nodes, plain.nodes)

    def test_immediate_win_and_block(self):
        win = Board.from_moves("B5 A5 C5 I1 D5 H1 E5 G2".split())
        block = Board.from_moves("I9 B5 A5 C5 I8 D5 H9 E5".split())
        for algorithm in ("minimax", "alphabeta"):
            agent = make_agent(AgentConfig(algorithm, 2, 8))
            self.assertEqual(coordinate(agent.choose(win).move), "F5")
            self.assertEqual(coordinate(agent.choose(block).move), "F5")

    def test_tactical_moves_survive_candidate_cap(self):
        board = Board.from_moves("B5 I1 C5 I2 D5 H1 E5 H2".split())
        candidates = candidate_moves(board, 1)
        self.assertIn(parse_coordinate("A5"), candidates)
        self.assertIn(parse_coordinate("F5"), candidates)
        self.assertGreater(len(candidates), 1)

    def test_evaluation_perspective(self):
        board = Board.from_moves("E5 D5 E4".split())
        self.assertEqual(evaluate(board, X), -evaluate(board, -X))


class MCTSTests(unittest.TestCase):
    def test_uct_zero_visits_and_formula(self):
        child = MCTSNode(Board().play(40))
        self.assertTrue(math.isinf(uct_value(child, 0, 1.4)))
        child.visits, child.wins = 4, 3
        self.assertAlmostEqual(uct_value(child, 10, 1.4), .75 + 1.4 * math.sqrt(math.log(10) / 4))

    def test_reward_alternates_with_player_just_moved(self):
        root = MCTSNode(Board())  # previous mover O
        child = MCTSNode(root.board.play(40), root, 40)  # previous mover X
        grandchild = MCTSNode(child.board.play(39), child, 39)  # previous mover O
        backpropagate(grandchild, X)
        self.assertEqual((root.wins, child.wins, grandchild.wins), (0, 1, 0))
        backpropagate(grandchild, 0)
        self.assertEqual((root.wins, child.wins, grandchild.wins), (.5, 1.5, .5))
        self.assertEqual((root.visits, child.visits, grandchild.visits), (2, 2, 2))

    def test_budget_seed_robust_child_and_legal_move(self):
        board = Board.from_moves("E5 D5 E4 D4".split())
        cfg = AgentConfig("mcts", iterations=150)
        a = make_agent(cfg, 99).choose(board)
        b = make_agent(cfg, 99).choose(board)
        self.assertEqual(a.root_children, b.root_children)
        self.assertEqual(a.move, b.move)
        self.assertIn(a.move, board.legal_moves())
        self.assertEqual(sum(ch["visits"] for ch in a.root_children), cfg.iterations)
        chosen = next(ch for ch in a.root_children if ch["move"] == a.move)
        self.assertEqual(chosen["visits"], max(ch["visits"] for ch in a.root_children))
        self.assertLessEqual(a.nodes, cfg.iterations + 1)
        for child in a.root_children:
            self.assertTrue(0 <= child["reward_sum"] <= child["visits"])

    def test_random_rollout_and_tactical_immediate_win(self):
        board = Board.from_moves("B5 A5 C5 I1 D5 H1 E5 G2".split())
        winner, count = rollout(board, random.Random(1), "tactical")
        self.assertEqual((winner, count), (X, 1))
        terminal = board.play(parse_coordinate("F5"))
        self.assertEqual(rollout(terminal, random.Random(1)), (X, 0))
        for seed in range(5):
            winner, count = rollout(Board(), random.Random(seed))
            self.assertIn(winner, (-X, 0, X))
            self.assertTrue(9 <= count <= 81)

    def test_random_is_seeded_and_all_algorithms_reject_terminal(self):
        a, b = make_agent(AgentConfig("random"), 123), make_agent(AgentConfig("random"), 123)
        self.assertEqual(a.choose(Board()).move, b.choose(Board()).move)
        terminal = Board.from_moves("A1 I9 B1 I8 C1 I7 D1 H9 E1".split())
        for kind in ("random", "minimax", "alphabeta", "mcts"):
            with self.assertRaises(ValueError):
                make_agent(AgentConfig(kind)).choose(terminal)

    def test_cancel_and_parameter_validation(self):
        cancel = threading.Event()
        cancel.set()
        for kind in ("random", "minimax", "alphabeta", "mcts"):
            with self.assertRaises(SearchCancelled):
                make_agent(AgentConfig(kind)).choose(Board(), cancel)
        for kwargs in ({"depth": 0}, {"iterations": 0}, {"c": 0},
                       {"c": float("nan")}, {"candidates": 0}, {"algorithm": "oops"}):
            with self.assertRaises(ValueError):
                AgentConfig(**kwargs)


class LoggingTests(unittest.TestCase):
    def test_save_load_and_reject_illegal_replay(self):
        cfg = AgentConfig("random")
        record = new_record(cfg, cfg, 123)
        board = Board()
        for move in (40, 39, 31):
            board = add_move(record, board, move)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game.json"
            save_record(record, path)
            loaded, restored = load_record(path)
            self.assertEqual(restored, board)
            self.assertEqual(len(loaded["moves"]), 3)
            record["moves"][1]["move"] = 40
            save_record(record, path)
            with self.assertRaises(ValueError):
                load_record(path)

    def test_experiment_minimum_games_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            for count in (0, 1, 2, 19, 21):
                with self.assertRaises(ValueError):
                    run_suite(Path(directory), games=count)


if __name__ == "__main__":
    unittest.main()
