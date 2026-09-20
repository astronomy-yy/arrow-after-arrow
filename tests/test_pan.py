"""棋盘缩放与拖动的测试。

对应缺陷：「棋盘能放大缩小，但拖不动」。原来的 `_compute_geometry()` 只按缩放
算出居中坐标，没有任何平移量 —— 放到最大时 12 关**每一关**都会横向溢出可视区
（153~171 像素，其中 5 关纵向也溢出），溢出的部分用户既看不到也够不着。

但直接「按住就拖」又和「点击线段让它飞」冲突：正式关卡填充率 0.94~1.00，
几乎每一格都是线段，想拖棋盘就一定先点飞一支箭。所以改成
**按下记账、抬起了结**：位移没超过 `DRAG_THRESHOLD` 才算点击，超过了就改判成
拖动棋盘，被判成拖动的那一次点击作废。这里把这条规则、边界夹取，以及
「棋盘永远不会被拖出屏幕」都锁住。
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                    # noqa: E402
import pytest                                    # noqa: E402

from game import theme                           # noqa: E402
from game.settings import (
    BOTTOM_BAR_HEIGHT,
    TOP_BAR_HEIGHT,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from game.states import GameState                # noqa: E402
from main import (                               # noqa: E402
    DRAG_THRESHOLD,
    PAN_STEP,
    ZOOM_MAX,
    ZOOM_MIN,
    Game,
)


@pytest.fixture
def game(tmp_path):
    instance = Game(save_path=str(tmp_path / "save.json"))
    theme.set_theme("night")
    instance.start_game()
    yield instance
    pygame.quit()


# ---------------- 合成鼠标事件 ----------------

def press(game, pos, button=1):
    game._dispatch_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": button}))


def motion(game, pos, buttons=(1, 0, 0)):
    game._dispatch_event(pygame.event.Event(
        pygame.MOUSEMOTION,
        {"pos": (int(pos[0]), int(pos[1])), "buttons": buttons}))


def release(game, pos, button=1):
    game._dispatch_event(pygame.event.Event(
        pygame.MOUSEBUTTONUP, {"pos": pos, "button": button}))


def drag(game, start, end, steps=4):
    """按下、分几步拖到终点、松手。每步都取整，总位移能精确对上。"""
    start = (int(start[0]), int(start[1]))
    end = (int(end[0]), int(end[1]))
    press(game, start)
    for i in range(1, steps + 1):
        motion(game, (start[0] + (end[0] - start[0]) * i / steps,
                      start[1] + (end[1] - start[1]) * i / steps))
    release(game, end)


def zoom_max(game, anchor=None):
    game.on_zoom_slider(1.0, anchor=anchor)
    assert game.zoom == pytest.approx(ZOOM_MAX)


def some_free_arrow(game):
    return next(a for a in game.board.arrows if game.board.can_fly_arrow(a))


def centered_x(game):
    return (WINDOW_WIDTH - game.board_pixel_w) // 2


# ---------------- 前置事实 ----------------

def test_zoom_max_overflows_the_viewport(game):
    """锁住前提：放到最大时棋盘确实溢出，否则「拖不动」根本不算问题。"""
    assert game._can_drag() is False, "默认缩放下棋盘放得下，本来就不该能拖"
    zoom_max(game)
    assert game._can_drag() is True
    assert game.board_pixel_w > game._viewport().width


def test_board_smaller_than_viewport_is_centered_and_stuck(game):
    game.on_zoom_slider(0.0)
    assert game.zoom == pytest.approx(ZOOM_MIN)
    before = (game.board_x, game.board_y)
    assert game.pan_by(120, 90) is False
    assert (game.board_x, game.board_y) == before
    assert game.board_x == centered_x(game)


def test_viewport_sits_between_the_two_bars(game):
    view = game._viewport()
    assert view.top == TOP_BAR_HEIGHT
    assert view.bottom == WINDOW_HEIGHT - BOTTOM_BAR_HEIGHT
    assert view.width == WINDOW_WIDTH


# ---------------- 拖动 ----------------

def test_left_drag_pans_the_board(game):
    zoom_max(game)
    start = game._grid_center(*some_free_arrow(game).head)
    x0, y0 = game.board_x, game.board_y

    drag(game, start, (start[0] + 60, start[1] + 40))

    # 棋盘跟着指针走：右移 60、下移 40
    assert game.board_x == x0 + 60
    assert game.board_y == y0 + 40


def test_dragging_never_fires_an_arrow(game):
    """撑着棋盘拖，绝不能顺手把线段点飞或者扣心。"""
    zoom_max(game)
    start = game._grid_center(*some_free_arrow(game).head)
    before = (game.board.remaining, game.board.mistakes)
    x0, y0 = game.board_x, game.board_y

    drag(game, start, (start[0] + 90, start[1]))

    assert (game.board.remaining, game.board.mistakes) == before
    assert not game.flying and not game.blocked
    assert game.board.arrows, "线段一支都不该少"
    assert (game.board_x, game.board_y) != (x0, y0), "棋盘应当挪动了"


def test_press_alone_does_not_click(game):
    """只按下不松手：什么都不该发生（先记账、松手才了结）。"""
    zoom_max(game)
    before = game.board.remaining
    press(game, game._grid_center(*some_free_arrow(game).head))
    assert game.board.remaining == before
    assert not game.flying


def test_click_without_moving_still_fires(game):
    zoom_max(game)
    before = game.board.remaining
    pos = game._grid_center(*some_free_arrow(game).head)
    press(game, pos)
    release(game, pos)
    assert game.board.remaining == before - 1
    assert game.flying


def test_tiny_jitter_still_counts_as_a_click(game):
    """手抖一点点（不超过阈值）仍算点击，不能因为拖拽判定把点击吃掉。"""
    zoom_max(game)
    before = game.board.remaining
    pos = game._grid_center(*some_free_arrow(game).head)
    shifted = (pos[0] + DRAG_THRESHOLD - 1, pos[1])
    press(game, pos)
    motion(game, shifted)
    release(game, shifted)
    assert game.board.remaining == before - 1


def test_release_far_from_press_is_not_a_click(game):
    """位移超过阈值又没形成拖动（棋盘小到拖不动）时，这次点击作废。"""
    game.on_zoom_slider(0.0)
    before = game.board.remaining
    pos = game._grid_center(*some_free_arrow(game).head)
    press(game, pos)
    release(game, (pos[0] + DRAG_THRESHOLD * 4, pos[1]))
    assert game.board.remaining == before


def test_middle_and_right_button_drag(game):
    zoom_max(game)
    for button in (2, 3):
        buttons = tuple(1 if i == button - 1 else 0 for i in range(3))
        x0, remaining = game.board_x, game.board.remaining
        press(game, (320, 500), button=button)
        motion(game, (350, 500), buttons=buttons)
        release(game, (350, 500), button=button)
        assert game.board_x == x0 + 30, button
        assert game.board.remaining == remaining, "中 / 右键拖动不该碰到线段"


def test_drag_state_recovers_when_the_up_event_is_lost(game):
    """指针拖出窗口、在窗口外松手时抬起事件可能收不到，靠 motion 的按键状态收尾。"""
    zoom_max(game)
    press(game, (320, 500))
    motion(game, (380, 560))                     # 变成拖动
    assert game.dragging is True
    motion(game, (400, 580), buttons=(0, 0, 0))  # 已经松手了
    assert game.dragging is False
    x0 = game.board_x
    motion(game, (430, 610), buttons=(0, 0, 0))
    assert game.board_x == x0, "松手后不该继续跟着指针走"


def test_hover_is_cleared_while_dragging(game):
    zoom_max(game)
    start = game._grid_center(*some_free_arrow(game).head)
    motion(game, start, buttons=(0, 0, 0))
    assert game.hover_arrow is not None
    drag(game, start, (start[0] + 40, start[1]))
    assert game.hover_arrow is None


def test_pan_is_clamped_so_board_never_leaves_the_screen(game):
    zoom_max(game)
    view = game._viewport()
    for target in (6000, -6000):
        drag(game, (320, 500), (target, target))
        assert view.right - game.board_pixel_w <= game.board_x <= view.left
        assert view.bottom - game.board_pixel_h <= game.board_y <= view.top
        # 可视区里一定还留着能点的格子
        assert any(game._cell_rect(r, c).colliderect(view)
                   for r in range(game.board.rows)
                   for c in range(game.board.cols)), "棋盘被拖出屏幕了"


def test_pan_does_not_accumulate_at_the_edge(game):
    """拖到边界后 pan 必须写回夹取结果，否则往回拖会先「空转」一大段。"""
    zoom_max(game)
    drag(game, (320, 500), (6000, 6000))         # 用力怼到右下极限
    x0, y0 = game.board_x, game.board_y
    drag(game, (320, 500), (310, 490))           # 再往回拖 10 像素
    assert (game.board_x, game.board_y) == (x0 - 10, y0 - 10)


def test_cell_hit_test_survives_panning(game):
    zoom_max(game)
    drag(game, (320, 500), (200, 440))
    assert game.board_x == 640 - game.board_pixel_w, "已经怼到左边界了"
    for (row, col) in [(0, 0), (game.board.rows - 1, game.board.cols - 1),
                       (game.board.rows // 2, game.board.cols // 2)]:
        assert game._cell_at(game._grid_center(row, col)) == (row, col)


def test_drag_through_window_coordinates(game):
    """走真窗口那条路：窗口坐标 → 画布坐标 → 拖动（缩放过的窗口也算得对）。"""
    game._resize(583, 940)
    zoom_max(game)
    arrow = some_free_arrow(game)
    cx, cy = game._grid_center(*arrow.head)
    window_pos = (game.view_rect.x + cx * game.view_scale,
                  game.view_rect.y + cy * game.view_scale)
    before = (game.board.remaining, game.board_x)

    press(game, game._to_world(window_pos))
    moved = game._to_world((window_pos[0] + 60, window_pos[1] + 30))
    motion(game, moved)
    release(game, moved)

    assert game.board_x > before[1], "棋盘应该跟着指针往右下走"
    assert game.board.remaining == before[0], "拖动不该点飞线段"
    assert not game.flying


# ---------------- 缩放 ----------------

def test_zoom_anchor_keeps_the_point_under_the_cursor(game):
    """滚轮缩放要锚在指针上：缩放前后指针底下的棋盘位置尽量不动。"""
    anchor = (250, 400)
    u_before = (anchor[0] - game.board_x) / game.board_pixel_w

    zoom_max(game, anchor=anchor)

    u_after = (anchor[0] - game.board_x) / game.board_pixel_w
    assert abs(u_after - u_before) < 0.005
    # 不锚在指针上（按可视区中心缩放）会差出肉眼可见的一截
    centered = (anchor[0] - centered_x(game)) / game.board_pixel_w
    assert abs(centered - u_before) > abs(u_after - u_before)


def test_wheel_zooms_around_the_pointer(game, monkeypatch):
    game._update_view()
    pos = (280, 420)                             # 窗口坐标
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
    text = game._to_world(pos)
    u_before = (text[0] - game.board_x) / game.board_pixel_w

    game._handle_wheel(pygame.event.Event(pygame.MOUSEWHEEL, {"y": 1, "x": 0}))
    assert game.zoom > 1.0
    u_after = (text[0] - game.board_x) / game.board_pixel_w
    assert abs(u_after - u_before) < 0.01

    game._handle_wheel(pygame.event.Event(pygame.MOUSEWHEEL,
                                         {"y": -1, "x": 0}))
    assert game.zoom == pytest.approx(1.0, abs=1e-6)


def test_wheel_is_ignored_outside_playing(game):
    game.state = GameState.START
    game._handle_wheel(pygame.event.Event(pygame.MOUSEWHEEL, {"y": 1, "x": 0}))
    assert game.zoom == pytest.approx(1.0)


def test_zoom_never_leaves_its_range(game):
    for _ in range(20):
        game.nudge_zoom(0.2)
    assert game.zoom == pytest.approx(ZOOM_MAX)
    for _ in range(40):
        game.nudge_zoom(-0.2)
    assert game.zoom == pytest.approx(ZOOM_MIN)


def test_zoom_out_to_fit_centers_the_board_again(game):
    zoom_max(game)
    drag(game, (320, 500), (420, 560))
    assert game.pan != [0, 0]
    game.on_zoom_slider(0.0)
    assert game.pan == [0, 0]
    assert game.board_x == centered_x(game)


def test_keyboard_pan_zoom_and_reset(game):
    zoom_max(game)
    x0 = game.board_x
    game._handle_key(pygame.K_LEFT)              # 视野往左看：棋盘右移
    assert game.board_x == x0 + PAN_STEP
    game._handle_key(pygame.K_RIGHT)
    assert game.board_x == x0
    y0 = game.board_y
    game._handle_key(pygame.K_UP)
    assert game.board_y == y0 + PAN_STEP

    game._handle_key(pygame.K_MINUS)
    assert game.zoom < ZOOM_MAX
    game._handle_key(pygame.K_EQUALS)
    assert game.zoom == pytest.approx(ZOOM_MAX)

    game._handle_key(pygame.K_0)
    assert game.zoom == pytest.approx(1.0)
    assert game.pan == [0, 0]
    assert game.board_x == centered_x(game)


def test_reset_view_puts_the_board_back(game):
    zoom_max(game)
    drag(game, (320, 500), (420, 600))
    game.reset_view()
    assert game.zoom == pytest.approx(1.0)
    assert game.pan == [0, 0]
    assert game.board_y == game._base_position()[1]


# ---------------- 换关 / 重开 ----------------

def test_new_level_resets_pan(game):
    zoom_max(game)
    drag(game, (320, 500), (420, 560))
    assert game.pan != [0, 0]

    game.select_level(3)
    assert game.pan == [0, 0]
    assert game.board_x == centered_x(game)

    zoom_max(game)
    drag(game, (320, 500), (420, 560))
    assert game.pan != [0, 0]
    game.restart_level()
    assert game.pan == [0, 0]
