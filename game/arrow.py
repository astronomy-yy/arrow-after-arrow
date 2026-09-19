"""方向枚举、方向映射与箭头绘制。"""

from enum import Enum

import pygame

# 空格标记
EMPTY = "."


class Direction(Enum):
    """四个飞行方向，枚举值与关卡网格中的字符保持一致。"""

    UP = "U"
    DOWN = "D"
    LEFT = "L"
    RIGHT = "R"


# 网格字符 -> 方向枚举
CHAR_TO_DIRECTION = {
    "U": Direction.UP,
    "D": Direction.DOWN,
    "L": Direction.LEFT,
    "R": Direction.RIGHT,
}

# 方向 -> (行增量 dr, 列增量 dc)
DIRECTION_DELTA = {
    Direction.UP: (-1, 0),
    Direction.DOWN: (1, 0),
    Direction.LEFT: (0, -1),
    Direction.RIGHT: (0, 1),
}


def draw_arrow(surface, direction, center, size, color):
    """以 center 为中心绘制实心三角形箭头，size 为箭头整体边长。"""
    cx, cy = center
    r = size // 2

    if direction == Direction.RIGHT:
        points = ((cx + r, cy), (cx - r, cy - r), (cx - r, cy + r))
    elif direction == Direction.LEFT:
        points = ((cx - r, cy), (cx + r, cy - r), (cx + r, cy + r))
    elif direction == Direction.UP:
        points = ((cx, cy - r), (cx - r, cy + r), (cx + r, cy + r))
    else:  # Direction.DOWN
        points = ((cx, cy + r), (cx - r, cy - r), (cx + r, cy - r))

    pygame.draw.polygon(surface, color, points)
