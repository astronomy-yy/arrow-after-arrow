"""路径检测 Board.can_fly 的单元测试。

覆盖：
- 四个方向无阻挡可飞出
- 贴边朝外箭头可飞出（边界不越界）
- 四个方向有阻挡不可飞出
- 紧邻阻挡、身后箭头不影响、空格处理
- 三个内置关卡按给定通关顺序全程可飞（关卡可通关回归测试）
"""

import pytest

from game.board import Board
from game.level import LEVELS


def make_board(grid, mistakes=3):
    """用二维网格快速构造一个棋盘。"""
    return Board({"mistakes": mistakes, "grid": grid})


# ---------- 无阻挡：四个方向 ----------

def test_fly_up():
    b = make_board([
        [".", ".", "."],
        [".", ".", "."],
        [".", "U", "."],
    ])
    assert b.can_fly(2, 1) is True


def test_fly_down():
    b = make_board([
        [".", "D", "."],
        [".", ".", "."],
        [".", ".", "."],
    ])
    assert b.can_fly(0, 1) is True


def test_fly_left():
    b = make_board([
        [".", ".", "."],
        [".", ".", "L"],
        [".", ".", "."],
    ])
    assert b.can_fly(1, 2) is True


def test_fly_right():
    b = make_board([
        [".", ".", "."],
        ["R", ".", "."],
        [".", ".", "."],
    ])
    assert b.can_fly(1, 0) is True


# ---------- 边界：贴边朝外的箭头一步出界 ----------

EDGE_CASES = [
    (0, 1, "U"),
    (2, 1, "D"),
    (1, 0, "L"),
    (1, 2, "R"),
]


@pytest.mark.parametrize("r,c,ch", EDGE_CASES)
def test_edge_arrow_flies_out(r, c, ch):
    grid = [["."] * 3 for _ in range(3)]
    grid[r][c] = ch
    b = make_board(grid)
    assert b.can_fly(r, c) is True


# ---------- 有阻挡：四个方向 ----------

BLOCKED_CASES = [
    # 被挡箭头 (r, c) 与字符，阻挡箭头位置 (br, bc)
    (2, 1, "U", 0, 1),
    (0, 1, "D", 2, 1),
    (1, 2, "L", 1, 0),
    (1, 0, "R", 1, 2),
]


@pytest.mark.parametrize("r,c,ch,br,bc", BLOCKED_CASES)
def test_blocked_four_directions(r, c, ch, br, bc):
    grid = [["."] * 3 for _ in range(3)]
    grid[r][c] = ch
    grid[br][bc] = "U"  # 阻挡箭头的方向无所谓，只要非空
    b = make_board(grid)
    assert b.can_fly(r, c) is False


# ---------- 紧邻阻挡 / 身后不影响 / 空格 ----------

def test_adjacent_arrow_blocks():
    b = make_board([["R", "R", "."]])
    assert b.can_fly(0, 0) is False   # 右边紧邻箭头，被挡
    assert b.can_fly(0, 1) is True    # 前方畅通；身后 (0,0) 不影响


def test_empty_cell_returns_false():
    b = make_board([["."]])
    assert b.can_fly(0, 0) is False


# ---------- 三个内置关卡：给定通关顺序必须全程可飞 ----------

SOLUTIONS = [
    [(3, 0), (4, 4), (2, 2), (0, 0)],
    [(2, 5), (4, 3), (5, 2), (3, 3), (1, 3), (0, 4), (0, 5)],
    [(1, 2), (4, 5), (1, 4), (2, 5), (3, 0), (5, 1), (5, 0),
     (0, 2), (0, 1), (0, 0)],
]


@pytest.mark.parametrize("level_index", [0, 1, 2])
def test_level_solution(level_index):
    board = Board(LEVELS[level_index])
    for step, (r, c) in enumerate(SOLUTIONS[level_index], 1):
        assert board.can_fly(r, c) is True, (
            f"第{level_index + 1}关第{step}步 {(r, c)} 应能飞出"
        )
        board.remove_arrow(r, c)
    assert board.remaining == 0
