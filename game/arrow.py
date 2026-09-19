"""方向枚举、方向映射与线段箭绘制。"""

from enum import Enum

import pygame

from game.settings import SEGMENT_WIDTH

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


def draw_arrow_head(surface, direction, end_center, size, color):
    """在线段末端画饱满三角箭头，尖端沿方向凸出在线段最前端。"""
    px, py = end_center
    dr, dc = DIRECTION_DELTA[direction]
    fx, fy = dc, dr                  # 行列增量换算为屏幕 x/y 增量
    half_w = size * 0.46             # 三角底边半宽（约为线宽的 1.8 倍）

    tip = (px + fx * size * 0.55, py + fy * size * 0.55)
    base = (px - fx * size * 0.42, py - fy * size * 0.42)
    perp = (-fy, fx)                 # 垂直方向

    points = [
        tip,
        (base[0] + perp[0] * half_w, base[1] + perp[1] * half_w),
        (base[0] - perp[0] * half_w, base[1] - perp[1] * half_w),
    ]
    pygame.draw.polygon(surface, color, points)


def draw_segment(surface, centers, direction, color,
                 width=SEGMENT_WIDTH, head_size=None):
    """画圆角折线，并在末端（最后一个点）加箭头。

    centers：按“尾端 -> 箭头端”顺序的像素坐标列表。
    """
    if head_size is None:
        head_size = int(width * 1.9)

    # 相邻点逐段画粗直线，节点画圆，拐角圆润、尾端圆头
    for p1, p2 in zip(centers, centers[1:]):
        pygame.draw.line(surface, color, p1, p2, width)
    for point in centers:
        pygame.draw.circle(surface, color, point, width // 2)

    draw_arrow_head(surface, direction, centers[-1], head_size, color)


def build_segment_surface(centers, direction, color,
                          width=SEGMENT_WIDTH, padding=None):
    """把整条线段预渲染到独立透明 Surface（供动画使用）。"""
    if padding is None:
        padding = int(width * 1.8)

    xs = [p[0] for p in centers]
    ys = [p[1] for p in centers]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    w = (maxx - minx) + padding * 2
    h = (maxy - miny) + padding * 2
    surf = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
    local = [(x - minx + padding, y - miny + padding) for (x, y) in centers]
    draw_segment(surf, local, direction, color, width)
    return surf, (minx - padding, miny - padding)
