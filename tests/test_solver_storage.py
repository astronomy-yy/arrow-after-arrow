"""求解器、撤销、存档与主题的单元测试。

覆盖：AI 求解能找到完整通关顺序、无解局面如实返回 None、
apply_solution / next_move / greedy_hint 的行为、撤销栈能回退到上一步、
存档读写与损坏存档兜底、切主题时箭头配色跟着变。
"""

import json
import os

import pytest

from game import generator, theme
from game.board import Board
from game.level import LEVELS
from game.settings import ARROW_PALETTE, ARROW_PALETTE_DAY
from game.solver import apply_solution, greedy_hint, is_solvable, next_move, solve
from game.storage import DEFAULT, Save


def seg(cells, direction, color=0):
    return {"cells": cells, "dir": direction, "color": color}


def make_board(arrows, rows=5, cols=5, mistakes=3):
    return Board({"mistakes": mistakes, "rows": rows, "cols": cols,
                  "arrows": arrows})


# ---------- 求解器 ----------

@pytest.mark.parametrize("level_index", [0, 4, 8])
def test_solver_clears_generated_levels(level_index):
    board = Board(LEVELS[level_index])
    order = solve(board)
    assert order is not None
    assert sorted(order) == sorted(a.id for a in board.arrows)
    assert apply_solution(board, order) is True
    assert board.remaining == 0


def test_solver_reports_unsolvable_board():
    """两支互相封死对方的箭：谁也飞不出去，必然无解。"""
    board = make_board([
        seg([(2, 0)], "R"),          # 头朝右，被 (2, 2) 挡住
        seg([(2, 2)], "L"),          # 头朝左，被 (2, 0) 挡住
    ], rows=3, cols=3)
    assert solve(board) is None
    assert is_solvable(board) is False
    # 提示退化为「随便挑一支能飞的」，这里没有能飞的
    assert next_move(board) is None
    assert greedy_hint(board) is None


def test_next_move_prefers_solvable_step():
    board = Board(LEVELS[0])
    first = next_move(board)
    assert first is not None
    arrow = next(a for a in board.arrows if a.id == first)
    assert board.can_fly_arrow(arrow)
    board.remove_arrow(arrow)
    assert is_solvable(board) is True


def test_apply_solution_rejects_bad_order():
    """顺序不对（第一步就飞不出去）时 apply_solution 必须如实返回 False。"""
    board = make_board([
        seg([(2, 0)], "R"),          # 被 (2, 2) 挡住
        seg([(2, 2)], "L"),
    ], rows=3, cols=3)
    assert apply_solution(board, [0, 1]) is False
    assert board.remaining == 2


def test_solve_empty_board():
    bench_level = {"mistakes": 3, "rows": 3, "cols": 3, "arrows": []}
    assert solve(Board(bench_level)) == []


# ---------- 撤销 ----------

def test_undo_restores_previous_step():
    board = Board(LEVELS[0])
    total = board.total
    arrow = board.flyable_arrows()[0]
    board.snapshot()
    board.remove_arrow(arrow)
    assert board.remaining == total - 1

    assert board.can_undo is True
    assert board.undo() is True
    assert board.remaining == total
    assert board.can_undo is False
    assert board.undo() is False     # 空栈再撤销返回 False


def test_undo_restores_mistakes_and_wrong_marks():
    board = Board(LEVELS[1])
    blocked = board.arrows[0]
    before = board.mistakes
    board.snapshot()
    board.mistakes -= 1
    board.mark_wrong(blocked)

    board.undo()
    assert board.mistakes == before
    assert board.wrong_ids == set()


# ---------- 存档 ----------

def test_save_roundtrip(tmp_path):
    path = os.path.join(tmp_path, "save.json")
    save = Save(path)
    save.data["coins"] = 42
    save.mark_clear(3, 2, 42, 88)
    assert save.flush() is True

    again = Save(path)
    assert again.data["coins"] == 42
    assert again.is_cleared(3) is True
    assert again.stars_of(3) == 2
    assert again.data["best_time"]["3"] == 88


def test_save_never_downgrades_stars(tmp_path):
    save = Save(os.path.join(tmp_path, "save.json"))
    save.mark_clear(1, 3, 10)
    save.mark_clear(1, 1, 12)
    assert save.stars_of(1) == 3


def test_save_survives_broken_file(tmp_path):
    path = os.path.join(tmp_path, "save.json")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{这不是 JSON")
    save = Save(path)
    assert save.data == json.loads(json.dumps(DEFAULT))

    # 类型不对的字段被丢掉，其余照常读出来
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"coins": "很多", "theme": "day"}, handle)
    save = Save(path)
    assert save.data["coins"] == DEFAULT["coins"]
    assert save.data["theme"] == "day"


def test_reset_all_keeps_settings(tmp_path):
    save = Save(os.path.join(tmp_path, "save.json"))
    save.data["theme"] = "day"
    save.data["coins"] = 99
    save.mark_clear(1, 3, 99)
    save.reset_all()
    assert save.data["theme"] == "day"
    assert save.data["coins"] == DEFAULT["coins"]
    assert save.is_cleared(1) is False


# ---------- 主题 ----------

@pytest.fixture(autouse=True)
def restore_theme():
    before = theme.get().name
    yield
    theme.set_theme(before)


def test_theme_switches_arrow_palette():
    theme.set_theme("night")
    assert theme.arrow_palette() == ARROW_PALETTE
    theme.set_theme("day")
    assert theme.arrow_palette() == ARROW_PALETTE_DAY
    assert theme.toggle().name == "night"


def test_arrow_color_wraps_index():
    theme.set_theme("night")
    assert theme.arrow_color(0) == ARROW_PALETTE[0]
    assert theme.arrow_color(len(ARROW_PALETTE)) == ARROW_PALETTE[0]
    assert theme.arrow_color(-1) == ARROW_PALETTE[-1]


def test_arrow_color_follows_theme_live():
    """Arrow.color 是属性：切主题后同一支箭自动换色。"""
    board = Board(LEVELS[0])
    arrow = board.arrows[0]
    theme.set_theme("night")
    night_color = arrow.color
    theme.set_theme("day")
    assert arrow.color != night_color
    assert arrow.color == ARROW_PALETTE_DAY[arrow.color_index]


def test_day_palette_has_same_length():
    assert len(ARROW_PALETTE_DAY) == len(ARROW_PALETTE)


def test_all_levels_still_solvable_after_regeneration():
    for level in LEVELS:
        assert generator.verify_solution(level) is True, level["name"]
