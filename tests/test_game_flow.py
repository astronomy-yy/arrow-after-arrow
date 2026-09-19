"""端到端冒烟测试：真的「点」完一整关。

用 pygame 的 dummy 驱动起一个无窗口的 Game，按 level.py 里给出的
solution 顺序，把每一次点击都合成成 MOUSEBUTTONDOWN 事件打到箭头
那一格上，然后推进主循环让飞行动画跑完，最后断言本关通关。

这一层测试覆盖的是「点击 -> 判定 -> 飞出动画 -> 判定通关」整条链路，
单元测试覆盖不到的接线问题基本都能在这里暴露。
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                    # noqa: E402
import pytest                                    # noqa: E402

from game import theme                           # noqa: E402
from game.settings import COIN_REWARD_CLEAR, HINT_COST   # noqa: E402
from game.states import GameState                # noqa: E402
from game.storage import Save                    # noqa: E402
from main import Game                            # noqa: E402


@pytest.fixture
def game(tmp_path):
    instance = Game(save_path=str(tmp_path / "save.json"))
    theme.set_theme("night")
    yield instance
    pygame.quit()


def click_cell(game, row, col):
    """把一次左键点击合成到某一格上。"""
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": game._grid_center(row, col), "button": 1},
    )
    game._dispatch_event(event)


# 两支箭互相对着、谁也飞不出去：专门用来测「点错」这条分支
BLOCKED_LEVEL = {
    "id": 99,
    "name": "测试关",
    "shape": "rect",
    "mistakes": 3,
    "rows": 3,
    "cols": 3,
    "time_limit": 120,
    "arrows": [
        {"cells": [[2, 0]], "dir": "R", "color": 0},
        {"cells": [[2, 2]], "dir": "L", "color": 1},
    ],
    "solution": [],
}


def settle(game, limit=3000):
    """推进主循环，直到所有飞出 / 弹回动画都播完。"""
    steps = 0
    while (game.flying or game.blocked) and steps < limit:
        game._update(1.0 / 60.0)
        steps += 1
    assert steps < limit, "动画没有在合理步数内结束"
    return steps


def test_full_playthrough_clears_level(game):
    game.start_game()
    assert game.state == GameState.PLAYING
    level = game.levels[0]
    total = game.board.total
    assert total > 0
    coins_before = game.coins

    for step, arrow_id in enumerate(level["solution"], 1):
        arrow = next(a for a in game.board.arrows if a.id == arrow_id)
        click_cell(game, *arrow.head)
        settle(game)
        assert game.board.remaining == total - step, f"第 {step} 步没飞出去"

    # 最后一支飞完后，主循环应当判定通关
    game._update(1.0 / 60.0)
    assert game.state == GameState.LEVEL_CLEAR
    assert game.stars >= 1
    assert game.coins == coins_before + COIN_REWARD_CLEAR
    # 进度确实写进了存档
    saved = Save(game.save.path)
    assert saved.is_cleared(level.get("id", 1)) is True


def test_wrong_click_costs_a_heart(game):
    game.start_game()
    game._load_level(BLOCKED_LEVEL)
    game.state = GameState.PLAYING
    before = game.board.mistakes
    blocked = game.board.arrow_at(2, 0)
    assert game.board.can_fly_arrow(blocked) is False

    click_cell(game, 2, 0)
    assert game.board.mistakes == before - 1
    assert blocked.id in game.board.wrong_ids
    assert game.state == GameState.PLAYING
    settle(game)

    # 撤销把它恢复回来
    assert game.undo() is True
    assert game.board.mistakes == before
    assert game.board.wrong_ids == set()


def test_generated_level_has_blocked_arrows(game):
    """正式关卡必须有阻挡：开局既要有能点的，也要有被压住点不动的。

    这里以前断言的是「开局每支箭都能飞」，那其实是生成器多了一条多余
    约束造成的 bug —— 全盘都能飞等于无脑乱点必通关，已经修掉。
    """
    game.start_game()
    board = game.board
    free = board.flyable_arrows()
    assert 0 < len(free) < board.total, "开局必须有能点的，也必须有点不动的"
    blocked = [a for a in board.arrows if not board.can_fly_arrow(a)]
    assert blocked, "关卡里应当有被别的箭压住的箭"

    # 提示与 AI 求解在真实难度的盘面上也要给出合法的一步
    assert game.use_hint() is True
    assert game.auto_solve() is True
    assert game.auto_queue[0] in {a.id for a in board.flyable_arrows()}
    assert game.board.remaining == game.board.total


def test_clicking_empty_cell_is_free(game):
    game.start_game()
    # 换到圆形关卡：圆外的格子是空的，但仍落在棋盘范围内
    game.select_level(2)
    mask = game._mask_cells()
    target = None
    for r in range(game.board.rows):
        for c in range(game.board.cols):
            if (r, c) not in mask and game._cell_at(
                    game._grid_center(r, c)) == (r, c):
                target = (r, c)
                break
        if target is not None:
            break
    assert target is not None, "圆形关卡应该有棋盘内的空格"

    before = game.board.mistakes
    click_cell(game, *target)
    assert game.board.mistakes == before
    assert game.state == GameState.PLAYING
    assert not game.flying and not game.blocked


def test_flying_locks_input_until_animation_ends(game):
    game.start_game()
    first = next(a for a in game.board.arrows if game.board.can_fly_arrow(a))
    click_cell(game, *first.head)
    assert game.flying, "点击后应当立刻进入飞行动画"
    remaining = game.board.remaining

    # 动画期间再点别的箭：不应生效
    others = [a for a in game.board.arrows if a is not first]
    if others:
        click_cell(game, *others[0].head)
        assert game.board.remaining == remaining

    settle(game)


def test_hint_needs_coins(game):
    game.start_game()
    game.coins = 99
    assert game.use_hint() is True
    assert game.hint_arrow_id is not None
    assert game.hint_pulse is not None
    assert game.coins == 99 - HINT_COST

    game.hint_pulse = None
    game.hint_arrow_id = None
    game.coins = 0
    assert game.use_hint() is False
    assert game.hint_pulse is None


def test_theme_toggle_recolors_board(game):
    game.start_game()
    arrow = game.board.arrows[0]
    night_color = arrow.color
    game.toggle_theme()
    assert theme.get().name == "day"
    assert arrow.color != night_color
    assert game.hud.theme_switch.is_night is False
    game.toggle_theme()
    assert game.hud.theme_switch.is_night is True


def test_restart_and_random_level(game):
    game.start_game()
    first = next(a for a in game.board.arrows if game.board.can_fly_arrow(a))
    click_cell(game, *first.head)
    settle(game)
    assert game.board.remaining < game.board.total

    game.restart_level()
    assert game.board.remaining == game.board.total
    assert game.state == GameState.PLAYING

    game.new_random_level()
    assert game.current_level.get("random") is True
    assert game.board.total > 0
    assert game.state == GameState.PLAYING
