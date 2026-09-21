"""程序图标：把开始页的观感缩成一张正方形小图。

图标是**画出来的**，不是素材文件 —— 竖向渐变底 + 开始页同款的箭形暗纹 +
那只卡通箭。两个地方共用这个函数，改一次两边同时变：

- ``main.py`` 启动时把 64×64 那张交给 ``pygame.display.set_icon``，
  于是窗口标题栏、任务栏、Alt-Tab 用的是同一个形象；
- ``tools/make_icon.py`` 用 256×256 那张生成打包用的 ``assets/icon.ico``。

因为游戏运行时是现场画的，所以仓库里仍然**没有游戏要读的图片素材**；
``icon.ico`` 只是打包时喂给 PyInstaller 的产物。
"""

import pygame

from game import paint, theme

# 圆角半径 / 边长。Windows 自己的图标就是圆角矩形，跟上去更协调。
CORNER_RATIO = 0.22
# 吉祥物宽 / 边长。
MASCOT_RATIO = 0.78
# 四周那圈极淡的亮边：保证图标压在纯黑任务栏上也能看出轮廓。
RIM_ALPHA = 46
# 底纹按开始页的 640 宽等比缩下来，疏密才和游戏里一致。
# （paint 的默认 step=88 / arrow=54 是按整屏调的，直接搬到小图上会显得很粗。）
_PATTERN_REF_WIDTH = 640
_PATTERN_STEP = 88
_PATTERN_ARROW = 54
# 吉祥物的落点略高于中线：视觉重心往上一点，小尺寸下更精神。
_MASCOT_Y_RATIO = 0.52


def surface(size=256, palette=None):
    """返回一张带透明圆角的方形图标，边长 ``size`` 逻辑像素。

    ``palette`` 留空用夜间主题（游戏默认那套）；日间主题可以显式传
    ``theme.DAY``。同一尺寸会被 ``paint`` 的缓存复用，重复调用很便宜。
    """
    size = max(32, int(size))
    pal = theme.NIGHT if palette is None else palette
    canvas = pygame.Surface((size, size), pygame.SRCALPHA)

    ratio = size / _PATTERN_REF_WIDTH
    paint.blit_pattern(canvas, (size, size), pal.menu_top, pal.menu_bottom,
                       pal.pattern, pal.pattern_alpha,
                       step=max(8, int(_PATTERN_STEP * ratio)),
                       arrow=max(6, int(_PATTERN_ARROW * ratio)))

    center = (size // 2, int(size * _MASCOT_Y_RATIO))
    paint.blit_glow(canvas, center, int(size * 0.62), pal.glow, 70, 2.1)

    mascot = paint.arrow_mascot(
        int(size * MASCOT_RATIO), pal.mascot_light, pal.mascot_dark,
        pal.mascot_line, pal.mascot_gloss, eye=pal.mascot_eye,
        pupil=pal.mascot_pupil, shadow=pal.mascot_shadow, shadow_alpha=70,
        shadow_offset=(max(1, size // 64), max(2, size // 26)), tilt=-10,
        outline_width=max(3, size // 42))
    canvas.blit(mascot, mascot.get_rect(center=center))

    _round_corners(canvas, size)
    return canvas


def _round_corners(canvas, size):
    """把方角裁成圆角，再压一圈淡亮边。

    裁剪走 ``BLEND_RGBA_MULT``：遮罩四角是 ``(0, 0, 0, 0)``，相乘之后
    alpha 归零即透明；用 draw + colorkey 之类反而会留下黑角。
    """
    radius = max(4, int(size * CORNER_RATIO))
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, size, size),
                     border_radius=radius)
    canvas.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    # 亮边画在独立图层上再贴：draw 是直接写像素，在同一张图上画会盖掉底色。
    rim = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(rim, (255, 255, 255, RIM_ALPHA), (0, 0, size, size),
                     width=max(1, size // 64), border_radius=radius)
    canvas.blit(rim, (0, 0))
    return canvas
