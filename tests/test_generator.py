"""关卡生成器 / 造型遮罩的单元测试。

覆盖：每个造型的遮罩都在棋盘内且四连通、生成出来的关卡必然可通关、
填充率达到「铺得满」的下限、风格参数真的起作用（越禁直行拐弯越多）、
大造型也能生成出东西。
"""

import pytest

from game import generator
from game.board import Board
from game.shapes import SHAPE_NAMES, cells_of, is_connected
from game.solver import solve

SHAPES = [name for name, _ in SHAPE_NAMES]


# ---------- 造型遮罩 ----------

@pytest.mark.parametrize("shape", SHAPES)
def test_shape_mask_inside_board_and_connected(shape):
    mask = cells_of(13, 13, shape)
    assert mask, f"{shape} 遮罩不能为空"
    for (r, c) in mask:
        assert 0 <= r < 13 and 0 <= c < 13
    assert is_connected(mask), f"{shape} 遮罩必须四连通"


def test_unknown_shape_falls_back_to_rect():
    assert cells_of(4, 5, "不存在的造型") == cells_of(4, 5, "rect")


def test_is_connected_rejects_scattered():
    assert is_connected({(0, 0), (2, 2)}) is False
    assert is_connected(set()) is False


# ---------- 关卡生成 ----------

@pytest.mark.parametrize("shape,rows,cols,seed", [
    ("rect", 12, 9, 1101021),
    ("round", 11, 11, 3303008),
    ("heart", 13, 13, 6606048),
    ("ring", 15, 15, 12121104),
])
def test_generated_level_is_solvable(shape, rows, cols, seed):
    level = generator.build_level(rows, cols, shape, seed, mistakes=3,
                                 max_attempts=12)
    assert level is not None
    # 每条箭都落在遮罩里，且格子首尾相连
    mask = cells_of(rows, cols, shape)
    for arrow in level["arrows"]:
        assert len(arrow["cells"]) >= 2
        assert arrow["dir"] in "UDLR"
        for (r, c) in arrow["cells"]:
            assert (r, c) in mask
        for (r1, c1), (r2, c2) in zip(arrow["cells"], arrow["cells"][1:]):
            assert abs(r1 - r2) + abs(c1 - c2) == 1, "相邻格必须上下左右相连"
    # 逆向构造给出的 solution 必须真的能走完
    assert generator.verify_solution(level) is True
    assert level["solution"] == list(range(len(level["arrows"]) - 1, -1, -1))
    # 求解器独立解一遍，交叉验证
    assert solve(Board(level)) is not None


@pytest.mark.parametrize("shape,rows,cols,seed", [
    ("rect", 12, 9, 1101021),
    ("round", 11, 11, 3303008),
    ("diamond", 13, 13, 4404016),
])
def test_generated_level_is_dense(shape, rows, cols, seed):
    """参考图的盘面几乎铺满，填充率不应低于 0.85。"""
    level = generator.build_level(rows, cols, shape, seed, mistakes=3,
                                  max_attempts=40)
    assert generator.fill_ratio(level) >= 0.85


def test_style_controls_turning_frequency():
    """直行概率调到 0 时，线段拐弯次数应明显多于直行概率高的版本。"""
    straight = generator.build_level(
        13, 13, "round", 4242, max_attempts=6,
        style={"max_piece": 14, "straight_bias": 0.95, "stop_chance": 0.1,
               "window": 2})
    twisty = generator.build_level(
        13, 13, "round", 4242, max_attempts=6,
        style={"max_piece": 14, "straight_bias": 0.05, "stop_chance": 0.1,
               "window": 2})

    def turns(level):
        total = 0
        for arrow in level["arrows"]:
            cells = arrow["cells"]
            steps = [(b[0] - a[0], b[1] - a[1])
                     for a, b in zip(cells, cells[1:])]
            total += sum(1 for s, t in zip(steps, steps[1:]) if s != t)
        return total / len(level["arrows"])

    assert turns(twisty) > turns(straight)


def test_random_level_is_playable():
    level = generator.random_level(seed=20260919)
    assert level is not None
    assert level.get("random") is True
    assert generator.verify_solution(level) is True


def test_difficulty_helpers():
    level = generator.build_level(12, 9, "rect", 1101021, max_attempts=8)
    assert generator.arrow_count(level) == len(level["arrows"])
    assert generator.total_cells(level) == sum(len(a["cells"])
                                               for a in level["arrows"])
    assert generator.difficulty(level) > 0
    assert generator.difficulty({"arrows": []}) == 0


# ---------- 棋盘密度 ----------

def test_basic_levels_use_the_denser_grid():
    """基础 12 关的棋盘整体加密过一轮（约 1.4 倍），别退回旧尺寸。

    旧尺寸是 11x11 ~ 18x13（遮罩 84 ~ 234 格），
    现在是 16x16 ~ 25x19（遮罩 155 ~ 475 格）。箭数随遮罩水涨船高，
    但造型之间浮动很大（十字只有十几支、满盘矩形五十多支），所以钉不死，
    这里只钉尺寸与格子数。
    """
    from game.level import LEVELS

    for level in LEVELS:
        mask = cells_of(level["rows"], level["cols"],
                        level.get("shape", "rect"))
        assert level["rows"] >= 16, level["name"]
        assert level["cols"] >= 13, level["name"]
        assert len(mask) >= 150, (level["name"], len(mask))
        assert len(level["arrows"]) >= 12, level["name"]


def test_random_levels_also_use_the_denser_grid():
    """随机关卡的尺寸表也跟着放大了，不然从开始页随机进去还是老盘面。"""
    for shape, rows, cols in generator.RANDOM_SHAPES:
        assert rows >= 16, (rows, cols)
        assert cols >= 13, (rows, cols)
        assert len(cells_of(rows, cols, shape)) >= 150, (shape, rows, cols)
