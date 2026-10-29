"""Immutable game states. X starts; any line of at least five wins.

The tenth bit in each row is an unused sentinel, preventing wraparound when
checking rows and diagonals with bit operations. Public moves are 0..80.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

SIZE = 9
CELLS = SIZE * SIZE
X, O, EMPTY = 1, -1, 0
BITS = tuple(1 << (r * 10 + c) for r in range(SIZE) for c in range(SIZE))
FULL_MASK = sum(BITS)
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))


def has_five(bits: int) -> bool:
    for shift in (1, 10, 11, 9):
        pair = bits & (bits >> shift)
        if pair & (pair >> (2 * shift)) & (bits >> (4 * shift)):
            return True
    return False


def moves_from_mask(mask: int) -> list[int]:
    result = []
    while mask:
        bit = mask & -mask
        position = bit.bit_length() - 1
        result.append((position // 10) * 9 + position % 10)
        mask ^= bit
    return result


def symbol(player: int) -> str:
    return {X: "X", O: "O", EMPTY: "."}[player]


def coordinate(move: int) -> str:
    """Human coordinates: row 1..9, column A..I, e.g. E5."""
    return f"{chr(65 + move % SIZE)}{move // SIZE + 1}"


def parse_coordinate(value: str) -> int:
    value = value.strip().upper()
    if len(value) != 2 or value[0] not in "ABCDEFGHI" or value[1] not in "123456789":
        raise ValueError("Nhập tọa độ như E5 (cột A-I, hàng 1-9).")
    return (int(value[1]) - 1) * SIZE + ord(value[0]) - 65


def _make_lines() -> tuple[int, ...]:
    lines = []
    for r in range(SIZE):
        for c in range(SIZE):
            for dr, dc in DIRECTIONS:
                er, ec = r + 4 * dr, c + 4 * dc
                if 0 <= er < SIZE and 0 <= ec < SIZE:
                    lines.append(sum(BITS[(r + k * dr) * SIZE + c + k * dc]
                                     for k in range(5)))
    return tuple(lines)


LINES = _make_lines()
CELL_LINES = tuple(tuple(line for line in LINES if line & bit) for bit in BITS)
NEIGHBOR_MASKS = tuple(
    sum(BITS[rr * SIZE + cc]
        for rr in range(max(0, r - 2), min(SIZE, r + 3))
        for cc in range(max(0, c - 2), min(SIZE, c + 3)))
    for r in range(SIZE) for c in range(SIZE)
)


@dataclass(frozen=True, slots=True)
class Board:
    x_bits: int = 0
    o_bits: int = 0
    turn: int = X
    ply: int = 0
    winner: int = EMPTY
    last_move: int | None = None

    @property
    def occupied(self) -> int:
        return self.x_bits | self.o_bits

    @property
    def terminal(self) -> bool:
        return self.winner != EMPTY or self.ply == CELLS

    @property
    def outcome(self) -> int | None:
        """None=ongoing, 0=draw, 1=X wins, -1=O wins."""
        return self.winner if self.terminal else None

    def at(self, move: int) -> int:
        if not isinstance(move, int) or not 0 <= move < CELLS:
            raise ValueError("Ô cờ nằm ngoài bàn 9x9.")
        bit = BITS[move]
        return X if self.x_bits & bit else O if self.o_bits & bit else EMPTY

    def legal_moves(self) -> list[int]:
        return [] if self.terminal else moves_from_mask(FULL_MASK ^ self.occupied)

    def play(self, move: int) -> Board:
        if self.terminal:
            raise ValueError("Ván cờ đã kết thúc.")
        if self.at(move) != EMPTY:
            raise ValueError("Ô này đã có quân. Hãy chọn ô trống.")
        xb, ob = self.x_bits, self.o_bits
        if self.turn == X:
            xb |= BITS[move]
            won = has_five(xb)
        else:
            ob |= BITS[move]
            won = has_five(ob)
        return Board(xb, ob, -self.turn, self.ply + 1,
                     self.turn if won else EMPTY, move)

    def winning_line(self) -> list[int]:
        if not self.winner or self.last_move is None:
            return []
        r, c = divmod(self.last_move, SIZE)
        for dr, dc in DIRECTIONS:
            line = [self.last_move]
            for sign in (-1, 1):
                rr, cc = r + sign * dr, c + sign * dc
                while 0 <= rr < SIZE and 0 <= cc < SIZE:
                    move = rr * SIZE + cc
                    if self.at(move) != self.winner:
                        break
                    line.append(move)
                    rr, cc = rr + sign * dr, cc + sign * dc
            if len(line) >= 5:
                return sorted(line)
        return []

    def text(self) -> str:
        rows = ["    " + "  ".join("ABCDEFGHI")]
        for r in range(SIZE):
            rows.append(f"{r + 1:2}  " + "  ".join(symbol(self.at(r * SIZE + c))
                                                  for c in range(SIZE)))
        return "\n".join(rows)

    @classmethod
    def from_moves(cls, moves: Iterable[int | str]) -> Board:
        state = cls()
        for move in moves:
            state = state.play(parse_coordinate(move) if isinstance(move, str) else move)
        return state


# All evaluation windows are exactly 5 cells; this is a heuristic, not a win rule.
WEIGHTS = (0, 2, 12, 120, 2500, 1_000_000)
WIN_SCORE = 100_000_000


def evaluate(board: Board, perspective: int) -> int:
    if board.winner:
        return (WIN_SCORE - board.ply) * (1 if board.winner == perspective else -1)
    if board.terminal:
        return 0
    score = 0
    for line in LINES:
        nx, no = (board.x_bits & line).bit_count(), (board.o_bits & line).bit_count()
        if no == 0:
            score += WEIGHTS[nx]
        if nx == 0:
            score -= WEIGHTS[no]
    return perspective * score


def move_priority(board: Board, move: int) -> int:
    """Order offense and defense without changing the legal-move rules."""
    mine, theirs = ((board.x_bits, board.o_bits) if board.turn == X
                    else (board.o_bits, board.x_bits))
    score = 0
    for line in CELL_LINES[move]:
        own, enemy = (mine & line).bit_count(), (theirs & line).bit_count()
        if enemy == 0:
            score += 2 * WEIGHTS[own + 1]
        if own == 0:
            score += WEIGHTS[enemy + 1]
    r, c = divmod(move, SIZE)
    return score * 20 - abs(r - 4) - abs(c - 4)


def candidate_moves(board: Board, limit: int = 10) -> list[int]:
    """Near existing stones, keep the best K and ALL immediate wins/blocks.

    Limit is a soft cap: never discard tactical moves because K is small.
    Both plain MiniMax and Alpha-Beta use this identical deterministic policy.
    """
    if limit < 1:
        raise ValueError("Số ứng viên phải >= 1.")
    if board.terminal:
        return []
    if board.ply == 0:
        return [40]
    vicinity = 0
    for move in moves_from_mask(board.occupied):
        vicinity |= NEIGHBOR_MASKS[move]
    moves = moves_from_mask(vicinity & (FULL_MASK ^ board.occupied))
    mine, theirs = ((board.x_bits, board.o_bits) if board.turn == X
                    else (board.o_bits, board.x_bits))
    wins = [m for m in moves if has_five(mine | BITS[m])]
    blocks = [m for m in moves if m not in wins and has_five(theirs | BITS[m])]
    rest = [m for m in moves if m not in wins and m not in blocks]
    rest.sort(key=lambda m: (-move_priority(board, m), m))
    forced = wins + blocks
    return forced + rest[:max(0, limit - len(forced))]
