"""窗口尺寸收敛与缩放响应的测试。

对应 bug：窗口默认高 1000，比桌面（逻辑尺寸 900）还高，Windows 把它垂直
居中后标题栏跑到屏幕上边、底边跑到屏幕下边，用户既抓不到边框缩放、也抓不到
标题栏拖动。这里的测试锁住「初始窗口必须放得下」和「缩放响应不再重建窗口」。
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                    # noqa: E402
import pytest                                    # noqa: E402

import main as m                                 # noqa: E402
from game import theme                           # noqa: E402
from game.settings import (                      # noqa: E402
    DEFAULT_WINDOW_H,
    DEFAULT_WINDOW_W,
    MIN_WINDOW_H,
    MIN_WINDOW_W,
    SCREEN_RESERVE_H,
    SCREEN_RESERVE_W,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)


@pytest.fixture
def game(tmp_path):
    instance = m.Game(save_path=str(tmp_path / "save.json"))
    theme.set_theme("night")
    yield instance
    pygame.quit()


# ---------------- 纯函数 ----------------

def test_usable_cap_leaves_room_for_chrome():
    cap_w, cap_h = m.usable_window_cap((1440, 900))
    assert cap_w == 1440 - SCREEN_RESERVE_W
    assert cap_h == 900 - SCREEN_RESERVE_H


def test_usable_cap_never_goes_absurdly_small():
    assert m.usable_window_cap((100, 80)) == (200, 200)


def test_fit_shrinks_tall_window_to_desktop():
    """1440x900 的桌面（200% 缩放屏幕的逻辑尺寸）装不下 620x1000。"""
    width, height = m.fit_to_screen(620, 1000, (1440, 900))
    assert height <= 900 - SCREEN_RESERVE_H
    assert width < 620
    # 等比缩放：宽高比保持不变（允许 1px 取整误差）
    assert abs(width / height - 620 / 1000) < 0.01


def test_fit_never_upscales():
    assert m.fit_to_screen(DEFAULT_WINDOW_W, DEFAULT_WINDOW_H,
                           (3840, 2160)) == (DEFAULT_WINDOW_W,
                                             DEFAULT_WINDOW_H)
    # 1080p 的桌面上可用高只有 940，装不下 1000 高的窗口，必须缩
    assert m.fit_to_screen(620, 1000, (1920, 1080)) == (583, 940)
    # 竖过来够高的桌面才保持原样
    assert m.fit_to_screen(620, 1000, (1920, 1200)) == (620, 1000)


def test_fit_result_always_fits_on_screen():
    for desktop in [(1440, 900), (1366, 768), (1280, 720), (1024, 768),
                    (3840, 2160), (800, 600)]:
        cap_w, cap_h = m.usable_window_cap(desktop)
        width, height = m.fit_to_screen(DEFAULT_WINDOW_W, DEFAULT_WINDOW_H,
                                        desktop)
        assert width <= cap_w and height <= cap_h, desktop


def test_desktop_size_is_none_under_dummy_driver():
    """dummy 驱动会谎报 1024x768，必须被识别成「拿不到」，否则截图会变形。"""
    pygame.init()
    assert pygame.display.get_driver() == "dummy"
    assert m.desktop_size() is None


# ---------------- 接到 Game 上 ----------------

def test_initial_window_fits_inside_desktop(monkeypatch, tmp_path):
    """把桌面换成 1440x900（200% 缩放屏的逻辑尺寸），初始窗口必须放得下。"""
    desktop = (1440, 900)
    monkeypatch.setattr(m, "desktop_size", lambda: desktop)
    instance = m.Game(save_path=str(tmp_path / "save.json"))
    try:
        cap_w, cap_h = m.usable_window_cap(desktop)
        width, height = instance.screen.get_size()
        assert width <= cap_w
        assert height <= cap_h
        assert width >= instance.min_window[0]
        assert height >= instance.min_window[1]
        assert instance.min_window == (min(MIN_WINDOW_W, cap_w),
                                       min(MIN_WINDOW_H, cap_h))
    finally:
        pygame.quit()


def test_dummy_run_keeps_default_window_size(game):
    """无窗口（截图 / 测试）下不做任何收敛，尺寸必须还是默认值。"""
    assert game.screen.get_size() == (DEFAULT_WINDOW_W, DEFAULT_WINDOW_H)
    assert game.min_window == (MIN_WINDOW_W, MIN_WINDOW_H)


def test_view_follows_window_size(game):
    game._resize(900, 900)
    assert game.screen.get_size() == (900, 900)
    assert game.view_rect.width <= 900 and game.view_rect.height <= 900
    # 画布按等比缩放塞进窗口，取较小的一边
    assert abs(game.view_scale - min(900 / WINDOW_WIDTH,
                                     900 / WINDOW_HEIGHT)) < 1e-6

    game._resize(500, 1200)
    assert game.screen.get_size() == (500, 1200)
    assert game.view_rect.width <= 500
    assert game.view_rect.height <= 1200


def test_resize_clamps_to_min_window(game):
    min_w, min_h = game.min_window
    game._resize(100, 100)
    assert game.screen.get_size() == (min_w, min_h)
    # 再喂一次同尺寸也不该无限循环改窗口
    game._resize(*game.screen.get_size())
    assert game.screen.get_size() == (min_w, min_h)


def test_resize_skips_set_mode_when_surface_already_matches(game):
    """尺寸和当前 surface 一致时不该再 set_mode。

    真实窗口下 SDL2 会先把 surface 换成新尺寸，所以正常拖拽根本走不到
    set_mode —— 这正是「拖拽时不再反复重建窗口」的关键。
    """
    game._resize(800, 900)
    surface = game.screen
    game._resize(*surface.get_size())
    assert game.screen is surface


def test_click_mapping_still_accurate_after_resize(game):
    game.start_game()
    game._resize(900, 900)
    rows, cols = game.board.rows, game.board.cols
    for (row, col) in [(0, 0), (rows - 1, cols - 1),
                       (rows // 2, cols // 2)]:
        cx, cy = game._grid_center(row, col)
        on_screen = (game.view_rect.x + cx * game.view_scale,
                     game.view_rect.y + cy * game.view_scale)
        assert game._cell_at(game._to_world(on_screen)) == (row, col)
