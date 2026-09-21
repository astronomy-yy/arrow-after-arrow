"""程序图标（game/appicon.py）的测试。

图标是打包时喂给 PyInstaller 的那张图，也是窗口 / 任务栏图标。这里锁住几件
容易在改绘制代码时被悄悄破坏的事：尺寸、圆角真的裁透了、画面不是空白、
两套主题能出不同的图。
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                     # noqa: E402
import pytest                                     # noqa: E402

from game import appicon, theme                   # noqa: E402


@pytest.fixture(autouse=True)
def display():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def _alpha(picture, x, y):
    return picture.get_at((x, y)).a


# ---------------- 基本形状 ----------------

@pytest.mark.parametrize("size", [32, 64, 256])
def test_square_and_sized(size):
    picture = appicon.surface(size)
    assert picture.get_size() == (size, size)
    assert picture.get_flags() & pygame.SRCALPHA


def test_corners_are_transparent():
    """四角必须真的透明 —— 否则任务栏上会是一个突兀的黑方块。"""
    size = 128
    picture = appicon.surface(size)
    for point in [(0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)]:
        assert _alpha(picture, *point) == 0, point


def test_edges_are_opaque():
    """圆角只削四个角，四边中点必须还是实心的。"""
    size = 128
    picture = appicon.surface(size)
    half = size // 2
    for point in [(half, 0), (half, size - 1), (0, half), (size - 1, half)]:
        assert _alpha(picture, *point) == 255, point


def test_center_is_painted():
    """吉祥物压在中间，中心必定是不透明的。"""
    size = 128
    picture = appicon.surface(size)
    assert _alpha(picture, size // 2, int(size * appicon._MASCOT_Y_RATIO)) == 255


def test_minimum_size_is_clamped():
    """比 32 还小的请求会被抬到 32：再小吉祥物的五官就糊成一团了。"""
    assert appicon.surface(8).get_size() == (32, 32)


# ---------------- 画面不是空白 ----------------

def test_not_blank_and_round_enough():
    """不透明像素要覆盖绝大部分，且颜色要够杂（说明底纹 + 吉祥物都画上了）。

    纯色背景会退化成「只有一个颜色的方块」，那样打包出来的图标毫无辨识度。
    """
    size = 64
    picture = appicon.surface(size)
    opaque = 0
    colors = set()
    for x in range(size):
        for y in range(size):
            pixel = picture.get_at((x, y))
            if pixel.a:
                opaque += 1
                colors.add(pixel[:3])
    # 1/4 圆角：四角各去掉约 (1 - π/4)·r²，实测占比在 0.97 上下
    assert opaque / (size * size) > 0.94
    assert len(colors) > 40


def test_rim_still_leaves_rounded_corners():
    """亮边不能把圆角重新填回方角（画边时容易被写成整块 fill）。"""
    size = 128
    picture = appicon.surface(size)
    radius = int(size * appicon.CORNER_RATIO)
    # 角上「半径外」那一小块必须是透明的
    assert _alpha(picture, max(0, radius // 4), max(0, radius // 4)) == 0


# ---------------- 两套主题 ----------------

def test_palette_makes_a_difference():
    size = 64
    night = appicon.surface(size, theme.NIGHT)
    day = appicon.surface(size, theme.DAY)
    assert night.get_at((4, 4))[:3] != day.get_at((4, 4))[:3]


def test_default_palette_is_night():
    size = 64
    assert (appicon.surface(size).get_at((4, 4))[:3]
            == appicon.surface(size, theme.NIGHT).get_at((4, 4))[:3])
