"""阻挡与难度的回归测试。

这一组测试是为了防止**关卡退化成「无脑乱点必通关」**：
早先的生成器多了一条「身体不许压在别人射线上」的约束，数学上等价于
`射线(a) ∩ 身体(b) = ∅`，于是开局每一支箭都能直接飞，点什么都对。

覆盖：正式关卡确实互相阻挡、难度随关卡递增、生成器的阻挡旋钮真的起作用、
求解器（拓扑排序）在人为构造的阻挡链 / 环路 / 大关上都给出正确结果。
"""

import time

import pytest

from game.board import Board
from game.generator import (
    DEFAULT_STYLE,
    board_stats,
    build_level,
    verify_solution,
)
from game.level import LEVELS
from game.solver import apply_solution, free_ids, solve


def seg(cells, direction, color=0):
    return {"cells": cells, "dir": direction, "color": color}


def make_board(arrows, rows=5, cols=5, mistakes=3):
    return Board({"mistakes": mistakes, "rows": rows, "cols": cols,
                  "arrows": arrows})


# ---------- 正式关卡必须真的互相阻挡 ----------

def test_every_level_has_real_blocking():
    """任何一关都不该出现「开局全部能飞」。"""
    for level in LEVELS:
        stats = board_stats(level)
        assert stats["arrows"] > 0
        assert stats["free"] < stats["arrows"], (
            f"{level['name']} 开局所有箭都能飞，等于没有阻挡")
        assert stats["blocked_ratio"] >= 0.25, (
            f"{level['name']} 只有 {stats['blocked_ratio']:.0%} 的箭被挡住")
        assert stats["avg_blockers"] > 0.5, level["name"]


def test_difficulty_ramps_up_across_levels():
    """开局能直接飞的箭占比应当逐关下降，最后一关明显最难。"""
    ratios = [board_stats(level)["free_ratio"] for level in LEVELS]
    for earlier, later in zip(ratios, ratios[1:]):
        assert later <= earlier + 1e-9, f"难度曲线出现回升：{ratios}"
    assert ratios[0] >= 0.5, "第 1 关该给新手留够容错"
    assert ratios[-1] <= 0.2, "第 12 关应当很紧"


def test_first_level_is_friendly_and_last_level_is_not():
    first = board_stats(LEVELS[0])
    last = board_stats(LEVELS[-1])
    assert first["blocked_ratio"] <= 0.5
    assert last["blocked_ratio"] >= 0.8
    assert last["avg_blockers"] > first["avg_blockers"]


# ---------- 生成器的阻挡旋钮 ----------

@pytest.mark.parametrize("shape,rows,cols,seed", [
    ("rect", 12, 9, 1101021),
    ("round", 13, 13, 3303008),
    ("heart", 13, 13, 6606048),
    ("rect", 18, 13, 13131200),
])
def test_ray_pref_controls_blocking(shape, rows, cols, seed):
    """ray_pref=1 必然大量互相阻挡；ray_pref=0 基本不阻挡。"""
    blocking = build_level(rows, cols, shape, seed, max_attempts=30,
                           style=dict(DEFAULT_STYLE, ray_pref=1.0))
    loose = build_level(rows, cols, shape, seed, max_attempts=30,
                        style=dict(DEFAULT_STYLE, ray_pref=0.0))
    assert blocking is not None and loose is not None

    strong = board_stats(blocking)
    weak = board_stats(loose)
    assert strong["blocked_ratio"] >= 0.5, strong
    assert weak["blocked_ratio"] <= 0.2, weak
    assert strong["free_ratio"] < weak["free_ratio"]


def test_max_free_is_respected_when_achievable():
    level = build_level(13, 13, "round", 3303008, max_attempts=60,
                        style=dict(DEFAULT_STYLE, ray_pref=1.0),
                        max_free=0.3)
    assert board_stats(level)["free_ratio"] <= 0.3


@pytest.mark.parametrize("shape,rows,cols", [
    ("rect", 12, 9), ("round", 13, 13), ("heart", 13, 13),
    ("ring", 15, 15), ("hourglass", 14, 12),
])
def test_generated_levels_are_solvable_and_blocked(shape, rows, cols):
    """重阻挡不会把关卡生成成死局：solution 与求解器两边都要过。"""
    for seed in (7, 1234, 9909072):
        level = build_level(rows, cols, shape, seed, max_attempts=20,
                            style=dict(DEFAULT_STYLE, ray_pref=1.0))
        assert level is not None
        assert verify_solution(level) is True
        assert solve(Board(level)) is not None
        assert board_stats(level)["free"] >= 1


# ---------- 求解器（拓扑排序）的正确性 ----------

def test_solver_handles_blocking_chain():
    """一条 A 被 B 挡、B 被 C 挡的链：只能从 C 开始点。"""
    board = make_board([
        seg([(0, 0)], "R"),      # A：射线经过 B、C
        seg([(0, 2)], "R"),      # B：射线经过 C
        seg([(0, 4)], "R"),      # C：贴边朝外，随时能飞
    ], rows=1, cols=5)
    assert board.can_fly(0, 0) is False
    assert board.can_fly(0, 2) is False
    assert board.can_fly(0, 4) is True
    assert solve(board) == [2, 1, 0]


def test_solver_reports_cycle_as_unsolvable():
    """互相封死形成环 → 真的无解。"""
    board = make_board([
        seg([(2, 0)], "R"),
        seg([(2, 2)], "L"),
    ], rows=3, cols=3)
    assert solve(board) is None


def test_free_ids_matches_board():
    """求解器算的「入度为 0」必须和棋盘自己的判定完全一致。"""
    for level in LEVELS:
        board = Board(level)
        assert free_ids(board) == sorted(a.id for a in board.flyable_arrows())


@pytest.mark.parametrize("level_index", range(len(LEVELS)))
def test_solver_solves_every_shipped_level(level_index):
    level = LEVELS[level_index]
    board = Board(level)
    order = solve(board)
    assert order is not None
    assert sorted(order) == sorted(a.id for a in board.arrows)
    assert apply_solution(board, order) is True
    assert board.remaining == 0


def test_solver_is_fast_on_the_biggest_level():
    """拓扑排序是 O(n²)：最大的关卡也必须毫秒级出结果。

    （旧的 DFS 版本在这里会打满节点上限，把有解的关卡报成无解。）
    """
    biggest = max(LEVELS, key=lambda lv: board_stats(lv)["arrows"])
    t0 = time.time()
    order = solve(Board(biggest))
    assert order is not None
    assert time.time() - t0 < 0.5
