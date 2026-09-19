"""方向枚举、方向映射与线段箭绘制。"""

import math
from enum import Enum

import pygame

from game.settings import (
    MAX_SEGMENT_WIDTH,
    MIN_SEGMENT_WIDTH,
    SEGMENT_WIDTH_RATIO,
)

# 空格标记
EMPTY = "."


class Direction(Enum):
    """四个飞行方向，枚举值与关卡数据字符一致。"""

    UP = "U"
    DOWN = "D"
    LEFT = "L"
    RIGHT = "R"


CHAR_TO_DIRECTION = {
    "U": Direction.UP,
    "D": Direction.DOWN,
    "L": Direction.LEFT,
    "R": Direction.RIGHT,
}

DIRECTION_DELTA = {
    Direction.UP: (-1, 0),
    Direction.DOWN: (1, 0),
    Direction.LEFT: (0, -1),
    Direction.RIGHT: (0, 1),
}


def segment_width(cell_size):
    """按格子大小算线宽，保证缩放时线宽与格子的比例稳定。"""
    width = int(cell_size * SEGMENT_WIDTH_RATIO)
    return max(MIN_SEGMENT_WIDTH, min(MAX_SEGMENT_WIDTH, width))


SPRITE_SCALE = 4            # 小图形的超采样倍数（4 倍≈16 个子像素）
_SPRITE_CACHE = {}
_SPRITE_CACHE_LIMIT = 256


def _cached_sprite(key, build):
    """按 key 缓存贴图：图形只跟「形状 + 尺寸 + 颜色」有关，缓存后每帧只是 blit。"""
    sprite = _SPRITE_CACHE.get(key)
    if sprite is None:
        if len(_SPRITE_CACHE) >= _SPRITE_CACHE_LIMIT:
            _SPRITE_CACHE.clear()
        sprite = _SPRITE_CACHE[key] = build()
    return sprite


def disc_sprite(radius, color):
    """抗锯齿实心圆，直径 2r+1，和 pygame 画的整数圆一样宽。

    pygame 的 draw.circle / draw.polygon 没有抗锯齿，斜边会一排锯齿；画在
    会移动的线段上时这些锯齿还会「爬行」。这里放大 4 倍画好再缩回来，
    边缘就有半透明的过渡像素了。
    """
    radius = max(1, int(radius))
    color = tuple(color[:3])

    def build():
        scale = SPRITE_SCALE
        span = radius * 2 + 1
        big = pygame.Surface((span * scale, span * scale), pygame.SRCALPHA)
        # 透明处也填成同一个颜色：缩小时取平均才不会往边上渗黑
        big.fill((*color, 0))
        center = span * scale / 2.0
        pygame.draw.circle(big, (*color, 255), (center, center),
                           int(round((radius + 0.5) * scale)))
        return pygame.transform.smoothscale(big, (span, span))

    return _cached_sprite(("disc", radius, color), build)


def blit_disc(surface, center, radius, color, alpha=None):
    """贴一个抗锯齿圆点（圆头 / 圆角拐点 / 残影都用它）。"""
    sprite = disc_sprite(radius, color)
    sprite.set_alpha(255 if alpha is None else max(0, min(255, int(alpha))))
    half = sprite.get_width() / 2
    surface.blit(sprite, (int(round(center[0] - half)),
                          int(round(center[1] - half))))


def arrow_head_points(direction, center, size):
    """箭头三角的三个顶点（相对 center）：尖端沿方向凸出 0.58×size，
    底边半宽 0.46×size（size 取 1.85×线宽，即底边约为线宽的 1.8 倍）。
    """
    px, py = center
    dr, dc = DIRECTION_DELTA[direction]
    fx, fy = dc, dr                  # 行列增量换算为屏幕 x/y 增量
    half_w = size * 0.46             # 三角底边半宽（约为线宽的 1.8 倍）

    tip = (px + fx * size * 0.58, py + fy * size * 0.58)
    base = (px - fx * size * 0.44, py - fy * size * 0.44)
    perp = (-fy, fx)                 # 垂直方向

    return [
        tip,
        (base[0] + perp[0] * half_w, base[1] + perp[1] * half_w),
        (base[0] - perp[0] * half_w, base[1] - perp[1] * half_w),
    ]


def arrow_head_sprite(direction, size, color):
    """抗锯齿箭头三角，贴图正中就是 end_center。"""
    size = max(3, int(size))
    color = tuple(color[:3])
    direction = Direction(direction)

    def build():
        scale = SPRITE_SCALE
        span = int(math.ceil(size * 1.36)) + 2      # 最远顶点 ≈ 0.64 * size
        big = pygame.Surface((span * scale, span * scale), pygame.SRCALPHA)
        big.fill((*color, 0))
        center = span * scale / 2.0
        pygame.draw.polygon(big, (*color, 255),
                            arrow_head_points(direction, (center, center),
                                              size * scale))
        return pygame.transform.smoothscale(big, (span, span))

    return _cached_sprite(("head", direction, size, color), build)


def draw_arrow_head(surface, direction, end_center, size, color):
    """在线段末端画饱满三角箭头，尖端沿方向凸出在线段最前端。"""
    sprite = arrow_head_sprite(direction, size, color)
    half = sprite.get_width() / 2
    surface.blit(sprite, (int(round(end_center[0] - half)),
                          int(round(end_center[1] - half))))


def joint_indices(points):
    """折线里「需要补圆点」的节点下标：两端 + 真正拐弯的地方。

    直线段上的中间节点不用补：圆点比线段宽 1~2 像素，每个节点都补的话
    整条线上会挂一串小疙瘩（放大看很明显），直线看着就不直了。
    """
    indices = [0]
    for index in range(1, len(points) - 1):
        ax = points[index][0] - points[index - 1][0]
        ay = points[index][1] - points[index - 1][1]
        bx = points[index + 1][0] - points[index][0]
        by = points[index + 1][1] - points[index][1]
        if ax * by != ay * bx:               # 叉积非零：这里拐弯了
            indices.append(index)
    if len(points) > 1:
        indices.append(len(points) - 1)
    return indices


def stroke_polyline(surface, points, color, width):
    """画一条粗折线：直段逐段画实心矩形，拐点与两端用圆点收口。

    线段都是横平竖直的，直段的边本来就锐利；圆点只负责把拐角补圆、
    把尾端收成圆头 —— 顺带因为带抗锯齿，拐角不会有一圈锯齿。
    """
    width = int(width)
    for p1, p2 in zip(points, points[1:]):
        pygame.draw.line(surface, color, p1, p2, width)
    for index in joint_indices(points):
        blit_disc(surface, points[index], width // 2, color)


def draw_segment(surface, centers, direction, color, width=None,
                 cell_size=None, head_size=None):
    """画圆角折线，并在末端（最后一个点）加箭头。

    centers：按「尾端 -> 箭头端」顺序的像素坐标列表。
    """
    if width is None:
        width = segment_width(cell_size or 34)
    width = int(width)
    if head_size is None:
        head_size = int(width * 1.85)

    stroke_polyline(surface, centers, color, width)
    draw_arrow_head(surface, direction, centers[-1], head_size, color)


def lighten(color, amount=55):
    """提亮一个颜色，用于悬停 / 提示高亮。"""
    return tuple(min(255, channel + amount) for channel in color)
