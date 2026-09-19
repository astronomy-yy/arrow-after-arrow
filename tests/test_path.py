"""线段箭路径检测 Board.can_fly 的单元测试。

覆盖：四方向无阻挡、贴边出界、四方向被挡、线段身体阻挡、
空格处理、删除后阻挡解除与重置、三个生成关卡的通关顺序回归。
"""

import pytest

from game.board import Board
from game.level import LEVELS


def make_board(arrows, rows=5, cols=5, mistakes=3):
    return Board({"mistakes": mistakes, "rows": rows, "cols": cols,
                  "arrows": arrows})


def seg(cells, direction, color=0):
    return {"cells": cells, "dir": direction, "color": color}


# ---------- 四方向无阻挡 ----------

def test_four_directions_clear():
    b = make_board([
        seg([(4, 2)], "U", 1),
        seg([(0, 1)], "D", 2),
        seg([(1, 4)], "L", 3),
        seg([(3, 0)], "R", 4),
    ])
    assert b.can_fly(4, 2) is True
    assert b.can_fly(0, 1) is True
    assert b.can_fly(1, 4) is True
    assert b.can_fly(3, 0) is True


# ---------- 贴边朝外，一步出界 ----------

EDGE_CASES = [(0, 0, "U"), (4, 4, "D"), (0, 4, "L"), (4, 0, "R")]


@pytest.mark.parametrize("r,c,d", EDGE_CASES)
def test_edge_flies_out(r, c, d):
    b = make_board([seg([(r, c)], d)], rows=5, cols=5)
    assert b.can_fly(r, c) is True


# ---------- 四方向被挡 ----------

BLOCKED_CASES = [
    ((2, 1), "U", (0, 1), "U"),
    ((0, 1), "D", (2, 1), "D"),
    ((1, 2), "L", (1, 0), "L"),
    ((1, 0), "R", (1, 2), "R"),
]


@pytest.mark.parametrize("head,d,block,block_dir", BLOCKED_CASES)
def test_blocked_four_directions(head, d, block, block_dir):
    b = make_board([
        seg([head], d, 0),
        seg([block], block_dir, 1),
    ], rows=3, cols=3)
    assert b.can_fly(*head) is False   # 被挡
    assert b.can_fly(*block) is True   # 阻挡者贴边朝外，自己能飞


# ---------- 线段的“身体”也会形成阻挡 ----------

def test_segment_body_blocks():
    b = make_board([
        seg([(2, 0)], "R", 0),                    # 横箭，头朝右
        seg([(2, 3), (1, 3), (0, 3)], "U", 1),    # 竖线，身体经过 (2,3)
    ])
    assert b.can_fly(2, 0) is False   # 被竖线身体挡住
    assert b.can_fly(0, 3) is True    # 竖线箭头端朝上，直接出界


# ---------- 空格 ----------

def test_empty_cell():
    b = make_board([seg([(0, 0)], "R")], rows=2, cols=2)
    assert b.can_fly(1, 1) is False


# ---------- 删除后阻挡解除、重置恢复 ----------

def test_remove_unblocks_and_reset():
    b = make_board([
        seg([(1, 0)], "R", 0),
        seg([(1, 2)], "R", 1),
    ], rows=3, cols=3)
    assert b.can_fly(1, 0) is False

    blocker = b.arrow_at(1, 2)
    b.remove_arrow(blocker)
    assert b.can_fly(1, 0) is True
    assert b.remaining == 1

    b.reset()
    assert b.remaining == 2
    assert b.mistakes == 3


# ---------- 三个生成关卡：solution 必须全程可飞 ----------

@pytest.mark.parametrize("level_index", [0, 1, 2])
def test_generated_level_solution(level_index):
    level = LEVELS[level_index]
    b = Board(level)
    by_id = {a.id: a for a in b.arrows}
    for step, arrow_id in enumerate(level["solution"], 1):
        arrow = by_id[arrow_id]
        assert b.can_fly_arrow(arrow), (
            f"第{level_index + 1}关第{step}步 箭{arrow_id} 应能飞出"
        )
        b.remove_arrow(arrow)
    assert b.remaining == 0
